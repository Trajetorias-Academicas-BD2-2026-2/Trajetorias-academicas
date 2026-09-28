# Coleta real do SIGAA — 28/09/2026

## Resultado e limite central

Foram coletados dados reais das páginas públicas do SIGAA, sem login e sem
dados de alunos. A coleta recuperou **1.786 registros de reserva/oferta por
curso**, correspondentes a **735 turmas distintas** pela chave
`(disciplina, turma, ano, período)`, nos cinco cursos e nove semestres de
2022.1 a 2026.1.

**Não foi recuperada a série de vagas ocupadas.** A página de turmas do curso
informa **Vgs Reservadas**, isto é, vagas reservadas àquele curso. Esse valor
não deve ser renomeado para vagas totais ou vagas ocupadas. Logo, a coleta
não basta para responder à pergunta original sobre lotação.

Os dados ficam em `data/coleta_publica_2026-09-28/`. Não foram colocados em
`data/raw/`, pois o loader original espera outra semântica e exige ocupação.
O banco original não foi populado nem foram produzidos benchmarks SQL.

## Dados obtidos

| Conjunto | Quantidade | Observação |
|---|---:|---|
| Catálogo da FCTE | 585 componentes | Inclui disciplinas e atividades, não somente disciplinas obrigatórias |
| Cursos-alvo | 5 | Identificados no agrupamento FCTE da listagem pública |
| Consultas históricas por curso | 45 | Cinco cursos × nove semestres; todas com registros |
| Registros curso–turma–semestre | 1.786 | Sem duplicação da chave com curso |
| Turmas distintas sem curso na chave | 735 | Uma turma pode reservar vagas para vários cursos |
| Estruturas curriculares selecionadas | 6 | Duas versões de Automotiva; uma por cada outro curso |
| Vínculos currículo–componente | 625 | Preserva versão curricular e natureza obrigatória/optativa |
| Componentes com detalhes de pré-requisitos | 23 | **Coleta parcial**, não é um grafo completo de pré-requisitos |

| Curso | Registros históricos |
|---|---:|
| Engenharia de Software | 597 |
| Engenharia Aeroespacial | 285 |
| Engenharia Automotiva | 292 |
| Engenharia de Energia | 308 |
| Engenharia Eletrônica | 304 |

Não interpretar 1.786 como número de turmas únicas: há compartilhamento de
turmas entre cursos. Não somar ou preencher vagas ocupadas com esses números.

## Estruturas preservadas

| Curso | Currículo | Início da vigência |
|---|---|---|
| Software | 6360/2 | 2024.2 |
| Aeroespacial | 60836/3 | 2026.1 |
| Automotiva | 6297/2 | 2021.2 |
| Automotiva | 6297/3 | 2027.1 |
| Energia | 6289/2 | 2024.2 |
| Eletrônica | 6131/3 | 2025.1 |

A listagem marca Automotiva 6297/3 como ativa, embora sua vigência comece em
2027.1. A versão 6297/2 aparece como inativa. Ambas foram preservadas, sem
inferir qual se aplica a cada aluno ou turma histórica. Aeroespacial e Energia
possuem outras versões ativas que não integram este recorte curricular.
Para analisar obrigatoriedade em cada semestre, é necessário completar o
histórico de currículos e definir a regra de vigência; não aplicar a matriz
de 2026 retrospectivamente como se fosse a de 2022.

## Arquivos e significado

- `componentes_catalogo.csv`: código, nome, tipo e carga horária observados na
  listagem da FCTE. A ausência de pré-requisito nesse arquivo não significa
  ausência de pré-requisito no SIGAA.
- `cursos.csv`: cinco cursos, códigos internos do projeto, turno e URL pública.
- `ofertas_por_curso.csv`: disciplina, turma, semestre, curso, docentes,
  horário e **vagas_reservadas**. Chave composta inclui `curso_codigo`.
- `curriculos.csv`: versões selecionadas e início da vigência.
- `curso_disciplina_por_curriculo.csv`: vínculos sem colapsar versões;
  preserva `natureza` e grupo/nível da estrutura.
- `prerequisitos_parciais.csv`: expressões de 23 componentes. Campo `-`
  reproduz a fonte; componentes não coletados não são representados como
  sem pré-requisito. FGA0242 foi capturado inicialmente sem timestamp
  individual, mantido vazio em vez de inventado.
- `resumo_coleta.csv` e `resumo.json`: contagens verificadas.
- `evidencias/`: resultados estruturados extraídos das páginas públicas,
  incluindo as consultas gerais por unidade e detalhes coletados.

As evidências preservam conteúdo tabular público; não contêm cookies ou
credenciais. Horários de coleta registrados usam UTC. A reprodução futura
pode mudar porque a fonte é mutável.

## Como o histórico foi encontrado

