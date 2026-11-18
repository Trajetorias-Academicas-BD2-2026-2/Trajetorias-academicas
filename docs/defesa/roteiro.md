# Roteiro da defesa (20 minutos, banca técnica e de gestão)

**Slides:** [deck da defesa](https://claude.ai/artifact/9MUCuK24U3iNVTMLthMyQU), com 14 slides na ordem deste roteiro e notas do apresentador. Baixe em PowerPoint ou PDF pelo menu Exportar. O deck é privado: quem for apresentar precisa recebê-lo compartilhado pelo menu Compartilhar.

**Regra do roteiro:** cada bloco abre com a decisão que a plataforma permite (para gestão) e fecha com a evidência de como o número é garantido (para a banca técnica). Os slides seguem esta ordem.

**Preparar antes de entrar:**
- `docker compose up -d --build` uns 10 min antes; confirmar `localhost:8080` (painel) e `localhost:8090` (Pauta).
- Abas abertas:
  - painel publicado: <https://trajetorias-academicas-bd2-2026-2.github.io/Trajetorias-academicas/>;
  - catálogo: `…/catalogo/`;
  - Pauta: `localhost:8090`;
  - terminal na pasta do projeto.
- **Plano B geral:** se o Docker falhar, tudo tem versão publicada (painel e catálogo no Pages) ou gravada (`docs/evidencias/e4-*.txt`). Nunca improvisar um comando novo ao vivo.

| Tempo | Bloco | Fala (o essencial) | Mostrar | Plano B |
|---|---|---|---|---|
| 0:00–2:30 | **1. O problema e a decisão** | "O coordenador de Eletrônica negocia vagas com Matemática e Física sem saber como estão as reservas. Hoje ele pode ver isto: em 2026, **79% dos lugares guardados para Eletrônica vêm de outros departamentos**, e **43 das 55 obrigatórias nunca guardaram um lugar** para o curso. Ele sabe com quem negociar e o quê." | Painel publicado, cenas 3 e 6, em Eletrônica | Slide com o print |
| 2:30–5:00 | **2. A resposta à pergunta** | Pergunta de gestão em uma frase. Software foi de 544 para 3.816 lugares (7×); os outros quatro cursos caíram de 29% a 74%. **Limite dito em voz alta:** lugar guardado não é aluno; a partir de 2023/2 a forma de registrar parece ter mudado | Painel, cenas 1 a 4 | Slides |
| 5:00–8:00 | **3. O dado volta e muda o que acontece (ETL reverso)** | A Pauta da coordenação recebe 206 itens: reservas grandes a confirmar, obrigatórias sem lugar, quedas fortes. **Ao vivo:** `docker compose stop coordenacao`, rodar o ETL (pendentes, pipeline não cai), `start`, rodar de novo (entregue, sem duplicar). Marcar um item como revisado | Terminal + Pauta | `e4-etl-reverso.txt` |
| 8:00–11:00 | **4. Uma definição por métrica** | "Se duas telas mostram números diferentes, a plataforma perde a confiança." As 8 métricas estão num YAML do MetricFlow. Painel, Pauta e CSV leem a mesma tabela. Rodar `tests/metricas_consistentes.py`: 586 comparações, 0 divergências. Contar a divergência provocada (3.816 → 3.900), que o teste pegou | Terminal; rodapé "Como cada número é calculado" no painel | `e4-consistencia.txt` |
| 11:00–13:30 | **5. Seguir uma coluna até a origem** | Pegar "3.816" e voltar: painel → `metricas_oficiais` → MetricFlow → `fct_reservas` → `reserva_vaga` → CSV com SHA-256 → campo "Vgs Reservadas" do SIGAA | Catálogo publicado (grafo de linhagem) + tabela de `docs/catalogo-e-linhagem.md` | Slide da linhagem |
| 13:30–16:00 | **6. LGPD e acesso** | Único dado pessoal: nome de docente. Onde está (inclusive no Delta da E2, que **tiramos**). Base legal, retenção até 30/06/2027, descarte por pseudonimização. **Ao vivo:** `acesso-tests`, em que o coordenador de Software só vê Software e o auditor recebe *permission denied* no nome. O que **não** conseguimos apagar: o histórico do git | Terminal | `e4-acesso.txt`, `e4-descarte.txt` |
| 16:00–18:30 | **7. As decisões e os gatilhos** | 5 ADRs vigentes, um por estágio. Dois gatilhos dispararam (E1: sem ocupação, scrapers falharam) e as decisões foram revistas no mesmo dia. Um parcial (histórico de execuções → GitHub Actions). A opção nula ganhou com número três vezes (recarga × Kafka, cron × Airflow, arquivo × servidor) | Slide do portfólio (`docs/adr/README.md`) | — |
| 18:30–20:00 | **8. Limites e próximo passo** | Pedido via LAI para obter ocupação real; versões curriculares antigas; a Pauta não avisa itens retirados. Fecho para gestão: "a coordenação chega à reunião de vagas sabendo **com quem** negociar e **o quê** conferir" | Slide final | — |

**Divisão sugerida entre a Squad:** um apresentador por bloco ou dois, com uma pessoa só no terminal. Ensaiar duas vezes cronometrado. Se passar de 21 min, cortar o bloco 5 (o catálogo fica para a arguição).

**Comandos ao vivo** (copiar de um arquivo, não digitar):

```bash
docker compose stop coordenacao
docker compose run --rm --no-deps analytics python /workspace/analytics/etl_reverso.py
docker compose start coordenacao
docker compose run --rm --no-deps analytics python /workspace/analytics/etl_reverso.py
docker compose run --rm --no-deps analytics python /workspace/tests/metricas_consistentes.py
docker compose --profile test run --rm --no-deps acesso-tests
```
