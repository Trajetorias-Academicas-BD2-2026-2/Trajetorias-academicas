-- Uma linha por semestre letivo do calendário oficial da UnB.
select
    ano * 10 + periodo as semestre_key,
    ano,
    periodo,
    concat(ano, '.', periodo) as semestre,
    encerramento
from {{ source('oltp', 'semestre_letivo') }}
