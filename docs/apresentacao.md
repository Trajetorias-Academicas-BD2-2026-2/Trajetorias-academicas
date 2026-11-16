# Entrega 3 — Observatório analítico

## O que foi entregue

Transformamos os dados de reservas de vagas em uma camada analítica testada,
um dashboard para consulta e uma camada vetorial para busca semântica.

| Parte | Resultado |
|---|---|
| Dados | 733 turmas, 1.776 reservas e 9 semestres |
| Transformação | dbt com staging, fato e mart |
| Observatório | Dashboard com filtros por curso e semestre |
| Qualidade | Testes de unicidade, volume, distribuição e freshness |
| Operação | Retry, backfill, ETL reverso e controle de acesso |
| Camada vetorial | pgvector, embeddings e busca por similaridade |

## 1. Problema de gestão

O projeto responde:

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas para
> cada curso da FCTE nas disciplinas obrigatórias do currículo de referência
> selecionado para 2026.1?

O foco é **reserva publicada**. Isso não significa ocupação real por alunos
nem oferta total de vagas.

## 2. Fluxo completo

```text
Dados públicos do SIGAA
          ↓
Lote conferido por checksum
          ↓
PostgreSQL transacional
          ↓
dbt: staging → fct_reservas → mart_observatorio
          ↓
Dashboard e ETL reverso
          ↓
Busca vetorial opcional
```

## 3. Modelo analítico

A `fct_reservas` tem uma linha por **turma, curso, disciplina e semestre**.
O `mart_observatorio` disponibiliza:

- `vagas_reservadas`;
- `obrigatorias_com_reserva`;
- `turmas_com_reserva`.

Exemplo: se `FGA_SOFT`, em `2026.1`, apresenta 3.816 vagas reservadas, 30
obrigatórias com reserva e 79 turmas, as reservas publicadas somaram 3.816
vagas em 30 disciplinas e 79 turmas. Isso não significa 3.816 alunos.

A decisão está registrada na
[ADR-0006 da camada analítica](adr/0006-camada-analitica-observatorio-e3.md).

## 4. Dashboard

O dashboard é executado localmente porque depende do PostgreSQL, das
migrações, da carga e do dbt.

```bash
docker compose up --build
```

Depois abra <http://localhost:8080> e filtre `FGA_SOFT` e `2026.1`.

## 5. Qualidade e governança

Foram implementados:

- 18 testes dbt aprovados;
- freshness;
- retry e backfill;
- ETL reverso para `operations.alertas_reserva`;
- catálogo, linhagem e controle de acesso;
- evidências de `EXPLAIN`.

```bash
docker compose run --rm analytics
docker compose --profile test run --rm analytics-tests
```

## 6. Camada vetorial

A camada vetorial usa pgvector para encontrar disciplinas semanticamente
parecidas:

```text
nome → embedding de 384 dimensões → índice HNSW → vizinhos
```

Foi utilizado o modelo `intfloat/multilingual-e5-small`.

```bash
docker compose --profile ml run --rm ml
docker compose --profile ml run --rm ml-tests
```

Resultado validado:

- 638 textos vetorizados;
- 100% das 72 disciplinas do fato com vetor;
- vetores com 384 dimensões e norma 1;
- testes finalizados com código 0.

## 7. Demonstração

1. Explique a pergunta de gestão.
2. Mostre PostgreSQL → dbt → mart.
3. Abra o dashboard e filtre `FGA_SOFT` e `2026.1`.
4. Mostre os testes e as evidências.
5. Mostre a busca vetorial.
6. Explique as limitações.

## 8. Limitações

- Mede vagas reservadas publicadas, não ocupação real.
- Reservas não representam a oferta total.
- O currículo de referência é o de 2026.1.
- O dashboard é uma demonstração local.
- A camada vetorial apoia busca semântica, mas não substitui o modelo
  relacional das métricas.

## Conclusão

A Entrega 3 transforma dados operacionais em informação analítica
reproduzível: o dbt organiza e testa as métricas, o dashboard permite a
consulta por curso e semestre, a governança documenta o uso e a camada
vetorial amplia o projeto com busca semântica.
