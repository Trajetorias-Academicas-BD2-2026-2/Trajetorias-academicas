# Carga de trabalho medida

Gerado por `loader/caracterizar.py` em 2026-09-28 14:35 UTC, sobre o banco carregado com o lote `coleta_publica_2026-09-28` (PostgreSQL 16.13). Não edite à mão: rode o script de novo.

## Volume por tabela

| Tabela | Linhas | Tamanho (dados + índices) |
|---|---:|---:|
| `unidade` | 1 | 40 kB |
| `disciplina` | 633 | 176 kB |
| `curso` | 5 | 48 kB |
| `curriculo` | 6 | 40 kB |
| `curriculo_componente` | 625 | 136 kB |
| `docente` | 98 | 40 kB |
| `semestre_letivo` | 10 | 32 kB |
| `turma` | 733 | 208 kB |
| `turma_docente` | 773 | 104 kB |
| `reserva_vaga` | 1776 | 328 kB |
| **total** | 4660 | 1.152 kB |

Lote versionado em `data/coleta_publica_2026-09-28/`: 903 kB com evidências (limite para versionar: 5 MB).

## Por semestre (taxa de escrita)

| Semestre | Turmas | Reservas (turma x curso) | Vagas reservadas | Turmas de outras unidades |
|---|---:|---:|---:|---:|
| 2022.1 | 92 | 255 | 1796 | 32 |
| 2022.2 | 85 | 251 | 1660 | 33 |
| 2023.1 | 71 | 192 | 1491 | 23 |
| 2023.2 | 82 | 193 | 2836 | 22 |
| 2024.1 | 79 | 174 | 3167 | 22 |
| 2024.2 | 75 | 162 | 3401 | 20 |
| 2025.1 | 80 | 155 | 4769 | 17 |
| 2025.2 | 78 | 170 | 4527 | 23 |
| 2026.1 | 91 | 224 | 4310 | 30 |

- Escrita: uma carga em lote por semestre encerrado: 71 a 92 turmas (média 81) e 155 a 255 reservas (média 197); nenhuma escrita entre cargas.
- Crescimento: cerca de +81 turmas e +197 reservas por semestre, +395 reservas por ano.

## Qualidade e dado faltante

- Turmas que reservam vagas para mais de um curso: 38.3% (média de 2.42 cursos por turma).
- Turno das turmas: DIURNO 720, INTEGRAL 10, NOTURNO 3.
- Obrigatórias dos currículos de referência com ao menos uma reserva no recorte: 85 de 254 pares curso x disciplina.
- Pré-requisitos coletados: 23 de 585 componentes da FCTE.
- Reservas de 50 vagas ou mais, por semestre: 2022.1: 4 (270 vagas), 2022.2: 4 (280 vagas), 2023.1: 4 (280 vagas), 2023.2: 17 (1395 vagas), 2024.1: 25 (2181 vagas), 2024.2: 28 (2320 vagas), 2025.1: 41 (3891 vagas), 2025.2: 40 (3870 vagas), 2026.1: 39 (3226 vagas). Uma mudança brusca aqui indica mudança na forma de registrar a reserva, não necessariamente mais vagas.
- Linhas rejeitadas na última carga (reserva_vaga: turma com horário/docente divergente entre cursos): 10

## Consultas de referência (mediana de 5 execuções, latência tolerada 2000 ms)

| Consulta | Tempo (ms) | Usa índice | Dentro da latência |
|---|---:|:---:|:---:|
| `q0_pergunta_de_gestao.sql` | 5.6 | sim | sim |
| `q1_serie_reservas_por_curso.sql` | 1.2 | não | sim |
| `q2_obrigatorias_sem_reserva.sql` | 1.4 | não | sim |
| `q3_reservas_por_unidade_de_origem.sql` | 1.6 | não | sim |
| `q4_turmas_compartilhadas.sql` | 0.9 | não | sim |
| `q5_variacao_obrigatorias_2022_2025.sql` | 2.5 | não | sim |

## Para copiar no ADR-0003

Os blocos abaixo têm o mesmo formato das seções **Contexto** e **Medição** do ADR-0003.

### Contexto: carga

- Volume: 733 turmas e 1776 reservas em 9 semestres (2022.1 a 2026.1); 633 disciplinas, 625 vínculos curriculares; 1.152 kB em disco com índices.
- Escrita: uma carga em lote por semestre encerrado, de 155 a 255 reservas (média 197); nenhuma escrita entre cargas.
- Latência tolerada: 2000 ms por consulta.

### Medição

| Alternativa | Linhas | Tamanho | `q0` (ms) | Dentro de 2 s | Observação medida |
|---|---:|---:|---:|:---:|---|
| A: opção nula, tabela única espelhando a página do curso | 1776 | 264 kB | 1.9 | sim | cada turma repetida em média 2.42 vezes (1776 linhas para 733 turmas) |
| B: normalizado, currículo sem versão | - | - | - | - | FGA_AUTO 6297/2 → 6297/3: 42 saem, 25 entram, 4 mudam de natureza (71 disciplinas) |
| **C: normalizado, turma + reserva + currículo versionado (escolhida)** | 733 turmas + 1776 reservas | 1.152 kB | 5.5 | sim | cada turma guardada uma vez |
