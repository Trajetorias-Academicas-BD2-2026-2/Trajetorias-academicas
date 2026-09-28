"""
Mede a carga de trabalho no banco carregado e imprime Markdown: o passo 1
do Método de Decisão com números medidos, mais a medição do ADR-0003
(esquema normalizado x tabela única espelhando a fonte).

Uso (depois de `docker compose up --build`):
    docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
"""

import glob
import json
import os
import statistics
from datetime import datetime, timezone

import psycopg

import config

CONSULTAS_DIR = os.getenv("CONSULTAS_DIR", "../db/consultas")
REPETICOES = 5
LATENCIA_TOLERADA_MS = 2000
TABELAS = [
    "unidade", "disciplina", "curso", "curriculo", "curriculo_componente",
    "docente", "semestre_letivo", "turma", "turma_docente", "reserva_vaga",
]

# q0 escrita sobre a tabela única (alternativa A do ADR-0003).
Q0_TABELA_UNICA = """
    SELECT curso_codigo, ano || '.' || periodo AS semestre,
           sum(vagas_reservadas) AS vagas_reservadas, count(*) AS turmas_com_reserva,
           count(DISTINCT disciplina_codigo) AS obrigatorias_com_reserva
    FROM reserva_plana
    WHERE natureza_no_curriculo_referencia = 'OBRIGATORIA'
      AND (ano, periodo) BETWEEN (2022, 1) AND (2026, 1)
    GROUP BY curso_codigo, ano, periodo
    ORDER BY curso_codigo, ano, periodo
"""


def tempo_consulta(cur, sql: str) -> tuple[float, bool]:
    """Mediana do tempo de execução (ms) em REPETICOES rodadas e se o plano usa índice."""
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


def um(cur, sql: str, params=()):
    cur.execute(sql, params)
    return cur.fetchone()


