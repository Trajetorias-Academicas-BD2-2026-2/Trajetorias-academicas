# Caracterização da carga de trabalho

Passo 1 do Método de Decisão. Os **números medidos** (linhas, bytes,
crescimento por semestre, tempo de cada consulta) são gerados a partir do
banco carregado e ficam em [`carga-medida.md`](carga-medida.md):

```bash
docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
```

Este documento descreve o que foi medido e por quê.

## Volume

| Tabela | O que cresce | Crescimento |
|---|---|---|
| `oferta_turma` | uma linha por turma de cada semestre encerrado | a cada semestre, append-only |
| `disciplina` | componentes curriculares da FCTE | quase estático; muda com revisão de currículo |
| `curso` | 5 cursos do Campus Gama | estático |
| `curso_disciplina` | matriz de cada curso | quase estático |
| `pre_requisito` | disciplinas citadas nas expressões de pré-requisito | quase estático |
| `docente` | nomes distintos de docentes nas turmas | cresce devagar |

Recorte carregado: **2022.1 a 2026.1** (9 semestres, 4 anos e meio).
`tests/sanity_checks.sql` exige ao menos 8 semestres consecutivos e 1 000
linhas em `oferta_turma`.

## Cardinalidade

- Uma disciplina tem várias turmas por semestre; uma turma pertence a uma
  disciplina e a um semestre.
- Uma disciplina aparece em vários cursos (N:N), obrigatória em uns e
  optativa em outros.
- As consultas agrupam por disciplina, semestre, turno e curso: poucas
  centenas de disciplinas, 9 semestres, 3 turnos úteis, 5 cursos.

## Taxa de escrita

- **Em lote**, uma carga por semestre encerrado (o loader recusa semestre
  em andamento). Entre cargas, nenhuma escrita.
- `oferta_turma` só recebe INSERT; UPDATE e DELETE são bloqueados por trigger.
- As demais tabelas recebem upsert na mesma carga, com volume desprezível.

## Taxa e padrão de leitura

Poucos usuários (coordenadores de curso), consultas ocasionais,
**analíticas e agregadas**; nenhuma busca por registro único. As
consultas de referência estão em [`db/consultas/`](../db/consultas/):

| Consulta | Pergunta |
|---|---|
| `q0_pergunta_de_gestao.sql` | Obrigatórias mais lotadas por curso e turno, 2022.1–2026.1 |
| `q1_serie_ocupacao.sql` | Série de ocupação de cada disciplina por semestre |
| `q2_ranking_prerequisitos.sql` | Disciplinas que mais aparecem como pré-requisito |
| `q3_diurno_vs_noturno.sql` | Ocupação no diurno x noturno por disciplina |
| `q4_turmas_lotadas.sql` | Turmas lotadas por semestre |
| `q5_obrigatorias_sem_oferta.sql` | Obrigatórias sem turma no último semestre |

## Latência tolerada

Apoio à decisão, não tempo real: **até 2 s por consulta**. Nada exige
resposta abaixo de 100 ms. O `caracterizar.py` compara a mediana de cada
consulta com esse limite.

## Sazonalidade

A escrita acompanha o calendário acadêmico: uma carga após o fim de cada
semestre. A leitura se concentra no planejamento da oferta do semestre
seguinte, antes da matrícula.
