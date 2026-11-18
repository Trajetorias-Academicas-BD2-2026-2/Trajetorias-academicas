# Portfólio de decisões (ADRs) e revisão dos gatilhos

Cinco decisões vigentes, uma por estágio do ciclo de vida, e duas substituídas. Na E4 relemos **cada gatilho de revisão** para saber se disparou durante o semestre e o que foi feito.

| ADR | Estágio | Decisão | Status |
|---|---|---|---|
| [0003](0003-reservas-por-curso-e-curriculo-versionado.md) | Geração/armazenamento (E1) | Turmas e reservas por curso insert-only; currículo versionado; referência fixa em 2026.1 | Aceito |
| [0004](0004-coleta-publica-versionada.md) | Geração (E1) | Carga a partir de lote versionado conferido por SHA-256 | Aceito |
| [0005](0005-ingestao-e2.md) | Ingestão (E2) | Lote idempotente por partição + CDC por outbox; Delta Lake | Aceito (revisado na E4) |
| [0006](0006-camada-analitica-observatorio-e3.md) | Transformação (E3) | Estrela em dbt, fato por turma × curso, script + cron | Aceito |
| [0007](0007-disponibilizacao-e4.md) | Disponibilização (E4) | Camada semântica MetricFlow, cópia por arquivo, ETL reverso por API com fila | Aceito |
| [0001](0001-modelagem-fonte-origem.md) | E1 | Oferta insert-only para medir lotação | **Substituído** pelo 0003 |
| [0002](0002-extracao-via-navegador-real.md) | E1 | Raspar o SIGAA com navegador a cada carga | **Substituído** pelo 0004 |

## Gatilhos: disparou?

Legenda: **Disparou** · **Parcial** · Não disparou.

### ADR-0001 e ADR-0002 (substituídos)

| Gatilho | Situação | Evidência e o que fizemos |
|---|---|---|
| 0001: "Uma entrega pedir ocupação" / a série de ocupação não ser obtida | **Disparou** em 28/09 | A coleta real não trouxe vagas ocupadas. A pergunta mudou para vagas reservadas e o ADR-0003 substituiu o 0001 |
| 0002: scrapers falharem no site real | **Disparou** em 28/09 | Falharam em 4 pontos. O ADR-0004 trocou a raspagem por lote versionado |

### ADR-0003

| Gatilho | Situação | Evidência e o que fizemos |
|---|---|---|
| Fonte com vagas ocupadas (ex.: pedido via LAI) | Não disparou | **Pendência honesta:** o pedido pela Lei de Acesso à Informação não foi feito. É o próximo passo para voltar à pergunta de lotação |
| Coleta das versões curriculares de 2022–2024 | Não disparou | Continuam faltando para 4 dos 5 cursos. A `dim_curriculo_componente` (E3) já está pronta para recebê-las |
| Lote novo com divergências | Não disparou | Só houve um lote (28/09). O loader recusa divergências; não foi preciso decidir |
| Consulta de referência acima de 2 s | Não disparou | Todas abaixo de 10 ms; o q0 otimizado leva 1,9 ms |

### ADR-0004

| Gatilho | Situação | Evidência e o que fizemos |
|---|---|---|
| Coletor automatizado para catálogo, currículo e pré-requisitos | Não disparou | Só o coletor de reservas existe |
| Coletor HTTP falhar ao gerar lote novo | Não disparou | Nenhum lote novo foi gerado no semestre. **Risco:** o coletor não foi exercitado desde 28/09 |

### ADR-0005

| Gatilho | Situação | Evidência e o que fizemos |
|---|---|---|
| Latência < 1 min ou mais de um consumidor da mesma mudança | Não disparou | A Pauta (E4) consome métricas, não eventos de CDC. O Delta do CDC segue com um consumidor |
| Outbox acima de 1 milhão de eventos | Não disparou | Cerca de 3.060 eventos após uma carga e as demonstrações |
| Leitura da série acima de 100 ms ou mais de 100 partições | Não disparou | 9 partições, menos de 1 ms |
| *(não era gatilho, mas mudou a decisão)* Dado pessoal no armazenamento analítico | Revisão na E4 | A análise de LGPD mostrou nomes de docentes no Delta do lote. A coluna saiu (`qtd_docentes` no lugar). Ver [`docs/lgpd.md`](../lgpd.md) |

### ADR-0006

| Gatilho | Situação | Evidência e o que fizemos |
|---|---|---|
| Segunda fonte ou esquema que muda muito | Não disparou | Uma fonte, esquema estável |
| Mais de 10 etapas, grafo não linear ou necessidade de **histórico de execuções** | **Parcial** | O histórico apareceu como necessidade na E4, para provar execução agendada. Foi atendido pelo GitHub Actions (workflow `Publicar painel`, semanal, com histórico na aba Actions), sem trocar para Airflow. O grafo continua linear, agora com cerca de 9 etapas no CI |
| `dbt build` acima de 5 min ou consulta acima de 2 s | Não disparou | `dbt build` em poucos segundos; o `run.sh` completo em 13,6 s |

### ADR-0007

Os gatilhos são novos (E4); nenhum disparou ainda.

## O que esta revisão ensinou

- **Os dois gatilhos que dispararam foram na E1, no primeiro contato com o dado real.** Em ambos a decisão foi revista no mesmo dia. Nenhum gatilho disparado ficou sem revisão.
- **O risco que mais nos preocupa é de dado, não de tecnologia.** A pergunta de gestão depende de um conjunto fixo de obrigatórias, por falta das versões curriculares antigas. E a série tem a mudança de registro de 2023.2, que nenhum ADR trata como gatilho. As duas coisas estão declaradas como limites no painel e na defesa.
