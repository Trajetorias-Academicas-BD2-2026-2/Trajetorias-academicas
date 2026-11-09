-- Camada de consumo da E3/E4. As tabelas analíticas são recriadas pelo dbt
-- após a carga do OLTP; esta migração cria apenas o contrato, acesso e ETL
-- reverso para que o pipeline seja reproduzível.

CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS operations;

CREATE TABLE IF NOT EXISTS operations.alertas_reserva (
    curso_codigo VARCHAR(20) NOT NULL,
    semestre VARCHAR(7) NOT NULL,
    disciplina_codigo VARCHAR(20) NOT NULL,
    vagas_reservadas INTEGER NOT NULL CHECK (vagas_reservadas >= 0),
    obrigatoria BOOLEAN NOT NULL,
    gerado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (curso_codigo, semestre, disciplina_codigo)
);

COMMENT ON TABLE operations.alertas_reserva IS
    'ETL reverso: filas de decisão para a coordenação acompanhar reservas de obrigatórias';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dashboard_reader') THEN
        CREATE ROLE dashboard_reader NOLOGIN;
    END IF;
END
$$;

GRANT USAGE ON SCHEMA analytics TO dashboard_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA analytics TO dashboard_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytics
    GRANT SELECT ON TABLES TO dashboard_reader;
GRANT USAGE ON SCHEMA operations TO dashboard_reader;
GRANT SELECT ON operations.alertas_reserva TO dashboard_reader;
