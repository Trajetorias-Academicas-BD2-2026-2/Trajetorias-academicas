# Recorte versionado

CSVs brutos raspados do SIGAA, um arquivo por fonte e um por semestre de
turmas (`turmas_<ano>_<periodo>.csv`). São a entrada do `load_to_db.py`.

- Gerados pelos scrapers em `loader/`; cada linha traz `fonte`, `carga_id`
  e `coletado_em` (quando foi raspada).
- Estão no git para que qualquer pessoa suba o banco igual, sem depender
  de o SIGAA estar no ar ou de o layout dele não ter mudado.
- Para raspar tudo de novo: `RASPAR=1 docker compose up --build loader`,
  revisar o diff e commitar.
