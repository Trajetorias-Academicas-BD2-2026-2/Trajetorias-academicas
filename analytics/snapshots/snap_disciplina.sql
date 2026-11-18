{#
  SCD tipo 2 em tempo de processamento: cada execução do dbt compara nome,
  carga horária e tipo da disciplina com a última versão guardada; se
  mudou, fecha a versão anterior (dbt_valid_to) e abre outra. É o que
  preserva o histórico de uma correção de catálogo no SIGAA, que no OLTP
  chega como UPDATE (upsert) e sobrescreve o valor anterior.
#}
{% snapshot snap_disciplina %}
{{ config(
    target_schema='analytics',
    unique_key='disciplina_id',
    strategy='check',
    check_cols=['disciplina_nome', 'carga_horaria', 'tipo', 'unidade_id'],
    invalidate_hard_deletes=True
) }}
select
    id as disciplina_id,
    codigo as disciplina_codigo,
    nome as disciplina_nome,
    carga_horaria,
    tipo,
    unidade_id
from {{ source('oltp', 'disciplina') }}
{% endsnapshot %}
