"""
Carrega um lote de coleta versionado (config.DATA_DIR) no banco, numa
única transação: ou tudo entra, ou nada entra.

Antes de tocar no banco, valida o lote:
  - integridade: cada arquivo confere com SHA256SUMS.txt;
  - recorte: cada curso tem reservas em todos os semestres esperados e
    nenhum semestre fora do recorte;
  - calendário: cada semestre está no calendário acadêmico oficial
    (CALENDARIO) e já tinha encerrado quando foi coletado;
  - chaves: nenhuma reserva duplicada.

Reprocessamento: turma, turma_docente e reserva_vaga são insert-only
(triggers no banco bloqueiam UPDATE e DELETE). Ao encontrar uma turma ou
reserva que já está no banco, o loader compara os dados:
  - iguais: conta como "idêntica (reprocessamento)" e segue;
  - diferentes (horário, turno, docentes ou vagas): é uma DIVERGÊNCIA. A
    carga inteira é desfeita, as divergências vão para
    DEBUG_DIR/divergencias.csv e o loader termina com erro. Aceitar um
    valor novo exige decisão explícita da Squad (ver docs/historico.md).
unidade, disciplina, curso, curriculo, curriculo_componente e
semestre_letivo recebem upsert (valem os dados mais recentes).

Dado faltante e inconsistente: nada é descartado em silêncio. Linhas que
não entram vão para DEBUG_DIR/rejeitados.csv, com o motivo, e são somadas
no resumo final.
"""

import csv
import hashlib
import os
import sys
from collections import Counter, defaultdict
from datetime import date

import psycopg

import config
from parsing import extrair_horario, inferir_turno, normalizar_natureza, parse_docentes
from semestres import encerrado_em, ler_calendario, parse_semestre, rotulo

ARQUIVOS = [
    config.ARQ_CURSOS, config.ARQ_COMPONENTES, config.ARQ_PRE_REQUISITOS,
    config.ARQ_CURRICULOS, config.ARQ_CURRICULO_COMPONENTES, config.ARQ_OFERTAS,
]


def _caminho(nome: str) -> str:
    return os.path.join(config.DATA_DIR, nome)


