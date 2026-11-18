#!/usr/bin/env python3
"""Teste da E4: a mesma métrica mostra o mesmo valor em todas as telas.

Compara, para todo curso × semestre (e para os totais por curso):
  1. o que o MetricFlow calcula agora (definição em models/semantic/semantica.yml);
  2. analytics.metricas_oficiais (o que os consumidores leem);
  3. analytics.mart_observatorio (o mart da E3);
  4. a API do painel (/api/observatorio);
  5. a Pauta da coordenação (itens recebidos pelo ETL reverso).

Qualquer divergência termina com código 1.
    docker compose run --rm --no-deps analytics python /workspace/tests/metricas_consistentes.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from collections import Counter

sys.path.insert(0, "/workspace/analytics")
from semantica import conectar, consultar  # noqa: E402

PAINEL = os.getenv("PAINEL_URL", "http://dashboard:8080")
PAUTA = os.getenv("PAUTA_URL", "http://coordenacao:8090")
TOLERANCIA = 1e-9
falhas: list[str] = []
conferidos = Counter()


def igual(rotulo: str, a: float, b: float) -> None:
    conferidos[rotulo.split(":")[0]] += 1
    if abs(float(a) - float(b)) > TOLERANCIA:
        falhas.append(f"{rotulo}: {a} ≠ {b}")


def http_json(url: str):
    with urllib.request.urlopen(url, timeout=10) as resposta:
        return json.loads(resposta.read())


def main() -> int:
    # 1. MetricFlow, agora
    mf = {}
    for linha in consultar(["lugares_guardados", "turmas_que_guardaram", "materias_com_reserva",
                            "participacao_outros_departamentos"],
                           ["reserva__curso_codigo", "reserva__semestre"]):
        mf[(linha["reserva__curso_codigo"], linha["reserva__semestre"])] = linha
    mf_cob = {l["item_curricular__curso_codigo"]: l for l in consultar(
        ["obrigatorias_no_curriculo", "obrigatorias_cobertas"], ["item_curricular__curso_codigo"])}

    # 2 e 3. tabela oficial e mart
    with conectar() as conn, conn.cursor() as cur:
        cur.execute("SELECT metrica, curso_codigo, semestre, valor FROM analytics.metricas_oficiais WHERE recorte = 'total'")
        oficial = {(m, c, s): v for m, c, s, v in cur.fetchall()}
        cur.execute("""SELECT metrica, curso_codigo, substr(recorte, 12), semestre, valor
                       FROM analytics.metricas_oficiais WHERE recorte LIKE 'disciplina:%%'""")
        oficial_disc = {(c, d, s): v for _, c, d, s, v in cur.fetchall()}
        cur.execute("""SELECT curso_codigo, semestre, vagas_reservadas, turmas_com_reserva, obrigatorias_com_reserva
                       FROM analytics.mart_observatorio""")
        mart = {(c, s): (v, t, o) for c, s, v, t, o in cur.fetchall()}

    for (curso, semestre), l in mf.items():
        for metrica in ("lugares_guardados", "turmas_que_guardaram", "materias_com_reserva",
                        "participacao_outros_departamentos"):
            igual(f"mf×oficial:{metrica}:{curso}:{semestre}", l[metrica], oficial[(metrica, curso, semestre)])
        v, t, o = mart[(curso, semestre)]
        igual(f"mart×oficial:lugares:{curso}:{semestre}", v, oficial[("lugares_guardados", curso, semestre)])
        igual(f"mart×oficial:turmas:{curso}:{semestre}", t, oficial[("turmas_que_guardaram", curso, semestre)])
        igual(f"mart×oficial:materias:{curso}:{semestre}", o, oficial[("materias_com_reserva", curso, semestre)])
    for curso, l in mf_cob.items():
        for metrica in ("obrigatorias_no_curriculo", "obrigatorias_cobertas"):
            igual(f"mf×oficial:{metrica}:{curso}", l[metrica], oficial[(metrica, curso, "todos")])

    # 4. API do painel
    api = http_json(f"{PAINEL}/api/observatorio")
    for linha in api["serie"]:
        chave = (linha["curso_codigo"], linha["semestre"])
        igual(f"painel×oficial:lugares:{chave}", linha["vagas_reservadas"], oficial[("lugares_guardados", *chave)])
        igual(f"painel×oficial:turmas:{chave}", linha["turmas_com_reserva"], oficial[("turmas_que_guardaram", *chave)])
        igual(f"painel×oficial:materias:{chave}", linha["obrigatorias_com_reserva"], oficial[("materias_com_reserva", *chave)])
        igual(f"painel×oficial:participacao:{chave}", linha["participacao_outros"],
              oficial[("participacao_outros_departamentos", *chave)])
    for t in api["totais"]:
        igual(f"painel×oficial:{t['metrica']}:{t['curso_codigo']}", t["valor"], oficial[(t["metrica"], t["curso_codigo"], "todos")])

    # 5. Pauta da coordenação
    itens = http_json(f"{PAUTA}/api/itens")
    sem_reserva = Counter(i["curso_codigo"] for i in itens if i["tipo"] == "obrigatoria_sem_reserva")
    for curso in mf_cob:
        esperado = float(oficial[("obrigatorias_no_curriculo", curso, "todos")]) - float(oficial[("obrigatorias_cobertas", curso, "todos")])
        igual(f"pauta×oficial:obrigatorias_sem_reserva:{curso}", sem_reserva[curso], esperado)
    for item in itens:
        dados = json.loads(item["dados"])
        if dados["tipo"] == "reserva_grande":
            igual(f"pauta×oficial:reserva_grande:{dados['curso_codigo']}:{dados['disciplina_codigo']}", dados["valor"],
                  oficial_disc[(dados["curso_codigo"], dados["disciplina_codigo"], dados["semestre"])])
    for alerta in api["alertas"]:
        igual(f"painel×pauta:vale_conferir:{alerta['curso_codigo']}:{alerta['disciplina_codigo']}", alerta["vagas_reservadas"],
              oficial_disc[(alerta["curso_codigo"], alerta["disciplina_codigo"], alerta["semestre"])])

    print("Valores conferidos por comparação:")
    for nome, n in sorted(conferidos.items()):
        print(f"  {nome:<22} {n:>5}")
    if falhas:
        print(f"\nFALHOU: {len(falhas)} divergências")
        for f in falhas[:30]:
            print("  " + f)
        return 1
    print(f"\nOK: {sum(conferidos.values())} valores, 0 divergências entre MetricFlow, tabela oficial, mart, painel e Pauta.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
