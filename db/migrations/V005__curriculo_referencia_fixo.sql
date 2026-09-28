-- V005__curriculo_referencia_fixo.sql
-- A pergunta de gestão usa o currículo de referência SELECIONADO PARA 2026.1
-- (ADR-0003). Na V003 a view escolhia a versão em vigor no último semestre
-- presente em `turma`: ao carregar 2026.2 ou 2027.1 ela mudaria sozinha (em
-- Automotiva, 6297/2 viraria 6297/3) e a mesma q0 passaria a responder outra
-- pergunta. Aqui o semestre de referência é explícito e não depende dos dados.
--
-- Mudar o semestre de referência é mudar a pergunta: exige nova migração e
-- atualização do ADR-0003, nunca uma alteração silenciosa.

CREATE OR REPLACE VIEW curriculo_referencia AS
SELECT DISTINCT ON (c.curso_id) c.*
FROM curriculo c
WHERE (c.inicio_vigencia_ano, c.inicio_vigencia_periodo) <= (2026, 1)
ORDER BY c.curso_id, c.inicio_vigencia_ano DESC, c.inicio_vigencia_periodo DESC;

COMMENT ON VIEW curriculo_referencia IS
    'Currículo de referência da pergunta de gestão: versão de cada curso em vigor em 2026.1 (fixo; ver ADR-0003)';
