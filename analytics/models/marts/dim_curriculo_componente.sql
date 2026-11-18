-- SCD tipo 2 em tempo de negócio: a natureza (obrigatória/optativa) de uma
-- disciplina num curso, por versão curricular. A versão vale do semestre de
-- início de vigência até o início da versão seguinte do mesmo curso
-- (valid_to_key exclusivo; nulo = sem versão posterior coletada).
-- Antes da primeira versão coletada não há linha: a natureza da época é desconhecida.
with versoes as (
    select distinct curso_id, curriculo_id, vigencia_inicio_key
    from {{ ref('stg_curriculo_componente') }}
),
janelas as (
    select
        curriculo_id,
        lead(vigencia_inicio_key) over (partition by curso_id order by vigencia_inicio_key) as valid_to_key
    from versoes
)
select
    md5(s.curriculo_id::text || ':' || s.disciplina_id::text) as curriculo_componente_sk,
    s.curso_id,
    s.disciplina_id,
    s.curriculo_codigo,
    s.natureza,
    s.grupo,
    s.vigencia_inicio_key as valid_from_key,
    j.valid_to_key,
    s.e_referencia_2026_1
from {{ ref('stg_curriculo_componente') }} s
join janelas j on j.curriculo_id = s.curriculo_id
