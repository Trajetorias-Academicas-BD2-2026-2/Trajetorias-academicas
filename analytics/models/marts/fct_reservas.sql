{#
  Fato de reservas. Granularidade: uma linha por turma e curso (uma turma
  já pertence a uma disciplina e a um semestre), isto é, as vagas que uma
  turma de um semestre reservou para um curso.

  Incremental por janela de semestre (delete+insert):
    - sem variável: reprocessa só os semestres que têm linha ingerida depois
      da última execução (carga nova ou dado atrasado de semestre antigo);
    - --vars '{backfill_semestre: "2024.1"}': reprocessa só essa janela;
    - --full-refresh: reconstrói tudo.
#}
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='semestre_key',
    on_schema_change='sync_all_columns'
) }}

with origem as (
    select * from {{ ref('stg_reservas') }}
    {% if var('backfill_semestre', none) %}
    where semestre = '{{ var("backfill_semestre") }}'
    {% elif is_incremental() %}
    where semestre_key in (
        select distinct semestre_key from {{ ref('stg_reservas') }}
        where ingerido_em > (select coalesce(max(ingerido_em), '-infinity') from {{ this }})
    )
    {% endif %}
)
select
    o.turma_id,
    o.curso_id,
    o.disciplina_id,
    d.disciplina_sk,
    o.semestre_key,
    o.ano,
    o.periodo,
    o.semestre,
    o.curso_codigo,
    o.curso_nome,
    o.disciplina_codigo,
    o.disciplina_nome,
    o.unidade_origem,
    o.de_outra_unidade,
    o.obrigatoria,
    cc.natureza as natureza_na_epoca,
    o.vagas_reservadas,
    o.ingerido_em,
    now() as processado_em
from origem o
left join {{ ref('dim_disciplina') }} d
  on d.disciplina_id = o.disciplina_id
 and o.ingerido_em >= d.valid_from
 and (d.valid_to is null or o.ingerido_em < d.valid_to)
left join {{ ref('dim_curriculo_componente') }} cc
  on cc.curso_id = o.curso_id
 and cc.disciplina_id = o.disciplina_id
 and o.semestre_key >= cc.valid_from_key
 and (cc.valid_to_key is null or o.semestre_key < cc.valid_to_key)
