-- V013 (E4): fila de envio do ETL reverso para a Pauta da coordenação.
--
-- operations.alertas_reserva (E3) era uma tabela que nenhuma aplicação lia.
-- Ela sai; no lugar entra uma fila de envio (outbox) para um sistema real:
-- cada item da pauta é gravado aqui e só fica "enviado" depois que a Pauta
-- confirmar. Se a Pauta estiver fora do ar, o item fica "pendente" e a
-- próxima execução reenvia. A chave do item + a versão do conteúdo vão no
-- header Idempotency-Key: reenviar não duplica.

DROP TABLE IF EXISTS operations.alertas_reserva;

CREATE TABLE IF NOT EXISTS operations.envio_pauta (
    chave          TEXT PRIMARY KEY,
    versao         TEXT NOT NULL,
    curso_codigo   VARCHAR(20) NOT NULL,
    tipo           TEXT NOT NULL CHECK (tipo IN ('reserva_grande', 'obrigatoria_sem_reserva', 'queda_forte')),
    payload        JSONB NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pendente' CHECK (status IN ('pendente', 'enviado', 'retirado')),
    tentativas     INTEGER NOT NULL DEFAULT 0,
    ultimo_erro    TEXT,
    criado_em      TIMESTAMPTZ NOT NULL DEFAULT now(),
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    enviado_em     TIMESTAMPTZ
);
COMMENT ON TABLE operations.envio_pauta IS
    'ETL reverso (E4): itens para a Pauta da coordenação, com estado de entrega';

GRANT SELECT, INSERT, UPDATE ON operations.envio_pauta TO etl_reverso;
GRANT SELECT ON operations.envio_pauta TO dashboard_reader;
