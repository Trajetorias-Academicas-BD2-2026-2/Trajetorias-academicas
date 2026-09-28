"""
Carrega o recorte versionado em DATA_DIR nas tabelas do banco, numa única
transação (ou tudo entra, ou nada entra).

Reprocessamento: rodar de novo com os mesmos CSVs não duplica nem altera
nada.
  - oferta_turma é insert-only: ON CONFLICT DO NOTHING, e um trigger no
    banco bloqueia UPDATE/DELETE (migração V002).
  - unidade, disciplina, curso e curso_disciplina: upsert (refletem a
    versão mais recente da estrutura curricular).
  - pre_requisito: substituído por disciplina a cada carga, para que um
    pré-requisito retirado no SIGAA também saia do banco.

Dado faltante: linhas que não podem entrar (disciplina fora do recorte,
vagas não lidas, carga horária ausente) são contadas, gravadas em
DEBUG_DIR/rejeitados.csv e resumidas no final, nunca descartadas em silêncio.
"""

import csv
import glob
import hashlib
import os
import re
import sys
from collections import Counter

import psycopg

import config
from semestres import encerrado, rotulo


def _ler(nome: str) -> list[dict]:
    caminho = os.path.join(config.DATA_DIR, nome)
    if not os.path.exists(caminho):
        raise SystemExit(f"Arquivo ausente: {caminho}. Rode os scrapers (RASPAR=auto).")
    with open(caminho, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _arquivos_turmas() -> dict[tuple[int, int], str]:
    arquivos = {}
    for caminho in glob.glob(os.path.join(config.DATA_DIR, "turmas_*_*.csv")):
        m = re.search(r"turmas_(\d{4})_([12])\.csv$", caminho)
        if m:
            arquivos[(int(m.group(1)), int(m.group(2)))] = caminho
    return arquivos


def validar_recorte() -> dict[tuple[int, int], str]:
    """Confere o recorte antes de tocar no banco."""
    arquivos = _arquivos_turmas()
    esperados = config.semestres_da_carga()

    faltando = [rotulo(*s) for s in esperados if s not in arquivos]
    if faltando:
        raise SystemExit(f"Faltam semestres em {config.DATA_DIR}: {', '.join(faltando)}")

    abertos = [rotulo(*s) for s in arquivos if not encerrado(*s)]
    if abertos:
        raise SystemExit(f"Recusando semestre(s) em andamento: {', '.join(abertos)}")

    # Se o filtro de semestre do formulário for ignorado, o SIGAA devolve o
    # semestre padrão para todos: arquivos com o mesmo conteúdo denunciam isso.
    por_conteudo: dict[str, list[str]] = {}
    for semestre, caminho in arquivos.items():
        with open(caminho, newline="", encoding="utf-8") as f:
            corpo = sorted(
                (r["disciplina_codigo"], r["turma_codigo"], r["vagas_ofertadas"], r["vagas_ocupadas"], r["docente"])
                for r in csv.DictReader(f)
            )
        chave = hashlib.sha256(repr(corpo).encode()).hexdigest()
        por_conteudo.setdefault(chave, []).append(rotulo(*semestre))
    repetidos = [grupo for grupo in por_conteudo.values() if len(grupo) > 1]
    if repetidos:
        raise SystemExit(
            f"Semestres com turmas idênticas: {repetidos}. O filtro de ano/período "
            "provavelmente não foi aplicado na raspagem."
        )
    return dict(sorted(arquivos.items()))


def load(conn: psycopg.Connection) -> Counter:
    arquivos_turmas = validar_recorte()
    componentes = _ler(config.ARQ_COMPONENTES)
    prereqs = _ler(config.ARQ_PRE_REQUISITOS)
    cursos = _ler(config.ARQ_CURSOS)
    curriculo = _ler(config.ARQ_CURSO_DISCIPLINA)

    stats: Counter = Counter()
    rejeitados: list[dict] = []

    def rejeitar(tabela: str, motivo: str, linha: dict) -> None:
        stats[f"{tabela}: rejeitada ({motivo})"] += 1
        rejeitados.append({"tabela": tabela, "motivo": motivo, "linha": repr(linha)})

    with conn.cursor() as cur:
        for nome in sorted({r["unidade"] for r in componentes + cursos}):
            cur.execute("INSERT INTO unidade (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (nome,))

        # disciplina (upsert)
        codigos_carregados = []
        for r in componentes:
            if not r["carga_horaria"]:
                rejeitar("disciplina", "carga horária não lida", r)
                continue
            cur.execute(
                """
                INSERT INTO disciplina (codigo, nome, unidade_id, carga_horaria, pre_requisito_expressao)
                SELECT %s, %s, u.id, %s, NULLIF(%s, '') FROM unidade u WHERE u.nome = %s
                ON CONFLICT (codigo) DO UPDATE
                  SET nome = EXCLUDED.nome,
                      carga_horaria = EXCLUDED.carga_horaria,
                      pre_requisito_expressao = EXCLUDED.pre_requisito_expressao
                """,
                (r["codigo"], r["nome"], int(r["carga_horaria"]), r["pre_requisito_expressao"], r["unidade"]),
            )
            codigos_carregados.append(r["codigo"])
            stats["disciplina: carregada"] += 1

        # pre_requisito (substitui o conjunto de cada disciplina carregada)
        cur.execute(
            "DELETE FROM pre_requisito WHERE disciplina_id IN (SELECT id FROM disciplina WHERE codigo = ANY(%s))",
            (codigos_carregados,),
        )
        for r in prereqs:
            cur.execute(
                """
                INSERT INTO pre_requisito (disciplina_id, pre_requisito_id)
                SELECT d1.id, d2.id FROM disciplina d1, disciplina d2
                WHERE d1.codigo = %s AND d2.codigo = %s
                ON CONFLICT DO NOTHING
                """,
                (r["disciplina_codigo"], r["pre_requisito_codigo"]),
            )
            if cur.rowcount:
                stats["pre_requisito: carregado"] += 1
            else:
                # Ex.: pré-requisito de outra unidade (MAT, IFD...). A relação
                # continua registrada em disciplina.pre_requisito_expressao.
                rejeitar("pre_requisito", "disciplina ausente do banco", r)

        # curso (upsert)
        for r in cursos:
            cur.execute(
                """
                INSERT INTO curso (codigo, nome, unidade_id)
                SELECT %s, %s, u.id FROM unidade u WHERE u.nome = %s
                ON CONFLICT (codigo) DO UPDATE SET nome = EXCLUDED.nome
                """,
                (r["codigo"], r["nome"], r["unidade"]),
            )
            stats["curso: carregado"] += 1

        # curso_disciplina (upsert: a matriz mais recente vale)
        for r in curriculo:
            obrigatoria = r["obrigatoria"].strip().lower() in ("true", "1")
            cur.execute(
                """
                INSERT INTO curso_disciplina (curso_id, disciplina_id, obrigatoria)
                SELECT c.id, d.id, %s FROM curso c, disciplina d
                WHERE c.codigo = %s AND d.codigo = %s
                ON CONFLICT (curso_id, disciplina_id) DO UPDATE SET obrigatoria = EXCLUDED.obrigatoria
                """,
                (obrigatoria, r["curso_codigo"], r["disciplina_codigo"]),
            )
            if cur.rowcount:
                stats["curso_disciplina: carregada"] += 1
            else:
                rejeitar("curso_disciplina", "disciplina ausente do banco", r)

        # oferta_turma (insert-only)
        for semestre, caminho in arquivos_turmas.items():
            with open(caminho, newline="", encoding="utf-8") as f:
                turmas = list(csv.DictReader(f))
            for r in turmas:
                if r["vagas_ofertadas"] == "" or r["vagas_ocupadas"] == "":
                    rejeitar("oferta_turma", "vagas não lidas", r)
                    continue
                if r["docente"]:
                    cur.execute(
                        "INSERT INTO docente (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
                        (r["docente"],),
                    )
                cur.execute(
                    """
                    INSERT INTO oferta_turma (
                        disciplina_id, codigo_turma, ano, periodo, turno, docente_id,
                        vagas_ofertadas, vagas_ocupadas, horario, local,
                        fonte, carga_id, coletado_em
                    )
                    SELECT d.id, %s, %s, %s, %s, doc.id, %s, %s, NULLIF(%s, ''), %s, %s, %s, %s
                    FROM disciplina d
                    LEFT JOIN docente doc ON doc.nome = NULLIF(%s, '')
                    WHERE d.codigo = %s
                    ON CONFLICT (disciplina_id, codigo_turma, ano, periodo) DO NOTHING
                    RETURNING id
                    """,
                    (
                        r["turma_codigo"], int(r["ano"]), int(r["periodo"]), r["turno"],
                        int(r["vagas_ofertadas"]), int(r["vagas_ocupadas"]),
                        r["horario"], r["local"], r["fonte"], r["carga_id"], r["coletado_em"],
                        r["docente"], r["disciplina_codigo"],
                    ),
                )
                if cur.fetchone():
                    stats[f"oferta_turma {rotulo(*semestre)}: inserida"] += 1
                else:
                    cur.execute("SELECT 1 FROM disciplina WHERE codigo = %s", (r["disciplina_codigo"],))
                    if cur.fetchone():
                        stats["oferta_turma: já existia (reprocessamento)"] += 1
                    else:
                        rejeitar("oferta_turma", "disciplina ausente do banco", r)

    conn.commit()

    os.makedirs(config.DEBUG_DIR, exist_ok=True)
    with open(os.path.join(config.DEBUG_DIR, "rejeitados.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tabela", "motivo", "linha"])
        writer.writeheader()
        writer.writerows(rejeitados)
    return stats


if __name__ == "__main__":
    with psycopg.connect(
        host=config.DB_HOST, port=config.DB_PORT, dbname=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
    ) as conn:
        resumo = load(conn)
    print("Resumo da carga:")
    for chave in sorted(resumo):
        print(f"  {chave}: {resumo[chave]}")
    if any("rejeitada" in k for k in resumo):
        print(f"Linhas rejeitadas detalhadas em {config.DEBUG_DIR}/rejeitados.csv", file=sys.stderr)
