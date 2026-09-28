-- V003__reservas_por_curso.sql
-- Troca o modelo de "oferta com vagas ocupadas" pelo que a fonte pública de
-- fato fornece: turmas e as vagas que cada uma RESERVA para cada curso,
-- mais a estrutura curricular com versão (ADR-0003, que substitui o ADR-0001).
--
-- Por que remover tabelas: a coleta real de 28/09/2026 mostrou que a consulta
-- geral de turmas não devolve o histórico da FCTE e que a página do curso só
-- informa vagas reservadas, sem ocupação (docs/COLETA_SIGAA_2026-09-28.md).
-- Nenhum dado real chegou a ser carregado em oferta_turma, curso_disciplina
-- ou pre_requisito.

DROP TABLE oferta_turma;            -- leva junto os triggers insert-only da V002
DROP FUNCTION oferta_turma_insert_only();
DROP TABLE curso_disciplina;         -- substituída por curriculo_componente (com versão)
DROP TABLE pre_requisito;            -- coleta parcial (23 de 585 componentes); fica só a expressão

-- ---------- disciplina ----------
-- Disciplinas de outras unidades (MAT, IFD...) aparecem nas reservas e nos
-- currículos, mas não no catálogo da FCTE: ficam sem unidade (NULL = fora do
-- catálogo coletado), nunca com uma unidade inventada.
ALTER TABLE disciplina ALTER COLUMN unidade_id DROP NOT NULL;
ALTER TABLE disciplina ALTER COLUMN carga_horaria DROP NOT NULL;
ALTER TABLE disciplina ADD COLUMN tipo VARCHAR(20) CHECK (tipo IN ('DISCIPLINA', 'ATIVIDADE'));
ALTER TABLE disciplina ADD COLUMN co_requisito_expressao TEXT;
ALTER TABLE disciplina ADD COLUMN pre_requisito_coletado BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE disciplina ADD COLUMN pre_requisito_coletado_em TIMESTAMPTZ;
ALTER TABLE disciplina DROP COLUMN nivel;
ALTER TABLE disciplina ADD CONSTRAINT disciplina_prereq_so_se_coletado
    CHECK (pre_requisito_coletado OR (pre_requisito_expressao IS NULL AND co_requisito_expressao IS NULL));
COMMENT ON COLUMN disciplina.unidade_id IS 'NULL = componente de outra unidade, fora do catálogo da FCTE coletado';
COMMENT ON COLUMN disciplina.pre_requisito_expressao IS
    'Expressão como o SIGAA mostra ("-" = sem pré-requisito). Só vale se pre_requisito_coletado';
COMMENT ON COLUMN disciplina.pre_requisito_coletado IS
    'FALSE = detalhe do componente não coletado; não significa ausência de pré-requisito';
COMMENT ON COLUMN disciplina.pre_requisito_coletado_em IS
    'Quando o detalhe foi coletado; pode faltar mesmo com pre_requisito_coletado (a fonte não registrou)';

-- ---------- curso ----------
ALTER TABLE curso ADD COLUMN turno VARCHAR(20) CHECK (turno IN ('DIURNO', 'NOTURNO', 'INTEGRAL'));
ALTER TABLE curso ADD COLUMN url_fonte TEXT;

-- ---------- currículo com versão ----------
CREATE TABLE curriculo (
    id                      SERIAL PRIMARY KEY,
    curso_id                INTEGER NOT NULL REFERENCES curso(id),
    codigo                  VARCHAR(20) NOT NULL UNIQUE,     -- ex.: 6360/2
    inicio_vigencia_ano     INTEGER NOT NULL CHECK (inicio_vigencia_ano BETWEEN 2000 AND 2100),
    inicio_vigencia_periodo SMALLINT NOT NULL CHECK (inicio_vigencia_periodo IN (1, 2)),
    fonte                   VARCHAR(50) NOT NULL,
    lote                    VARCHAR(60) NOT NULL,
    coletado_em             TIMESTAMPTZ NOT NULL
);
COMMENT ON TABLE curriculo IS 'Versão da estrutura curricular de um curso, com início de vigência';

CREATE TABLE curriculo_componente (
    curriculo_id    INTEGER NOT NULL REFERENCES curriculo(id),
    disciplina_id   INTEGER NOT NULL REFERENCES disciplina(id),
    natureza        VARCHAR(12) NOT NULL CHECK (natureza IN ('OBRIGATORIA', 'OPTATIVA')),
    grupo           VARCHAR(30) NOT NULL,                    -- ex.: "3º Nível", "Optativas"
    PRIMARY KEY (curriculo_id, disciplina_id)
);
CREATE INDEX idx_curriculo_componente_disciplina ON curriculo_componente(disciplina_id);

