"""Monta os itens da Pauta da coordenação a partir das MÉTRICAS OFICIAIS.

Usado pelo ETL reverso (envio por API) e pelo CSV agendado (opção nula).
Nenhuma métrica é recalculada aqui: o valor de cada item vem de
analytics.metricas_oficiais (camada semântica) ou da lista de obrigatórias
do currículo de referência (mart_cobertura_curriculo).

Tipos de item:
  reserva_grande           a matéria guardou 50 lugares ou mais para o curso no último semestre
  obrigatoria_sem_reserva  a matéria é obrigatória e nunca guardou lugar para o curso
  queda_forte              os lugares guardados caíram pela metade ou mais de 2022 para 2025
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

LIMITE_RESERVA_GRANDE = 50
MINIMO_PARA_QUEDA = 20
CURSOS = {"FGA_SOFT": "Software", "FGA_AERO": "Aeroespacial", "FGA_AUTO": "Automotiva",
          "FGA_ELET": "Eletrônica", "FGA_ENERG": "Energia"}
DEPARTAMENTOS = {"FGA": "a própria FCTE", "MAT": "o Departamento de Matemática", "IFD": "o Instituto de Física",
                 "CIC": "o Departamento de Ciência da Computação", "EST": "o Departamento de Estatística",
                 "CDT": "o Centro de Desenvolvimento Sustentável", "ENM": "o Departamento de Engenharia Mecânica"}
MINUSC = {"de", "da", "do", "das", "dos", "e", "em", "para", "a", "o", "à", "ao", "na", "no", "com"}


def titulo(texto: str) -> str:
    palavras = texto.lower().split()
    return " ".join(p.upper() if p in {"i", "ii", "iii", "iv", "v"} else p if i and p in MINUSC else p.capitalize()
                    for i, p in enumerate(palavras))


def semestre_longo(s: str) -> str:
    ano, periodo = s.split(".")
    return f"{periodo}º semestre de {ano}"


def departamento(codigo: str) -> str:
    prefixo = "".join(c for c in codigo if c.isalpha())
    return DEPARTAMENTOS.get(prefixo, f"o departamento {prefixo}")


def _chave(*partes: str) -> str:
    return hashlib.sha256("|".join(partes).encode()).hexdigest()[:24]


def _item(tipo, curso, semestre, disciplina, nome, tit, detalhe, metrica, versao_metrica, valor):
    item = {
        "chave": _chave(tipo, curso, semestre, disciplina),
        "tipo": tipo, "curso_codigo": curso, "curso": CURSOS.get(curso, curso),
        "semestre": semestre, "disciplina_codigo": disciplina, "disciplina": nome,
        "titulo": tit, "detalhe": detalhe,
        "metrica": metrica, "versao_metrica": versao_metrica, "valor": valor,
    }
    # a versão muda só se o conteúdo ou a definição da métrica mudar
    item["versao"] = hashlib.sha256(json.dumps(item, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    return item


def montar(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute("SELECT disciplina_codigo, disciplina_nome FROM analytics.dim_disciplina WHERE is_current")
        nomes = dict(cur.fetchall())
        cur.execute("""SELECT curso_codigo, semestre, substr(recorte, 12) AS disciplina_codigo, valor, versao
                       FROM analytics.metricas_oficiais
                       WHERE metrica = 'lugares_guardados' AND recorte LIKE 'disciplina:%%'""")
        por_disciplina = cur.fetchall()
        cur.execute("""SELECT curso_codigo, curriculo_codigo, disciplina_codigo, disciplina_nome
                       FROM analytics.mart_cobertura_curriculo WHERE semestres_com_reserva = 0""")
        sem_reserva = cur.fetchall()
        cur.execute("SELECT versao FROM analytics.metricas_definicoes WHERE metrica = 'obrigatorias_cobertas'")
        versao_cobertura = cur.fetchone()[0]

    itens = []
    ultimo = defaultdict(str)
    for curso, semestre, *_ in por_disciplina:
        ultimo[curso] = max(ultimo[curso], semestre)

    anos = defaultdict(lambda: {"2022": 0, "2025": 0, "versao": 1})
    for curso, semestre, disc, valor, versao in por_disciplina:
        valor = int(valor)
        nome = titulo(nomes.get(disc, disc))
        if semestre == ultimo[curso] and valor >= LIMITE_RESERVA_GRANDE:
            itens.append(_item(
                "reserva_grande", curso, semestre, disc, nome,
                f"{nome}: {valor} lugares guardados para {CURSOS[curso]} no {semestre_longo(semestre)}",
                f"É uma reserva grande. Confirme com {departamento(disc)} se esses lugares são mesmo para o curso "
                f"antes de negociar o próximo semestre: desde o 2º semestre de 2023 reservas grandes ficaram comuns "
                f"e podem ser só a forma de registro.",
                "lugares_guardados", versao, valor))
        ano = semestre.split(".")[0]
        if ano in ("2022", "2025"):
            anos[(curso, disc)][ano] += valor
            anos[(curso, disc)]["versao"] = versao

    for (curso, disc), v in anos.items():
        if v["2022"] >= MINIMO_PARA_QUEDA and v["2025"] <= v["2022"] / 2:
            nome = titulo(nomes.get(disc, disc))
            itens.append(_item(
                "queda_forte", curso, "2022→2025", disc, nome,
                f"{nome}: de {v['2022']} para {v['2025']} lugares guardados para {CURSOS[curso]} (2022 → 2025)",
                f"Os lugares guardados caíram pela metade ou mais. Vale entender com {departamento(disc)} o que mudou.",
                "lugares_guardados", v["versao"], v["2025"] - v["2022"]))

    for curso, curriculo, disc, nome_bruto in sem_reserva:
        nome = titulo(nome_bruto)
        itens.append(_item(
            "obrigatoria_sem_reserva", curso, "2022.1–2026.1", disc, nome,
            f"{nome} nunca guardou lugar para {CURSOS[curso]}",
            f"É obrigatória no currículo {curriculo}, mas nenhuma turma de 2022 a 2026 guardou lugar para o curso. "
            f"Negociar com {departamento(disc)}.",
            "obrigatorias_cobertas", versao_cobertura, 0))
    return sorted(itens, key=lambda i: (i["curso_codigo"], i["tipo"], i["titulo"]))
