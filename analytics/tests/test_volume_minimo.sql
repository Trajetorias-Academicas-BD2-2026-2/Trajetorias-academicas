select count(*) as n
from {{ ref('fct_reservas') }}
having count(*) < 1500
