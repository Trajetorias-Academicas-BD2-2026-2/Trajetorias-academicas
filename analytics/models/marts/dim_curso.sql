select
    id as curso_id,
    codigo as curso_codigo,
    nome as curso_nome,
    turno
from {{ source('oltp', 'curso') }}
