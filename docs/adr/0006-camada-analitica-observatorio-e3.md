# ADR-0006: Camada analítica dbt e observatório de reservas da E3

- **Status:** aceito
- **Data:** 2026-11-08
- **Decisores:** Squad G2 — Ana Joyce, Gustavo Alves, Gabriel Lima da Silva, Nathan Abreu, Guilherme Evangelista, Angélica Campos e Davi Araújo

## Contexto

A E3 exige que os dados carregados na E2 sejam transformados em uma camada
analítica reproduzível, validada e consumível por uma aplicação. O projeto
precisa responder à pergunta:

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas para
> cada curso da FCTE nas disciplinas obrigatórias do currículo de referência
> selecionado para 2026.1?

O banco transacional continua sendo a fonte operacional. O dashboard, porém,
não deve recalcular regras diretamente sobre as tabelas do OLTP, porque isso
duplicaria lógica, dificultaria os testes e permitiria que a tela e o ETL
reverso apresentassem métricas diferentes.

## Alternativas consideradas

| Alternativa | Descrição | Resultado |
|---|---|---|
| A | Consultar diretamente `public.turma`, `public.reserva_vaga` e o currículo no dashboard | Rejeitada: acopla a apresentação ao OLTP e espalha regras de negócio |
| B | Criar tabelas analíticas manualmente por scripts SQL sem camada de transformação versionada | Rejeitada: dificulta testes, documentação de linhagem e reprocessamento |
| C | Usar dbt com staging, dimensões, fato e marts, consumidos pelo dashboard e pelo ETL reverso | Escolhida: separa responsabilidades e torna as transformações reproduzíveis |

## Decisão

Adotar a alternativa C com as seguintes regras:

1. O dbt será a camada de transformação entre o OLTP e os consumidores
   analíticos.
2. A fato `fct_reservas` terá uma linha por turma, curso, disciplina e
   semestre, preservando a granularidade necessária para agregações sem
   contar a mesma turma indevidamente.
3. O `mart_observatorio` filtrará as disciplinas obrigatórias do currículo de
   referência de 2026.1 e definirá as métricas oficiais:
   `vagas_reservadas`, `obrigatorias_com_reserva` e `turmas_com_reserva`.
4. O dashboard lerá apenas o mart analítico e oferecerá filtros por curso e
   semestre.
5. O ETL reverso usará as mesmas regras do mart e publicará alertas agregados
   em `operations.alertas_reserva`; ele não escreverá novamente nas tabelas
   de origem.
6. A execução será protegida por testes de unicidade, volume, distribuição e
   freshness. O pipeline também deverá demonstrar retry e backfill.
7. O acesso do dashboard será feito pelo papel `dashboard_reader`, com
   permissão de leitura somente nos objetos necessários da camada analítica e
   operacional.

## Evidências

- 18 testes dbt executados com `PASS=18 WARN=0 ERROR=0 SKIP=0`.
- Fato com 1.776 linhas no recorte carregado.
- ETL reverso com 113 registros agregados.
- Dashboard respondendo em `http://localhost:8080`.
- Evidências de retry, backfill, controle de acesso e planos `EXPLAIN` na
  pasta `docs/evidencias/`.

## Consequências

### Positivas

- A regra de negócio fica centralizada e pode ser testada antes do consumo.
- O dashboard e o ETL reverso utilizam a mesma definição de métrica.
- A linhagem fica explícita: OLTP → staging → fato → mart → consumidores.
- O modelo permite reprocessar um semestre sem alterar a fonte operacional.

### Negativas

- O projeto passa a manter uma ferramenta e uma camada de modelos adicionais.
- O mart precisa ser atualizado após novas cargas do OLTP.
- O recorte responde sobre vagas reservadas publicadas, não sobre ocupação real
  nem sobre a oferta total de vagas.
- O dashboard não deve ser interpretado como sistema transacional.

## Gatilhos de revisão

- Mudança da pergunta de gestão para ocupação real ou demanda de matrícula:
  será necessário obter novas fontes e revisar o modelo.
- Alteração da granularidade da reserva ou do currículo de referência:
  revisar a fato e o mart em novo ADR.
- Crescimento do volume que torne o refresh dbt ou as consultas superiores ao
  SLA de 24 horas para atualização e 2 segundos para consulta:
  avaliar materialização, particionamento ou outro motor analítico.
- Necessidade de atualização em tempo real:
  revisar a estratégia de batch e a integração com o CDC da E2.
