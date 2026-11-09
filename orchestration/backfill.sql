-- Backfill demonstrável: a transformação é determinística e recalcula a
-- tabela de consumo inteira a partir da fonte histórica versionada.
select count(*) as linhas_historicas
from analytics.fct_reservas
where (:'semestre' = '' or semestre = :'semestre');

select count(*) as linhas_totais_apos_backfill
from analytics.fct_reservas;
