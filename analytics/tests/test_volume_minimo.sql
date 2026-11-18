-- Volume: o fato não pode encolher abaixo do lote conhecido, e nenhum
-- semestre pode ter menos da metade da mediana de reservas por semestre
-- (pega carga parcial de um semestre, que um limite global não pega).
with por_semestre as (
    select semestre, count(*) as n from {{ ref('fct_reservas') }} group by semestre
),
mediana as (
    select percentile_cont(0.5) within group (order by n) as m from por_semestre
)
select 'fato abaixo de 1500 linhas' as problema, null as semestre, count(*) as n
from {{ ref('fct_reservas') }}
having count(*) < 1500
union all
select 'semestre abaixo de 50% da mediana', p.semestre, p.n
from por_semestre p cross join mediana
where p.n < 0.5 * mediana.m
