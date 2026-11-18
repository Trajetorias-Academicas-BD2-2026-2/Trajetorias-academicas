-- Freshness: o mart não pode estar mais de 24 h atrás da última carga da origem (SLA).
select * from {{ ref('metricas_freshness') }}
where atraso_horas > sla_horas
