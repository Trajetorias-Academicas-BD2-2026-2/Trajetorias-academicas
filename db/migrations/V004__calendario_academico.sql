-- V004__calendario_academico.sql
-- "Semestre encerrado" passa a vir do calendário acadêmico oficial da UnB
-- (data/calendario_academico.csv, com a fonte de cada data), e não de uma
-- aproximação pelo mês. O banco só aceita uma turma se o semestre dela está
-- no calendário e já tinha encerrado quando a turma foi coletada.

CREATE TABLE semestre_letivo (
    ano                 INTEGER NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    periodo             SMALLINT NOT NULL CHECK (periodo IN (1, 2)),
    primeiro_dia_aulas  DATE,
    ultimo_dia_aulas    DATE,
    ultimo_dia_letivo   DATE,
    consolidacao_ate    DATE,          -- prazo de registro/consolidação das turmas no SIGAA
    -- Data a partir da qual o semestre não muda mais: a mais tardia das três.
    encerramento        DATE GENERATED ALWAYS AS
                            (GREATEST(ultimo_dia_aulas, ultimo_dia_letivo, consolidacao_ate)) STORED,
    fonte_url           TEXT NOT NULL,
    observacao          TEXT,
    PRIMARY KEY (ano, periodo),
    CHECK (COALESCE(ultimo_dia_aulas, ultimo_dia_letivo, consolidacao_ate) IS NOT NULL)
);
COMMENT ON TABLE semestre_letivo IS 'Datas do calendário acadêmico de graduação da UnB (SAA), com a fonte de cada linha';
COMMENT ON COLUMN semestre_letivo.encerramento IS
    'Maior data entre último dia de aulas, último dia letivo e prazo de consolidação';

-- NOT VALID: vale para toda turma nova; turmas já existentes são conferidas
-- por tests/sanity_checks.sql (em banco novo, a tabela turma está vazia).
ALTER TABLE turma ADD CONSTRAINT turma_semestre_letivo_fk
    FOREIGN KEY (ano, periodo) REFERENCES semestre_letivo (ano, periodo) NOT VALID;

CREATE FUNCTION exige_semestre_encerrado() RETURNS trigger AS $$
DECLARE
    fim DATE;
BEGIN
    SELECT encerramento INTO fim FROM semestre_letivo WHERE ano = NEW.ano AND periodo = NEW.periodo;
    IF fim IS NULL THEN
        RAISE EXCEPTION 'Semestre %.% sem data de encerramento no calendário acadêmico', NEW.ano, NEW.periodo;
    END IF;
    IF NEW.coletado_em::date <= fim THEN
        RAISE EXCEPTION 'Turma de %.% coletada em % , antes do encerramento do semestre (%)',
            NEW.ano, NEW.periodo, NEW.coletado_em::date, fim;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER turma_exige_semestre_encerrado BEFORE INSERT ON turma
    FOR EACH ROW EXECUTE FUNCTION exige_semestre_encerrado();
