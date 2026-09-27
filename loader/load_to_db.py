"""
Lê os CSVs mais recentes em STAGING_DIR e carrega nas tabelas finais
(unidade, disciplina, pre_requisito, docente, oferta_turma, curso, curso_disciplina).

Idempotente: os UPSERTs usam as UNIQUE constraints do esquema,
então rodar duas vezes com o mesmo CSV não duplica linhas.
"""

import csv
import glob
import os

import psycopg

import config


def _latest(prefix: str) -> str | None:
    files = [
        os.path.join(config.STAGING_DIR, f)
        for f in os.listdir(config.STAGING_DIR)
        if f.startswith(prefix) and f.endswith(".csv")
    ]
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def _read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load(conn: psycopg.Connection) -> None:
    componentes_path = _latest("componentes_raw")
    prereq_path = _latest("pre_requisitos_raw")
    turmas_path = _latest("turmas_raw")
    cursos_path = _latest("cursos_raw")
    curriculo_path = _latest("curso_disciplina_raw")

    with conn.cursor() as cur:
        unidades = set()
        if componentes_path:
            unidades |= {r["unidade"] for r in _read_csv(componentes_path)}
        if cursos_path:
            unidades |= {r["unidade"] for r in _read_csv(cursos_path)}

        for nome in unidades:
            cur.execute(
                "INSERT INTO unidade (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
                (nome,),
            )

        if componentes_path:
            for r in _read_csv(componentes_path):
                carga = int(r["carga_horaria"] or 0)
                if carga <= 0:
                    continue

                cur.execute(
                    """
                    INSERT INTO disciplina (codigo, nome, unidade_id, carga_horaria)
                    SELECT %s, %s, u.id, %s FROM unidade u WHERE u.nome = %s
                    ON CONFLICT (codigo) DO UPDATE
                      SET nome = EXCLUDED.nome, carga_horaria = EXCLUDED.carga_horaria
                    """,
                    (r["codigo"], r["nome"], carga, r["unidade"]),
                )

        if prereq_path:
            for r in _read_csv(prereq_path):
                cur.execute(
                    """
                    INSERT INTO pre_requisito (disciplina_id, pre_requisito_id)
                    SELECT d1.id, d2.id
                    FROM disciplina d1, disciplina d2
                    WHERE d1.codigo = %s AND d2.codigo = %s
                    ON CONFLICT DO NOTHING
                    """,
                    (r["disciplina_codigo"], r["pre_requisito_codigo"]),
                )

        if cursos_path:
            for r in _read_csv(cursos_path):
                cur.execute(
                    """
                    INSERT INTO curso (codigo, nome, unidade_id)
                    SELECT %s, %s, u.id FROM unidade u WHERE u.nome = %s
                    ON CONFLICT (codigo) DO UPDATE
                      SET nome = EXCLUDED.nome
                    """,
                    (r["codigo"][:10], r["nome"], r["unidade"]),
                )

        if curriculo_path:
            for r in _read_csv(curriculo_path):
                obrigatoria = r.get("obrigatoria", "True").strip().lower() in ("true", "1")
                cur.execute(
                    """
                    INSERT INTO curso_disciplina (curso_id, disciplina_id, obrigatoria)
                    SELECT c.id, d.id, %s
                    FROM curso c, disciplina d
                    WHERE c.codigo = %s AND d.codigo = %s
                    ON CONFLICT DO NOTHING
                    """,
                    (obrigatoria, r["curso_codigo"][:10], r["disciplina_codigo"][:10]),
                )

        if turmas_path:
            for r in _read_csv(turmas_path):
                if r["docente"]:
                    cur.execute(
                        "INSERT INTO docente (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
                        (r["docente"],),
                    )

                horario_limpo = r["horario"].split("(")[0].strip()[:10]

                cur.execute(
                    """
                    INSERT INTO oferta_turma (
                        disciplina_id, codigo_turma, ano, periodo, turno,
                        docente_id, vagas_ofertadas, vagas_ocupadas, horario,
                        local, fonte, carga_id, ingerido_em
                    )
                    SELECT d.id, %s, %s, %s, %s, doc.id, %s, %s, %s, %s, %s, %s, %s
                    FROM disciplina d
                    LEFT JOIN docente doc ON doc.nome = %s
                    WHERE d.codigo = %s
                    ON CONFLICT (disciplina_id, codigo_turma, ano, periodo) DO NOTHING
                    """,
                    (
                        r["turma_codigo"][:10], int(r["ano"]), int(r["periodo"]), r["turno"][:10],
                        int(r["vagas_ofertadas"] or 0), int(r["vagas_ocupadas"] or 0),
                        horario_limpo, r["local"], r["fonte"][:10], r["carga_id"], r["ingerido_em"],
                        r["docente"], r["disciplina_codigo"][:10],
                    ),
                )

    conn.commit()


if __name__ == "__main__":
    with psycopg.connect(
        host=config.DB_HOST, dbname=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
    ) as conn:
        load(conn)
    print("Carga concluída.")
