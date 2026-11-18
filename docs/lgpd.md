# Análise de LGPD do que foi construído (E4)

Esta análise olha artefato por artefato, não só o banco. Para cada dado pessoal, responde: onde está, sob que base legal é tratado, por quanto tempo fica, como é descartado e quem pode ver.

## 1. Inventário

O único dado pessoal coletado é o **nome de docente**, que o SIGAA publica na página de turmas. **Nenhum dado de estudante** foi coletado: nem matrícula, nem nome, nem nota.

| Artefato | Onde | Dado pessoal? | Situação depois da E4 |
|---|---|---|---|
| `public.docente.nome` | OLTP | **Sim**: 98 nomes | Mantido só para conferir divergência entre lotes; **coluna bloqueada** para todos os papéis de consumo (V012) |
| `public.turma_docente` | OLTP | Indireto: liga turma a docente por id | Visível só ao dono e ao `auditor_lgpd`, que não vê o nome |
| `data/coleta_publica_2026-09-28/ofertas_por_curso.csv`, coluna `docentes` | Repositório público | **Sim** | Necessário para a carga reprodutível (E1). Ver o que **não** se apaga (seção 5) |
| `evidencias/sigaa_turmas_coleta.json`, `sigaa_oferta_curso.jsonl`, `sigaa_detalhe_FGA0242.json`, `sigaa_detalhes_coleta.jsonl` | Repositório público | **Sim** | Provas da coleta (ADR-0004); mesma situação do CSV |
| Delta `analytical/batch/ofertas` (E2) | Armazenamento analítico | **Era sim** (coluna `docentes`) | **Removido na E4**: agora só `qtd_docentes` (minimização). Não vai para o git (`.gitignore`) |
| Outbox do CDC (`e2_cdc_outbox`), Delta do CDC | Analítico | Não | Captura `reserva_vaga`, `disciplina` e `curriculo_componente`; nenhuma delas tem nome de pessoa |
| Schema `analytics` (marts, fato, métricas) | Analítico | Não | Nenhuma coluna de pessoa (o catálogo marca `dado_pessoal: false` em cada modelo) |
| Painel, `observatorio.json` no Pages, Pauta, CSV da pauta | Consumo | Não | Só curso, disciplina, semestre e números |
| Camada vetorial (`ml`) | Analítico | Não | Vetoriza nomes de disciplina e curso |
| `debug/rejeitados.csv`, `debug/divergencias.csv` | Disco local do pipeline | **Pode ter** | Fora do git (`.gitignore`); apagados junto com o ambiente (`docker compose down -v` não os apaga, apague a pasta `debug/`) |
| Evidências em `docs/evidencias/` | Repositório público | Não | A evidência do descarte mostra o nome **mascarado** (só a inicial) |

## 2. Base legal e finalidade

- **Finalidade:** estudo acadêmico sobre a oferta de vagas para os cursos de engenharia da FCTE, na disciplina Sistemas de Banco de Dados 2. O nome do docente **não é necessário** para nenhuma métrica. Ele entra só porque vem na mesma página da reserva e serve para detectar divergência entre lotes.
- **Base legal:**
  - **LGPD, art. 7º, §§ 3º e 4º.** O dado foi tornado manifestamente público pela própria UnB no SIGAA. O tratamento respeita a finalidade, a boa-fé e o interesse público que justificaram a publicação, que é a transparência da oferta acadêmica.
  - **Lei 12.527/2011 (LAI).** A atuação do servidor público, como "quem ministra qual turma", é informação de interesse público.
  - **LGPD, art. 7º, IV (estudos por órgão de pesquisa).** Cabe se o projeto for assumido pela UnB. **Ressalva:** essa base precisa ser confirmada pela universidade e pelo encarregado de dados antes de qualquer uso institucional.
- **O que não fazemos:**
  - não cruzamos o nome do docente com outra base;
  - não publicamos o nome em nenhuma tela;
  - não usamos o nome para avaliar o docente.

## 3. Minimização aplicada no código

