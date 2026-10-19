-- Infraestrutura mínima da E2: outbox transacional para CDC equivalente ao WAL.

CREATE TABLE IF NOT EXISTS e2_oltp_reserva_demo (
    reserva_id       TEXT PRIMARY KEY,
    curso_codigo     TEXT NOT NULL,
    disciplina_codigo TEXT NOT NULL,
    vagas            INTEGER NOT NULL CHECK (vagas >= 0),
    atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS e2_cdc_outbox (
    id             BIGSERIAL PRIMARY KEY,
    aggregate_key  TEXT NOT NULL,
    operation      TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    payload        JSONB NOT NULL,
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_e2_cdc_outbox_id ON e2_cdc_outbox(id);

CREATE TABLE IF NOT EXISTS e2_cdc_checkpoint (
    consumer       TEXT PRIMARY KEY,
    last_event_id  BIGINT NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION e2_capture_reserva_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO e2_cdc_outbox (aggregate_key, operation, payload)
    VALUES (
        COALESCE(NEW.reserva_id, OLD.reserva_id),
        TG_OP,
        CASE WHEN TG_OP = 'DELETE'
             THEN jsonb_build_object()
             ELSE jsonb_build_object(
                 'reserva_id', NEW.reserva_id,
                 'curso_codigo', NEW.curso_codigo,
                 'disciplina_codigo', NEW.disciplina_codigo,
                 'vagas', NEW.vagas,
                 'atualizado_em', NEW.atualizado_em
             )
        END
    );
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS e2_reserva_cdc ON e2_oltp_reserva_demo;
CREATE TRIGGER e2_reserva_cdc
AFTER INSERT OR UPDATE OR DELETE ON e2_oltp_reserva_demo
FOR EACH ROW EXECUTE FUNCTION e2_capture_reserva_change();
