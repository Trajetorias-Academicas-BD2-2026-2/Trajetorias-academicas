"""Pauta da coordenação: o sistema operacional que recebe o ETL reverso (E4).

É um sistema separado do warehouse, com banco próprio (SQLite em volume).
O coordenador abre a pauta antes da reunião de negociação de vagas com
cada departamento e marca o que já revisou.

    POST /api/itens          recebe um item (header Idempotency-Key obrigatório)
    GET  /api/itens?curso=   lista os itens
    POST /api/itens/<chave>/revisar   marca como revisado
    GET  /saude              verificação de vida
    GET  /                   a tela da pauta

Idempotência: a chave identifica o item; a Idempotency-Key identifica a
versão. Reenviar a mesma versão não muda nada (200). Uma versão nova do
mesmo item atualiza o conteúdo e volta o item para "a revisar" (200).
Um item novo é criado (201).
"""

from __future__ import annotations

import html
import json
import os
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

BANCO = os.getenv("PAUTA_DB", "/dados/pauta.sqlite3")
CURSOS = {"FGA_SOFT": "Software", "FGA_AERO": "Aeroespacial", "FGA_AUTO": "Automotiva",
          "FGA_ELET": "Eletrônica", "FGA_ENERG": "Energia"}
TIPOS = {
    "reserva_grande": "Confirmar reserva grande",
    "obrigatoria_sem_reserva": "Negociar lugar para o curso",
    "queda_forte": "Entender a queda",
}


def conectar() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(BANCO), exist_ok=True)
    conn = sqlite3.connect(BANCO)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS item (
            chave TEXT PRIMARY KEY,
            versao TEXT NOT NULL,
            curso_codigo TEXT NOT NULL,
            tipo TEXT NOT NULL,
            titulo TEXT NOT NULL,
            detalhe TEXT NOT NULL,
            dados TEXT NOT NULL,
            recebido_em TEXT NOT NULL,
            atualizado_em TEXT NOT NULL,
            revisado_em TEXT,
            revisado_por TEXT
        )""")
    return conn


def agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def receber(item: dict, versao: str) -> int:
    with conectar() as conn:
        atual = conn.execute("SELECT versao FROM item WHERE chave = ?", (item["chave"],)).fetchone()
        if atual and atual["versao"] == versao:
            return 200  # mesma versão: reenvio idempotente, nada muda
        campos = (versao, item["curso_codigo"], item["tipo"], item["titulo"], item["detalhe"],
                  json.dumps(item, ensure_ascii=False), agora())
        if atual:
            conn.execute("""UPDATE item SET versao=?, curso_codigo=?, tipo=?, titulo=?, detalhe=?, dados=?,
                            atualizado_em=?, revisado_em=NULL, revisado_por=NULL WHERE chave=?""",
                         (*campos, item["chave"]))
            return 200
        conn.execute("""INSERT INTO item (versao, curso_codigo, tipo, titulo, detalhe, dados, atualizado_em,
                        chave, recebido_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                     (*campos, item["chave"], agora()))
        return 201


def listar(curso: str | None) -> list[dict]:
    with conectar() as conn:
        sql = "SELECT * FROM item" + (" WHERE curso_codigo = ?" if curso else "") + " ORDER BY curso_codigo, tipo, titulo"
        return [dict(r) for r in conn.execute(sql, (curso,) if curso else ())]


def pagina(curso: str | None) -> str:
    itens = listar(curso)
    abas = "".join(
        f'<a class="aba{" ativa" if c == curso else ""}" href="/?curso={c}">{n}</a>' for c, n in CURSOS.items())
    blocos = []
    for tipo, nome_tipo in TIPOS.items():
        do_tipo = [i for i in itens if i["tipo"] == tipo]
        if not do_tipo:
            continue
        linhas = "".join(f"""
          <li class="{'feito' if i['revisado_em'] else ''}">
            <div><strong>{html.escape(i['titulo'])}</strong><p>{html.escape(i['detalhe'])}</p>
            <small>{CURSOS.get(i['curso_codigo'], i['curso_codigo'])} · recebido em {i['recebido_em'][:10]}</small></div>
            {f"<span class='ok'>Revisado em {i['revisado_em'][:10]}</span>" if i['revisado_em'] else
             f"<form method='post' action='/api/itens/{html.escape(i['chave'])}/revisar?volta={html.escape(curso or '')}'><button>Marcar como revisado</button></form>"}
          </li>""" for i in do_tipo)
        pendentes = sum(1 for i in do_tipo if not i["revisado_em"])
        blocos.append(f"<section><h2>{nome_tipo} <span>{pendentes} a revisar de {len(do_tipo)}</span></h2><ul>{linhas}</ul></section>")
    corpo = "".join(blocos) or "<p class='vazio'>Nenhum item na pauta. Rode o pipeline para receber os itens.</p>"
    return f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Pauta da coordenação</title>
