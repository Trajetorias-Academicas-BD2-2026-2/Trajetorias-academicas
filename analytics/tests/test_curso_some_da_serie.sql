-- Distribuição: todo curso precisa ter reserva em obrigatória em todos os
-- semestres da série. Um curso que some entre dois semestres é carga
-- incompleta, não um zero.
with semestres as (select distinct semestre_key from {{ ref('fct_reservas') }}),
cursos as (select distinct curso_codigo from {{ ref('fct_reservas') }})
select c.curso_codigo, s.semestre_key
from cursos c cross join semestres s
left join {{ ref('mart_observatorio') }} m
  on m.curso_codigo = c.curso_codigo and m.semestre_key = s.semestre_key
where m.curso_codigo is null
