# Declaração sobre histórico

**Decisão:** `turma`, `turma_docente` e `reserva_vaga` são **insert-only**,
com uma linha por turma (e por reserva) de cada semestre **encerrado**.
`disciplina`, `curso`, `curriculo` e `curriculo_componente` usam
**upsert**. Justificativa e alternativas no
[ADR-0003](adr/0003-reservas-por-curso-e-curriculo-versionado.md).

## Por quê

A pergunta de gestão compara as vagas reservadas a cada curso entre
semestres. Se a reserva fosse sobrescrita, cada carga apagaria a evidência
do semestre anterior.

Só entram semestres encerrados porque a turma e a reserva de um semestre
em andamento ainda mudam. Guardar um retrato parcial como se fosse o final
distorceria a série. "Encerrado" vem do calendário acadêmico oficial da
UnB (`data/calendario_academico.csv`, tabela `semestre_letivo`), com a
fonte de cada data: o semestre encerra na data mais tardia entre o último
dia de aulas, o último dia letivo e o prazo de consolidação das turmas no
SIGAA.

O currículo tem **versão** (`curriculo`), e não histórico por sobrescrita:
cada versão coletada é uma linha própria, com início de vigência. Isso
preserva as versões, mas não resolve sozinho a leitura histórica: a
pergunta de gestão aplica de propósito o currículo de referência de 2026.1
a toda a série, e as versões em vigor em 2022–2024 não foram coletadas
para 4 dos 5 cursos.

## O que isso permite perguntar

- Como evoluíram as vagas reservadas a cada curso, por semestre, turno e disciplina.
- Quais obrigatórias do currículo tiveram reserva para o curso, e em quais semestres.
- Quanto das reservas vem de disciplinas da FCTE e quanto de outras unidades.
- Quantas turmas são compartilhadas entre cursos.

## O que isso **não** permite perguntar

- Se uma turma lotou ou faltou vaga: as fontes que conseguimos consultar
  não trazem ocupação.
- Qual foi a oferta total de turmas: só aparecem turmas que reservam vagas
  para algum dos cinco cursos.
- Como a reserva mudou durante o semestre (só entra o retrato final).
- O que era obrigatório em cada semestre passado: o conjunto de
  obrigatórias é o do currículo de referência de 2026.1.
- Qual versão do catálogo ou do pré-requisito valia num semestre passado.

## Como isso aparece no esquema e na carga

- `UNIQUE (disciplina_id, codigo_turma, ano, periodo)` em `turma` e chave
  `(turma_id, curso_id)` em `reserva_vaga`: cada semestre gera linhas novas.
- Triggers da migração V003 levantam erro em UPDATE, DELETE e TRUNCATE nas
  três tabelas.
- Reprocessar o mesmo lote não duplica nem altera nada: o loader compara
  cada turma e reserva com o que já está no banco e conta as iguais como
  "idêntica (reprocessamento)".
- Um lote que traz **outro valor** para uma turma ou reserva já carregada
  (horário, turno, docentes ou vagas) é recusado inteiro: a transação é
  desfeita e as diferenças vão para `debug/divergencias.csv`. Aceitar o
  valor novo exige decisão da Squad em ADR (por exemplo, guardar um
  retrato por coleta), nunca uma sobrescrita silenciosa.
- Docentes só entram junto com a turma nova; uma turma já carregada não
  ganha nem perde docentes.
- Semestre sem data no calendário, ainda não encerrado ou coletado antes
  do encerramento é recusado pelo loader, e o trigger
  `turma_exige_semestre_encerrado` (V004) recusa no banco a turma coletada
  antes do encerramento do seu semestre.
- Carimbos: `ano`/`periodo` (quando a turma aconteceu), `coletado_em`
  (quando foi coletada), `ingerido_em` (quando entrou no banco), mais
  `lote` e `fonte` para rastrear a origem.
