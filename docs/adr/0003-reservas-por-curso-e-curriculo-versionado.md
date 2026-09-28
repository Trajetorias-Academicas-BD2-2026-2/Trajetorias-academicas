# ADR-0003: Turmas e reservas por curso são registradas insert-only e separadas, com o currículo versionado

- **Status:** aceito (substitui o [ADR-0001](0001-modelagem-fonte-origem.md))
- **Data:** 2026-09-28
- **Decisores:** Squad G2 — Ana Joyce, Gustavo Alves, Gabriel Lima da Silva, Nathan Abreu, Guilherme Evangelista, Angélica Campos e Davi Araújo

## Contexto

O ADR-0001 modelava turmas com vagas ocupadas para medir lotação. Na
coleta de 28/09/2026 ([relatório](../COLETA_SIGAA_2026-09-28.md)) **não
conseguimos obter essa série nas fontes e consultas testadas**:

- a consulta geral de turmas exige unidade e, com a FCTE, não devolveu
  2022.1–2025.2 (2023.1 e 2025.2 conferidos de novo à mão);
- a página de turmas de cada curso só informa as vagas reservadas ao curso;
- o conjunto "Turmas" do portal de dados abertos da UnB é um retrato de
  junho de 2022.

Isso não prova que não exista outra fonte, mas basta para mudar a pergunta
da E1:

> Como evoluíram, entre 2022.1 e 2026.1, as vagas reservadas publicadas
> para cada curso da FCTE nas disciplinas obrigatórias do currículo de
> referência selecionado para 2026.1?

**Carga** (medida em [`docs/carga-medida.md`](../carga-medida.md)):

- Volume: 733 turmas e 1.776 reservas em 9 semestres (2022.1 a 2026.1);
  633 disciplinas e 625 vínculos curriculares; 1.152 kB em disco com índices, banco recém-carregado.
- Escrita: uma carga em lote por semestre encerrado, de 155 a 255 reservas
  (média 197); nenhuma escrita entre cargas.
- Leitura: cerca de 50 consultas agregadas por semana no pico (5
  coordenadores x 10, nas 4 semanas de planejamento; estimativa da Squad,
  em [`docs/carga-de-trabalho.md`](../carga-de-trabalho.md)); nenhuma
  busca de registro único.
- Latência tolerada: 2 000 ms por consulta.

**O que os dados mostram:**
- 38% das turmas reservam vagas para mais de um curso (média de 2,42
  cursos por turma).
- Automotiva tem duas versões curriculares coletadas, que diferem em
  71 disciplinas.
- Reserva não é oferta total nem ocupação.

## Alternativas consideradas

| | Alternativa |
|---|---|
| A | **Opção nula:** uma tabela espelhando a página "Turmas" do curso (uma linha por curso x turma x semestre) |
| B | Normalizado (turma separada da reserva), mas com um único currículo por curso, sem versão |
| C | Normalizado, com turma, reserva por curso e currículo versionado |

As três guardam o histórico insert-only. Sobrescrever a cada carga (CRUD)
foi descartado no ADR-0001, e o motivo continua valendo.

## Medição

Medido por `loader/caracterizar.py` sobre o lote real
(`docker compose run --rm -T loader python caracterizar.py`). `q0` é a
consulta da pergunta de gestão, mediana de 5 execuções.

| Alternativa | Linhas | Tamanho | `q0` (ms) | Dentro de 2 s | Observação medida |
|---|---:|---:|---:|:---:|---|
| A: tabela única | 1.776 | 264 kB | 1,9 | sim | cada turma repetida em média 2,42 vezes |
| B: currículo sem versão | - | - | - | - | Automotiva 6297/2 → 6297/3: 42 disciplinas saem, 25 entram e 4 mudam de natureza (71 no total) |
| **C: escolhida** | 733 turmas + 1.776 reservas | 1.152 kB | 5,5 | sim | cada turma guardada uma vez |

A é mais rápida e menor, mas A e C ficam três ordens de grandeza abaixo
da latência tolerada, então desempenho não decide. O que decide é a
correção:

- **Em A**, contar turmas exige `DISTINCT` em toda consulta; sem ele, a
  contagem sai 2,42 vezes maior.