| Onde | Antes | Depois (E4) |
|---|---|---|
| Lote Delta da E2 (`ingestion/batch_to_delta.py`) | coluna `docentes` com os nomes | `qtd_docentes` (só a contagem) |
| Painel (`dashboard/app.py`) | conectava como `g2`, que lia tudo | papel `painel`, sem acesso a `public` |
| ETL reverso | conectava como `g2` | papel `etl_reverso`: lê métricas, escreve só a fila |
| Auditoria | — | `auditor_lgpd`: conta docentes por id, `permission denied` na coluna `nome` |

Evidência do recorte de coluna: [`e4-acesso.txt`](evidencias/e4-acesso.txt).

## 4. Retenção e descarte

- **Retenção:** até **30/06/2027**, que é o fim da disciplina (31/12/2026) mais 6 meses para eventual revisão de nota.
- **Descarte no banco:** `operations.descartar_dados_pessoais(motivo, true)` (V014) **pseudonimiza** `docente.nome` para `DOCENTE-<id>`.
  - Os vínculos `turma_docente` continuam, com a contagem de docentes por turma, mas sem identificar ninguém.
  - Cada execução é registrada em `operations.descartes`, com quando, quem, motivo e quantas linhas.
  - Com `false`, a função só simula.
- **Demonstração:** [`e4-descarte.txt`](evidencias/e4-descarte.txt). Simulação: 98 nomes. Descarte: 0 nomes reais restantes, 773 vínculos preservados e painel inalterado (22.943 lugares). Para não apagar o banco de desenvolvimento, a demonstração roda numa transação revertida; no fim da retenção, a chamada é a mesma, com COMMIT.
- **Delta do lote:** já não tem nomes. **Delta do CDC:** nunca teve.

## 5. O que **não** se apaga, e o que faríamos

- **O lote e as evidências estão no histórico público do git.** Pseudonimizar o arquivo na `main` não apaga os commits antigos. O descarte completo exige reescrever o histórico (`git filter-repo` no `ofertas_por_curso.csv` e nas evidências JSON) e pedir aos forks e clones que apaguem as cópias.
  - **Decisão da Squad:** não reescrever agora, porque a E1 depende do lote para ser reproduzível e a correção da disciplina usa as tags.
  - **Ao fim da retenção:** substituir o lote por uma versão pseudonimizada, reescrever o histórico e avisar a monitoria. Os passos estão descritos aqui, mas não foram executados.
- **O dado continua público no SIGAA.** A Squad não controla essa fonte. O descarte vale para as nossas cópias.
- **Depois de pseudonimizar o banco, recarregar o mesmo lote original geraria divergência**, porque os nomes não batem mais com os pseudônimos. O loader recusaria o lote, e esse é o comportamento certo. A recarga, a partir daí, deve usar o lote pseudonimizado.

## 6. Risco de reidentificação

Duas bases "inofensivas" podem identificar alguém juntas.

| Combinação | Risco | Mitigação |
|---|---|---|
| Painel (curso, disciplina, semestre) + oferta pública do SIGAA (turma, horário, docente) | Com turma e horário seria possível saber qual docente teve a reserva | O painel e a Pauta **não mostram turma nem horário**, só agregados por curso, disciplina e semestre |
| Disciplina com uma única turma no semestre | Com uma turma só, "disciplina × semestre" aponta para a turma e, com o SIGAA, para o docente | O número é sobre vagas reservadas da turma, que a UnB já publica junto com o nome; **não acrescentamos** informação sobre a pessoa. Não publicamos nada sobre desempenho ou carga do docente |
| Reservas muito pequenas (1–2 vagas) | Em dados de estudantes, valores pequenos permitem reidentificar; aqui não há estudante | Não se aplica a estudantes, porque não há dado deles. Se a plataforma ganhar dado de matrícula, aplicar supressão de células pequenas (k ≥ 5) antes de publicar |
| Delta do lote com nomes + painel | Existia até a E3 | Eliminado na E4 (`qtd_docentes`) |

## 7. Direitos do titular

- **Pedido de acesso, correção ou eliminação de um docente:** ele pode procurar o encarregado de dados da UnB ou a Squad, pelos contatos no repositório.
- **O que fazemos:** pseudonimizar o docente em todas as cópias sob nosso controle, usando a mesma função de descarte filtrada pelo id, e registrar o pedido em `operations.descartes`.
- **Prazo:** 15 dias, por analogia com o art. 19 da LGPD.
