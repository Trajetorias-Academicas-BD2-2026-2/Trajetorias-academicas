{{ config(materialized='view') }}
-- Métrica de freshness da tabela de consumo mart_observatorio.
-- SLA: o mart reflete uma carga nova da origem em até 24 horas.
--   atraso_horas = quanto a última carga da origem está à frente do mart
--   (0 = em dia). Testado por test_sla_freshness_mart.
with origem as (
    select max(ingerido_em) as ultima_carga_origem from {{ source('oltp', 'reserva_vaga') }}
),
mart as (
    select max(freshness_at) as ultima_carga_no_mart, max(processado_em) as mart_processado_em
    from {{ ref('mart_observatorio') }}
)
select
    'mart_observatorio' as tabela,
    o.ultima_carga_origem,
    m.ultima_carga_no_mart,
    m.mart_processado_em,
    round(greatest(extract(epoch from (o.ultima_carga_origem - m.ultima_carga_no_mart)), 0) / 3600.0, 2) as atraso_horas,
    24 as sla_horas,
    round(extract(epoch from (now() - m.mart_processado_em)) / 3600.0, 2) as idade_mart_horas
from origem o cross join mart m
