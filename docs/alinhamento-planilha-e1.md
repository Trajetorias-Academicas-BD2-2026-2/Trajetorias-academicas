# Alinhamento da planilha com a E1

Documento de alinhamento entre a planilha de acompanhamento da disciplina e a
implementação da Entrega E1 do projeto G2.

- Planilha: [acompanhamento BD2](https://docs.google.com/spreadsheets/d/1Wnzigh8YNYRDPBxWrEo3hbZSJzccpGC6mWE-PiaiEig/edit?gid=964426200#gid=964426200)
- Repositório: [Trajetorias-Academicas-BD2-2026-2/Documentation](https://github.com/Trajetorias-Academicas-BD2-2026-2/Documentation)
- Data da conferência: 2026-09-28

## Objetivo

Registrar o que deve ser apresentado na E1, distinguir o que já está
implementado do que é planejamento futuro e evitar que a apresentação prometa
funcionalidades que não fazem parte da fonte transacional atual.

## Escopo implementado na E1

A E1 trata da fonte OLTP de ofertas de disciplinas da FCTE no Campus Gama,
usando páginas públicas do SIGAA e um lote de coleta versionado.

Pergunta de gestão:

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas para
> cada curso da FCTE nas disciplinas obrigatórias do currículo de referência
> selecionado para 2026.1?

O sistema registra **vagas reservadas**, não oferta total e não ocupação da
turma. Essa distinção deve aparecer na apresentação e em qualquer documento que
descreva o resultado.

## O que a planilha mostra

A planilha contém as abas `Identificação`, `1 Fontes`, `2 Formatos`,
`3 Modelos`, `4 Cargas e Engines`, `5 Pipeline` e `ADR`. O painel indica cinco
de sete blocos concluídos, com pendências em `1 Fontes` e `Riscos`.

Parte do preenchimento ainda descreve um escopo mais amplo ou anterior, com:

- dados de alunos, matrícula, cotas e formas de ingresso;
- tempo de formação, evasão, demanda e ocupação;
- Parquet como camada analítica;
- comparação genérica entre PostgreSQL, MySQL e MongoDB.

Esses itens não devem ser apresentados como funcionalidades entregues na E1,
pois não correspondem à carga atual descrita no repositório. Podem permanecer
como planejamento para entregas futuras, desde que sejam identificados como tal.

## Correspondência com a implementação

| Bloco da planilha | Preenchimento coerente com a E1 |
|---|---|
| Identificação | Oferta de disciplinas, turmas e vagas reservadas da FCTE entre 2022.1 e 2026.1 |
| Fontes | Páginas públicas do SIGAA, componentes curriculares, currículos e calendário acadêmico oficial da UnB |
| Formatos | Lote CSV versionado como entrada; PostgreSQL como armazenamento OLTP; checksum para integridade |
| Modelos | `curso`, `disciplina`, `curriculo`, `curriculo_componente`, `semestre_letivo`, `turma`, `reserva_vaga`, `turma_docente` e `docente` |
| Cargas e Engines | Carga semestral de semestres encerrados, PostgreSQL 16, loader Python e Docker Compose |
| Pipeline | Lote versionado, validação, migrações, loader, carga transacional e testes pós-carga |
| ADR | ADR-0003 como decisão aceita de modelagem; ADR-0004 como decisão de coleta versionada |

## Números para a apresentação

Os números medidos no lote atual são:

- 733 turmas;
- 1.776 reservas;
- 633 disciplinas;
- 625 vínculos curriculares;
- 4.660 registros nas tabelas medidas;
- 1.152 kB no banco com dados e índices;
- 9 semestres encerrados, de 2022.1 a 2026.1;
- 155 a 255 reservas por semestre, com média de 197;
- aproximadamente 50 consultas agregadas por semana no pico estimado;
- latência tolerada de 2.000 ms por consulta;
- consulta principal medida em aproximadamente 5,5 ms.

Evidências usadas na escolha da modelagem:

- 38% das turmas reservam vagas para mais de um curso;
- uma turma atende, em média, 2,42 cursos;
- duas versões curriculares da Automotiva diferem em 71 disciplinas;
- o lote versionado ocupa aproximadamente 903 kB com evidências.

## Decisão de modelagem

A decisão aceita é a alternativa C do ADR-0003:

> Modelo normalizado, com `turma` separada de `reserva_vaga`, currículo
> versionado e histórico `insert-only` para turmas, docentes e reservas.

Essa escolha evita contar uma turma várias vezes quando ela atende cursos
diferentes e preserva as versões curriculares. O banco impede alterações
silenciosas por meio de chaves, restrições, triggers e validações do loader.

Os dados de `turma`, `turma_docente` e `reserva_vaga` não são sobrescritos.
Reprocessar o mesmo lote conta como repetição idêntica; uma divergência desfaz a
carga inteira e gera um relatório de diagnóstico.

## Roteiro da apresentação

### 1. Problema

O coordenador de curso precisa comparar a evolução das vagas reservadas para
disciplinas obrigatórias, mas a informação está espalhada nas páginas do SIGAA.

### 2. Pergunta de gestão

Apresentar a pergunta exatamente como definida neste documento e esclarecer que
“vaga reservada” não significa ocupação.

### 3. Fonte e recorte

Mostrar o SIGAA, os cinco cursos e os nove semestres encerrados. Explicar que o
calendário oficial define quando um semestre pode ser carregado.

### 4. Modelo

Mostrar a separação entre `turma` e `reserva_vaga`, além do currículo
versionado. Não é necessário exibir todas as colunas.

### 5. Decisão

Explicar por que CRUD, tabela única e currículo sem versão foram descartados.
Usar os números de turmas compartilhadas e de mudanças curriculares como
evidência.

### 6. Carga e desempenho

Apresentar volume, taxa de escrita, padrão de leitura, latência tolerada e
latência medida.

### 7. Reprodutibilidade

Demonstrar, em uma máquina limpa:

```bash
docker compose down -v
docker compose up --build
docker compose run --rm tests
```

O fluxo sobe o PostgreSQL, aplica as migrações, valida o lote, executa o loader
e roda os testes.

### 8. Limitações

Declarar que a fonte não permite responder se uma turma lotou, qual foi a oferta
total da universidade ou como uma reserva mudou durante o semestre. Também
explicar que o currículo de referência de 2026.1 foi aplicado retrospectivamente
à série.

## Riscos e mitigações

| Risco | Mitigação |
|---|---|
| A fonte não informa ocupação real | Declarar que a métrica é vaga reservada, não lotação |
| Uma turma atende vários cursos | Separar `turma` e `reserva_vaga` |
| O lote pode mudar ou ficar indisponível | Versionar os arquivos e conferir SHA-256 |
| Semestre em andamento distorce a série | Carregar apenas semestres encerrados pelo calendário oficial |
| Currículos mudam ao longo do tempo | Preservar versões e fixar explicitamente o currículo de referência |

## Pendências antes da defesa

1. Atualizar a planilha para separar o escopo implementado da visão futura.
2. Substituir o ADR genérico sobre PostgreSQL e Parquet pelo ADR-0003 na
   narrativa da E1.
3. Preencher a aba `Riscos` com pelo menos três riscos reais e respectivas
   mitigações.
4. Remover ou marcar como futuro o conteúdo sobre alunos, matrículas, cotas,
   tempo de formação e Parquet, caso ele não esteja implementado na versão
   apresentada.
5. Confirmar que a tag `e1` aponta para a versão efetivamente entregue.
6. Conferir a composição da equipe: a planilha e o README consultado listam
   sete pessoas, enquanto o enunciado menciona squads de quatro a cinco
   integrantes.

## Fontes internas

- `README.md`: escopo, execução, testes e estrutura do repositório.
- `docs/adr/0003-reservas-por-curso-e-curriculo-versionado.md`: decisão de modelagem.
- `docs/adr/0004-coleta-publica-versionada.md`: decisão sobre o lote reproduzível.
- `docs/carga-de-trabalho.md`: caracterização da carga.
- `docs/carga-medida.md`: números medidos.
- `docs/historico.md`: política `insert-only` e limites da série.