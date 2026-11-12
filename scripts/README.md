# Scripts de banco

A pasta contém o provisionamento e as migrações PostgreSQL ativas.

| Arquivo | Finalidade |
|---|---|
| `provision-alert-db.sh` | Provisiona banco/usuário operacional e aplica 001–003 |
| `sql/001_alertas.sql` | Ciclos, episódios, eventos, fila e tentativas |
| `sql/002_administracao.sql` | Telemetria, produtos, controles e auditoria |
| `sql/003_gestao_institucional.sql` | Domínios e gestão institucional estadual |
| [Documentação 003](sql/003_gestao_institucional.md) | Modelo, limites, testes e aplicação na VM |

Banco próprio: `pli_hazardtrack`; usuário: `hazardtrack_app`.
O banco SIGMA não recebe estas migrações. O provisionador também altera
permissões e ambiente: não executá-lo como simples consulta ou apenas
para repetir uma migração já aplicada.

## Aplicação

As migrações devem ser aplicadas em transação, com o proprietário do banco.
O inicializador `core/alert_store.py` serializa a inicialização por advisory
lock e inclui as três migrações. As inserções de domínios preservam
edições e inativações; recriam códigos iniciais removidos.

Na VM, a versão 3 foi aplicada em 12/11/2026. O backup e as verificações
estão no documento da migração. O código atualizado de inicialização
ainda depende do próximo deploy.

Para provisionamento inicial autorizado:

```bash
APP_DIR=/opt/pli-hazardtrack bash scripts/provision-alert-db.sh
```

Nunca imprimir DSNs completos, chaves ou senhas. Backup deve ficar
protegido no servidor; lista de conteúdo do dump não equivale a teste
de restauração.

## Testes

Definir `HAZARDTRACK_TEST_DATABASE_URL` para banco separado com nome
iniciado por `pli_hazardtrack_test_`:

```powershell
.\run.ps1 -m unittest tests.test_operacao_schema
.\run.ps1 -m unittest tests.test_alert_store tests.test_admin_store
```

Nunca apontar testes para produção. Alguns testes de integração limpam
tabelas do banco de teste. Sem a variável, os testes dependentes de
PostgreSQL são ignorados. A criação das tabelas não habilita envios.

Scripts de preparação geográfica e produtos estão em
[../ferramentas/](../ferramentas/README.md).
