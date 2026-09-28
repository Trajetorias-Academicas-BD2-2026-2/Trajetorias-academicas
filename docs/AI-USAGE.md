# Uso de IA neste projeto

Registro do uso de IA (Claude, via chat) no desenvolvimento da E1 do G2.
Este documento é atualizado à medida que o projeto avança, reflete o que
foi de fato pedido e decidido, não um resumo genérico escrito no final.

## Como usamos

A IA foi usada como par de programação: escrevemos o domínio, as perguntas
de gestão e as decisões de modelagem em conversa com ela, e ela gerou
código e documentação a partir disso, que revisamos e corrigimos conforme
rodávamos de verdade contra o SIGAA. Nenhuma decisão de modelagem foi
aceita sem que o grupo entendesse o motivo, o restante deste documento
existe justamente para registrar esses motivos.

## O que foi gerado com apoio de IA

- **Esquema inicial** (`db/migrations/V001__schema_base.sql`): tabelas,
  tipos, `CHECK`s, chaves estrangeiras e índices, a partir do domínio
  (oferta de disciplinas) e das quatro perguntas de gestão do grupo.
- **`docker-compose.yml`**, `Dockerfile` do loader e a estrutura de pastas
  (`db/migrations/`, `loader/`, `tests/`).
- **Scrapers Playwright** (`loader/scrape_turmas.py`,
  `scrape_componentes.py`, `scrape_cursos.py`) e o script de carga
  (`load_to_db.py`).
- **ADR-0001, caracterização de carga e declaração de histórico**, a
  partir das decisões de domínio discutidas com o grupo.

## Problemas reais que apareceram ao rodar contra o SIGAA, e como foram resolvidos

Isso é o que mais importa registrar aqui: nenhuma dessas soluções foi
aceita "porque a IA disse", cada uma só ficou no código depois que
conseguimos ver, em um print de tela ou num log real, que era de fato o
problema.

1. **Acessar a URL de busca direto gerava uma sessão quebrada.**
   Confirmamos isso vendo, num log de rede, que o clique em "Buscar"
   sempre devolvia um redirecionamento HTTP (302) para a página inicial
   do SIGAA, mesmo com o formulário preenchido corretamente. Testamos
   isolando variáveis (sem unidade, sem nenhum campo preenchido) até
   confirmar que não era um erro do que preenchíamos, e sim de como
   chegávamos na página. A solução, inspecionar o link real da home e
   usar a URL com o parâmetro `?aba=p-ensino`, só foi aceita depois de
   testada e confirmada por log.
2. **Uma checkbox ao lado de "Unidade Responsável" precisa estar marcada**
   para o filtro valer, confirmado visualmente num print de tela do
   formulário antes de o código ser ajustado.
3. **Um campo de nível de ensino usa substring**, o que fazia
   "GRADUAÇÃO" bater por engano com "PÓS-GRADUAÇÃO", corrigido para
   tentar correspondência exata primeiro.
4. **Bug de dados, não de scraping:** o `load_to_db.py` tentava inserir
   em `curso_disciplina` sem preencher a coluna `obrigatoria`
   (`NOT NULL` no esquema), e o `scrape_cursos.py` tinha um caminho de
   reserva que escrevia uma coluna `semestre` que não existia no
   cabeçalho do CSV, os dois quebravam a carga silenciosamente ou com
   erro, e foram corrigidos depois de conferir os dados reais no banco
   (`SELECT * FROM curso;` vazio apontou o primeiro).
5. **Captura de pré-requisitos incompleta:** a expressão original só
   pegava a primeira linha depois de "Pré-Requisitos:", perdendo
   disciplinas com mais de um pré-requisito listado. Corrigido para
   capturar até a próxima seção da página.

## Revisão pós-entrega da E1 (28/09/2026)

Pedimos à IA (Claude) que conferisse o repositório contra o checklist de
aceite da E1 e corrigisse o que não atendia. O que ela apontou e o que
mudou:

