# Semana 13 (03/11 a 09/11)

## O que foi medido
- O observatório apresenta a série de vagas reservadas com filtro por curso.

## O que surpreendeu
- A mesma tabela de métricas atende o painel e a fila do ETL reverso.

## O que foi decidido
- Centralizar as métricas nos marts dbt e declarar freshness de 24 horas.

## Próxima semana
- [ ] Documentar LGPD e demonstrar privilégio mínimo.

## Revisão pós-entrega (17/11/2026)

A revisão do checklist da E3 mostrou lacunas que corrigimos:

- **Não havia SCD.** Agora `dim_disciplina` vem de um dbt snapshot (SCD 2),
  e `dim_curriculo_componente` guarda a natureza por versão curricular.
- **O backfill só contava linhas.** Agora o fato é incremental por semestre
  e `BACKFILL_SEMESTRE` refaz uma janela.
- **O retry era uma falha simulada antes de rodar.** Agora o banco é
  derrubado de verdade, e o grafo repete e depois desiste.
- **O EXPLAIN de antes e o de depois eram o mesmo plano**, porque o índice
  estava numa tabela que a consulta não lia. O plano do q0 mostrou um erro
  de estimativa no CTE; a reescrita levou de 5.721 a 188 buffers.
- **Faltavam testes** de integridade referencial e de distribuição que
  pegam dado sujo (curso que some, semestre incompleto, salto de série).
- **O painel virou uma página de análise por curso.**

O que surpreendeu: o índice da V008 era idêntico à chave primária.
