# Entrega 3 — Observatório analítico

## Visão geral

A Entrega 3 transforma os dados de reservas de vagas em informação analítica
reprodutível, com métricas por curso e semestre, dashboard, testes de
qualidade, governança e busca semântica.

| Componente | Implementação |
|---|---|
| Transformação | dbt |
| Banco operacional e analítico | PostgreSQL |
| Fato principal | `fct_reservas` |
| Mart de consumo | `mart_observatorio` |
| Dashboard | Observatório de reservas |
| Camada vetorial | pgvector |

## Pergunta de gestão

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas para
> cada curso da FCTE nas disciplinas obrigatórias do currículo de referência
> selecionado para 2026.1?

O projeto analisa **vagas reservadas publicadas**. Esse indicador não
representa ocupação real por estudantes nem oferta total de vagas.

## Dados analisados

| Indicador do recorte | Resultado |
|---|---:|
| Turmas | 733 |
| Reservas de vagas | 1.776 |
| Semestres | 9 |
| Período analisado | 2022.1 a 2026.1 |
| Disciplinas do fato com vetor | 72 |

## Arquitetura implementada

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
Busca vetorial semântica
```

O PostgreSQL preserva os dados operacionais. O dbt centraliza as regras
analíticas para que o dashboard e os demais consumidores utilizem as mesmas
definições.

## Modelo analítico

A `fct_reservas` possui uma linha por turma, curso, disciplina e semestre.
O `mart_observatorio` apresenta três métricas principais:

| Métrica | Significado |
|---|---|
| `vagas_reservadas` | Soma das vagas reservadas para o curso |
| `obrigatorias_com_reserva` | Disciplinas obrigatórias com pelo menos uma reserva |
| `turmas_com_reserva` | Turmas que reservaram vagas para o curso |

### Exemplo de resultado do observatório

| Curso | Semestre | Vagas reservadas | Obrigatórias com reserva | Turmas |
|---|---|---:|---:|---:|
| `FGA_SOFT` | `2026.1` | 3.816 | 30 | 79 |

Esse resultado significa que as reservas publicadas para `FGA_SOFT` em
2026.1 somaram 3.816 vagas, distribuídas em 30 disciplinas obrigatórias e
79 turmas. O número não representa 3.816 alunos matriculados.

## Observatório e governança

O dashboard apresenta os dados do `mart_observatorio` com filtros por curso e
semestre. A camada de governança acrescenta:

| Controle | Resultado |
|---|---|
| Testes dbt | 18 aprovados |
| Freshness | Validada |
| Retry | Falha controlada e recuperação |
| Backfill | 2024.1 reprocessado sem duplicidade |
| ETL reverso | 113 registros em `operations.alertas_reserva` |
| Controle de acesso | `dashboard_reader` com acesso mínimo |
| Performance | Planos `EXPLAIN` antes e depois |

A decisão arquitetural está registrada na
[ADR-0006 da camada analítica](adr/0006-camada-analitica-observatorio-e3.md).

## Camada vetorial

A camada vetorial amplia o projeto com busca semântica de disciplinas.

```text
Nome da disciplina
        ↓
Embedding de 384 dimensões
        ↓
Índice HNSW
        ↓
Disciplinas semanticamente semelhantes
```

| Validação da camada vetorial | Resultado |
|---|---:|
| Textos vetorizados | 638 |
| Disciplinas do fato com vetor | 100% de 72 |
| Dimensão dos vetores | 384 |
| Vetores fora da norma esperada | 0 |
| Modelos de embedding ativos | 1 |
| Testes da camada vetorial | Código 0 |

### Exemplo de busca semântica

Para a disciplina consultada, os resultados mais próximos incluíram:

| Código | Disciplina | Distância |
|---|---|---:|
| `FGA0137` | Sistemas de Banco de Dados 1 | 0,026 |
| `FGA0135` | Sistemas de Bancos de Dados | 0,027 |
| `FGA0389` | Monitoria em Sistemas de Banco de Dados 2 | 0,042 |
| `FGA0030` | Estruturas de Dados 2 | 0,057 |
| `FGA0146` | Estruturas de Dados 1 | 0,082 |

Quanto menor a distância, maior a proximidade semântica entre os textos.

## Resultados consolidados

| Dimensão | Resultado obtido |
|---|---|
| Integração | Dados operacionais transformados em modelos analíticos |
| Reprodutibilidade | Cargas, testes, retry e backfill documentados |
| Consumo | Dashboard com visão por curso e semestre |
| Governança | Linhagem, catálogo e privilégio mínimo |
| Inteligência semântica | Busca de disciplinas semelhantes com pgvector |

## Limitações

- O recorte mede reservas publicadas, não ocupação real.
- Reservas não representam a oferta total de vagas.
- O currículo de referência utilizado na série é o de 2026.1.
- O dashboard é uma demonstração local, não um serviço público de produção.
- A camada vetorial complementa o modelo relacional e não substitui as
  métricas analíticas.

## Conclusão

A Entrega 3 disponibiliza um observatório analítico reproduzível para apoiar
a análise de reservas de vagas da FCTE. O dbt organiza e testa as métricas, o
dashboard facilita a consulta por curso e semestre, a governança documenta o
fluxo de dados e o pgvector acrescenta busca semântica sobre as disciplinas.
