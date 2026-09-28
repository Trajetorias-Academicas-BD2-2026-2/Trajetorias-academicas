# Semana 07 (22/09 a 28/09)

**Presentes:** ⟨PREENCHER⟩

## O que foi medido
- Nada ainda sobre dados reais: o recorte de `data/raw/` não foi raspado.
- As correções foram testadas num Postgres 16 local com um recorte
  sintético de 9 semestres (registro em [`docs/AI-USAGE.md`](../AI-USAGE.md)):
  - migrações aplicadas num banco novo e num que já tinha a V001;
  - uma migração com erro interrompeu a execução com código 3;
  - a segunda carga do mesmo recorte não inseriu nenhuma linha;
  - o trigger bloqueou UPDATE em `oferta_turma`.
- ⟨PREENCHER: o que a Squad mediu nesta semana, se algo⟩

## O que surpreendeu
- A revisão da E1 contra o checklist de aceite encontrou problemas que a
  Squad não tinha visto:
  - `scrape_cursos.py` inventava a matriz curricular quando a raspagem falhava;
  - `scrape_turmas.py` escondia turmas superlotadas trocando as vagas;
  - `psql` sem `ON_ERROR_STOP` terminava com código 0 mesmo com erro de SQL.
- A E1 carregava só 2026.2, um semestre ainda em andamento. Essa era a
  maior lacuna frente ao checklist de volume.
- ⟨PREENCHER⟩

## O que foi decidido
- Recorte de 2022.1 a 2026.1, só semestres encerrados; o loader recusa
  semestre em andamento (decidido em 28/09;
  [ADR-0001](../adr/0001-modelagem-fonte-origem.md)).
- Recorte bruto versionado em `data/raw/`
  ([ADR-0002](../adr/0002-extracao-via-navegador-real.md)).
- Pergunta de gestão reescrita em uma frase, com sujeito e recorte (README).
- ⟨PREENCHER: quem decidiu⟩

## Próxima semana
- [ ] Rodar a carga real e commitar `data/raw/` (⟨responsável⟩)
- [ ] Gerar `docs/carga-medida.md` e preencher o ADR-0001 (⟨responsável⟩)
- [ ] Definir a taxa de leitura em `docs/carga-de-trabalho.md` (⟨responsável⟩)
- [ ] Combinar com a professora a nova tag da E1 (⟨responsável⟩)
