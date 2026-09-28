# Caracterização da carga de trabalho

Passo 1 do Método de Decisão. Os **números medidos** estão em
[`carga-medida.md`](carga-medida.md), gerado a partir do banco carregado:

```bash
docker compose run --rm -T loader python caracterizar.py > docs/carga-medida.md
```

Este documento descreve o que foi medido e por quê.

## Volume

| Tabela | O que guarda | Medido (lote de 28/09/2026) | Crescimento |
|---|---|---:|---|
| `turma` | uma linha por turma de semestre encerrado que reserva vagas para algum curso | 733 | +71 a +92 por semestre |
| `reserva_vaga` | vagas que uma turma reserva para um curso | 1.776 | +155 a +255 por semestre |
| `turma_docente` | docentes de cada turma | 773 | acompanha `turma` |
| `disciplina` | catálogo da FCTE e disciplinas de outras unidades citadas | 633 | quase estático |
| `curriculo` / `curriculo_componente` | versões curriculares e seus componentes | 6 / 625 | a cada revisão de currículo |
| `curso` | 5 cursos de engenharia do Campus Gama | 5 | estático |

Recorte: **2022.1 a 2026.1** (9 semestres encerrados). O banco inteiro
ocupa 1,1 MB com índices; o lote versionado, 903 kB com evidências.

## Cardinalidade

- Uma turma reserva vagas para 1 a 5 cursos (média 2,42; 38% das turmas
  atendem mais de um curso).
- Uma disciplina pertence a várias versões curriculares, com natureza
  (obrigatória ou optativa) que pode mudar entre versões.
- As consultas agrupam por curso (5) e semestre (9). Turno não entra na
  pergunta: 720 das 733 turmas são diurnas.

## Taxa de escrita

- **Em lote**, uma carga por lote de coleta; só semestres encerrados
  segundo o calendário acadêmico oficial (`data/calendario_academico.csv`).
- `turma`, `turma_docente` e `reserva_vaga` só recebem INSERT (trigger
  bloqueia UPDATE e DELETE).
- Estrutura curricular e catálogo recebem upsert na mesma carga.

## Taxa e padrão de leitura

| Parâmetro | Valor | Origem |
|---|---|---|
| Usuários | 5 coordenadores (um por curso do Gama) | recorte do domínio |
| Consultas por usuário no planejamento | 10 por semana | premissa da Squad |
| Semanas de planejamento por semestre | 4 (antes da matrícula) | premissa da Squad |
| Taxa de leitura no pico | 50 consultas por semana (5 × 10), cerca de 10 por dia útil | cálculo |
| Fora do planejamento | perto de zero | premissa da Squad |
| Total por semestre | cerca de 200 consultas (50 × 4) | cálculo |

A premissa é uma **estimativa da Squad, ainda não validada com um
coordenador**: supõe que cada coordenador consulte a série algumas vezes
por semana enquanto negocia as reservas do semestre seguinte, e quase
nunca fora desse período. Mesmo que a taxa real seja dez vezes maior
(500 consultas por semana), cada consulta de referência leva menos de
10 ms ([carga medida](carga-medida.md)); a leitura não pressiona o banco,
então errar esta premissa não muda nenhuma decisão do ADR-0003.

Todas as consultas são **analíticas e agregadas**; nenhuma busca por
registro único. As consultas de referência estão em
[`db/consultas/`](../db/consultas/):

| Consulta | Pergunta |
|---|---|
| `q0_pergunta_de_gestao.sql` | Vagas reservadas a cada curso nas obrigatórias do currículo de referência de 2026.1, por semestre |
| `q1_serie_reservas_por_curso.sql` | Série de reservas de cada curso, todas as disciplinas |
| `q2_obrigatorias_sem_reserva.sql` | Obrigatórias sem nenhuma reserva para o curso no recorte |
| `q3_reservas_por_unidade_de_origem.sql` | Reservas em disciplinas da FCTE x de outras unidades |
| `q4_turmas_compartilhadas.sql` | Turmas que reservam vagas para mais de um curso |
| `q5_variacao_obrigatorias_2022_2025.sql` | Variação das reservas por obrigatória entre 2022 e 2025 |

## Latência tolerada

Apoio à decisão, não tempo real: **até 2 s por consulta**. Medido: todas
as consultas de referência abaixo de 10 ms.

## Sazonalidade

A escrita acompanha o calendário acadêmico: um lote novo depois do fim de
cada semestre. A leitura se concentra no planejamento da oferta do
semestre seguinte, quando o coordenador negocia as reservas.