def main() -> None:
    saida: list[str] = []
    p = saida.append
    with psycopg.connect(
        host=config.DB_HOST, port=config.DB_PORT, dbname=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
    ) as conn, conn.cursor() as cur:
        versao = um(cur, "SELECT version()")[0].split(",")[0]
        lotes = um(cur, "SELECT string_agg(DISTINCT lote, ', ') FROM turma")[0]

        p("# Carga de trabalho medida")
        p("")
        p(f"Gerado por `loader/caracterizar.py` em {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC, "
          f"sobre o banco carregado com o lote `{lotes}` ({versao}). "
          "Não edite à mão: rode o script de novo.")
        p("")

        # ---------- Volume ----------
        p("## Volume por tabela")
        p("")
        p("| Tabela | Linhas | Tamanho (dados + índices) |")
        p("|---|---:|---:|")
        linhas_tab = {}
        for t in TABELAS:
            linhas_tab[t] = um(cur, f"SELECT count(*) FROM {t}")[0]
            p(f"| `{t}` | {linhas_tab[t]} | {kb(tamanho(cur, t))} |")
        bytes_total = sum(tamanho(cur, t) for t in TABELAS)
        p(f"| **total** | {sum(linhas_tab.values())} | {kb(bytes_total)} |")
        p("")
        arquivos = glob.glob(os.path.join(config.DATA_DIR, "**", "*"), recursive=True)
        bytes_lote = sum(os.path.getsize(a) for a in arquivos if os.path.isfile(a))
        p(f"Lote versionado em `data/{config.lote()}/`: {kb(bytes_lote)} com evidências "
          "(limite para versionar: 5 MB).")
        p("")

        # ---------- Escrita por semestre ----------
        cur.execute("""
            SELECT t.ano, t.periodo, count(DISTINCT t.id), count(*), sum(rv.vagas_reservadas),
                   count(DISTINCT t.id) FILTER (WHERE d.unidade_id IS NULL)
            FROM turma t
            JOIN reserva_vaga rv ON rv.turma_id = t.id
            JOIN disciplina d ON d.id = t.disciplina_id
            GROUP BY t.ano, t.periodo ORDER BY t.ano, t.periodo
        """)
        por_semestre = cur.fetchall()
        p("## Por semestre (taxa de escrita)")
        p("")
        p("| Semestre | Turmas | Reservas (turma x curso) | Vagas reservadas | Turmas de outras unidades |")
        p("|---|---:|---:|---:|---:|")
        for ano, periodo, turmas, reservas, vagas, externas in por_semestre:
            p(f"| {ano}.{periodo} | {turmas} | {reservas} | {vagas} | {externas} |")
        p("")
        turmas_sem = [r[2] for r in por_semestre]
        reservas_sem = [r[3] for r in por_semestre]
        if turmas_sem:
            p(f"- Escrita: uma carga em lote por semestre encerrado: {min(turmas_sem)} a {max(turmas_sem)} turmas "
              f"(média {statistics.mean(turmas_sem):.0f}) e {min(reservas_sem)} a {max(reservas_sem)} reservas "
              f"(média {statistics.mean(reservas_sem):.0f}); nenhuma escrita entre cargas.")
            p(f"- Crescimento: cerca de +{statistics.mean(turmas_sem):.0f} turmas e "
              f"+{statistics.mean(reservas_sem):.0f} reservas por semestre, "
              f"+{2 * statistics.mean(reservas_sem):.0f} reservas por ano.")
        p("")

        # ---------- Qualidade ----------
        compartilhadas = um(cur, """
            SELECT round(100.0 * count(*) FILTER (WHERE n > 1) / count(*), 1), round(avg(n), 2)
            FROM (SELECT count(*) AS n FROM reserva_vaga GROUP BY turma_id) x
        """)
        turno = um(cur, "SELECT string_agg(turno || ' ' || n, ', ' ORDER BY n DESC) FROM "
                        "(SELECT turno, count(*) AS n FROM turma GROUP BY turno) x")[0]
        prereq = um(cur, "SELECT count(*) FILTER (WHERE pre_requisito_coletado), "
                         "count(*) FILTER (WHERE unidade_id IS NOT NULL) FROM disciplina")
        obrig = um(cur, """
            SELECT count(*), count(*) FILTER (WHERE EXISTS (
                SELECT 1 FROM reserva_vaga rv JOIN turma t ON t.id = rv.turma_id
                WHERE rv.curso_id = cr.curso_id AND t.disciplina_id = cc.disciplina_id))
            FROM curriculo_referencia cr
            JOIN curriculo_componente cc ON cc.curriculo_id = cr.id AND cc.natureza = 'OBRIGATORIA'
        """)
        p("## Qualidade e dado faltante")
        p("")
        p(f"- Turmas que reservam vagas para mais de um curso: {compartilhadas[0]}% "
          f"(média de {compartilhadas[1]} cursos por turma).")
        p(f"- Turno das turmas: {turno}.")
        p(f"- Obrigatórias dos currículos de referência com ao menos uma reserva no recorte: "
          f"{obrig[1]} de {obrig[0]} pares curso x disciplina.")
        p(f"- Pré-requisitos coletados: {prereq[0]} de {prereq[1]} componentes da FCTE.")
        cur.execute("""
            SELECT t.ano || '.' || t.periodo, count(*), sum(rv.vagas_reservadas)
            FROM reserva_vaga rv JOIN turma t ON t.id = rv.turma_id
            WHERE rv.vagas_reservadas >= 50
            GROUP BY t.ano, t.periodo ORDER BY t.ano, t.periodo
        """)
        grandes = ", ".join(f"{s}: {n} ({v} vagas)" for s, n, v in cur.fetchall())
        p(f"- Reservas de 50 vagas ou mais, por semestre: {grandes or 'nenhuma'}. Uma mudança brusca "
          "aqui indica mudança na forma de registrar a reserva, não necessariamente mais vagas.")
        rejeitados = os.path.join(config.DEBUG_DIR, "rejeitados.csv")
        if os.path.exists(rejeitados):
            import csv
            with open(rejeitados, newline="", encoding="utf-8") as f:
                motivos: dict[str, int] = {}
                for r in csv.DictReader(f):
                    chave = f"{r['tabela']}: {r['motivo']}"
                    motivos[chave] = motivos.get(chave, 0) + 1
            for chave, n in sorted(motivos.items()):
                p(f"- Linhas rejeitadas na última carga ({chave}): {n}")
        p("")

        # ---------- Consultas de referência ----------
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

        # ---------- Medição do ADR-0003 ----------
        # A: tabela única espelhando a página "Turmas" do curso, uma linha por reserva.
        cur.execute("""
            CREATE TEMP TABLE reserva_plana AS
            SELECT c.codigo AS curso_codigo, d.codigo AS disciplina_codigo, d.nome AS disciplina_nome,
                   t.codigo_turma, t.ano, t.periodo, t.horario, t.turno,
                   (SELECT string_agg(doc.nome, ' , ' ORDER BY doc.nome)
                      FROM turma_docente td JOIN docente doc ON doc.id = td.docente_id
                     WHERE td.turma_id = t.id) AS docentes,
                   rv.vagas_reservadas,
                   (SELECT cc.natureza FROM curriculo_referencia cr
                      JOIN curriculo_componente cc ON cc.curriculo_id = cr.id
                     WHERE cr.curso_id = c.id AND cc.disciplina_id = d.id) AS natureza_no_curriculo_referencia
            FROM reserva_vaga rv
            JOIN turma t ON t.id = rv.turma_id
            JOIN disciplina d ON d.id = t.disciplina_id
            JOIN curso c ON c.id = rv.curso_id
        """)
        cur.execute("ANALYZE reserva_plana")
        linhas_a = um(cur, "SELECT count(*) FROM reserva_plana")[0]
        bytes_a = tamanho(cur, "reserva_plana")
        ms_a, _ = tempo_consulta(cur, Q0_TABELA_UNICA)
        with open(os.path.join(CONSULTAS_DIR, "q0_pergunta_de_gestao.sql"), encoding="utf-8") as f:
            ms_c, _ = tempo_consulta(cur, f.read())
        conn.rollback()

        # B: currículo sem versão. Para cada par de versões do mesmo curso,
        # quantas disciplinas saem, entram ou mudam de natureza (o que uma
        # matriz única por curso teria de escolher ou misturar).
        cur.execute("""
            SELECT cu.codigo, a.codigo, b.codigo,
                   count(*) FILTER (WHERE cb.disciplina_id IS NULL)                        AS saem,
                   count(*) FILTER (WHERE ca.disciplina_id IS NULL)                        AS entram,
                   count(*) FILTER (WHERE ca.natureza IS DISTINCT FROM cb.natureza
                                      AND ca.disciplina_id IS NOT NULL
                                      AND cb.disciplina_id IS NOT NULL)                   AS mudam
            FROM curriculo a
            JOIN curriculo b ON b.curso_id = a.curso_id
             AND (b.inicio_vigencia_ano, b.inicio_vigencia_periodo) > (a.inicio_vigencia_ano, a.inicio_vigencia_periodo)
            JOIN curso cu ON cu.id = a.curso_id
            CROSS JOIN LATERAL (
                SELECT disciplina_id FROM curriculo_componente WHERE curriculo_id IN (a.id, b.id)
                GROUP BY disciplina_id
            ) u
            LEFT JOIN curriculo_componente ca ON ca.curriculo_id = a.id AND ca.disciplina_id = u.disciplina_id
            LEFT JOIN curriculo_componente cb ON cb.curriculo_id = b.id AND cb.disciplina_id = u.disciplina_id
            GROUP BY cu.codigo, a.codigo, b.codigo
        """)
        versoes = cur.fetchall()
        turmas = linhas_tab["turma"]

        def dentro(ms: float) -> str:
            return "sim" if ms <= LATENCIA_TOLERADA_MS else "**não**"

        p("## Para copiar no ADR-0003")
        p("")
        p("Os blocos abaixo têm o mesmo formato das seções **Contexto** e **Medição** do ADR-0003.")
        p("")
        p("### Contexto: carga")
        p("")
        if turmas_sem:
            p(f"- Volume: {turmas} turmas e {linhas_tab['reserva_vaga']} reservas em {len(turmas_sem)} semestres "
              f"({por_semestre[0][0]}.{por_semestre[0][1]} a {por_semestre[-1][0]}.{por_semestre[-1][1]}); "
              f"{linhas_tab['disciplina']} disciplinas, {linhas_tab['curriculo_componente']} vínculos curriculares; "
              f"{kb(bytes_total)} em disco com índices.")
            p(f"- Escrita: uma carga em lote por semestre encerrado, de {min(reservas_sem)} a {max(reservas_sem)} "
              f"reservas (média {statistics.mean(reservas_sem):.0f}); nenhuma escrita entre cargas.")
        p(f"- Latência tolerada: {LATENCIA_TOLERADA_MS} ms por consulta.")
        p("")
        p("### Medição")
        p("")
        p("| Alternativa | Linhas | Tamanho | `q0` (ms) | Dentro de 2 s | Observação medida |")
        p("|---|---:|---:|---:|:---:|---|")
        p(f"| A: opção nula, tabela única espelhando a página do curso | {linhas_a} | {kb(bytes_a)} | "
          f"{ms_a:.1f} | {dentro(ms_a)} | cada turma repetida em média {linhas_a / turmas:.2f} vezes "
          f"({linhas_a} linhas para {turmas} turmas) |")
        dif = "; ".join(
            f"{c} {va} → {vb}: {saem} saem, {entram} entram, {mudam} mudam de natureza "
            f"({saem + entram + mudam} disciplinas)"
            for c, va, vb, saem, entram, mudam in versoes
        ) or "só uma versão por curso"
        p(f"| B: normalizado, currículo sem versão | - | - | - | - | {dif} |")
        p(f"| **C: normalizado, turma + reserva + currículo versionado (escolhida)** | "
          f"{turmas} turmas + {linhas_tab['reserva_vaga']} reservas | {kb(bytes_total)} | {ms_c:.1f} | {dentro(ms_c)} | "
          f"cada turma guardada uma vez |")
        p("")

    while saida and not saida[-1].strip():
        saida.pop()
    print("\n".join(saida))


if __name__ == "__main__":
    main()