O formulário geral em `public/turmas/listar.jsf`, usado pelo scraper original,
não forneceu o histórico esperado para a FCTE: as buscas de 2022.1 a 2025.2
retornaram sem resultados e 2026.1 mostrou somente uma turma, FGA0069/03.
Isso é um resultado da consulta pública, **não evidência de que não houve
outras turmas**. Não foi determinada a regra interna que produz essa diferença.

Já o caminho **Cursos de Graduação → portal do curso → Ensino → Turmas**
retornou registros históricos. Sua tabela tem os campos Período/Ano, Turma,
Docente, Vgs Reservadas e Horários. Ela não contém ocupação.

Fontes:
- https://sigaa.unb.br/sigaa/public/home.jsf
- https://sigaa.unb.br/sigaa/public/curso/lista.jsf?nivel=G&aba=p-graduacao
- URLs individuais dos portais estão em `cursos.csv`.

## Reprodução das ofertas por curso

Foi adicionado um coletor separado, `loader/coletar_ofertas_por_curso.py`,
que descobre os portais pela listagem pública e usa uma sessão HTTP iniciada
na home antes de submeter os formulários JSF. Ele salva um CSV por curso e
semestre, preserva arquivos já existentes e interrompe em caso de semestre
divergente, duplicação ou resultado vazio. Não modifica o loader original.

```bash
python -m pip install requests beautifulsoup4
python loader/coletar_ofertas_por_curso.py --saida data/nova_coleta
```

Teste de uma consulta:

```bash
python loader/coletar_ofertas_por_curso.py --curso FGA_SOFT --semestre 2022.1 --saida data/teste_coleta
```

Os arquivos entregues foram extraídos por navegação nos formulários e leitura
das tabelas renderizadas. O estado da validação do coletor HTTP está no
arquivo `data/coleta_publica_2026-09-28/VALIDACAO.md`.

## Implicações para a E1

1. Para manter a pergunta sobre **lotação**, obter da UnB uma fonte histórica
   de vagas totais e ocupadas por turma, com identificação que permita junção.
2. Se a equipe optar por usar apenas os dados públicos já coletados, uma
   pergunta possível é: “Como evoluiu a oferta de turmas e de vagas reservadas
   aos cinco cursos da FCTE entre 2022.1 e 2026.1?” Essa é uma **proposta**, não
   uma alteração já aplicada ao projeto.
3. Uma adaptação deve modelar a reserva por curso separada da turma, pois a
   mesma turma aparece em vários cursos. O modelo original não recebe esses
   dados corretamente sem mudança de esquema e de carga.
4. Completar os detalhes de pré-requisitos antes de usar o ranking associado.
5. Medir volume e desempenho após carregar o esquema escolhido; contagens de
   CSV não substituem tamanho de tabelas/índices e latências medidas no banco.

## Falhas do scraper original observadas no site real

- O nome da unidade aparece numa linha de agrupamento acima dos cursos;
  procurar GAMA/FCTE em cada linha do curso descarta os cursos-alvo.
- “Estruturas Curriculares” fica em um menu de Ensino e abre uma listagem de
  versões. É necessário abrir uma versão e percorrer as abas dos níveis,
  optativas e complementares para extrair seus componentes.
- Nas matrizes, código, nome e carga horária aparecem juntos na mesma célula;
  exigir uma célula contendo somente o código deixa a extração vazia.
- Nos componentes, a ação disponível chama-se “Detalhes do Componente
  Curricular”; o seletor original por `title*='Exibir'` não corresponde à ação
  observada e pode deixar pré-requisitos sem coleta.

Essas observações são adicionais à revisão estática inicial. A coleta real
não torna automaticamente os scrapers antigos válidos nem conclui a E1.

## Atualização: como o lote passou a ser usado (28/09/2026)

Depois deste relatório, a Squad testou de novo `listar.jsf` para 2023.1 e
2025.2: sem unidade a consulta é recusada (campo obrigatório) e com a
FCTE (ID 673) não há resultados; o seletor não tem opção com o nome antigo
da Faculdade do Gama. Com isso:

- a pergunta de gestão passou a ser sobre **vagas reservadas** por curso
  ([ADR-0003](adr/0003-reservas-por-curso-e-curriculo-versionado.md));
- este lote passou a ser a entrada da carga, lido direto desta pasta e
  conferido pelo `SHA256SUMS.txt` ([ADR-0004](adr/0004-coleta-publica-versionada.md));
- os scrapers Playwright foram removidos;
- o `coletar_ofertas_por_curso.py` passou a gravar no mesmo formato de
  `ofertas_por_curso.csv` e ganhou `--consolidar`.

A conclusão que os testes sustentam é que **não conseguimos obter** a série
de ocupação nas fontes e consultas testadas; isso não prova que não exista
outra fonte pública ou oficial (ver o gatilho de revisão do ADR-0003).
