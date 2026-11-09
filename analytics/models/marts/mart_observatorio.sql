select
    curso_codigo,
    curso_nome,
    semestre,
    sum(vagas_reservadas) as vagas_reservadas,
    count(distinct disciplina_codigo) filter (where obrigatoria) as obrigatorias_com_reserva,
    count(distinct disciplina_codigo) as disciplinas_com_reserva,
    count(distinct turma_id) as turmas_com_reserva,
    max(ingerido_em) as freshness_at
from {{ ref('fct_reservas') }}
where obrigatoria
group by curso_codigo, curso_nome, semestre
