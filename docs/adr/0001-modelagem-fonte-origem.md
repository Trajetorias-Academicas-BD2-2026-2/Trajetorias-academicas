# ADR-0001: A oferta de turmas é registrada insert-only, uma linha por turma e semestre encerrado, num esquema em 3FN

- **Status:** substituído pelo [ADR-0003](0003-reservas-por-curso-e-curriculo-versionado.md) em 2026-09-28
- **Data:** 2026-09-28
- **Decisores:** Squad G2 — Ana Joyce · Gustavo Alves · Gabriel Lima da Silva · Nathan Abreu · Guilherme Evangelista · Angélica Campos · Davi Araújo

> **Substituído antes da carga real.** A coleta de 28/09/2026 mostrou que a série de
> vagas ocupadas não é pública (ver ADR-0003). Os campos de medição ficaram sem
> valor porque este modelo nunca recebeu dados reais; o texto é mantido como registro.

## Contexto

O coordenador de curso decide quais turmas abrir sem ver o histórico de
lotação. A plataforma precisa responder: *entre 2022.1 e 2026.1, quais
disciplinas obrigatórias dos cinco cursos de graduação da FCTE ficaram
lotadas com mais frequência, por turno?* Responder exige comparar
semestres, então o sistema de origem precisa guardar a série histórica.

**Carga** (passo 1; os números vêm da seção "Para copiar no ADR-0001" de
[`docs/carga-medida.md`](../carga-medida.md); detalhamento em
[`docs/carga-de-trabalho.md`](../carga-de-trabalho.md)):

- Volume e escrita: não medidos (o modelo foi substituído antes da carga real).
- Leitura: agregações sobre a série inteira (ocupação por disciplina,
  semestre e turno), nunca busca de registro único.
- Latência tolerada: 2 000 ms por consulta (apoio à decisão, não tempo real).

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

Medido por `loader/caracterizar.py` sobre o recorte real de `data/raw/`
(reproduzível: `docker compose run --rm -T loader python caracterizar.py`).
`q0` é a consulta da pergunta de gestão
([`db/consultas/q0_pergunta_de_gestao.sql`](https://github.com/Trajetorias-Academicas-BD2-2026-2/Trajetorias-academicas/blob/main/db/consultas/q0_pergunta_de_gestao.sql)),
mediana de 5 execuções. C' é a massa de C numa tabela única desnormalizada,
com histórico, para medir se a desnormalização se paga.

| Alternativa | Linhas de oferta | Tamanho total | `q0` (ms) | Dentro de 2 s | Semestres comparáveis |
|---|---:|---:|---:|:---:|---:|
| A: opção nula, tabela única sobrescrita | — | — | não responde | - | 1 |
| B: 3FN com UPDATE (CRUD) | — | — | não responde | - | 1 |
| **C: 3FN insert-only (escolhida)** | — | — | — | — | — |
| C': tabela única com histórico (desnormalizada) | — | — | — | — | — |
| D: insert-only por coleta (4 coletas/semestre, projeção) | — | — | — | - | — |

A e B não respondem à pergunta de gestão porque guardam um único semestre.

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
   duas vezes em agregações sem cuidado. A medição de C x C' não chegou a ser feita. Se a desnormalização passar a
   se pagar, entra como view materializada derivada (ver gatilho).
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
