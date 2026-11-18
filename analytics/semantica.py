#!/usr/bin/env python3
"""Materializa as métricas da camada semântica em analytics.metricas_oficiais.

As métricas são DEFINIDAS em analytics/models/semantic/semantica.yml
(MetricFlow). Este script só pede ao MetricFlow os valores e os grava numa
tabela que todos os consumidores leem: o painel (API), a Pauta da
coordenação (ETL reverso) e o CSV agendado. Ninguém recalcula métrica fora
daqui; tests/metricas_consistentes.py confere isso.

Saída, em formato longo:
    analytics.metricas_oficiais(metrica, versao, curso_codigo, semestre, recorte, valor, calculado_em)
    analytics.metricas_definicoes(metrica, rotulo, descricao, tipo, versao, desde)
semestre = 'todos' quando a métrica vale para o período inteiro;
recorte = 'total', 'disciplina:<código>' ou 'unidade:<prefixo do departamento>'.
"""

from __future__ import annotations

import csv
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg

PROJETO = Path(__file__).resolve().parent
CONSULTAS = [
    # (métricas, agrupamento, coluna do curso, coluna do semestre)
    (
        ["lugares_guardados", "turmas_que_guardaram", "materias_com_reserva",
         "lugares_outros_departamentos", "participacao_outros_departamentos"],
        ["reserva__curso_codigo", "reserva__semestre"],
        "reserva__curso_codigo", "reserva__semestre",
    ),
    (
        ["lugares_guardados", "lugares_outros_departamentos", "participacao_outros_departamentos"],
        ["reserva__curso_codigo"],
        "reserva__curso_codigo", None,
    ),
    (
        ["lugares_guardados"],
        ["reserva__curso_codigo", "reserva__semestre", "reserva__disciplina_codigo"],
        "reserva__curso_codigo", "reserva__semestre",
    ),
    (
        ["lugares_guardados"],
        ["reserva__curso_codigo", "reserva__unidade_origem"],
        "reserva__curso_codigo", None,
    ),
    (
        ["obrigatorias_no_curriculo", "obrigatorias_cobertas", "cobertura_curricular"],
        ["item_curricular__curso_codigo"],
        "item_curricular__curso_codigo", None,
    ),
]


def conectar() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "db"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    )


def definicoes() -> dict[str, dict[str, object]]:
    manifesto = json.loads((PROJETO / "target" / "manifest.json").read_text(encoding="utf-8"))
    saida = {}
    for no in manifesto["metrics"].values():
        meta = no.get("meta") or no.get("config", {}).get("meta", {})
        saida[no["name"]] = {
            "rotulo": no.get("label") or no["name"],
            "descricao": " ".join((no.get("description") or "").split()),
            "tipo": no.get("type"),
            "versao": int(meta.get("versao", 1)),
            "desde": meta.get("desde"),
        }
    return saida


def consultar(metricas: list[str], agrupamento: list[str]) -> list[dict[str, str]]:
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as arquivo:
        destino = arquivo.name
    subprocess.run(
        ["mf", "query", "--metrics", ",".join(metricas), "--group-by", ",".join(agrupamento),
         "--decimals", "6", "--csv", destino],
        cwd=PROJETO, check=True, env={**os.environ, "DBT_PROFILES_DIR": str(PROJETO)},
        stdout=subprocess.DEVNULL,
    )
    with open(destino, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def recorte(registro: dict[str, str]) -> str:
    if registro.get("reserva__disciplina_codigo"):
        return f"disciplina:{registro['reserva__disciplina_codigo']}"
    if registro.get("reserva__unidade_origem"):
        return f"unidade:{registro['reserva__unidade_origem']}"
    return "total"


def main() -> None:
    defs = definicoes()
    agora = datetime.now(timezone.utc)
    linhas = []
    for metricas, agrupamento, col_curso, col_semestre in CONSULTAS:
        for registro in consultar(metricas, agrupamento):
            for metrica in metricas:
                valor = registro.get(metrica)
                if valor in (None, ""):
                    continue
                linhas.append((metrica, defs[metrica]["versao"], registro[col_curso],
                               registro[col_semestre] if col_semestre else "todos",
                               recorte(registro), valor, agora))

    with conectar() as conn, conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analytics.metricas_oficiais (
                metrica TEXT NOT NULL, versao INTEGER NOT NULL, curso_codigo TEXT NOT NULL,
                semestre TEXT NOT NULL, recorte TEXT NOT NULL DEFAULT 'total',
                valor NUMERIC NOT NULL, calculado_em TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (metrica, curso_codigo, semestre, recorte))""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS analytics.metricas_definicoes (
                metrica TEXT PRIMARY KEY, rotulo TEXT NOT NULL, descricao TEXT NOT NULL,
                tipo TEXT NOT NULL, versao INTEGER NOT NULL, desde TEXT)""")
        # substitui o conteúdo na mesma transação: quem lê nunca vê a tabela pela metade
        cur.execute("DELETE FROM analytics.metricas_oficiais")
        cur.executemany(
            "INSERT INTO analytics.metricas_oficiais (metrica, versao, curso_codigo, semestre, recorte, valor, calculado_em) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)", linhas)
        cur.execute("DELETE FROM analytics.metricas_definicoes")
        cur.executemany(
            "INSERT INTO analytics.metricas_definicoes VALUES (%s, %s, %s, %s, %s, %s)",
            [(n, d["rotulo"], d["descricao"], d["tipo"], d["versao"], d["desde"]) for n, d in defs.items()])
        # o acesso por curso (RLS) e os grants vêm da V012; aqui só garantimos que valem
        cur.execute("SELECT to_regprocedure('operations.aplicar_acesso_analytics()') IS NOT NULL")
        if cur.fetchone()[0]:
            cur.execute("SELECT operations.aplicar_acesso_analytics()")
    print(f"metricas_oficiais: {len(linhas)} valores de {len(defs)} métricas, calculados em {agora:%Y-%m-%d %H:%M} UTC")


if __name__ == "__main__":
    main()
