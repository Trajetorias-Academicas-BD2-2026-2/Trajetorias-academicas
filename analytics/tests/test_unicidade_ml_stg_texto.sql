-- Cada item (entidade, chave) aparece uma única vez no staging da camada vetorial.
select entidade, chave_origem, count(*) as ocorrencias
from {{ ref('ml_stg_texto') }}
group by entidade, chave_origem
having count(*) > 1
