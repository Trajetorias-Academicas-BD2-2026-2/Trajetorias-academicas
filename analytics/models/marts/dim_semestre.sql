select distinct
    ano,
    periodo,
    concat(ano, '.', periodo) as semestre
from {{ source('oltp', 'turma') }}
