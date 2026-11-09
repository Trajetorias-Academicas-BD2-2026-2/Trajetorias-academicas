select turma_id, curso_id, count(*) as n
from {{ ref('fct_reservas') }}
group by turma_id, curso_id
having count(*) > 1
