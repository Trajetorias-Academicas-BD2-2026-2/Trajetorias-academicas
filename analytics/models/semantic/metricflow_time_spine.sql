-- Calendário diário exigido pelo MetricFlow (camada semântica da E4).
{{ config(materialized='table') }}
select d::date as date_day
from generate_series(date '2020-01-01', date '2027-12-31', interval '1 day') as d
