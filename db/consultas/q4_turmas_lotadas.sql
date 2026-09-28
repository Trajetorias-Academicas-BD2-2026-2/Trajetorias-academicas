-- Turmas lotadas por semestre.
SELECT ano, periodo,
       count(*) AS turmas,
       count(*) FILTER (WHERE vagas_ofertadas > 0 AND vagas_ocupadas >= vagas_ofertadas) AS lotadas
FROM oferta_turma
GROUP BY ano, periodo
ORDER BY ano, periodo;
