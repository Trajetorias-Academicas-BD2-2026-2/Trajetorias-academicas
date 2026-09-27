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

## O que ainda precisa de validação humana antes da entrega

- Conferir se os números em `docs/carga-de-trabalho.md` batem com o
  volume real carregado no banco (a versão inicial era uma estimativa).
- Revisar o `ADR-0001` para que reflita as decisões acima (chegar via
  link da home, disfarce do navegador), não só o plano original.
- Remover do `config.py` as flags `TESTE_SEM_UNIDADE` e `TESTE_MINIMO`,
  usadas só para isolar os problemas acima, não fazem parte da solução
  final.
- Qualquer integrante do grupo deve conseguir explicar, sem citar a IA
  como fonte, por que `oferta_turma` é insert-only, por que o loader usa
  um browser real (Playwright) em vez de requisições HTTP diretas, e por
  que a URL de busca precisa do parâmetro `?aba=p-ensino`, essas são as
  perguntas mais prováveis numa defesa.