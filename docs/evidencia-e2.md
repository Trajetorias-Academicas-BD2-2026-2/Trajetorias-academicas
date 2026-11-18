# Evidência da E2

Tudo abaixo foi executado num banco recém-criado
(`docker compose down -v && docker compose up --build`), em 17/11/2026. A
saída completa está em [`evidencias/e2-roteiro.txt`](evidencias/e2-roteiro.txt).

```bash
docker compose run --rm --build e2-cdc bash ingestion/run_e2.sh
```

## 1. Lote idempotente

`ingestion/batch_to_delta.py` lê `data/coleta_publica_2026-09-28/ofertas_por_curso.csv`
(SHA-256 `3bba2352…a321df`), grava Parquet zstd em `ano=/periodo=` e a
tabela Delta `analytical/batch/ofertas/delta`.

| Execução | Linhas | Partições | Tempo |
|---|---:|---:|---:|
| 1ª | 1.786 | 9 | 185 ms |
| 2ª (mesma fonte) | 1.786 | 9 | 140 ms |
| janela `--semestre 2024.1` | 174 reescritas | 1 | 82 ms |

A segunda execução reconstrói a tabela e chega às mesmas 1.786 linhas. Não
há append.

## 2. Dado atrasado

`ingestion/demo_atraso.py` acrescenta, a uma cópia da fonte, uma reserva de
2023.1 coletada em 17/11/2026 e reprocessa só a janela 2023.1:

- 2023.1: 192 → 193 linhas; os outros 8 semestres ficam iguais;
- os arquivos das outras partições continuam os mesmos (`arquivos_das_outras_particoes_intactos: true`);
- a linha atrasada fica em `ano=2023/periodo=1`, com `coletado_em` de novembro;
- no fim, a janela é reprocessada a partir da fonte original e a tabela volta ao estado inicial (Delta versão 2).

## 3. CDC sobre o OLTP real

A migração V010 captura `reserva_vaga`, `disciplina` e `curriculo_componente`.

| Passo | O que acontece | Eventos lidos | Linhas no Delta | Checkpoint |
|---|---|---:|---:|---:|
| 3. primeiro consumo | INSERTs da carga (1.776 reservas, 633 disciplinas, 625 componentes) + 23 UPDATEs do próprio upsert do loader | 3.057 | 3.034 | 0 → 3.057 |
| 4. mudança no OLTP | `FGA0137`: nome "… (REVISADA)", 60 h → 90 h | — | — | — |
| 5. queda simulada | MERGE feito, checkpoint **não** avançado | 1 | 3.034 | 3.057 |
| 6. reexecução | relê o mesmo evento; MERGE não duplica | 1 | 3.034 | 3.058 |
| 7. de novo | nada novo | 0 | 3.034 | 3.058 |
| 8. reverter FGA0137 | novo UPDATE, consumido | 1 | 3.034 | 3.059 |

## 4. Verificação

`ingestion/verify_e2.py` (passo 9):

- lote: 1.786 linhas no Delta = 1.786 na fonte;
- CDC: uma linha por `(tabela, chave)`;
- CDC: 1.776 / 633 / 625 linhas = contagens atuais no OLTP;
- CDC: FGA0137 no Delta = valor atual no OLTP.

## Formato e compressão

`ingestion/medir_formatos.py`; tabela completa em
[`evidencias/e2-formatos.txt`](evidencias/e2-formatos.txt) e a
interpretação no [ADR-0005](adr/0005-ingestao-e2.md).
