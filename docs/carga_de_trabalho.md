# Caracterização da carga de trabalho

## Volume e crescimento

| Tabela | Linhas por carga | Crescimento |
|---|---|---|
| `disciplina` | ~150–400 (por unidade carregada) | baixo — muda pouco entre semestres |
| `curso` | 5 (cursos do Campus Gama) | estático |
| `curso_disciplina` | ~200–500 | baixo |
| `pre_requisito` | ~100–300 | quase estático |
| `oferta_turma` | ~1.000–3.000 por semestre | +1.000 a +3.000 linhas a cada novo semestre carregado (append-only) |


Carregando os últimos 4 semestres: 4.000–12.000 linhas em `oferta_turma`,
volume suficiente para diferenciar um plano de execução com índice de um
sem índice.

## Padrão de escrita

- **Carga em lote**, não transacional: o loader roda uma vez por
  semestre a carregar (manual ou agendado via `docker compose up`), não
  há escrita contínua de usuários no banco.
- `oferta_turma` é append-only; `disciplina`, `curso`, `curso_disciplina`
  e `pre_requisito` fazem upsert (podem ser atualizados quando o SIGAA
  corrige algo, mas raramente).

## Padrão de leitura

Predominam consultas **analíticas e agregadas**, não busca por um
registro único:

1. Série de ocupação de uma disciplina ao longo dos semestres
   (`GROUP BY disciplina, ano, periodo`).
2. Ranking de disciplinas mais citadas em `pre_requisito.pre_requisito_id`.
3. Comparação de taxa de ocupação entre `turno = 'DIURNO'` e
   `turno = 'NOTURNO'` por disciplina.
4. Turmas com `vagas_ocupadas >= vagas_ofertadas` (lotadas) por
   semestre.
5. Disciplinas obrigatórias de um curso (`curso_disciplina.obrigatoria`)
   sem oferta em determinado semestre.

## Latência tolerada

Todas as consultas acima são para apoio à decisão do coordenador, não
tempo real: **1–2 segundos** é aceitável; nada abaixo de 100ms é
exigido.