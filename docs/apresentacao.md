# Apresentação do projeto

Use esta página como roteiro da defesa. A apresentação deve seguir a ordem:

**problema → dados → pipeline → camada analítica → dashboard → camada
vetorial → evidências e limites**.

## 1. Problema e pergunta de gestão

O projeto analisa a evolução das **vagas reservadas publicadas** para os
cursos da FCTE entre 2022.1 e 2026.1, considerando as disciplinas
obrigatórias do currículo de referência de 2026.1.

Vaga reservada não significa vaga ocupada nem oferta total de vagas.

## 2. Dados e armazenamento

O lote público foi carregado no PostgreSQL. O modelo operacional separa
turmas, reservas por curso, disciplinas, cursos, currículos e semestres.
O histórico é mantido de forma insert-only e o lote é conferido por checksum.

Mostre:

- [Visão geral do projeto](index.md);
- [Coleta pública](COLETA_SIGAA_2026-09-28.md);
- [Arquitetura e modelo de dados](historico.md).

## 3. Ingestão da E2

Explique que a E2 implementou:

- carga em lote;
- Parquet/Delta;
- outbox transacional;
- consumidor CDC;
- checkpoint e deduplicação;
- tratamento de dado atrasado.

Mostre a [evidência da E2](evidencia-e2.md) e o
[ADR-0005](adr/0005-ingestao-e2.md).

## 4. E3: camada analítica

O dbt transforma o PostgreSQL em uma camada própria para análise:

```text
OLTP → staging → fct_reservas → mart_observatorio → dashboard
```

A `fct_reservas` tem uma linha por turma, curso, disciplina e semestre. O
`mart_observatorio` calcula:

- vagas reservadas;
- disciplinas obrigatórias com reserva;
- turmas com reserva.

Mostre a [ADR-0006 da E3](adr/0006-camada-analitica-observatorio-e3.md) e o
[observatório e governança](observatorio-e-governanca.md).

## 5. Dashboard

O dashboard é executado localmente porque depende do PostgreSQL, das
migrações, da carga e do dbt.

```bash
docker compose up --build
```

Depois abra <http://localhost:8080> e filtre, por exemplo:

- curso: `FGA_SOFT`;
- semestre: `2026.1`.

Explique que os valores exibidos vêm do `mart_observatorio`, e não de uma
consulta improvisada diretamente nas tabelas operacionais.

## 6. Qualidade e operação

Execute:

```bash
docker compose run --rm analytics
docker compose --profile test run --rm analytics-tests
```

Mostre as evidências de [retry](evidencias/retry.txt), [backfill](evidencias/backfill-2024.1.txt),
[controle de acesso](evidencias/controle-acesso.txt) e
[`EXPLAIN` antes/depois](evidencias/explain-antes.txt). Explique também o ETL reverso para
`operations.alertas_reserva`.

## 7. Camada vetorial

A camada vetorial foi adicionada com pgvector para permitir busca de
disciplinas semanticamente parecidas:

```text
texto da disciplina → embedding de 384 dimensões → índice HNSW → vizinhos
```

Ela usa o modelo `intfloat/multilingual-e5-small`. A execução é opcional no
fluxo padrão:

```bash
docker compose --profile ml run --rm ml
docker compose --profile ml run --rm ml-tests
```

Resultado validado no lote atual:

- 638 textos vetorizados;
- 100% das 72 disciplinas do fato com vetor;
- vetores com 384 dimensões e norma 1;
- testes `ml-tests` finalizados com código 0.

Para demonstrar a busca:

```bash
docker compose exec -T db psql -U g2 -d ofertas_unb -v codigo=FGA0060 \
  < ml/consultas/consulta_vizinhos.sql
```

## 8. Fechamento e limitações

Finalize destacando:

- o projeto mede reservas publicadas, não ocupação real;
- o volume atual é pequeno;
- o dashboard é uma demonstração local;
- a camada vetorial apoia busca semântica, mas não substitui o modelo
  analítico relacional;
- novas fontes ou uma pergunta sobre ocupação exigiriam revisão da arquitetura.

## Ordem das páginas

1. [Início](index.md)
2. [ADR-0006 da E3](adr/0006-camada-analitica-observatorio-e3.md)
3. [Observatório e governança](observatorio-e-governanca.md)
4. Dashboard em <http://localhost:8080>
5. [Evidências de retry](evidencias/retry.txt)
6. Camada vetorial e busca por similaridade