- **Em B**, a matriz única de Automotiva teria de ficar com uma das
  versões ou misturar as duas. Nas duas escolhas há erro: 67 disciplinas
  pertencem a só uma das versões e 4 mudam de natureza de uma para a outra.

## Decisão

1. **Alternativa C.** Cada tabela guarda uma coisa:
   - `turma`: a turma, uma única vez;
   - `reserva_vaga`: quantas vagas ela reserva para cada curso;
   - `turma_docente`: os docentes da turma, que podem ser vários.
2. **Insert-only** em `turma`, `turma_docente` e `reserva_vaga`, garantido
   por trigger. Quando um lote traz de novo uma turma ou reserva que já
   está no banco:
   - com os mesmos valores, conta como repetição;
   - com valores diferentes (horário, turno, docentes ou vagas), é uma
     divergência: a carga inteira é desfeita e as divergências ficam
     registradas.
3. **Só semestres encerrados**, pela data oficial do calendário
   acadêmico da UnB (`semestre_letivo`, migração V004, com a fonte de
   cada data). O banco recusa uma turma coletada antes do encerramento
   do semestre dela.
4. **Currículo versionado, análise com um conjunto fixo.** O versionamento
   guarda cada versão coletada, com início de vigência. A pergunta,
   porém, aplica de propósito o currículo de referência de 2026.1 (view
   `curriculo_referencia`, fixada em 2026.1 pela migração V005 para não
   mudar quando semestres novos forem carregados) a toda a série. É uma análise retrospectiva:
   "como evoluíram as reservas nas disciplinas que hoje são obrigatórias".
   As versões em vigor em 2022–2024 **não foram coletadas** para 4 dos 5
   cursos (só Automotiva tem a versão de 2021.2), então a série não
   mostra o que era obrigatório em cada semestre.
5. **Dado faltante explícito:**
   - disciplina de outra unidade fica com `unidade_id` NULL;
   - pré-requisito não coletado fica com `pre_requisito_coletado = FALSE`;
   - turma com horário ou docente divergente entre cursos é rejeitada e
     registrada.
6. **Carimbos por papel:**
   - `ano`/`periodo`: quando a turma aconteceu (evento);
   - `coletado_em`: quando o dado foi coletado;
   - `ingerido_em`: quando entrou no banco;
   - `lote` e `fonte`: de onde veio (linhagem).

## Consequências

- **Ganhamos:**
  - a pergunta é respondida sem contar turma em dobro;
  - as versões curriculares ficam preservadas;
  - o banco impede reescrever o passado ou carregar um semestre antes de
    ele encerrar.
- **Perdemos:**
  - Lotação: nenhuma consulta responde se faltaram vagas.
  - Oferta total: só aparecem turmas que reservam vagas. Dos 254 pares
    curso x obrigatória do currículo de referência, 85 têm alguma
    reserva no recorte.
  - O que era obrigatório em cada semestre passado: o conjunto fixo de
    2026.1 é aplicado a toda a série.
  - Pré-requisitos: só 23 dos 585 componentes.
  - Continuidade da série: as reservas de 50 vagas ou mais passam de 4
    por semestre até 2023.1 para 17 a 41 depois, sobretudo em Software.
    Parece mudança na forma de registrar, não necessariamente mais vagas.
- **Custo de reversão:**
  - Voltar à tabela única é uma view sobre C.
  - Voltar à lotação exige outra fonte. `oferta_turma` foi removida na
    V003, mas o esquema dela continua no histórico das migrações.

## Gatilho de revisão

- Uma fonte com vagas ocupadas por turma (ex.: pedido à UnB pela Lei de
  Acesso à Informação) → novo ADR para voltar à pergunta de lotação.
- Coleta das versões curriculares em vigor em 2022–2024 → trocar o
  conjunto fixo pela versão em vigor em cada semestre.
- Um lote novo com divergências → decidir, em ADR, se vira uma nova
  versão da turma (retrato por coleta) ou se o lote é descartado.
- Mediana de qualquer consulta de `db/consultas/` acima de 2 000 ms →
  avaliar view materializada.