| Problema apontado | Correção |
|---|---|
| `scrape_cursos.py` inventava a matriz curricular (distribuía disciplinas entre os cursos em rodízio, todas obrigatórias) quando a raspagem falhava | Trecho removido; a raspagem agora falha com erro |
| `scrape_turmas.py` trocava vagas ofertadas e ocupadas quando a ocupação passava da oferta, escondendo turmas superlotadas | Troca removida; a V002 aceita ocupação acima da oferta, e os testes de dados sinalizam valores implausíveis |
| Carga de um único semestre (2026.2, ainda em andamento) | Recorte 2022.1–2026.1, só semestres encerrados; o loader recusa semestre aberto |
| Carga dependia do SIGAA no ar e o staging estava no `.gitignore` | Recorte bruto versionado em `data/raw/`; o SIGAA só é acessado para o que falta ([ADR-0002](adr/0002-extracao-via-navegador-real.md)) |
| `scrape_prerequisitos.py` deduzia pré-requisitos por posição na tabela e sobrescrevia os do `scrape_componentes.py` | Script removido; a expressão E/OU do SIGAA é guardada em `disciplina.pre_requisito_expressao` |
| `fonte` truncada para `sigaa_turm`; `horario` truncado em 10 caracteres | Truncamentos removidos |
| `curso_disciplina` usava `DO NOTHING`, contradizendo o `historico.md` | Upsert de verdade |
| `psql` sem `ON_ERROR_STOP`: migração com erro terminava com código 0 | `db/migrate.sh` com `ON_ERROR_STOP` e controle em `schema_migrations` |
| Insert-only só por convenção | Trigger bloqueia UPDATE, DELETE e TRUNCATE em `oferta_turma` |
| Turma sem horário virava DIURNO por padrão | Turno `SEM_HORARIO` explícito |
| Caracterização estimada "no olho" | `loader/caracterizar.py` mede no banco e gera `docs/carga-medida.md` |
| ADR fora do template Nygard, sem opção nula nem gatilho de revisão | ADR-0001 reescrito; decisão de extração separada no ADR-0002 |
| Pergunta de gestão com duas perguntas e sem recorte temporal | Uma frase com sujeito e recorte; o pré-requisito virou pergunta derivada |
| Testes de sanidade só listavam linhas, sem falhar | `tests/sanity_checks.sql` termina com erro se algum teste falhar |

**Como validamos:** testes unitários do parsing
(`loader/tests/test_parsing.py`); migrações aplicadas num banco novo, num
banco que já tinha a V001 e com uma migração propositalmente quebrada
(que interrompeu a execução com erro); loader rodado duas vezes sobre um
recorte sintético de 9 semestres (a segunda rodada não inseriu nada);
UPDATE em `oferta_turma` bloqueado pelo trigger; testes de dados e
`caracterizar.py` executados sobre essa carga; travas de semestre em
andamento, semestre faltando e semestres idênticos testadas. Os scrapers
não foram executados contra o SIGAA nesta revisão: isso é feito pela
Squad na primeira carga real, que também gera `data/raw/` e
`docs/carga-medida.md`.

## Segunda revisão: coleta real e mudança de pergunta (28/09/2026)

A coleta real (relatório em `docs/COLETA_SIGAA_2026-09-28.md`) e um teste
manual de `listar.jsf` feito pela Squad mostraram que a série de vagas
ocupadas da FCTE não foi obtida nas fontes e consultas testadas. Com apoio
da IA (Claude):

| O que mudou | Como foi validado |
|---|---|
| Pergunta de gestão passou de lotação para vagas reservadas por curso (decisão da Squad) | ADR-0003 com medição sobre o lote real |
| Migração V003: `turma`, `reserva_vaga`, `turma_docente`, `curriculo`, `curriculo_componente`; `oferta_turma`, `curso_disciplina` e `pre_requisito` removidas | Aplicada num banco novo e num banco com V001 e V002 |
| Loader lê o lote versionado, confere SHA-256 e valida o recorte | Lote real carregado duas vezes: 733 turmas e 1.776 reservas; a segunda rodada não inseriu nada |
| Turmas com horário ou docente divergente entre cursos são rejeitadas, não escolhidas | 2 turmas (10 reservas) em `debug/rejeitados.csv` |
| Scrapers Playwright removidos; coletor HTTP grava no formato do loader | Testes unitários do coletor com HTML mínimo; consolidar os CSVs por curso reproduz as linhas do lote |
| Testes de dados e `caracterizar.py` refeitos para o novo modelo | Todos os testes de dados passam no lote real; `docs/carga-medida.md` gerado dele |

