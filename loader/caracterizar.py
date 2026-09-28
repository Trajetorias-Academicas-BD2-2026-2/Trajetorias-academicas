"""
Mede a carga de trabalho no banco carregado e imprime Markdown (passo 1 do
Método de Decisão, com números medidos em vez de estimados), mais a
medição usada no ADR-0001 (esquema 3FN x tabela única desnormalizada).

Uso (depois de `docker compose up --build`):
    docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
"""

import csv
import glob
import json
import os
import statistics
from datetime import datetime, timezone

import psycopg

import config

CONSULTAS_DIR = os.getenv("CONSULTAS_DIR", "consultas")
REPETICOES = 5
LATENCIA_TOLERADA_MS = 2000
TABELAS = ["unidade", "disciplina", "curso", "curso_disciplina", "pre_requisito", "docente", "oferta_turma"]


def tempo_consulta(cur, sql: str) -> tuple[float, bool]:
    """Mediana do tempo de execução (ms) em REPETICOES rodadas e se o plano
    usa algum índice."""
    tempos, usa_indice = [], False
    for _ in range(REPETICOES):
        cur.execute("EXPLAIN (ANALYZE, FORMAT JSON) " + sql.strip().rstrip(";"))
        plano = cur.fetchone()[0]
        plano = plano if isinstance(plano, list) else json.loads(plano)
        tempos.append(plano[0]["Execution Time"])
        usa_indice = usa_indice or "Index" in json.dumps(plano[0]["Plan"])
    return statistics.median(tempos), usa_indice


def tamanho(cur, tabela: str) -> int:
    cur.execute("SELECT pg_total_relation_size(%s)", (tabela,))
    return cur.fetchone()[0]


def kb(n: int) -> str:
    return f"{n / 1024:,.0f} kB".replace(",", ".")


