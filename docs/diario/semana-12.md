# Semana 12 (27/10 a 02/11)

## O que foi medido
- O mart agrega reservas por curso e semestre e preserva a data de ingestão
  para freshness.

## O que surpreendeu
- O volume permite recomputar o recorte inteiro; não foi necessário um
  incremental complexo.

## O que foi decidido
- Usar tabelas dbt materializadas e retry no script de pipeline para manter
  a execução reproduzível.

## Próxima semana
- [ ] Publicar o observatório e executar o backfill.
