{{ config(severity='warn') }}
-- Distribuição: salto de série. Avisa quando as vagas reservadas de um curso
-- nas obrigatórias mais que dobram ou caem pela metade de um semestre para o
-- seguinte. É warn, não erro: a partir de 2023.2 há saltos conhecidos
-- (reservas de 50+ vagas em Software, ver README "Limites dos dados"); o
-- aviso obriga a olhar o semestre, não bloqueia a carga.
with serie as (
    select curso_codigo, semestre, vagas_reservadas,
           lag(vagas_reservadas) over (partition by curso_codigo order by semestre_key) as anterior
    from {{ ref('mart_observatorio') }}
)
select curso_codigo, semestre, anterior, vagas_reservadas,
       round(vagas_reservadas::numeric / anterior, 2) as razao
from serie
where anterior is not null
  and (vagas_reservadas > 2 * anterior or vagas_reservadas < 0.5 * anterior)
