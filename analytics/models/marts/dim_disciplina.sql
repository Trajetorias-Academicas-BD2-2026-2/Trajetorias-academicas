select
    id as disciplina_id,
    codigo as disciplina_codigo,
    nome as disciplina_nome,
    unidade_id,
    tipo
from {{ source('oltp', 'disciplina') }}