def main() -> None:
    saida: list[str] = []
    p = saida.append
    with psycopg.connect(
        host=config.DB_HOST, port=config.DB_PORT, dbname=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
    ) as conn, conn.cursor() as cur:
        cur.execute("SELECT version()")
        versao = cur.fetchone()[0].split(",")[0]

        p("# Carga de trabalho medida")
        p("")
        p(f"Gerado por `loader/caracterizar.py` em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, "
          f"sobre o banco carregado a partir de `data/raw/` ({versao}). "
          "Não edite à mão: rode o script de novo.")
        p("")

        # Volume
        p("## Volume por tabela")
        p("")
        p("| Tabela | Linhas | Tamanho (dados + índices) | Bytes por linha |")
        p("|---|---:|---:|---:|")
        for t in TABELAS:
            cur.execute(f"SELECT count(*) FROM {t}")
            linhas = cur.fetchone()[0]
            bytes_ = tamanho(cur, t)
            # Abaixo de ~100 linhas o mínimo de uma página (8 kB) domina e a média engana.
            por_linha = bytes_ // linhas if linhas >= 100 else "-"
            p(f"| `{t}` | {linhas} | {kb(bytes_)} | {por_linha} |")
        p("")
        arquivos = glob.glob(os.path.join(config.DATA_DIR, "*.csv"))
        bytes_csv = sum(os.path.getsize(a) for a in arquivos)
        p(f"Recorte versionado em `data/raw/`: {len(arquivos)} CSVs, {kb(bytes_csv)} "
          f"(limite para versionar: 5 MB).")
        p("")

        # Crescimento
        cur.execute("""
            SELECT ano, periodo, count(*), count(DISTINCT disciplina_id),
                   count(*) FILTER (WHERE vagas_ofertadas > 0 AND vagas_ocupadas >= vagas_ofertadas)
            FROM oferta_turma GROUP BY ano, periodo ORDER BY ano, periodo
        """)
        por_semestre = cur.fetchall()
        p("## `oferta_turma` por semestre (taxa de escrita)")
        p("")
        p("| Semestre | Turmas | Disciplinas distintas | Turmas lotadas |")
        p("|---|---:|---:|---:|")
        for ano, periodo, turmas, disciplinas, lotadas in por_semestre:
            p(f"| {ano}.{periodo} | {turmas} | {disciplinas} | {lotadas} |")
        p("")
        if por_semestre:
            contagens = [r[2] for r in por_semestre]
            p(f"- Semestres carregados: {len(contagens)} "
              f"({por_semestre[0][0]}.{por_semestre[0][1]} a {por_semestre[-1][0]}.{por_semestre[-1][1]}).")
            p(f"- Escrita: uma carga em lote por semestre, de {min(contagens)} a {max(contagens)} linhas "
              f"(média {statistics.mean(contagens):.0f}); nenhuma escrita entre cargas.")
            p(f"- Projeção: +{statistics.mean(contagens):.0f} linhas em `oferta_turma` a cada semestre, "
              f"cerca de +{2 * statistics.mean(contagens):.0f} por ano.")
        p("")

        # Dado faltante
        cur.execute("""
            SELECT round(100.0 * count(*) FILTER (WHERE turno = 'SEM_HORARIO') / nullif(count(*), 0), 1),
                   round(100.0 * count(*) FILTER (WHERE docente_id IS NULL) / nullif(count(*), 0), 1),
                   round(100.0 * count(*) FILTER (WHERE vagas_ocupadas > vagas_ofertadas) / nullif(count(*), 0), 1)
            FROM oferta_turma
        """)
        sem_horario, sem_docente, acima = cur.fetchone()
        cur.execute("SELECT count(*) FROM disciplina WHERE pre_requisito_expressao IS NOT NULL")
        com_prereq = cur.fetchone()[0]
        p("## Qualidade e dado faltante")
        p("")
        p(f"- Turmas sem horário (`turno = 'SEM_HORARIO'`): {sem_horario}%")
        p(f"- Turmas sem docente identificado: {sem_docente}%")
        p(f"- Turmas com ocupação acima da oferta: {acima}%")
        p(f"- Disciplinas com expressão de pré-requisito: {com_prereq}")
        rejeitados = os.path.join(config.DEBUG_DIR, "rejeitados.csv")
        if os.path.exists(rejeitados):
            with open(rejeitados, newline="", encoding="utf-8") as f:
                motivos: dict[str, int] = {}
                for r in csv.DictReader(f):
                    chave = f"{r['tabela']}: {r['motivo']}"
                    motivos[chave] = motivos.get(chave, 0) + 1
            for chave, n in sorted(motivos.items()):
                p(f"- Linhas rejeitadas na última carga ({chave}): {n}")
        p("")

        # Consultas de referência
        p(f"## Consultas de referência (mediana de {REPETICOES} execuções, latência tolerada {LATENCIA_TOLERADA_MS} ms)")
        p("")
        p("| Consulta | Tempo (ms) | Usa índice | Dentro da latência |")
        p("|---|---:|:---:|:---:|")
        for arquivo in sorted(glob.glob(os.path.join(CONSULTAS_DIR, "q*.sql"))):
            with open(arquivo, encoding="utf-8") as f:
                ms, indice = tempo_consulta(cur, f.read())
            p(f"| `{os.path.basename(arquivo)}` | {ms:.1f} | {'sim' if indice else 'não'} | "
              f"{'sim' if ms <= LATENCIA_TOLERADA_MS else '**não**'} |")
        p("")

        # Medição do ADR-0001: 3FN x tabela única desnormalizada
        cur.execute("""
            CREATE TEMP TABLE oferta_desnormalizada AS
            SELECT ot.ano, ot.periodo, ot.turno, ot.codigo_turma,
                   ot.vagas_ofertadas, ot.vagas_ocupadas, ot.horario, ot.local,
                   d.codigo AS disciplina_codigo, d.nome AS disciplina_nome, d.carga_horaria,
                   u.nome AS unidade, doc.nome AS docente,
                   c.codigo AS curso_codigo, c.nome AS curso_nome, cd.obrigatoria,
                   (SELECT count(*) FROM pre_requisito pr WHERE pr.pre_requisito_id = d.id) AS disciplinas_que_trava
            FROM oferta_turma ot
            JOIN disciplina d ON d.id = ot.disciplina_id
            JOIN unidade u ON u.id = d.unidade_id
            LEFT JOIN docente doc ON doc.id = ot.docente_id
            LEFT JOIN curso_disciplina cd ON cd.disciplina_id = d.id
            LEFT JOIN curso c ON c.id = cd.curso_id
        """)
        cur.execute("ANALYZE oferta_desnormalizada")
        cur.execute("SELECT count(*) FROM oferta_desnormalizada")
        linhas_flat = cur.fetchone()[0]
        bytes_flat = tamanho(cur, "oferta_desnormalizada")
        bytes_3fn = sum(tamanho(cur, t) for t in TABELAS)
        cur.execute("SELECT count(*) FROM oferta_turma")
        linhas_ot = cur.fetchone()[0]

        with open(os.path.join(CONSULTAS_DIR, "q0_pergunta_de_gestao.sql"), encoding="utf-8") as f:
            ms_3fn, _ = tempo_consulta(cur, f.read())
        ms_flat, _ = tempo_consulta(cur, """
            SELECT curso_codigo, disciplina_codigo, disciplina_nome, turno, count(*) AS turmas,
                   count(*) FILTER (WHERE vagas_ofertadas > 0 AND vagas_ocupadas >= vagas_ofertadas) AS turmas_lotadas,
                   round(sum(vagas_ocupadas)::numeric / nullif(sum(vagas_ofertadas), 0), 2) AS ocupacao_media,
                   max(disciplinas_que_trava) AS disciplinas_que_trava
            FROM oferta_desnormalizada
            WHERE obrigatoria AND (ano, periodo) BETWEEN (2022, 1) AND (2026, 1)
              AND turno IN ('DIURNO', 'NOTURNO')
            GROUP BY curso_codigo, disciplina_codigo, disciplina_nome, turno
            ORDER BY turmas_lotadas DESC, ocupacao_media DESC NULLS LAST
            LIMIT 30
        """)
        conn.rollback()

        p("## Medição do ADR-0001: esquema 3FN x tabela única desnormalizada")
        p("")
        p("Mesma massa de dados; a tabela única repete disciplina, docente e curso em cada linha "
          "(uma linha por turma x curso em que a disciplina aparece).")
        p("")
        p("| Alternativa | Linhas | Tamanho total | Pergunta de gestão (`q0`, ms) |")
        p("|---|---:|---:|---:|")
        p(f"| 3FN (escolhida) | {linhas_ot} em `oferta_turma` | {kb(bytes_3fn)} | {ms_3fn:.1f} |")
        p(f"| Tabela única desnormalizada | {linhas_flat} | {kb(bytes_flat)} | {ms_flat:.1f} |")
        p("")

    print("\n".join(saida))


if __name__ == "__main__":
    main()
