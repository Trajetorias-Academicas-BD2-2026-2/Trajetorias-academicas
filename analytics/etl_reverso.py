from __future__ import annotations

import os

import psycopg


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
            insert into operations.alertas_reserva
                (curso_codigo, semestre, disciplina_codigo,
                 vagas_reservadas, obrigatoria)
            select curso_codigo, semestre, disciplina_codigo,
                   sum(vagas_reservadas), bool_or(obrigatoria)
            from analytics.fct_reservas
            where obrigatoria and vagas_reservadas >= 50
            group by curso_codigo, semestre, disciplina_codigo
            on conflict (curso_codigo, semestre, disciplina_codigo) do update
            set vagas_reservadas = excluded.vagas_reservadas,
                obrigatoria = excluded.obrigatoria,
                gerado_em = now()
            """
        )
