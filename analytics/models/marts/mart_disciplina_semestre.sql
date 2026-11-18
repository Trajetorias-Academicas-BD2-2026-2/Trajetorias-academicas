-- Uma linha por curso, disciplina e semestre: vagas reservadas e turmas.
-- Alimenta a matriz disciplina × semestre e as maiores variações do painel.
select
    curso_codigo,
    curso_nome,
    disciplina_codigo,
    max(disciplina_nome) as disciplina_nome,
    unidade_origem,
    de_outra_unidade,
    obrigatoria,
    semestre_key,
    semestre,
    sum(vagas_reservadas) as vagas_reservadas,
    count(distinct turma_id) as turmas
from {{ ref('fct_reservas') }}
group by curso_codigo, curso_nome, disciplina_codigo, unidade_origem, de_outra_unidade,
         obrigatoria, semestre_key, semestre
