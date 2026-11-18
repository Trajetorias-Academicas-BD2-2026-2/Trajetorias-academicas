# Banco de perguntas da arguição

Resposta curta, de 30 a 60 segundos, e onde está a evidência. As perguntas de gestão vêm primeiro.

## Gestão

| # | Pergunta provável | Resposta | Evidência |
|---|---|---|---|
| G1 | O que a coordenação decide hoje que antes não decidia? | Com quem negociar e o quê. Ex.: Eletrônica tem 79% dos lugares de 2026 vindos de fora da FCTE e 43 de 55 obrigatórias sem nenhum lugar; a Pauta lista essas matérias com o departamento responsável | Painel (cenas 5–7), Pauta |
| G2 | Por que vaga reservada e não lotação? | A série de vagas ocupadas não está nas fontes públicas que testamos. Medir reserva com honestidade vale mais do que inferir lotação sem dado | ADR-0003, cena 1 do painel |
| G3 | Esse número de Software (7×) é real? | É o que o SIGAA publica. A partir de 2023/2 as reservas de 50 vagas ou mais ficaram comuns, o que parece mudança de registro. O painel avisa, e a Pauta pede para confirmar cada reserva grande com o departamento | Cena 4 (marco 2023/2), itens "reserva_grande" |
| G4 | Quanto custa manter? | Zero de infraestrutura: o GitHub Actions roda o pipeline e os testes toda semana e o Pages hospeda. Esforço: um lote novo por semestre | ADR-0007, workflow `Publicar painel` |
| G5 | Quem usa a Pauta e quando? | O coordenador, nas semanas antes da negociação de vagas do semestre seguinte. Marca cada item como revisado | ADR-0007, `e4-etl-reverso.txt` |
| G6 | E se a Pauta sair do ar? | O pipeline não cai. Os itens ficam pendentes e são entregues quando ela volta, sem duplicar | `e4-etl-reverso.txt`, passos 1–4 |
| G7 | Tem risco de LGPD? | O único dado pessoal é o nome de docente, que a UnB publica. Não aparece em nenhuma tela, fica bloqueado por coluna e é descartado em 30/06/2027. O que não conseguimos apagar é o histórico do git, e isso está declarado | `docs/lgpd.md` |
| G8 | Um coordenador pode ver os dados de outro curso? | Não. Recorte de linha: cada coordenador só vê o próprio curso | `e4-acesso.txt` |
| G9 | O que falta para ser usado de verdade? | Pedido via LAI para ter ocupação real, as versões curriculares antigas e a validação das premissas de uso com um coordenador | Retrospectiva, "Dívida técnica" |
| G10 | Por que confiar no painel? | Cada número tem uma definição só, testada contra todas as telas a cada execução. Uma divergência provocada foi pega | `e4-consistencia.txt` |

## Técnica

| # | Pergunta provável | Resposta | Evidência |
|---|---|---|---|
| T1 | Qual a granularidade do fato e por quê? | Uma linha por turma × curso. É a menor unidade do dado (a reserva). A turma já determina disciplina e semestre. Medimos as três granularidades: 1.776 / 676 / 45 linhas | ADR-0006 |
| T2 | Por que estrela, e não Data Vault ou OBT? | Uma fonte e esquema estável. Data Vault triplicaria os objetos sem integração a fazer. Uma tabela única contaria a mesma turma até 5 vezes ao somar por disciplina | ADR-0006 |
| T3 | Como a métrica é calculada? | `lugares_guardados` = soma de "Vgs Reservadas" nas obrigatórias do currículo de referência de 2026.1, definida em `semantica.yml` (MetricFlow, versão 1) | `semantica.yml`, rodapé do painel |
| T4 | Por que MetricFlow e não views? | Centraliza a definição com versão e descrição e gera o dicionário. Com views, a regra do filtro se repetiria em cada uma | ADR-0007 |
| T5 | Como garantem que as telas não divergem? | `tests/metricas_consistentes.py`: MetricFlow, tabela oficial, mart, API do painel e Pauta comparados no CI | `e4-consistencia.txt` |
| T6 | Semântica de entrega do ETL reverso? | At-least-once com fila (outbox) e `Idempotency-Key` por versão. O destino faz upsert, então reenviar não duplica | `etl_reverso.py`, `coordenacao/app.py` |
| T7 | Por que não Debezium na E2? | A recarga completa leva menos de 3 s e o dado muda uma vez por semestre. A outbox mostra a mudança sem JVM e Kafka. Gatilho para trocar: latência abaixo de 1 min ou mais de um consumidor | ADR-0005 |
| T8 | Como o RLS sobrevive ao dbt recriar as tabelas? | Função `aplicar_acesso_analytics()` no `on-run-end` do dbt, e um teste que confere as políticas depois do build | V012, `acesso_checks.sql` |
| T9 | O painel publicado lê o banco? | Não. Lê uma cópia em JSON gerada pelo Actions depois dos testes. Local: lê com o papel `painel`, sem acesso ao OLTP | ADR-0007, `painel.yml` |
| T10 | Como tratam dado atrasado? | Entra na partição do semestre do evento, por reprocessamento de janela, e não na data de ingestão. No fato, o incremental refaz os semestres que receberam linha nova | ADR-0005, ADR-0006 |
| T11 | E a SCD? | `dim_disciplina` por snapshot (tempo de processamento) e `dim_curriculo_componente` (tempo de negócio, versão curricular) | `scd.txt` |
| T12 | Que otimização o EXPLAIN mostrou? | Um CTE agregado sem estatística (estimou 5 linhas, eram 254) levava a 1.681 buscas por índice. A reescrita caiu de 5.721 para 188 buffers. O índice da V008 era idêntico à PK e foi removido | `explain-antes/depois.txt` |
| T13 | Algum gatilho de ADR disparou? | Dois na E1, revistos no mesmo dia. Um parcial na E3 (histórico de execuções → GitHub Actions) | `docs/adr/README.md` |
| T14 | Como seguir uma coluna até a fonte? | Painel → `metricas_oficiais` → MetricFlow → `fct_reservas` → `reserva_vaga` → CSV (SHA-256) → SIGAA "Vgs Reservadas" | `docs/catalogo-e-linhagem.md`, catálogo publicado |
| T15 | Reidentificação? | O painel não mostra turma nem horário. Sem dado de estudante, o risco de células pequenas não se aplica; se entrar matrícula, suprimir k < 5 | `docs/lgpd.md` §6 |

## Perguntas difíceis (ter a resposta pronta)

- **"Vocês corrigiram E1–E3 depois do prazo?"** Sim: na revisão de 17/11 encontramos lacunas reais (CDC de demonstração, EXPLAIN inválido, sem SCD). Corrigimos e registramos no diário. As tags marcam o estado corrigido.
- **"O teste de consistência não é circular?"** Não. Ele compara a tabela que os consumidores leem com o MetricFlow recalculando agora e com o mart da E3, que é um caminho SQL independente. A divergência provocada foi pega pelas duas comparações.
- **"Uma pauta com 169 itens de 'nunca guardou lugar' é útil?"** 23 dos 169 são atividades (estágio, TCC, extensão), que normalmente não reservam vaga. Filtrar por tipo de componente é o próximo ajuste. É uma pergunta legítima para validar com um coordenador.