<style>
body{{margin:0;font:17px/1.5 system-ui,sans-serif;background:#F4F6FB;color:#14213D}}
header{{background:#14213D;color:#F4F6FB;padding:28px 24px}} header p{{color:#B9C3D9;margin:6px 0 0}}
main{{max-width:960px;margin:0 auto;padding:24px}} h1{{margin:0;font-size:28px}}
.abas{{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}} .aba{{padding:8px 14px;border-radius:999px;background:#E6EAF3;color:#14213D;text-decoration:none;font-weight:600}}
.aba.ativa{{background:#14213D;color:#F4F6FB}}
section{{margin-top:26px}} h2{{font-size:21px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}} h2 span{{font-size:15px;color:#4E5B78;font-weight:500}}
ul{{list-style:none;padding:0;margin:0;display:grid;gap:10px}}
li{{background:#fff;border-radius:14px;padding:14px 16px;display:flex;justify-content:space-between;gap:16px;align-items:center;border-left:5px solid #FFC145}}
li.feito{{opacity:.6;border-left-color:#2BC4A9}} li p{{margin:4px 0;color:#4E5B78}} li small{{color:#4E5B78}}
button{{font:inherit;font-weight:600;border:0;background:#14213D;color:#fff;border-radius:10px;padding:9px 14px;cursor:pointer;white-space:nowrap}}
.ok{{color:#12806D;font-weight:600;white-space:nowrap}} .vazio{{color:#4E5B78}}
</style>
<header><h1>Pauta da coordenação</h1><p>O que conferir antes de negociar as vagas do próximo semestre com cada departamento.</p></header>
<main><nav class="abas"><a class="aba{' ativa' if not curso else ''}" href="/">Todos os cursos</a>{abas}</nav>{corpo}</main></html>"""


class Handler(BaseHTTPRequestHandler):
    def responder(self, status: int, corpo: bytes, tipo: str = "application/json; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        curso = (parse_qs(url.query).get("curso") or [None])[0]
        if url.path == "/saude":
            self.responder(200, b'{"ok": true}')
        elif url.path == "/api/itens":
            self.responder(200, json.dumps(listar(curso), ensure_ascii=False).encode())
        elif url.path == "/":
            self.responder(200, pagina(curso).encode(), "text/html; charset=utf-8")
        else:
            self.responder(404, b'{"erro": "nao encontrado"}')

    def do_POST(self) -> None:
        url = urlsplit(self.path)
        if url.path == "/api/itens":
            versao = self.headers.get("Idempotency-Key")
            if not versao:
                self.responder(400, b'{"erro": "Idempotency-Key obrigatorio"}')
                return
            item = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            status = receber(item, versao)
            self.responder(status, json.dumps({"chave": item["chave"], "status": status}).encode())
        elif url.path.startswith("/api/itens/") and url.path.endswith("/revisar"):
            chave = url.path.split("/")[3]
            with conectar() as conn:
                conn.execute("UPDATE item SET revisado_em = ?, revisado_por = ? WHERE chave = ?",
                             (agora(), "coordenação", chave))
            volta = (parse_qs(url.query).get("volta") or [""])[0]
            self.send_response(303)
            self.send_header("Location", f"/?curso={volta}" if volta else "/")
            self.end_headers()
        else:
            self.responder(404, b'{"erro": "nao encontrado"}')

    def log_message(self, *args: object) -> None:
        pass


if __name__ == "__main__":
    conectar().close()
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8090"))), Handler).serve_forever()
