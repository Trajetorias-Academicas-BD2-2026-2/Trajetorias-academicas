-- Dimensão de disciplina, SCD tipo 2 a partir do snapshot snap_disciplina.
-- Uma linha por versão da disciplina. A primeira versão vale desde sempre
-- (o snapshot começou depois da primeira carga); as seguintes, desde o
-- momento em que o dbt viu a mudança.
select
    dbt_scd_id as disciplina_sk,
    disciplina_id,
    disciplina_codigo,
    disciplina_nome,
    carga_horaria,
    tipo,
    unidade_id,
    case
        when row_number() over (partition by disciplina_id order by dbt_valid_from) = 1
            then timestamptz '1900-01-01 00:00+00'
        else dbt_valid_from
    end as valid_from,
    dbt_valid_to as valid_to,
    dbt_valid_to is null as is_current
from {{ ref('snap_disciplina') }}
