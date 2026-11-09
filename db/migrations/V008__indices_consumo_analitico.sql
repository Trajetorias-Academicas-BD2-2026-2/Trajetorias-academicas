-- Índices usados pela consulta de consumo e pelo filtro do observatório.
CREATE INDEX IF NOT EXISTS idx_reserva_vaga_turma_curso
    ON reserva_vaga (turma_id, curso_id);
CREATE INDEX IF NOT EXISTS idx_curriculo_componente_obrigatoria
    ON curriculo_componente (curriculo_id, disciplina_id)
    WHERE natureza = 'OBRIGATORIA';
