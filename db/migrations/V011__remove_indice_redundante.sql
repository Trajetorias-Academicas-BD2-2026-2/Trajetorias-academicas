-- A V008 criou idx_reserva_vaga_turma_curso (turma_id, curso_id), idêntico à
-- chave primária reserva_vaga_pkey. Um índice duplicado só custa escrita e
-- espaço; o plano da E3 mostrou o planner usando um ou outro indistintamente.
DROP INDEX IF EXISTS idx_reserva_vaga_turma_curso;
