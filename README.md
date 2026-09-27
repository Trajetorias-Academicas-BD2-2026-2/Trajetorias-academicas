# G2 — Oferta de Disciplinas UnB (Projeto Integrado BD2, E1)

Fonte transacional (OLTP) que apoia o coordenador de curso a decidir
quais disciplinas ofertar, a partir de três fontes públicas do SIGAA:
**Consulta de Turmas**, **Busca de Componentes Curriculares** e a
**listagem pública de cursos de graduação**.

## Pergunta de gestão

> Quais disciplinas obrigatórias, por curso e turno, têm demanda
> reprimida (turmas lotadas ou poucas turmas ofertadas) nos últimos
> semestres, e quais mais travam a grade por serem pré-requisito de
> outras?

Perguntas derivadas que o esquema também suporta:
- Quantas turmas de cada disciplina abrem por semestre, e isso está
  crescendo ou diminuindo?
- Quais disciplinas vivem no limite de vagas?
- O aluno do turno noturno tem o mesmo acesso a disciplinas
  obrigatórias que o do diurno?

## Domínio e persona

Persona: coordenador de curso de graduação da UnB, que hoje decide quais
turmas abrir "no olho", sem visibilidade histórica de lotação, o que
gera turmas lotadas e atraso na formatura dos alunos.

## Tecnologias

| Camada | Escolha |
|---|---|
| Banco de dados | PostgreSQL 16 |
| Migração | SQL puro, aplicado em ordem por um container `migrate` |
| Extração (loader) | Python + Playwright (browser real, não requests puro, ver [por quê](#por-que-um-browser-real-para-raspar)) |
| Orquestração | Docker Compose |

## Como rodar

Pré-requisito: Docker e Docker Compose instalados.

```bash
docker compose up --build
```

Isso sobe o Postgres, aplica as migrações em `db/migrations/` e roda o
loader (as três raspagens + a carga no banco), nessa ordem:

1. `scrape_componentes.py` — disciplinas, carga horária e pré-requisitos
2. `scrape_cursos.py` — cursos do Gama e sua matriz curricular
3. `scrape_turmas.py` — oferta de turmas do semestre configurado
4. `load_to_db.py` — carrega os CSVs de staging no banco, de forma idempotente

Ao final, o banco `ofertas_unb` está populado.

Se quiser reiniciar do zero (banco limpo):

```bash
docker compose down -v
docker compose up --build
```

Para carregar outra unidade, ano ou período, ajuste as variáveis de
ambiente do serviço `loader` no `docker-compose.yml`:

```yaml
SIGAA_UNIDADE: "CAMPUS UNB GAMA: FACULDADE DE CIÊNCIAS E TECNOLOGIAS EM ENGENHARIA - BRASÍLIA"
SIGAA_ANO: "2026"
SIGAA_PERIODO: "2"
```

## Verificação

```bash
psql -h localhost -U g2 -d ofertas_unb -f tests/sanity_checks.sql
```

Contagem rápida por tabela:

```sql
SELECT 'disciplina', count(*) FROM disciplina
UNION ALL SELECT 'curso', count(*) FROM curso
UNION ALL SELECT 'curso_disciplina', count(*) FROM curso_disciplina
UNION ALL SELECT 'oferta_turma', count(*) FROM oferta_turma
UNION ALL SELECT 'pre_requisito', count(*) FROM pre_requisito;
```

Ou, sem escrever SQL, abra o banco com o [DBeaver](https://dbeaver.io)
(Host `localhost`, porta `5432`, banco `ofertas_unb`, usuário `g2`,
senha `g2_dev_only`) e navegue pelas tabelas.

## Estrutura do repositório

```
db/migrations/    esquema versionado, aplicado em ordem pelo serviço migrate
docs/
    adr/0001-modelagem-fonte-origem.md   decisões de modelagem e por quê
    AI-USAGE.md       uso de IA no projeto e como cada solução foi validada
    carga-de-trabalho.md
    historico.md                         por que oferta_turma é insert-only
loader/           scrapers (Playwright) + carga idempotente no banco
  config.py         URLs, filtros (unidade/ano/período) e flags de diagnóstico
  sigaa_utils.py    utilitários compartilhados (seleção tolerante, disfarce do navegador)
  scrape_componentes.py
  scrape_cursos.py
  scrape_turmas.py
  load_to_db.py
  run.sh            orquestra as quatro etapas acima
tests/            testes de sanidade pós-carga
docker-compose.yml
README.md
```

## Decisões principais

Resumo, o raciocínio completo está no ADR:

- **`oferta_turma` é insert-only** (uma linha por turma por semestre),
  para preservar a série histórica que a pergunta de gestão exige. O
  restante do esquema (`disciplina`, `curso`, `pre_requisito`) usa
  upsert, porque muda raramente e não faz parte da comparação temporal.
- **Linhagem em toda oferta**: cada linha carrega `fonte`, `carga_id` e
  `ingerido_em`, para rastrear de qual execução do loader ela veio,
  necessário porque a fonte é raspada, não uma API estável.
- Ver `docs/adr/0001-modelagem-fonte-origem.md`, para a justificativa
  completa de cada decisão.

## Por que um browser real para raspar

As páginas do SIGAA são formulários JSF com postback (não uma API REST
simples). Duas descobertas moldaram o loader:

- Acessar a URL de busca **direto** (sem passar pela home) gera uma
  sessão com estado inválido, toda tentativa de busca é redirecionada
  de volta para a página inicial. É preciso chegar pela URL com o
  parâmetro `?aba=p-ensino`/`?aba=p-graduacao`, do jeito que um usuário
  real chegaria clicando num link.
- Alguns campos do formulário (ex.: "Unidade Responsável") só valem como
  filtro se a checkbox ao lado estiver marcada — selecionar o valor no
  menu sozinho não basta.

Ambos os problemas só apareceram testando contra o site real, e por isso
o loader usa Playwright (um browser de verdade) em vez de requisições
HTTP diretas, reduz a chance de depender de detalhes internos do
formulário que mudam entre versões.

## Uso de IA

Ver [`AI-USAGE.md`](docs/AI-USAGE.md) para o registro de onde e como IA foi usada, e como
cada decisão foi validada antes de entrar no código.
