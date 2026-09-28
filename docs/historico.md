# Declaração sobre histórico

**Decisão:** `oferta_turma` é **insert-only**, com uma linha por turma de
cada semestre **encerrado**. `disciplina`, `curso` e `curso_disciplina`
usam **upsert**; `pre_requisito` é substituído por disciplina a cada carga.
Justificativa e alternativas no [ADR-0001](adr/0001-modelagem-fonte-origem.md).

## Por quê

A pergunta de gestão compara a lotação das disciplinas entre semestres.
Se `oferta_turma` fosse sobrescrita, a carga de um semestre apagaria a
evidência do anterior e a pergunta ficaria sem resposta.

Só entram semestres encerrados porque a ocupação de uma turma muda
enquanto o semestre está em andamento. Como a tabela guarda uma única
linha por turma e semestre, carregar um semestre aberto congelaria um
retrato parcial como se fosse o final.

A estrutura curricular muda raramente e a pergunta não compara versões
dela ("como o pré-requisito de X mudou" não é pergunta do projeto), então
guardar o histórico dessas tabelas não se paga nesta entrega.

## O que isso permite perguntar

- Como a ocupação de uma disciplina evoluiu de 2022.1 a 2026.1.
- Quais disciplinas obrigatórias ficaram lotadas em mais semestres, por turno.
- Se o número de turmas de uma disciplina está crescendo ou diminuindo.
- Quais obrigatórias ficaram sem turma em algum semestre.

## O que isso **não** permite perguntar

- Como a ocupação mudou durante o período de matrícula de um semestre.
- Qual era a matriz curricular ou o pré-requisito de uma disciplina num
  semestre passado (só a versão mais recente fica no banco).

## Como isso aparece no esquema e na carga

- `UNIQUE (disciplina_id, codigo_turma, ano, periodo)`: a chave inclui o
  semestre, então cada semestre gera linhas novas.
- Trigger `oferta_turma_bloqueia_alteracao` (migração V002): UPDATE, DELETE
  e TRUNCATE em `oferta_turma` levantam erro.
- Reprocessar o mesmo semestre não duplica nem altera nada:
  `ON CONFLICT DO NOTHING` preserva a primeira carga, e o loader informa
  quantas linhas "já existiam".
- `loader/semestres.py` e `tests/sanity_checks.sql` usam a mesma regra para
  identificar o semestre em andamento: janeiro e fevereiro contam como o
  2º semestre do ano anterior, de março a julho é o 1º semestre do ano, e
  de agosto a dezembro, o 2º.
- Cada linha carrega `coletado_em` (quando foi raspada) e `ingerido_em`
  (quando entrou no banco), além de `ano`/`periodo` (quando a oferta
  aconteceu).
- `curso_disciplina.obrigatoria` é atualizada quando a matriz muda (upsert);
  o valor anterior não é guardado.
