-- Componentes de cada versão curricular, com o semestre em que a versão começa a valer.
select
    c.curso_id,
    cc.disciplina_id,
    c.id as curriculo_id,
    c.codigo as curriculo_codigo,
    cc.natureza,
    cc.grupo,
    c.inicio_vigencia_ano * 10 + c.inicio_vigencia_periodo as vigencia_inicio_key,
    c.id = cr.id as e_referencia_2026_1
from {{ source('oltp', 'curriculo') }} c
join {{ source('oltp', 'curriculo_componente') }} cc on cc.curriculo_id = c.id
left join {{ source('oltp', 'curriculo_referencia') }} cr on cr.curso_id = c.curso_id
