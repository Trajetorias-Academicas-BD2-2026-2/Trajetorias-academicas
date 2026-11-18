{% test unique_combination(model, columns) %}
-- Unicidade da granularidade declarada (combinação de colunas).
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}
