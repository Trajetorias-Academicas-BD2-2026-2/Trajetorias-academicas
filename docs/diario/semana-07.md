# Semana 07 (22/09 a 28/09)

**Presentes:** ⟨PREENCHER⟩

## O que foi medido
- Coleta real do SIGAA em 28/09
  ([relatório](../COLETA_SIGAA_2026-09-28.md), lote em
  `data/coleta_publica_2026-09-28/`):
  - 45 consultas curso x semestre (5 cursos, 2022.1 a 2026.1);
  - 1.786 reservas, 585 componentes da FCTE, 6 versões curriculares;
  - pré-requisitos de 23 componentes.
- Teste manual de `listar.jsf` para 2023.1 e 2025.2 (Davi Araújo):
  - sem unidade a consulta é recusada;
  - com a FCTE (ID 673) não há resultados;
  - o seletor não tem opção com o nome antigo da Faculdade do Gama.
- Carga do lote no modelo novo (V003), num Postgres 16 local:
  - 733 turmas e 1.776 reservas; 10 reservas rejeitadas (2 turmas com
    horário ou docente divergente entre cursos);
  - todos os testes de dados passaram;
  - consultas de referência abaixo de 10 ms ([carga medida](../carga-medida.md)).

## O que surpreendeu
- Não conseguimos obter a série de vagas ocupadas da FCTE nas fontes e
  consultas testadas: a página do curso só mostra vagas reservadas, e a
  consulta geral não devolveu o histórico.
- Os scrapers Playwright falharam em quatro pontos do site real.
- As reservas cobrem só parte da oferta: 85 de 254 pares curso x
  obrigatória têm alguma reserva no recorte.
- A partir de 2023.2, as reservas de 50 vagas ou mais saltam de 4 para 17
  a 41 por semestre, sobretudo em Software.
- 38% das turmas reservam vagas para mais de um curso.
- Revisão externa do zip apontou cinco problemas, todos procedentes, entre
  eles a contagem errada de diferenças curriculares no ADR-0003 (75, o
  certo é 71) e a regra de semestre encerrado aproximada pelo mês.

## O que foi decidido
- Recorte de 2022.1 a 2026.1, só semestres encerrados.
- Pergunta de gestão passou de lotação para vagas reservadas nas
  obrigatórias do currículo de referência de 2026.1, sem turno
  ([ADR-0003](../adr/0003-reservas-por-curso-e-curriculo-versionado.md)).
- Semestre encerrado pelo calendário oficial da UnB (V004); lote que
  diverge do banco é recusado.
- Currículo de referência fixado em 2026.1 (V005).
- Premissa de leitura: 5 coordenadores × 10 consultas por semana, nas 4
  semanas de planejamento (estimativa, a validar).
- Modelo novo pela migração V003, substituindo o do ADR-0001.
- A carga lê o lote versionado e conferido por checksum; scrapers
  Playwright removidos ([ADR-0004](../adr/0004-coleta-publica-versionada.md)).
- Decisões acima tomadas por Davi Araújo em 28/09, na revisão da E1 com
  apoio de IA; ⟨PREENCHER: confirmação da Squad⟩

## Próxima semana
- [ ] Subir tudo com `docker compose` numa máquina limpa e rodar os testes (⟨PREENCHER: responsável⟩)
- [ ] Validar com um coordenador a premissa de leitura (5 × 10 consultas por semana) (⟨PREENCHER: responsável⟩)
- [ ] Investigar a quebra de 2023.2 nas reservas grandes de Software (⟨PREENCHER: responsável⟩)
- [ ] Combinar com a professora a nova tag da E1 (⟨PREENCHER: responsável⟩)
