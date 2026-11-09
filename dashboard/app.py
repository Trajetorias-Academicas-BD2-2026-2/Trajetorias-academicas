from __future__ import annotations

import html
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

import psycopg


def rows() -> list[tuple]:
    with psycopg.connect(
        host=os.getenv("PGHOST", "db"),
        port=os.getenv("PGPORT", "5432"),
        dbname=os.getenv("PGDATABASE", "ofertas_unb"),
        user=os.getenv("PGUSER", "g2"),
        password=os.getenv("PGPASSWORD", "g2_dev_only"),
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select curso_codigo, semestre, vagas_reservadas,
                       obrigatorias_com_reserva, turmas_com_reserva
                from analytics.mart_observatorio
                order by curso_codigo, semestre
                """
            )
            return cur.fetchall()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        data = rows()
        courses = sorted({r[0] for r in data})
        semesters = sorted({r[1] for r in data})
        course_html = "".join(
            f'<option value="{html.escape(c)}">{html.escape(c)}</option>' for c in courses
        )
        semester_html = "".join(
            f'<option value="{html.escape(s)}">{html.escape(s)}</option>' for s in semesters
        )
        table = "".join(
            "<tr>" + "".join(f"<td>{html.escape(str(value))}</td>" for value in row) + "</tr>"
            for row in data
        )
        body = f"""<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><title>Observatório de Reservas UnB</title>
<style>body{{font:16px system-ui;max-width:1100px;margin:2rem auto;color:#18324b}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ccd6df;padding:.55rem;text-align:left}}
header{{background:#0b5d7a;color:white;padding:1.2rem;border-radius:.5rem}}
select{{padding:.5rem;margin:1rem 0}}</style>
<header><h1>Observatório de Reservas UnB</h1>
<p>Como evoluíram as vagas reservadas nas obrigatórias do currículo de referência de 2026.1?</p></header>
<label>Curso <select id="curso"><option value="">Todos</option>{course_html}</select></label>
<label>Semestre <select id="semestre"><option value="">Todos</option>{semester_html}</select></label>
<table id="dados"><thead><tr><th>Curso</th><th>Semestre</th><th>Vagas reservadas</th>
<th>Obrigatórias com reserva</th><th>Turmas</th></tr></thead><tbody>{table}</tbody></table>
<script>
function filterRows() {{
  const curso = document.querySelector('#curso').value;
  const semestre = document.querySelector('#semestre').value;
  document.querySelectorAll('#dados tbody tr').forEach(row => {{
    row.hidden = (curso && row.cells[0].textContent !== curso)
      || (semestre && row.cells[1].textContent !== semestre);
  }});
}}
document.querySelector('#curso').onchange = filterRows;
document.querySelector('#semestre').onchange = filterRows;
</script>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode())


HTTPServer(("0.0.0.0", int(os.getenv("PORT", "8080"))), Handler).serve_forever()
