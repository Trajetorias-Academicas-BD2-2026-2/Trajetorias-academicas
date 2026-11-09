select
    turma_id,
    curso_id,
    disciplina_id,
    ano,
    periodo,
    semestre,
    curso_codigo,
    curso_nome,
    disciplina_codigo,
    disciplina_nome,
    obrigatoria,
    vagas_reservadas,
    ingerido_em
from {{ ref('stg_reservas') }}
