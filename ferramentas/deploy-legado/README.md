# Arquivos de deploy arquivados

Os arquivos desta pasta são históricos e não devem orientar a implantação
atual. A antiga desativação de uma VM não descreve o ambiente presente.

A implantação verificada em 12/11/2026 está em Docker na VM AWS, com
`docker-compose.vm.yml` na raiz e container `pli_hazardtrack_app`.
O banco operacional é `pli_hazardtrack` em `sigma_pli_db`.

Consultar o [README principal](../../README.md) e os
[scripts de banco](../../scripts/README.md). Não reativar automaticamente
arquivos `.disabled` nem remover containers a partir de instruções antigas.
