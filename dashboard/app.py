"""Observatório de reservas da FCTE: responde à pergunta de gestão da E1.

GET /                  página (static/index.html), gráficos desenhados no navegador
GET /api/observatorio  um JSON com tudo o que a página usa

Lê só a camada de consumo: analytics.mart_observatorio, mart_disciplina_semestre,
mart_cobertura_curriculo, metricas_freshness e a fila operations.alertas_reserva.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
from psycopg.rows import dict_row

PAGINA = Path(__file__).parent / "static" / "index.html"

CONSULTAS = {
    "cursos": "select curso_codigo as codigo, curso_nome as nome from analytics.dim_curso order by curso_codigo",
    "serie": """
        select curso_codigo, semestre_key, semestre, vagas_reservadas,
               obrigatorias_com_reserva, turmas_com_reserva
        from analytics.mart_observatorio order by curso_codigo, semestre_key""",
    "disciplinas": """
        select curso_codigo, disciplina_codigo, disciplina_nome, unidade_origem, obrigatoria,
               semestre_key, vagas_reservadas, turmas
        from analytics.mart_disciplina_semestre order by curso_codigo, disciplina_codigo, semestre_key""",
    "cobertura": """
        select curso_codigo, curriculo_codigo, disciplina_codigo, disciplina_nome, unidade_origem,
               grupo, semestres_com_reserva, vagas_no_recorte, primeiro_semestre, ultimo_semestre
        from analytics.mart_cobertura_curriculo order by curso_codigo, vagas_no_recorte desc""",
    "alertas": """
        select curso_codigo, semestre, disciplina_codigo, vagas_reservadas
        from operations.alertas_reserva order by curso_codigo, semestre desc, vagas_reservadas desc""",
    "semestres": "select semestre_key, semestre from analytics.dim_semestre order by semestre_key",
}


def conectar() -> psycopg.Connection:
    return psycopg.connect(
        host=os.getenv("PGHOST", "db"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
        row_factory=dict_row,
    )


def serializar(valor: object) -> object:
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    raise TypeError(type(valor))


def observatorio() -> dict[str, object]:
    with conectar() as conn, conn.cursor() as cur:
        dados: dict[str, object] = {}
        for chave, sql in CONSULTAS.items():
            cur.execute(sql)
            dados[chave] = cur.fetchall()
        cur.execute("select * from analytics.metricas_freshness")
        dados["freshness"] = cur.fetchone()
    # Só semestres que têm reserva no recorte (o calendário tem um a mais).
    com_dado = {linha["semestre_key"] for linha in dados["serie"]}
    dados["semestres"] = [s for s in dados["semestres"] if s["semestre_key"] in com_dado]
    return dados


class Handler(BaseHTTPRequestHandler):
    def responder(self, status: int, tipo: str, corpo: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:
        caminho = urlsplit(self.path).path
        if caminho == "/api/observatorio":
            try:
                corpo = json.dumps(observatorio(), default=serializar, ensure_ascii=False).encode()
                self.responder(200, "application/json; charset=utf-8", corpo)
            except psycopg.Error as erro:
                mensagem = {"erro": "Banco indisponível ou camada analítica não gerada. Rode docker compose up.",
                            "detalhe": str(erro).strip()}
                self.responder(503, "application/json; charset=utf-8", json.dumps(mensagem).encode())
        elif caminho in ("/", "/index.html"):
            self.responder(200, "text/html; charset=utf-8", PAGINA.read_bytes())
        else:
            self.responder(404, "text/plain; charset=utf-8", b"nao encontrado")

    def log_message(self, formato: str, *args: object) -> None:
        pass


ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()
