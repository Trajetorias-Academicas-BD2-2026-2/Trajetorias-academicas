#!/usr/bin/env bash
# Demonstração do descarte de dado pessoal (LGPD, E4). Saída em docs/evidencias/e4-descarte.txt.
# Roda DENTRO DE UMA TRANSAÇÃO REVERTIDA (ROLLBACK) para não apagar o banco de
# desenvolvimento; ao fim da retenção, a mesma chamada é feita com COMMIT.
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose exec -T db psql -U g2 -d ofertas_unb -X -v ON_ERROR_STOP=1 <<'SQL'
\echo '== 1. Antes: nomes de docente no banco (amostra mascarada nesta evidência: só a inicial) =='
SELECT id, left(nome, 1) || repeat('*', 8) AS nome_mascarado, length(nome) AS tamanho_do_nome FROM public.docente ORDER BY id LIMIT 3;
\echo '== 2. Simulação: o que seria descartado =='
SELECT * FROM operations.descartar_dados_pessoais('simulação', false);
BEGIN;
\echo '== 3. Descarte confirmado (fim da retenção) =='
SELECT * FROM operations.descartar_dados_pessoais('fim da retenção: 30/06/2027', true);
\echo '== 4. Depois: nomes pseudonimizados, vínculos preservados =='
SELECT id, nome FROM public.docente ORDER BY id LIMIT 3;
SELECT count(*) AS docentes_com_nome_real FROM public.docente WHERE nome NOT LIKE 'DOCENTE-%';
SELECT count(*) AS vinculos_turma_docente FROM public.turma_docente;
SELECT motivo, tabela, coluna, linhas FROM operations.descartes ORDER BY id DESC LIMIT 1;
\echo '== 5. Camada analítica e painel: nada muda (não usam nome de docente) =='
SELECT sum(vagas_reservadas) AS lugares_guardados_total FROM analytics.fct_reservas WHERE obrigatoria;
ROLLBACK;
\echo '== 6. Transação revertida: o banco de desenvolvimento continua como estava =='
SELECT count(*) AS docentes_com_nome_real FROM public.docente WHERE nome NOT LIKE 'DOCENTE-%';
SQL
