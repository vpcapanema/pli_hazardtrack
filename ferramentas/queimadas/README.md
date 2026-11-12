# Pipeline de risco de fogo

O módulo consome produtos oficiais INPE observados e previstos, agrega
o RF aos trechos rodoviários e publica GeoJSON/JSON. Não recalcula
atualmente o modelo INPE com IMERG/GFS locais.

## Execução atual

Preparação da base: `01_prepare_base_layers.py`.
Ciclo operacional: `05_compute_rf_grid.py` →
`06_aggregate_to_der_segments.py` → `07_export_public_layers.py`.

`core/fire_pipeline.py` executa essas três etapas em subprocessos,
com polling configurado por `QUEIMADAS_POLL_MIN` (padrão 30 minutos).
Portanto, esta subpasta é exceção entre as ferramentas: participa do
runtime e é incluída na imagem Docker.

`core/fire_risk.py` lá os produtos prontos sem executar downloads
durante a consulta HTTP. Horizontes atuais: observado, D+1, D+2 e D+3.
Scripts 02–04 são reservados a estudos/ingestões futuras, não requisitos
do processamento atual.

Dados em `data/queimadas/`; publicação em `static/data/queimadas/`;
versões administrativas em `hazardtrack.produto_monitoramento`.

A classificação RF é independente de RA/ICC/RD. A migração institucional
não criou entrega automática de alertas de fogo.

[Especificação detalhada](../../data/queimadas/README.md).
