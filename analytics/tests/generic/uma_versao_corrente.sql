{% test uma_versao_corrente(model) %}
-- SCD tipo 2: cada disciplina tem exatamente uma versão corrente.
select disciplina_id, count(*) filter (where is_current) as correntes
from {{ model }}
group by disciplina_id
having count(*) filter (where is_current) <> 1
{% endtest %}
