# ADR-0007: Métricas na camada semântica do dbt, consumo por cópia em arquivo e ETL reverso por API com fila de envio

- **Status:** aceito
- **Data:** 2026-11-18
- **Decisores:** Squad G2 — Ana Joyce · Gustavo Alves · Gabriel Lima da Silva · Nathan Abreu · Guilherme Evangelista · Angélica Campos · Davi Araújo

## Contexto

A E4 fecha o ciclo na disponibilização. O dado precisa chegar a quem decide, que é o coordenador de curso antes da negociação de vagas, e voltar para um sistema onde alguém age.

O que encontramos ao reler a E3:

- **A mesma métrica era calculada em três lugares.** O `mart_observatorio.sql` somava as vagas. O JavaScript do painel recalculava a parte "de fora da FCTE" e a cobertura a partir do mart de disciplinas. O `etl_reverso.py` aplicava a própria regra de "50 vagas ou mais". Nada garantia que os três números batessem.
- **O "ETL reverso" gravava `operations.alertas_reserva`, que nenhuma aplicação lia.** Era mais uma tabela, não ETL reverso.
- **O painel conectava como `g2`, dono e superusuário do banco.** Não havia privilégio mínimo.

**Carga** (de [`docs/carga-de-trabalho.md`](../carga-de-trabalho.md)):

- **Volume:** 1.776 reservas.
- **Atualização:** um lote por semestre.
- **Leitura:** 5 coordenadores, cerca de 50 consultas por semana no pico.
- **Latência tolerada:** 2 s por consulta; o mart deve refletir uma carga nova em até 24 h.

## Decisão 1: onde a métrica é definida

| Alternativa | Onde a métrica vive | Medido |
|---|---|---|
| Opção nula da E3: SQL do mart + recálculo em cada consumidor | 3 lugares (SQL, JS, Python) | nada impedia divergência; nenhum teste comparava |
| Views escritas à mão (`metricas_*` em SQL) | 1 lugar por view, mas cada consumidor escolhe a view e o filtro | simples; a regra "obrigatória do currículo de referência" teria de ser repetida em cada view |
| **Camada semântica do dbt (MetricFlow)** | **1 arquivo**: `analytics/models/semantic/semantica.yml`, com 8 métricas, cada uma com descrição em linguagem simples e `meta.versao` | 820 valores; 586 comparações sem divergência; divergência provocada é pega ([`e4-consistencia.txt`](../evidencias/e4-consistencia.txt)) |

**Escolha: MetricFlow** (`dbt-metricflow 0.7.1`, compatível com o dbt 1.8.2 já em uso, sem trocar de versão).

- **Gravação das métricas:** `analytics/semantica.py` pede ao MetricFlow os valores e grava `analytics.metricas_oficiais` na mesma transação. Leva cerca de 9 s, a maior parte em subir o container.
- **Consumidores:** painel, Pauta e CSV leem só essa tabela.
- **Teste de consistência:** `tests/metricas_consistentes.py` compara MetricFlow, tabela oficial, mart, API do painel e Pauta, e falha o CI em qualquer diferença.
- **Divergência provocada:** a evidência mostra o teste pegando uma "correção manual" de 3.816 para 3.900.

**Por que não só views:** a definição continuaria em SQL solto, sem dicionário nem versão, e a regra de filtro se repetiria. O MetricFlow também gera o dicionário que o painel mostra ("Como cada número é calculado").

## Decisão 2: como o consumidor lê

| Caminho | Latência medida (mediana) | Custo | Acoplamento |
|---|---|---|---|
| **Direto do warehouse:** `app.py` → PostgreSQL (`/api/observatorio`) | 8,5 ms (máx. 27 ms), 242 kB | servidor e banco ligados | o leitor precisa de rede até o banco e de um papel de banco |
| **Cópia por arquivo:** JSON publicado no GitHub Pages | 153 ms da internet (máx. 1,0 s no primeiro acesso), 244 kB | zero | nenhum: o leitor não sabe que existe um banco |
| Federação de consultas | — | — | descartada: há um único banco, nada a federar |

**Escolha: os dois, com papéis diferentes.**