A IA também apontou, ao conferir o lote, que as reservas cobrem só parte
da oferta (85 de 254 pares curso x obrigatória) e que há uma quebra na
série a partir de 2023.2 (reservas de 50 vagas ou mais). Os dois pontos
foram conferidos nos dados e registrados como limites no README e no ADR-0003.

## Terceira revisão: feedback de revisor (28/09/2026)

Um revisor conferiu o zip corrigido e apontou cinco problemas; todos
procediam e foram corrigidos:

| Problema apontado | Correção | Validação |
|---|---|---|
| ADR-0003 dizia "75 disciplinas" de diferença em Automotiva; a consulta contava duas vezes as mudanças de natureza | `caracterizar.py` separa as que saem (42), entram (25) e mudam de natureza (4): 71 | Conferido direto nos CSVs do lote |
| Texto dizia que a matriz de 2026 não era aplicada a 2022, mas a pergunta aplica justamente o currículo de 2026.1 a toda a série | Pergunta reescrita com "currículo de referência selecionado para 2026.1" e sem turno; ADR, README e histórico explicam o conjunto fixo | `q0` roda no lote real |
| `ON CONFLICT DO NOTHING` ignorava em silêncio um lote com valores diferentes, e docentes podiam ser acrescentados a turma existente | Loader compara com o banco: igual conta como repetição; diferente desfaz a carga e grava `debug/divergencias.csv`; docentes só com turma nova | Lote com 1 horário e 1 reserva alterados: 2 divergências, banco inalterado |
| "Semestre encerrado" era aproximado pelo mês | Calendário oficial da SAA/UnB em `data/calendario_academico.csv` (fonte por semestre), tabela `semestre_letivo` (V004) e trigger que recusa turma coletada antes do encerramento | Lote com 2026.1 coletado em 20/07/2026 recusado pelo loader e pelo banco |
| Conclusão categórica sobre indisponibilidade pública | Textos dizem "não conseguimos obter nas fontes e consultas testadas" | Revisão dos documentos |

## Quarta revisão: segundo feedback de revisor (28/09/2026)

| Problema apontado | Correção | Validação |
|---|---|---|
| `curriculo_referencia` escolhia a versão em vigor no último semestre presente em `turma`: com 2027.1 carregado, Automotiva passaria de 6297/2 para 6297/3 e a `q0` mudaria de pergunta | Migração V005 fixa a view em 2026.1; testes de dados conferem que nenhuma versão posterior aparece e que a view não depende de `turma` | Turma de 2027.1 inserida numa transação de teste: a view nova manteve 6297/2; a definição antiga devolveria 6297/3 |
| Linha em branco extra no fim de `docs/carga-medida.md` (`git diff --check`) | `caracterizar.py` remove linhas vazias do fim | `git diff --check` sem avisos |

Ao regenerar a medição num banco recém-criado, a `q0` levou 172 ms na
primeira execução, contra 5 ms depois de um `ANALYZE`: sem estatísticas, o
planejador escolhe planos ruins. O loader passou a rodar `ANALYZE` ao fim
de cada carga, e as medições do ADR-0003 foram refeitas nessa condição.

## Perguntas prováveis na defesa

Qualquer integrante deve conseguir explicar, sem citar a IA como fonte:
por que a pergunta mudou de lotação para reservas; por que reserva não é
oferta nem ocupação; por que turma e reserva são tabelas separadas; por
que o currículo tem versão e por que a pergunta usa o currículo de
referência de 2026.1 para toda a série; por que turma e reserva são
insert-only, o que acontece quando um lote diverge do banco e de onde vem
a data de encerramento de cada semestre; o que
significa cada carimbo de tempo; por que a carga lê um lote versionado em
vez de raspar o SIGAA.
