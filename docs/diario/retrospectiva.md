# Retrospectiva do ciclo de vida (E4)

O caminho do dado neste semestre, estágio por estágio. Para cada um: o que planejamos, o que a realidade impôs, o número que provou, o erro que cometemos e corrigimos, e o que faríamos diferente. Os números têm fonte nos diários das semanas 7 a 15 e em `docs/evidencias/`.

## 1. Geração: a fonte

- **Planejado (setembro):** dados de alunos, turmas e componentes da UnB para medir **lotação** de turmas, com a extensão Inep.
- **A realidade:** na coleta de 28/09, a série de vagas **ocupadas** não estava nas fontes públicas testadas. O SIGAA publica só **vagas reservadas** por curso. Os scrapers falharam em 4 pontos do site real.
- **Número:** 45 de 45 consultas curso × semestre coletadas; 1.786 reservas; 0 séries de ocupação.
- **O que fizemos:** trocamos a pergunta (ADR-0003) e a forma de carga, de raspar a cada execução para um lote versionado de 903 kB (ADR-0004). Dois gatilhos dispararam e os dois ADRs foram substituídos no mesmo dia.
- **Faríamos diferente:** um "spike" de coleta na semana 2, antes de modelar. Modelamos ocupação por quatro semanas sem ter visto o dado.

## 2. Armazenamento: o sistema de origem

- **Planejado:** 3FN insert-only para a oferta de turmas.
- **A realidade:** a mesma turma reserva vagas para até 5 cursos (média 2,42). O currículo tem versões, e a obrigatoriedade muda entre elas.
- **Número:** 733 turmas, 1.776 reservas e 9 semestres; triggers insert-only; 10 reservas rejeitadas por divergência entre cursos.
- **Erro corrigido:** o Postgres local na porta 5432 travava o `docker compose up` por minutos. Passou para a porta 5433 (17/11).
- **Faríamos diferente:** coletar todas as versões curriculares desde o início. Sem as de 2022–2024, a pergunta usa um conjunto fixo de 2026.1.

## 3. Ingestão

- **Planejado:** Parquet e um caminho de mudanças.
- **A realidade:** o primeiro CDC capturava uma tabela de demonstração fora do modelo, e o roteiro nunca tinha sido executado ("Docker desligado").
- **Número, depois da correção (17/11):**
  - 3.057 eventos reais;
  - queda antes do checkpoint seguida de reexecução sem duplicar (3.034 linhas antes e depois);
  - dado atrasado entrando na partição do evento (2023.1: 192 → 193).
- **Erros corrigidos:**
  - o consumidor relia a outbox inteira a cada execução;
  - o `deltalake` abortava ao sair ("terminate called"), contornado lendo os arquivos com pyarrow (`delta_io.py`);
  - a medição mostrou que **particionar deixa a leitura 3× mais lenta** neste volume. Mantivemos a partição por causa da escrita, e o ADR diz isso.
- **Faríamos diferente:** escrever o roteiro de demonstração **antes** do código. Ele teria mostrado que o CDC não via o OLTP real.

## 4. Transformação

- **Planejado:** dbt com fato e dimensões.
- **A realidade:**
  - a versão da E3 não tinha SCD;
  - o backfill só contava linhas;
  - o retry era uma falha simulada antes de rodar;
  - o EXPLAIN de antes e o de depois mostravam o **mesmo plano**, porque o índice estava numa tabela que a consulta não lia.
- **Número, depois da correção:**
  - SCD 2 com três versões de FGA0137;
  - backfill de 2024.1 com 174 linhas reprocessadas e o resto intacto;
  - retry com o banco derrubado de propósito;
  - q0 de 5.721 para 188 buffers.
- **Faríamos diferente:** ler o plano de execução antes de criar índice. O índice da V008 era idêntico à chave primária.

## 5. Disponibilização

- **Planejado:** painel e ETL reverso.
- **A realidade:**
  - a mesma métrica era calculada em três lugares;
  - o "ETL reverso" gravava uma tabela que ninguém lia;
  - o painel conectava como superusuário;
  - o nome de docente estava no Delta da E2.
- **Número (E4):**
  - 8 métricas numa definição só, com 586 comparações e 0 divergências;
  - 206 itens na Pauta, entregues depois de o destino voltar do ar e sem duplicar;
  - 16 verificações de acesso;
  - 160 colunas no catálogo, todas descritas;
  - o painel publicado no Pages, de graça.
- **Faríamos diferente:** começar pela pergunta "quem age com este número, e onde?". O painel bonito veio antes do consumidor real (a Pauta), e por isso o ETL reverso da E3 não tinha destino.

## O que levamos

1. **Medir antes de decidir pegou cinco erros que estavam no papel como "feito":**
   - CDC de demonstração;
   - EXPLAIN igual nos dois lados;
   - partição mais lenta;
   - métrica triplicada;
   - nome de docente no Delta.
2. **A opção nula ganhou várias vezes, com número:**
   - recarga de 3 s contra Kafka;
   - script + cron contra Airflow;
   - cópia por arquivo contra servidor sempre ligado.

   Quando não ganhou (ETL reverso por API contra CSV), foi por um motivo concreto: o estado do trabalho do coordenador.
3. **Honestidade sobre limites vale mais que número bonito.** O painel diz "guardado não é ocupado" na primeira cena e avisa sobre a mudança de registro de 2023/2.

## Dívida técnica que fica

- Pedido via LAI para obter vagas ocupadas: não feito (ADR-0003).
- Versões curriculares de 2022–2024: não coletadas.
- Coletor HTTP sem novo lote desde 28/09; não sabemos se ainda funciona com o SIGAA atual.
- A Pauta não é avisada quando um item deixa de existir; ele fica lá.
- Histórico do git com nomes de docentes; o plano de descarte está em `docs/lgpd.md`, sem execução.