- **Público e banca:** leem a **cópia por arquivo** no Pages. Ela é gerada pelo Actions depois que todos os testes passam. Está dentro de 2 s, não expõe banco nem senha e não "dorme".
- **Uso local e demonstração:** leem **direto** do warehouse, com o papel `painel`, que só lê a camada de consumo (V012).

A atualização da cópia por arquivo é semanal ou a cada mudança, com 24 h de folga sobre o SLA. Isso basta para um dado que muda uma vez por semestre.

## Decisão 3: o ETL reverso

| Alternativa | Até o coordenador ver | Destino fora do ar | Duplicação | Tamanho |
|---|---|---|---|---|
| **Opção nula:** CSV por curso a cada execução (`exportar_pauta_csv.py`) | próxima execução; o coordenador precisa buscar o arquivo | não se aplica: o arquivo é escrito no disco do pipeline | o arquivo é reescrito inteiro; o histórico de "revisado" não existe | 43 linhas; 15–63 ms para 206 itens |
| **API com fila de envio (outbox):** `etl_reverso.py` → Pauta da coordenação | ao fim do pipeline (13,6 s para freshness, dbt, semântica, ETL e CSV) | itens ficam pendentes com o erro registrado; o pipeline não falha; a próxima execução entrega | não duplica: `Idempotency-Key` por versão, destino faz upsert | 242 linhas (ETL + regras) + 173 do serviço |

Demonstrado em [`e4-etl-reverso.txt`](../evidencias/e4-etl-reverso.txt):

1. Com a Pauta fora do ar, 206 itens ficaram pendentes.
2. Quando a Pauta voltou, os 206 foram entregues.
3. Rodando de novo sem mudança, nada foi reenviado.
4. Num reenvio forçado da mesma versão, o destino respondeu "já existia" 206 vezes e continuou com 206 itens.
5. O coordenador marcou um item como revisado.

**Escolha: API com fila de envio, mantendo o CSV como saída paralela.**

A opção nula entrega a mesma informação, mas não guarda o estado do trabalho do coordenador: o que ele já revisou e o que mudou desde então. É esse estado que transforma "um número no painel" em "uma pendência resolvida antes da reunião". Quando o valor de um item muda, a Pauta recebe uma versão nova e o item volta para "a revisar".

**Quem consome e o que faz.** Antes de negociar as vagas do semestre seguinte, o coordenador abre a Pauta (`http://localhost:8090`) e trata três tipos de item:

- confirmar com o departamento as reservas de 50 lugares ou mais;
- negociar lugar nas obrigatórias que nunca guardaram nenhum (169 no total);
- entender as quedas de 50% ou mais entre 2022 e 2025.

Depois, marca cada item como revisado.

## Consequências

- **Ganhamos:**
  - uma definição por métrica, versionada e testada contra todos os consumidores;
  - o painel e a Pauta não podem discordar sem o CI acusar;
  - o dado volta para um sistema onde alguém age, com entrega garantida e sem duplicar;
  - privilégio mínimo nos dois consumidores (`painel`, `etl_reverso`).
- **Perdemos:**
  - mais uma dependência (`dbt-metricflow`), que prende o par de versões dbt-core 1.8 / MetricFlow 0.206;
  - mais um serviço no Compose (Pauta);
  - a tabela `metricas_oficiais` é gravada fora do dbt e entra na linhagem como *source*;
  - o MetricFlow não sabe rodar dentro do `dbt build`, por isso o passo extra no `run.sh`.
- **Limite do ETL reverso:** item que deixa de existir é marcado `retirado` na fila, mas a Pauta não é avisada e o item continua lá. Avisar a Pauta é o próximo passo, se a coordenação pedir.

## Gatilhos de revisão

- **Saída do dbt Cloud ou upgrade para dbt 1.9 ou mais novo:** rever o par dbt/MetricFlow, já que o MetricFlow mudou de licença e de pacote entre versões.
- **Mais de 1 consumidor operacional** (ex.: o sistema de matrícula pedir os itens): trocar o envio direto por publicação num tópico.
- **Coordenação precisar ver mudança no mesmo dia:** publicar a cópia por arquivo a cada carga, não toda semana.
- **Algum consumidor precisar de recorte por linha diferente do curso** (ex.: por departamento): ampliar `operations.acesso_curso`.
