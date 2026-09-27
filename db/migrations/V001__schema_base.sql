-- V001__schema_base.sql
-- Domínio: oferta de disciplinas de graduação na UnB (G2 - Projeto Integrado BD2)
-- Fontes: SIGAA "Consulta de Turmas" (oferta por semestre) +
--         SIGAA "Busca de Componentes Curriculares" (disciplina, carga horária, pré-requisitos)
--
-- Decisão de histórico: oferta_turma é INSERT-ONLY, uma linha por (disciplina, turma, ano, período).
-- Isso permite responder "está crescendo ou diminuindo" sem reconstruir histórico depois (ADR-0001).

CREATE TABLE IF NOT EXISTS unidade (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(255) NOT NULL UNIQUE
);
COMMENT ON TABLE unidade IS 'Departamento/Faculdade responsável pela disciplina ou curso (ex.: FCTE, DCC)';

CREATE TABLE IF NOT EXISTS curso (
    id          SERIAL PRIMARY KEY,
    codigo      VARCHAR(20) NOT NULL UNIQUE,   -- código SIGAA do curso, ex: 6584
    nome        VARCHAR(255) NOT NULL,
    unidade_id  INTEGER NOT NULL REFERENCES unidade(id)
);
COMMENT ON TABLE curso IS 'Curso de graduação (ex.: Engenharia de Software)';

CREATE TABLE IF NOT EXISTS disciplina (
    id              SERIAL PRIMARY KEY,
    codigo          VARCHAR(20) NOT NULL UNIQUE,  -- código do componente curricular, ex: FGA0242
    nome            VARCHAR(255) NOT NULL,
    unidade_id      INTEGER NOT NULL REFERENCES unidade(id),
    carga_horaria   INTEGER NOT NULL CHECK (carga_horaria > 0),  -- em horas
    nivel           VARCHAR(30) NOT NULL DEFAULT 'GRADUACAO'
);
COMMENT ON TABLE disciplina IS 'Componente curricular (disciplina), independente de curso ou semestre';
COMMENT ON COLUMN disciplina.codigo IS 'Código único do componente no SIGAA';

-- Relação N:N entre curso e disciplina: a mesma disciplina pode ser
-- obrigatória em um curso e optativa em outro.
CREATE TABLE IF NOT EXISTS curso_disciplina (
    curso_id        INTEGER NOT NULL REFERENCES curso(id),
    disciplina_id   INTEGER NOT NULL REFERENCES disciplina(id),
    obrigatoria     BOOLEAN NOT NULL,
    PRIMARY KEY (curso_id, disciplina_id)
);
COMMENT ON TABLE curso_disciplina IS 'Se uma disciplina é obrigatória ou optativa em um curso específico';

-- Auto-relacionamento: pré-requisitos entre disciplinas.
-- Usado para responder "quais disciplinas travam mais outras depois".
CREATE TABLE IF NOT EXISTS pre_requisito (
    disciplina_id       INTEGER NOT NULL REFERENCES disciplina(id),
    pre_requisito_id    INTEGER NOT NULL REFERENCES disciplina(id),
    PRIMARY KEY (disciplina_id, pre_requisito_id),
    CHECK (disciplina_id <> pre_requisito_id)
);
COMMENT ON TABLE pre_requisito IS 'disciplina_id exige pre_requisito_id como pré-requisito';

CREATE TABLE IF NOT EXISTS docente (
    id      SERIAL PRIMARY KEY,
    nome    VARCHAR(255) NOT NULL UNIQUE
);

-- Evento: uma oferta concreta de turma em um semestre específico.
-- INSERT-ONLY (nunca UPDATE de vagas depois de carregado): cada carga de
-- semestre gera novas linhas, preservando o histórico de oferta e ocupação.
CREATE TABLE IF NOT EXISTS oferta_turma (
    id                  BIGSERIAL PRIMARY KEY,
    disciplina_id       INTEGER NOT NULL REFERENCES disciplina(id),
    codigo_turma        VARCHAR(10) NOT NULL,      -- ex: "A", "01"
    ano                 INTEGER NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    periodo             SMALLINT NOT NULL CHECK (periodo IN (1, 2)),
    turno               VARCHAR(20) NOT NULL CHECK (turno IN ('DIURNO', 'NOTURNO', 'INTEGRAL')),
    docente_id          INTEGER REFERENCES docente(id),
    vagas_ofertadas     INTEGER NOT NULL CHECK (vagas_ofertadas >= 0),
    vagas_ocupadas      INTEGER NOT NULL CHECK (vagas_ocupadas >= 0 AND vagas_ocupadas <= vagas_ofertadas + 5),
    -- +5 de folga: SIGAA às vezes matricula um pouco acima da vaga ofertada (reserva/decisão judicial)
    horario             VARCHAR(50),               -- ex: "246M12" (notação SIGAA)
    local               VARCHAR(255),
    fonte               VARCHAR(50) NOT NULL,       -- ex: 'sigaa_turmas'
    carga_id            VARCHAR(50) NOT NULL,       -- identifica a execução do loader que inseriu a linha
    ingerido_em         TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (disciplina_id, codigo_turma, ano, periodo)
);
COMMENT ON TABLE oferta_turma IS 'Uma oferta de turma em um semestre — linha de evento, nunca sobrescrita';
COMMENT ON COLUMN oferta_turma.fonte IS 'De qual fonte/scraper esta linha veio (linhagem)';
COMMENT ON COLUMN oferta_turma.carga_id IS 'Identificador da execução do loader (idempotência e auditoria)';

CREATE INDEX IF NOT EXISTS idx_oferta_turma_ano_periodo ON oferta_turma(ano, periodo);
CREATE INDEX IF NOT EXISTS idx_oferta_turma_disciplina ON oferta_turma(disciplina_id);
CREATE INDEX IF NOT EXISTS idx_oferta_turma_turno ON oferta_turma(turno);
