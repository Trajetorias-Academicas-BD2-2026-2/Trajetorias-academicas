with reservas as (
    select
        rv.turma_id,
        rv.curso_id,
        rv.vagas_reservadas,
        t.disciplina_id,
        t.ano,
        t.periodo,
        concat(t.ano, '.', t.periodo) as semestre,
        c.codigo as curso_codigo,
        c.nome as curso_nome,
        d.codigo as disciplina_codigo,
        d.nome as disciplina_nome,
        coalesce(cc.natureza = 'OBRIGATORIA', false) as obrigatoria,
        rv.ingerido_em
    from {{ source('oltp', 'reserva_vaga') }} rv
    join {{ source('oltp', 'turma') }} t on t.id = rv.turma_id
    join {{ source('oltp', 'curso') }} c on c.id = rv.curso_id
    join {{ source('oltp', 'disciplina') }} d on d.id = t.disciplina_id
    left join {{ source('oltp', 'curriculo_referencia') }} cr
      on cr.curso_id = rv.curso_id
    left join {{ source('oltp', 'curriculo_componente') }} cc
      on cc.curriculo_id = cr.id and cc.disciplina_id = t.disciplina_id
)
select * from reservas
