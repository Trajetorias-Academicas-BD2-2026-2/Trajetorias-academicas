-- Uma linha por curso e obrigatória do currículo de referência de 2026.1,
-- inclusive as que nunca tiveram reserva no recorte (regra da q2).
with obrigatorias as (
    select cc.curso_id, cc.disciplina_id, cc.curriculo_codigo, cc.grupo
    from {{ ref('dim_curriculo_componente') }} cc
    where cc.e_referencia_2026_1 and cc.natureza = 'OBRIGATORIA'
),
reservas as (
    select curso_codigo, disciplina_codigo,
           count(*) as semestres_com_reserva,
           sum(vagas_reservadas) as vagas_no_recorte,
           min(semestre) as primeiro_semestre,
           max(semestre) as ultimo_semestre
    from {{ ref('mart_disciplina_semestre') }}
    group by curso_codigo, disciplina_codigo
)
select
    c.curso_codigo,
    c.curso_nome,
    o.curriculo_codigo,
    d.disciplina_codigo,
    d.disciplina_nome,
    substring(d.disciplina_codigo from '^[A-Z]+') as unidade_origem,
    o.grupo,
    coalesce(r.semestres_com_reserva, 0) as semestres_com_reserva,
    coalesce(r.vagas_no_recorte, 0) as vagas_no_recorte,
    r.primeiro_semestre,
    r.ultimo_semestre
from obrigatorias o
join {{ ref('dim_curso') }} c on c.curso_id = o.curso_id
join {{ ref('dim_disciplina') }} d on d.disciplina_id = o.disciplina_id and d.is_current
left join reservas r on r.curso_codigo = c.curso_codigo and r.disciplina_codigo = d.disciplina_codigo
