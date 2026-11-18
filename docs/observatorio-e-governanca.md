# Observatório, governança e consumo

## Referência de produto

O [Observatório da Evasão e Permanência do UnB DataLab](https://www.unbdatalab.org/observatoriodaevasao) usa um painel interativo para a gestão filtrar indicadores por curso e período. O projeto G2 aplica a mesma ideia ao domínio de reservas de vagas: o coordenador escolhe o curso e acompanha a série das obrigatórias do currículo de referência de 2026.1.

## Onde está cada parte (E4)

Na E4, a governança e o consumo foram refeitos. Este documento só aponta para os documentos atuais:

| Tema | Documento |
|---|---|
| Métricas oficiais (definição única, versionada) | [`analytics/models/semantic/semantica.yml`](../analytics/models/semantic/semantica.yml) e [ADR-0007](adr/0007-disponibilizacao-e4.md) |
| ETL reverso (Pauta da coordenação) | [ADR-0007](adr/0007-disponibilizacao-e4.md), [`e4-etl-reverso.txt`](evidencias/e4-etl-reverso.txt) |
| Catálogo e linhagem | [`catalogo-e-linhagem.md`](catalogo-e-linhagem.md) e o [catálogo publicado](https://trajetorias-academicas-bd2-2026-2.github.io/Trajetorias-academicas/catalogo/) |
| LGPD | [`lgpd.md`](lgpd.md) |
| Controle de acesso (linha e coluna) | [`db/migrations/V012__acesso_e4.sql`](../db/migrations/V012__acesso_e4.sql), [`e4-acesso.txt`](evidencias/e4-acesso.txt) |
| Freshness e SLA | view `analytics.metricas_freshness` (SLA de 24 h), testada em `test_sla_freshness_mart` e exibida no painel |
| Checklist da E4 com as evidências | [`evidencia-e4.md`](evidencia-e4.md) |

O que mudou desde a E3:
- **ETL reverso:** `operations.alertas_reserva` (E3) era uma tabela que nenhuma aplicação lia. Saiu na V013; no lugar entrou a fila de envio para a Pauta.
- **Acesso:** o papel `dashboard_reader` da V007 dava acesso por schema e o painel conectava como `g2`. Agora o painel usa o papel `painel` e há recorte de linha e de coluna.
