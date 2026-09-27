# Declaração sobre histórico

**Decisão:** `oferta_turma` é **insert-only**. `disciplina`, `curso`,
`curso_disciplina` e `pre_requisito` usam **upsert** (podem ser
corrigidos, mas não têm série histórica própria).

## Por quê

A pergunta de gestão do G2, *quais disciplinas têm demanda reprimida e
como isso evolui por semestre*, exige comparar valores de ocupação ao
longo do tempo. Se `oferta_turma` fosse sobrescrita a cada carga, a
carga de um novo semestre apagaria a evidência do semestre anterior, e
a pergunta central do projeto ficaria sem resposta.

Já `disciplina`, `curso` e `pre_requisito` descrevem a estrutura
curricular, que muda raramente e não faz parte da pergunta de gestão (a
pergunta não é "como o pré-requisito de X mudou nos últimos 5 anos").
Por isso não se justifica pagar o custo de mantê-los insert-only nesta
entrega; se uma pergunta futura precisar disso, isso vira um novo ADR.

## Como isso aparece no esquema

- `oferta_turma` tem `UNIQUE (disciplina_id, codigo_turma, ano, periodo)`
 , a chave inclui o semestre, então cada carga de um novo período
  sempre gera linhas novas, nunca conflita com o período anterior.
- Cada linha carrega `carga_id` e `ingerido_em`, permitindo saber
  exatamente de qual execução do loader ela veio, mesmo que o mesmo
  semestre seja recarregado por engano (nesse caso o `ON CONFLICT DO
  NOTHING` do loader evita duplicata, mas preserva a primeira carga).
- `curso_disciplina.obrigatoria` é sobrescrita por upsert quando a
  matriz curricular muda (ex.: uma disciplina passa de optativa para
  obrigatória), não guardamos o valor anterior, porque a pergunta de
  gestão não pede essa comparação.