-- ---------- turma e reserva (eventos, insert-only) ----------
CREATE TABLE turma (
    id              BIGSERIAL PRIMARY KEY,
    disciplina_id   INTEGER NOT NULL REFERENCES disciplina(id),
    codigo_turma    VARCHAR(10) NOT NULL,
    ano             INTEGER NOT NULL CHECK (ano BETWEEN 2000 AND 2100),
    periodo         SMALLINT NOT NULL CHECK (periodo IN (1, 2)),
    horario         VARCHAR(100),
    turno           VARCHAR(20) NOT NULL CHECK (turno IN ('DIURNO', 'NOTURNO', 'INTEGRAL', 'SEM_HORARIO')),
    fonte           VARCHAR(50) NOT NULL,
    lote            VARCHAR(60) NOT NULL,
    coletado_em     TIMESTAMPTZ NOT NULL,
    ingerido_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (disciplina_id, codigo_turma, ano, periodo)
);
COMMENT ON TABLE turma IS 'Turma de um semestre encerrado; evento, nunca alterado';
CREATE INDEX idx_turma_ano_periodo ON turma(ano, periodo);

CREATE TABLE turma_docente (
    turma_id    BIGINT NOT NULL REFERENCES turma(id),
    docente_id  INTEGER NOT NULL REFERENCES docente(id),
    PRIMARY KEY (turma_id, docente_id)
);

CREATE TABLE reserva_vaga (
    turma_id            BIGINT NOT NULL REFERENCES turma(id),
    curso_id            INTEGER NOT NULL REFERENCES curso(id),
    vagas_reservadas    INTEGER NOT NULL CHECK (vagas_reservadas > 0),
    fonte               VARCHAR(50) NOT NULL,
    lote                VARCHAR(60) NOT NULL,
    coletado_em         TIMESTAMPTZ NOT NULL,
    ingerido_em         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (turma_id, curso_id)
);
COMMENT ON TABLE reserva_vaga IS
    'Vagas que uma turma reserva para um curso ("Vgs Reservadas" no SIGAA). NÃO é oferta total nem ocupação';
CREATE INDEX idx_reserva_vaga_curso ON reserva_vaga(curso_id);

-- Currículo de referência de cada curso: a versão em vigor no último
-- semestre carregado (determinístico: não muda com a data em que se consulta).
CREATE VIEW curriculo_referencia AS
WITH ultimo AS (
    SELECT ano, periodo FROM turma ORDER BY ano DESC, periodo DESC LIMIT 1
)
SELECT DISTINCT ON (c.curso_id) c.*
FROM curriculo c, ultimo u
WHERE (c.inicio_vigencia_ano, c.inicio_vigencia_periodo) <= (u.ano, u.periodo)
ORDER BY c.curso_id, c.inicio_vigencia_ano DESC, c.inicio_vigencia_periodo DESC;

-- ---------- insert-only garantido pelo banco ----------
CREATE FUNCTION bloqueia_alteracao() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '% é insert-only: % não é permitido (ver docs/historico.md)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER turma_insert_only BEFORE UPDATE OR DELETE ON turma
    FOR EACH ROW EXECUTE FUNCTION bloqueia_alteracao();
CREATE TRIGGER turma_sem_truncate BEFORE TRUNCATE ON turma
    FOR EACH STATEMENT EXECUTE FUNCTION bloqueia_alteracao();
CREATE TRIGGER turma_docente_insert_only BEFORE UPDATE OR DELETE ON turma_docente
    FOR EACH ROW EXECUTE FUNCTION bloqueia_alteracao();
CREATE TRIGGER turma_docente_sem_truncate BEFORE TRUNCATE ON turma_docente
    FOR EACH STATEMENT EXECUTE FUNCTION bloqueia_alteracao();
CREATE TRIGGER reserva_vaga_insert_only BEFORE UPDATE OR DELETE ON reserva_vaga
    FOR EACH ROW EXECUTE FUNCTION bloqueia_alteracao();
CREATE TRIGGER reserva_vaga_sem_truncate BEFORE TRUNCATE ON reserva_vaga
    FOR EACH STATEMENT EXECUTE FUNCTION bloqueia_alteracao();
