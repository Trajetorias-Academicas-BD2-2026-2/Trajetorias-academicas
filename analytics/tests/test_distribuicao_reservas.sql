select *
from {{ ref('fct_reservas') }}
where vagas_reservadas <= 0 or vagas_reservadas > 200
