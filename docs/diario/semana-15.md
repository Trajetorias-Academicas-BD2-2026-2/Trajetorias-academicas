# Semana 15 (17/11 a 23/11)

## O que foi medido
- **Revisão das entregas (17/11).** A releitura dos checklists achou lacunas reais:
  - E2: CDC numa tabela de demonstração; dado atrasado só descrito;
  - E3: sem SCD; EXPLAIN de antes e depois com o mesmo plano.

  Todas corrigidas e medidas (commits `7408923` a `950e348`; tags e1–e3).
- **Painel narrativo publicado no GitHub Pages (18/11),** gerado pelo Actions só se
  os testes passam (`5057e7a`).
- **E4 (18/11):**
  - camada semântica com 8 métricas e 820 valores;
  - teste de consistência com 586 comparações e 0 divergências; uma divergência
    provocada (3.816 → 3.900) é pega ([`e4-consistencia.txt`](../evidencias/e4-consistencia.txt));
  - ETL reverso para a Pauta da coordenação: 206 itens, que ficam pendentes com a
    Pauta fora do ar e são entregues sem duplicar
    ([`e4-etl-reverso.txt`](../evidencias/e4-etl-reverso.txt));
  - RLS por curso e bloqueio da coluna `docente.nome`, com 16 verificações
    ([`e4-acesso.txt`](../evidencias/e4-acesso.txt)).

## O que surpreendeu
- **A métrica era calculada em três lugares** (SQL, JavaScript do painel, Python do ETL)
  e nada comparava os três. A camada semântica tornou isso testável.
- **O painel conectava como `g2`, superusuário do banco.**
- **O nome dos docentes estava no Delta do lote da E2,** que nem precisava dele. A
  análise de LGPD, feita artefato por artefato e não só no banco, foi o que achou isso.
- **O dbt recria as tabelas e apaga as políticas de RLS.** Resolvemos com uma função
  chamada no `on-run-end` e um teste que confere as políticas depois do build.

## O que foi decidido
- MetricFlow como camada semântica, cópia por arquivo no Pages para o público e
  ETL reverso por API com fila de envio, com o CSV como opção nula medida
  ([ADR-0007](../adr/0007-disponibilizacao-e4.md)).
- Minimização: o lote Delta passa a ter `qtd_docentes` em vez dos nomes ([LGPD](../lgpd.md)).
- O histórico do git **não** será reescrito agora; o plano de descarte fica registrado.

## Próxima semana
- [ ] Ensaiar a defesa cronometrada ([roteiro](../defesa/roteiro.md)) (Squad).
- [ ] Commits da E4 e tag `e4` (Gabriel).
