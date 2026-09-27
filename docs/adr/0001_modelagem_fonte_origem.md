# ADR-0001: Modelagem da fonte transacional de oferta de disciplinas

## Contexto

O G2 modela o problema de oferta de disciplinas de graduação na UnB: o
coordenador de curso hoje decide quais turmas abrir sem visibilidade
histórica clara sobre lotação, crescimento de demanda e disciplinas que
mais travam a grade (pré-requisitos). As fontes são três páginas
públicas do SIGAA:

1. **Consulta de Turmas**, oferta de turmas por semestre (vagas,
   docente, horário, turno).
2. **Busca de Componentes Curriculares**, disciplina, carga horária,
   pré-requisitos.
3. **Listagem pública de cursos de graduação**, cursos do Campus Gama
   e sua matriz curricular (quais disciplinas pertencem a quais cursos,
   e se são obrigatórias).

A pergunta de gestão que a fonte precisa suportar: *quais disciplinas
obrigatórias, por curso e turno, têm demanda reprimida nos últimos
semestres, e quais mais travam a grade por serem pré-requisito de
outras?*

## Caracterização da carga

- **Volume estimado:** ~150–400 componentes curriculares por unidade;
  ~1.000–3.000 linhas de `oferta_turma` por semestre carregado; 5 cursos
  do Gama e sua matriz curricular completa. *
- **Padrão de escrita:** em lote, uma vez por semestre carregado
  (execução do loader). `oferta_turma` é append-only; as demais tabelas
  fazem upsert.
- **Padrão de leitura:** consultas analíticas agregadas (contagens,
  médias de ocupação por disciplina/turno/semestre), não consulta de um
  único registro.

## Decisão

1. **Histórico, insert-only em `oferta_turma`.** Cada carga de
   semestre gera novas linhas, nunca sobrescreve. A pergunta de gestão
   exige comparar semestres. Justificativa completa em
   `docs/historico.md`.
2. **Carimbos de tempo nomeados por papel.** `oferta_turma.ingerido_em`
   marca quando o loader rodou; `ano`/`periodo` marcam quando o evento
   (a oferta) de fato ocorreu.
3. **Normalização em 3FN.** `disciplina`, `curso`, `curso_disciplina` e
   `pre_requisito` ficam separados para não repetir carga horária e
   nome de disciplina em cada linha de oferta.
4. **SGBD: PostgreSQL**, pensando na E2 (captura de mudanças via
   replicação lógica/Debezium).
5. **Linhagem obrigatória.** Toda linha de `oferta_turma` carrega
   `fonte` e `carga_id`, para rastrear de qual execução do scraper ela
   veio, necessário porque a fonte é raspada, não uma API confiável.
6. **Extração via browser real (Playwright), não requests/HTTP puro.**
   As páginas do SIGAA são formulários JSF com postback, e dois
   comportamentos só foram descobertos testando contra o site real:
   - Acessar a URL de busca **direto** (sem navegar a partir da home)
     gera uma sessão com estado inválido: qualquer envio do formulário é
     redirecionado de volta para a home (confirmado observando um
     código HTTP 302 na resposta, não uma suposição). A solução foi
     chegar pela URL com o parâmetro `?aba=p-ensino` / `?aba=p-graduacao`,
     do jeito que um link real da home aponta.
   - O campo "Unidade Responsável" só é aplicado como filtro se a
     checkbox ao lado estiver marcada, selecionar a opção no menu
     sozinho não basta (confirmado num print de tela do formulário).
   Um browser real absorve essas particularidades do JSF (gerenciamento
   de sessão, eventos de formulário) sem precisar reimplementar o
   protocolo manualmente.

## Alternativas consideradas

- **CRUD com sobrescrita de vagas** (descartada): perderia a série
  histórica de ocupação por semestre.
- **Raspagem via requests + parsing manual de ViewState** (descartada
  em favor de Playwright): mais rápida, mas exigiria reimplementar à
  mão o comportamento de sessão do JSF que só foi entendido depois de
  observar o site rodando de verdade, um browser real absorve isso.

## Consequências

- A carga depende de um browser headless (Playwright), aumentando a
  imagem Docker e o tempo de execução.
- Sem uma API estável do SIGAA, os seletores em `loader/config.py` e a
  lógica de navegação (`sigaa_utils.py`) podem quebrar se a UI mudar,
  mitigado documentando aqui os dois comportamentos não óbvios acima,
  para que o próximo ajuste não repita a mesma investigação do zero.
- `oferta_turma` cresce a cada carga (nunca é limpa), então o volume de
  dados é proporcional ao número de semestres carregados.