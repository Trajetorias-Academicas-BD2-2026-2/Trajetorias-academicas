-- P11 da camada vetorial: um texto por item a vetorizar.
-- Só o nome entra no texto; unidade, tipo e turno ficam em `atributos`, como
-- filtros. No protótipo, metadados no texto dominaram a similaridade.
-- Lido por ml/gerar_embeddings.py, que grava em ml.item_texto e ml.embedding.
with itens as (
    select
        'componente' as entidade,
        d.disciplina_codigo as chave_origem,
        regexp_replace(trim(d.disciplina_nome), '\s+', ' ', 'g') as texto,
        jsonb_build_object('tipo', d.tipo, 'unidade', u.nome) as atributos
    from {{ ref('dim_disciplina') }} d
    left join {{ source('oltp', 'unidade') }} u on u.id = d.unidade_id

    union all

    select
        'curso_unb' as entidade,
        c.curso_codigo as chave_origem,
        regexp_replace(trim(c.curso_nome), '\s+', ' ', 'g') as texto,
        jsonb_build_object('turno', c.turno) as atributos
    from {{ ref('dim_curso') }} c
)
select
    entidade,
    chave_origem,
    texto,
    encode(sha256(convert_to(texto, 'UTF8')), 'hex') as texto_sha256,
    atributos
from itens
where texto <> ''