def _ler(nome: str) -> list[dict]:
    with open(_caminho(nome), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _ts(valor: str) -> str | None:
    return valor.strip() or None


def verificar_checksums() -> None:
    """Confere cada arquivo listado em SHA256SUMS.txt e exige que os
    arquivos que o loader lê estejam na lista."""
    lista = _caminho(config.ARQ_CHECKSUMS)
    if not os.path.exists(lista):
        raise SystemExit(f"{lista} ausente: o lote precisa de checksums para ser reprodutível")
    esperados: dict[str, str] = {}
    with open(lista, encoding="utf-8") as f:
        for linha in f:
            if linha.strip():
                soma, nome = linha.split(maxsplit=1)
                esperados[nome.strip().lstrip("*")] = soma
    faltando = [a for a in ARQUIVOS if a not in esperados]
    if faltando:
        raise SystemExit(f"Arquivos fora de {config.ARQ_CHECKSUMS}: {faltando}")
    divergentes = []
    for nome, soma in esperados.items():
        with open(_caminho(nome), "rb") as f:
            if hashlib.sha256(f.read()).hexdigest() != soma:
                divergentes.append(nome)
    if divergentes:
        raise SystemExit(f"Checksum divergente (arquivo alterado depois da coleta): {divergentes}")


def validar_recorte(cursos: list[dict], ofertas: list[dict]) -> None:
    esperados = set(config.semestres_da_carga())
    presentes: dict[str, set] = defaultdict(set)
    for r in ofertas:
        presentes[r["curso_codigo"]].add((int(r["ano"]), int(r["periodo"])))

    todos = set().union(*presentes.values()) if presentes else set()
    fora = sorted(rotulo(*s) for s in todos - esperados)
    if fora:
        raise SystemExit(f"Semestres fora do recorte {config.SEMESTRE_INICIO}–{config.SEMESTRE_FIM}: {fora}")

    # Cada semestre precisa ter encerrado ANTES de ser coletado; senão o lote
    # guarda um retrato parcial (ver docs/historico.md).
    calendario = ler_calendario(config.CALENDARIO)
    primeira_coleta: dict[tuple, date] = {}
    for r in ofertas:
        sem = (int(r["ano"]), int(r["periodo"]))
        dia = date.fromisoformat(r["coletado_em"][:10])
        primeira_coleta[sem] = min(dia, primeira_coleta.get(sem, dia))
    cedo = sorted(
        f"{rotulo(*sem)} (coletado em {dia:%d/%m/%Y}, encerrou em {calendario[sem]['encerramento']:%d/%m/%Y})"
        for sem, dia in primeira_coleta.items() if not encerrado_em(calendario, *sem, dia)
    )
    if cedo:
        raise SystemExit(f"Semestre(s) coletados antes do encerramento: {cedo}")

    lacunas = []
    for c in cursos:
        faltam = sorted(rotulo(*s) for s in esperados - presentes.get(c["codigo"], set()))
        if faltam:
            lacunas.append(f"{c['codigo']}: {', '.join(faltam)}")
    if lacunas:
        raise SystemExit("Curso sem reservas em algum semestre do recorte: " + "; ".join(lacunas))

    chaves = Counter(
        (r["curso_codigo"], r["disciplina_codigo"], r["turma_codigo"], r["ano"], r["periodo"]) for r in ofertas
    )
    duplicadas = [k for k, n in chaves.items() if n > 1]
    if duplicadas:
        raise SystemExit(f"Reservas duplicadas no lote: {duplicadas[:5]}")


def load(conn: psycopg.Connection) -> Counter:
    verificar_checksums()
    cursos = _ler(config.ARQ_CURSOS)
    componentes = _ler(config.ARQ_COMPONENTES)
    prereqs = _ler(config.ARQ_PRE_REQUISITOS)
    curriculos = _ler(config.ARQ_CURRICULOS)
    curriculo_comp = _ler(config.ARQ_CURRICULO_COMPONENTES)
    ofertas = _ler(config.ARQ_OFERTAS)
    validar_recorte(cursos, ofertas)
    lote = config.lote()

    stats: Counter = Counter()
    rejeitados: list[dict] = []
    divergencias: list[dict] = []

    def divergir(tabela: str, chave: str, campo: str, no_banco, no_lote) -> None:
        divergencias.append({"tabela": tabela, "chave": chave, "campo": campo,
                             "no_banco": no_banco, "no_lote": no_lote})

    def rejeitar(tabela: str, motivo: str, linha: dict) -> None:
        stats[f"{tabela}: rejeitada ({motivo})"] += 1
        rejeitados.append({"tabela": tabela, "motivo": motivo, "linha": repr(linha)})

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO unidade (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING",
            (config.UNIDADE_FCTE,),
        )

        # disciplina: catálogo da FCTE (upsert)
        for r in componentes:
            cur.execute(
                """
                INSERT INTO disciplina (codigo, nome, unidade_id, carga_horaria, tipo)
                SELECT %s, %s, u.id, %s, %s FROM unidade u WHERE u.nome = %s
                ON CONFLICT (codigo) DO UPDATE
                  SET nome = EXCLUDED.nome, unidade_id = EXCLUDED.unidade_id,
                      carga_horaria = EXCLUDED.carga_horaria, tipo = EXCLUDED.tipo
                """,
                (r["codigo"], r["nome"], int(r["carga_horaria"]) if r["carga_horaria"] else None,
                 r["tipo"] or None, r["unidade"]),
            )
            stats["disciplina: do catálogo FCTE"] += 1

        # disciplina: de outras unidades, citadas em currículos ou reservas.
        # Sem unidade (NULL) e sem sobrescrever o que o catálogo trouxe.
        externas: dict[str, tuple[str, int | None]] = {}
        for r in curriculo_comp:
            externas.setdefault(r["disciplina_codigo"], (r["disciplina_nome"], int(r["carga_horaria"]) if r["carga_horaria"] else None))
        for r in ofertas:
            externas.setdefault(r["disciplina_codigo"], (r["disciplina_nome"], None))
        for codigo, (nome, ch) in sorted(externas.items()):
            cur.execute(
                "INSERT INTO disciplina (codigo, nome, carga_horaria) VALUES (%s, %s, %s) "
                "ON CONFLICT (codigo) DO NOTHING RETURNING id",
                (codigo, nome, ch),
            )
            if cur.fetchone():
                stats["disciplina: de outra unidade (sem catálogo)"] += 1

        # pré-requisitos: só os componentes cujo detalhe foi coletado
        for r in prereqs:
            cur.execute(
                """
                UPDATE disciplina
                   SET pre_requisito_coletado = TRUE,
                       pre_requisito_expressao = %s,
                       co_requisito_expressao = %s,
                       pre_requisito_coletado_em = %s
                 WHERE codigo = %s
                """,
                (r["pre_requisito_expressao"], r["co_requisito_expressao"], _ts(r["coletado_em"]),
                 r["disciplina_codigo"]),
            )
            if cur.rowcount:
                stats["disciplina: com detalhe de pré-requisito"] += 1
            else:
                rejeitar("disciplina", "pré-requisito de componente ausente", r)

        # curso (upsert)
        for r in cursos:
            cur.execute(
                """
                INSERT INTO curso (codigo, nome, unidade_id, turno, url_fonte)
                SELECT %s, %s, u.id, %s, %s FROM unidade u WHERE u.nome = %s
                ON CONFLICT (codigo) DO UPDATE
                  SET nome = EXCLUDED.nome, turno = EXCLUDED.turno, url_fonte = EXCLUDED.url_fonte
                """,
                (r["codigo"], r["nome"], r["turno"], r["url_fonte"], r["unidade"]),
            )
            stats["curso"] += 1

        # currículo (upsert)
        for r in curriculos:
            ano, periodo = parse_semestre(r["inicio_vigencia"])
            cur.execute(
                """
                INSERT INTO curriculo (curso_id, codigo, inicio_vigencia_ano, inicio_vigencia_periodo,
                                       fonte, lote, coletado_em)
                SELECT c.id, %s, %s, %s, 'sigaa_curriculos', %s, %s FROM curso c WHERE c.codigo = %s
                ON CONFLICT (codigo) DO UPDATE
                  SET inicio_vigencia_ano = EXCLUDED.inicio_vigencia_ano,
                      inicio_vigencia_periodo = EXCLUDED.inicio_vigencia_periodo,
                      lote = EXCLUDED.lote, coletado_em = EXCLUDED.coletado_em
                """,
                (r["curriculo_codigo"], ano, periodo, lote, r["coletado_em"], r["curso_codigo"]),
            )
            stats["curriculo"] += 1

        # componentes de cada versão curricular (upsert)
        for r in curriculo_comp:
            cur.execute(
                """
                INSERT INTO curriculo_componente (curriculo_id, disciplina_id, natureza, grupo)
                SELECT cu.id, d.id, %s, %s FROM curriculo cu, disciplina d
                WHERE cu.codigo = %s AND d.codigo = %s
                ON CONFLICT (curriculo_id, disciplina_id) DO UPDATE
                  SET natureza = EXCLUDED.natureza, grupo = EXCLUDED.grupo
                """,
                (normalizar_natureza(r["natureza"]), r["grupo"], r["curriculo_codigo"], r["disciplina_codigo"]),
            )
            stats["curriculo_componente"] += 1

        # calendário acadêmico (upsert): as turmas referenciam semestre_letivo
        with open(config.CALENDARIO, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                cur.execute(
                    """
                    INSERT INTO semestre_letivo (ano, periodo, primeiro_dia_aulas, ultimo_dia_aulas,
                                                 ultimo_dia_letivo, consolidacao_ate, fonte_url, observacao)
                    VALUES (%s, %s, NULLIF(%s, '')::date, NULLIF(%s, '')::date, NULLIF(%s, '')::date,
                            NULLIF(%s, '')::date, %s, NULLIF(%s, ''))
                    ON CONFLICT (ano, periodo) DO UPDATE
                      SET primeiro_dia_aulas = EXCLUDED.primeiro_dia_aulas,
                          ultimo_dia_aulas = EXCLUDED.ultimo_dia_aulas,
                          ultimo_dia_letivo = EXCLUDED.ultimo_dia_letivo,
                          consolidacao_ate = EXCLUDED.consolidacao_ate,
                          fonte_url = EXCLUDED.fonte_url, observacao = EXCLUDED.observacao
                    """,
                    (r["ano"], r["periodo"], r["primeiro_dia_aulas"], r["ultimo_dia_aulas"],
                     r["ultimo_dia_letivo"], r["consolidacao_ate"], r["fonte_url"], r["observacao"]),
                )
                stats["semestre_letivo"] += 1

        # turmas: a mesma turma aparece uma vez por curso que reserva vagas nela.
        por_turma: dict[tuple, list[dict]] = defaultdict(list)
        for r in ofertas:
            por_turma[(r["disciplina_codigo"], r["turma_codigo"], int(r["ano"]), int(r["periodo"]))].append(r)

        for (disc, cod, ano, periodo), linhas in sorted(por_turma.items()):
            # Se os cursos discordam sobre horário ou docentes da mesma turma, não
            # há como saber qual está certo: rejeita a turma e as reservas dela.
            atributos = {(r["horario"], r["docentes"]) for r in linhas}
            if len(atributos) > 1:
                for r in linhas:
                    rejeitar("reserva_vaga", "turma com horário/docente divergente entre cursos", r)
                continue

            horario = extrair_horario([linhas[0]["horario"]])
            turno = inferir_turno(horario)
            docentes = parse_docentes(linhas[0]["docentes"])
            chave_turma = f"{disc} turma {cod} {rotulo(ano, periodo)}"
            cur.execute(
                """
                INSERT INTO turma (disciplina_id, codigo_turma, ano, periodo, horario, turno,
                                   fonte, lote, coletado_em)
                SELECT d.id, %s, %s, %s, NULLIF(%s, ''), %s, %s, %s, %s FROM disciplina d WHERE d.codigo = %s
                ON CONFLICT (disciplina_id, codigo_turma, ano, periodo) DO NOTHING
                RETURNING id
                """,
                (cod, ano, periodo, horario, turno, linhas[0]["fonte"], lote,
                 min(r["coletado_em"] for r in linhas), disc),
            )
            nova = cur.fetchone()
            if nova:
                turma_id = nova[0]
                stats[f"turma {rotulo(ano, periodo)}: inserida"] += 1
                # Docentes só entram junto com a turma: depois disso a
                # composição da turma não muda (insert-only).
                for nome in docentes:
                    cur.execute("INSERT INTO docente (nome) VALUES (%s) ON CONFLICT (nome) DO NOTHING", (nome,))
                    cur.execute(
                        """INSERT INTO turma_docente (turma_id, docente_id)
                           SELECT %s, id FROM docente WHERE nome = %s""",
                        (turma_id, nome),
                    )
                if not docentes:
                    stats["turma: sem docente informado"] += 1
            else:
                cur.execute(
                    """SELECT t.id, coalesce(t.horario, ''), t.turno,
                              coalesce(array_agg(doc.nome ORDER BY doc.nome) FILTER (WHERE doc.nome IS NOT NULL), '{}')
                       FROM turma t
                       JOIN disciplina d ON d.id = t.disciplina_id
                       LEFT JOIN turma_docente td ON td.turma_id = t.id
                       LEFT JOIN docente doc ON doc.id = td.docente_id
                       WHERE d.codigo = %s AND t.codigo_turma = %s AND t.ano = %s AND t.periodo = %s
                       GROUP BY t.id, t.horario, t.turno""",
                    (disc, cod, ano, periodo),
                )
                turma_id, horario_banco, turno_banco, docentes_banco = cur.fetchone()
                iguais = True
                if horario_banco != horario:
                    divergir("turma", chave_turma, "horario", horario_banco, horario)
                    iguais = False
                if turno_banco != turno:
                    divergir("turma", chave_turma, "turno", turno_banco, turno)
                    iguais = False
                if sorted(docentes_banco) != sorted(docentes):
                    divergir("turma", chave_turma, "docentes", " , ".join(docentes_banco), " , ".join(sorted(docentes)))
                    iguais = False
                if iguais:
                    stats["turma: idêntica (reprocessamento)"] += 1

            for r in linhas:
                vagas = int(r["vagas_reservadas"])
                cur.execute(
                    """
                    INSERT INTO reserva_vaga (turma_id, curso_id, vagas_reservadas, fonte, lote, coletado_em)
                    SELECT %s, c.id, %s, %s, %s, %s FROM curso c WHERE c.codigo = %s
                    ON CONFLICT (turma_id, curso_id) DO NOTHING
                    RETURNING turma_id
                    """,
                    (turma_id, vagas, r["fonte"], lote, r["coletado_em"], r["curso_codigo"]),
                )
                if cur.fetchone():
                    stats["reserva_vaga: inserida"] += 1
                    continue
                cur.execute(
                    """SELECT rv.vagas_reservadas FROM reserva_vaga rv JOIN curso c ON c.id = rv.curso_id
                       WHERE rv.turma_id = %s AND c.codigo = %s""",
                    (turma_id, r["curso_codigo"]),
                )
                vagas_banco = cur.fetchone()[0]
                if vagas_banco == vagas:
                    stats["reserva_vaga: idêntica (reprocessamento)"] += 1
                else:
                    divergir("reserva_vaga", f"{chave_turma} curso {r['curso_codigo']}", "vagas_reservadas",
                             vagas_banco, vagas)

        if divergencias:
            conn.rollback()
            os.makedirs(config.DEBUG_DIR, exist_ok=True)
            caminho = os.path.join(config.DEBUG_DIR, "divergencias.csv")
            with open(caminho, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=["tabela", "chave", "campo", "no_banco", "no_lote"])
                writer.writeheader()
                writer.writerows(divergencias)
            raise SystemExit(
                f"{len(divergencias)} divergência(s) entre o lote e o banco; nada foi carregado. "
                f"Detalhes em {caminho}. Turmas e reservas são insert-only: aceitar valores novos "
                "exige decisão da Squad (ver docs/historico.md)."
            )

    conn.commit()

    # Estatísticas atualizadas logo após a carga: sem elas, o planejador do
    # Postgres escolhe planos ruins até o autovacuum rodar, e as medições de
    # caracterizar.py variam conforme o momento em que são feitas.
    with conn.cursor() as cur:
        cur.execute("ANALYZE")
    conn.commit()

    os.makedirs(config.DEBUG_DIR, exist_ok=True)
    with open(os.path.join(config.DEBUG_DIR, "rejeitados.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["tabela", "motivo", "linha"])
        writer.writeheader()
        writer.writerows(rejeitados)
    return stats


if __name__ == "__main__":
    print(f"Lote: {config.DATA_DIR}")
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
