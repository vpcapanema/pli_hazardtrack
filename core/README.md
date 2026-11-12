# Backend operacional

Arquitetura atualizada em 12/11/2026. O ciclo combina chuva observada,
previsão e risco; o módulo de fogo mantém processamento independente.

| Módulo | Responsabilidade |
|---|---|
| `zones.py` | Lá 809 UAs nos GeoJSONs geológico/hidrológico, preservando atributos nativos |
| `regions.py` | Lá polígonos e eixos das quatro regiões |
| `merge_inpe.py` | Download e decodificação MERGE/INPE |
| `merge_cache.py` | Cache RAM/disco de GRIBs e amostras |
| `merge_ingest.py` | Ingestão contínua em background |
| `gauge_primary.py` | SIBH/SP Águas como chuva prioritária com cobertura suficiente |
| `gauge_correction.py` | Correção do MERGE nas UAs que permanecem no satélite |
| `forecast_wrf_prec_hourly.py` | WRF horário para composição das janelas do cálculo de risco |
| `risk.py` | CPC, ICC, matriz RA × ICC e composição observado/previsão |
| `aggregator.py` | Snapshot e integração do ciclo |
| `ua_public_feed.py` | Feed público de UAs |
| `fire_pipeline.py` | Agenda e executa pipeline de fogo 05 → 06 → 07 |
| `fire_risk.py` | Consulta e publicação dos produtos de fogo |
| `alert_store.py` | Conexão PostgreSQL, migrações 001–003 e persistência de episódios/entregas |
| `admin_store.py` | Telemetria, produtos, controles, auditoria e importação de legado |
| `admin_telemetry.py` | Telemetria no banco configurado; arquivos no modo local sem DSN |
| `admin_analytics.py` | Séries e indicadores administrativos |
| `notifier.py` | Notificador legado de e-mail/webhook por canal geo/hidro |
| `admin.py`, `admin_auth.py`, `sigma_auth.py` | Administração e autenticação SIGMA |
| `actions.py` | Ações orientativas associadas ao nível operacional |

## Estado institucional

O banco operacional é separado do cadastro SIGMA. As tabelas novas
armazenam unidades, competências, abrangências, contatos institucionais
e configurações. Interlocutores são referências opcionais a pessoas
do SIGMA; não existem cadastros pessoais ou gestão de agentes internos
nestas tabelas.

A migração 003 está aplicada no banco da VM. O editor genérico de tabelas
está implementado em `database_admin.py` e documentado em
[Tabelas do Banco](../docs/TABELAS_DO_BANCO.md), ainda sem publicação.
Interface institucional integrada, validação SIGMA,
roteamento por competência e contrato de entrega JSON/API/webhook ainda
não estão implementados. A chave nova não controla o notificador legado.
Nenhum envio foi habilitado por essa migração.

Ver [gestão institucional](../docs/GESTAO_INSTITUCIONAL.md) e
[migração 003](../scripts/sql/003_gestao_institucional.md).

## Dados e histórico

- Base geográfica: `data/pli-hazardtrack.gpkg`.
- UAs: `data/ua_zones/ua_geo.geojson` e `ua_hidro.geojson`.
- Regiões: `data/regioes/regioes_estudo.geojson` e `regioes_eixos.geojson`.
- MERGE: `data/_cache/merge/`, volume próprio na VM.
- Fogo: `data/queimadas/` e `static/data/queimadas/`.
- Histórico/telemetria/produtos/controles: PostgreSQL quando configurado.

Linha do Tempo e consultas históricas utilizam MERGE observado.
Os registros administrativos não substituem o estado vivo do scheduler.
Os metadados detalhados dos pluviômetros são administrativos, não campos
extras no feed público.

Os antigos enriquecedores DER e geradores por polígonos estão arquivados.
RA e atributos administrativos vêm das UAs. O módulo DAEE legado não é
usado; isso não significa ausência de pluviômetros, já integrados via SIBH.
