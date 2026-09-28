# ADR-0001: A oferta de turmas é registrada insert-only, uma linha por turma e semestre encerrado, num esquema em 3FN

- **Status:** aceito
- **Data:** 2026-09-28
- **Decisores:** Squad G2 — [Ana Joyce, Gustavo Alves, Gabriel Lima da Silva, Nathan Abreu, Guilherme Evangelista, Angélica, Davi Araújo]

## Contexto

O coordenador de curso decide quais turmas abrir sem ver o histórico de
lotação. A plataforma precisa responder: *entre 2022.1 e 2026.1, quais
disciplinas obrigatórias dos cinco cursos de graduação da FCTE ficaram
lotadas com mais frequência, por turno?* Responder exige comparar
semestres, então o sistema de origem precisa guardar a série histórica.

**Carga** (passo 1; números medidos em [`docs/carga-medida.md`](../carga-medida.md),
detalhamento em [`docs/carga-de-trabalho.md`](../carga-de-trabalho.md)):

- Escrita: em lote, uma vez por semestre encerrado; nenhuma escrita
  transacional de usuário. Apenas `oferta_turma` cresce, uma carga por
  semestre; as demais tabelas são quase estáticas.
- Leitura: agregações sobre a série inteira (ocupação por disciplina,
  semestre e turno), nunca busca de registro único.
- Latência tolerada: 2 s por consulta (apoio à decisão, não tempo real).

**Restrições:** a fonte é raspada do SIGAA, sem API (ver ADR-0002); a
ocupação de uma turma muda enquanto o semestre está em andamento; a Squad
domina PostgreSQL; a E2 vai capturar mudanças deste banco (CDC).

## Alternativas consideradas

| | Alternativa | Preserva a série por semestre? | Observação |
|---|---|---|---|
| A | **Opção nula:** tabela única espelhando a listagem do SIGAA, sobrescrita a cada carga | Não | Menor esforço; cada carga apaga a anterior |
| B | 3FN, `oferta_turma` com UPDATE de vagas a cada carga (CRUD) | Não | Guarda só o último valor de cada turma |
| C | 3FN, `oferta_turma` insert-only, uma linha por turma e semestre **encerrado** | Sim | Escolhida |
| D | 3FN, insert-only por **coleta** (`coletado_em` na chave), incluindo semestre em andamento | Sim, e também dentro do semestre | Volume multiplicado pelo número de coletas; toda consulta precisa escolher "qual retrato" |

## Medição

`loader/caracterizar.py` compara, sobre os dados reais carregados, o
esquema 3FN com a mesma massa de dados numa tabela única desnormalizada
(alternativa A sem a sobrescrita): número de linhas, espaço em disco e
tempo da consulta da pergunta de gestão (`db/consultas/q0_pergunta_de_gestao.sql`).
Resultado na seção "Medição do ADR-0001" de [`docs/carga-medida.md`](../carga-medida.md).

## Decisão

1. **Histórico:** `oferta_turma` é insert-only, com chave
   `(disciplina, turma, ano, período)`, e só recebe semestres encerrados
   (o loader recusa semestre em andamento). Um trigger bloqueia UPDATE,
   DELETE e TRUNCATE. Estrutura curricular (`disciplina`, `curso`,
   `curso_disciplina`, `pre_requisito`) usa upsert: a pergunta não compara
   versões da matriz. Detalhes em [`docs/historico.md`](../historico.md).
2. **Normalização em 3FN.** A tabela única repete nome e carga horária da
   disciplina, docente e curso em cada turma, e multiplica cada turma pelo
   número de cursos em que a disciplina aparece, o que conta a mesma turma
   duas vezes em agregações sem cuidado. Neste volume, as duas
   alternativas ficam muito abaixo da latência tolerada, então a
   desnormalização não se paga; se passar a se pagar, entra como view
   materializada derivada (ver gatilho).
3. **Carimbos de tempo por papel:** `ano`/`periodo` = quando a oferta
   aconteceu (tempo do evento); `coletado_em` = quando o SIGAA foi raspado;
   `ingerido_em` = quando a linha entrou no banco. Todos com fuso
   (`TIMESTAMPTZ`).
4. **Linhagem:** toda linha de `oferta_turma` carrega `fonte` e `carga_id`.
5. **Pré-requisitos:** a expressão E/OU do SIGAA fica em
   `disciplina.pre_requisito_expressao`; `pre_requisito` guarda as
   disciplinas citadas, que é o que o ranking "quais disciplinas mais
   travam a grade" precisa.
6. **SGBD:** PostgreSQL (opção nula de tecnologia): a carga é pequena e
   relacional, e a E2 pode usar replicação lógica para CDC.

## Consequências

- **Ganhamos:** série de ocupação comparável entre semestres; o banco
  impede reescrever o passado; cada número tem origem rastreável.
- **Perdemos:** a evolução da ocupação *durante* o semestre (matrícula,
  ajustes); o histórico da matriz curricular e dos pré-requisitos; mais de
  um docente por turma (só o primeiro é guardado); o semestre corrente
  só entra depois de encerrado.
- **Custo de reversão:** migrar para D é barato (acrescentar `coletado_em`
  à chave; as linhas atuais viram o primeiro retrato). Voltar para A ou B
  é irreversível para o que for sobrescrito depois. Desnormalizar é uma
  view materializada sobre o esquema atual.

## Gatilho de revisão

- Mediana de qualquer consulta de `db/consultas/` acima de 2 000 ms em
  `docs/carga-medida.md` → avaliar view materializada (desnormalização).
- Uma entrega pedir ocupação durante a matrícula → migrar para a alternativa D.
- `oferta_turma` acima de 1 milhão de linhas → rever índices e particionamento
  por `ano`.
