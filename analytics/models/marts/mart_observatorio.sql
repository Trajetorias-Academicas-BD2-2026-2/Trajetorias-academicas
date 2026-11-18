-- Resposta à pergunta de gestão: uma linha por curso e semestre, só as
-- obrigatórias do currículo de referência de 2026.1.
select
    curso_codigo,
    curso_nome,
    semestre_key,
    semestre,
    sum(vagas_reservadas) as vagas_reservadas,
    count(distinct disciplina_codigo) as obrigatorias_com_reserva,
    count(distinct turma_id) as turmas_com_reserva,
    max(ingerido_em) as freshness_at,
    max(processado_em) as processado_em
from {{ ref('fct_reservas') }}
where obrigatoria
group by curso_codigo, curso_nome, semestre_key, semestre
