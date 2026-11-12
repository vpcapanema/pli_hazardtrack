# Integração legada — consulta histórica

`daee_rain.py` é um módulo legado, fora do pipeline operacional.
Seu endpoint antigo não deve ser apresentado como integração atual
nem usado como instrução de implantação.

Pluviômetros já estão integrados ao HazardTrack pela API SIBH/SP Águas:
`core/gauge_primary.py` é a fonte prioritária quando há cobertura, e
`core/gauge_correction.py` corrige as UAs que permanecem no MERGE.
Ver [backend](../../core/README.md).

Este diretório permanece como referência técnica; não há necessidade
de integrar o módulo antigo para habilitar chuva observada em solo.
