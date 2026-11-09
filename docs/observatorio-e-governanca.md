# Observatório, governança e consumo

## Referência de produto

O [Observatório da Evasão e Permanência do UnB DataLab](https://www.unbdatalab.org/observatoriodaevasao)
usa um painel interativo para que a gestão filtre indicadores por curso e
período. O projeto G2 aplica a mesma ideia ao domínio de reservas de vagas:
o coordenador filtra o curso e o semestre e acompanha a série das
disciplinas obrigatórias do currículo de referência de 2026.1.

## Métricas oficiais

- `vagas_reservadas`: soma de `reserva_vaga.vagas_reservadas`; não é ocupação
  nem oferta total.
- `obrigatorias_com_reserva`: quantidade de disciplinas obrigatórias distintas
  com ao menos uma reserva no curso e semestre.
- `turmas_com_reserva`: quantidade de turmas distintas com reserva.
- Freshness: maior `ingerido_em` da tabela fato; SLA de atualização: até 24
  horas após uma nova carga encerrada.

As definições ficam versionadas nos modelos dbt em `analytics/models/marts/`.
O painel e o ETL reverso leem as mesmas tabelas, evitando métricas divergentes.

## ETL reverso

`operations.alertas_reserva` é uma fila operacional. O pipeline copia para
ela as reservas obrigatórias com 50 ou mais vagas. A coordenação pode usar a
fila para revisar a negociação de vagas antes do planejamento do semestre.
O destino é operacional, diferente do mart analítico, e pode ser consumido
por uma aplicação ou exportado para o processo da coordenação.

## Catálogo e linhagem

| Campo de consumo | Transformação | Origem |
|---|---|---|
| `vagas_reservadas` | soma no `mart_observatorio` | `reserva_vaga.vagas_reservadas`, SIGAA |
| `obrigatorias_com_reserva` | `count(distinct disciplina_codigo)` filtrado | `curriculo_componente.natureza` |
| `turmas_com_reserva` | `count(distinct turma_id)` | `turma.id` |
| `semestre` | concatenação de `turma.ano` e `turma.periodo` | SIGAA e calendário UnB |

O lote público, checksums e evidências estão em
`data/coleta_publica_2026-09-28/`. A trilha completa é:

```text
SIGAA -> lote CSV com SHA-256 -> OLTP PostgreSQL
      -> staging dbt -> fct_reservas -> mart_observatorio
      -> dashboard / operations.alertas_reserva
```

## LGPD

O lote não coleta estudantes nem identificadores acadêmicos de alunos.
Nomes de docentes podem aparecer na origem, mas não são necessários para as
métricas e não são publicados no mart do observatório. A finalidade é apoiar
planejamento acadêmico; a base legal aplicável ao uso institucional deve ser
confirmada pela UnB antes de uso real. O recorte público é retido enquanto
for necessário para reproduzir a série histórica e deve ser descartado ou
anonimizado quando deixar de ter finalidade. Pedidos de remoção e acesso
devem ser tratados pelo encarregado de dados da universidade.

Risco residual: combinação de semestre, turma e docente pode reidentificar
uma pessoa em uma comunidade pequena. Por isso o painel expõe apenas
agregados por curso, disciplina e semestre.

## Controle de acesso

O papel `dashboard_reader` recebe apenas `SELECT` no schema `analytics` e na
fila operacional. Ele não recebe acesso às tabelas públicas do OLTP nem a
colunas de docente. O acesso mínimo é demonstrado em
`db/migrations/V007__camada_analitica_governanca.sql`.
