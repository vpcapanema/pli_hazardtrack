# Migração 003 — gestão institucional estadual

Cria 7 tabelas de domínio e 16 tabelas operacionais. É aditiva e
reaplicável: não altera alertas, notificações ou dados anteriores. Os
domínios recebem somente categorias iniciais; não há carga de pessoas,
instituições, competências, territórios ou destinatários presumidos.

## Domínios

No esquema `dominios`: `natureza_risco`,
`responsabilidade_operacional`, `tipo_unidade_operacional`,
`tipo_abrangencia`, `papel_institucional`, `fase_operacional` e
`canal_envio`. As linhas podem ser inseridas, renomeadas e inativadas.
Referências em uso impedem exclusão. Reaplicar a migração preserva
nomes e estados alterados; códigos iniciais ausentes são reinseridos.
As categorias de responsabilidade são propostas de cadastro, não uma
atribuição oficial automática a órgãos.

## Organização, competência e referência

- `instituicao_operadora`: UUID externo da instituição no SIGMA.
- `unidade_operacional`: hierarquia dentro da mesma instituição.
- `programa_operacional`: programa com coordenação estadual e vigência.
- `programa_fase`: fases aplicáveis ao programa.
- `abrangencia_operacional`: território com versão e vigência.
- `abrangencia_componente`: município, trecho/km, referência territorial
  ou geometria GeoJSON. Não há dependência nova de PostGIS.
- `documento_referencia`: fonte, publicação, hash, consulta e revisão.
- `competencia_operacional`: unidade, risco, responsabilidade, papel,
  abrangência, programa e fase opcional.
- `competencia_referencia` e `abrangencia_referencia`: fundamentos
  documentais, com localizador de página/artigo.
- `interlocutor_institucional`: pessoa do SIGMA, opcional, para contato
  institucional; não administra escalas ou agentes da instituição.

## Comunicação institucional

- `contato_operacional`: endereço institucional por unidade e canal.
- `regra_envio_alerta`: critérios por competência, com JSON e instruções
  da API habilitados como opções padrão. Critérios JSON não são DSL
  executável: sua semântica deverá ser validada pela futura API.
- `regra_envio_destino`: múltiplos contatos para uma regra, impedindo
  combinação acidental entre instituições diferentes.
- `integracao_institucional`: configuração por contato e referência
  externa ao segredo; nunca armazenar credenciais no campo de referência.
- `configuracao_envio`: chave geral, inicialmente falsa.

Contatos, regras e integrações começam desativados. Estas tabelas NÃO
estão conectadas ao notificador legado nesta etapa. Alterar a chave no
banco ainda não controla o dispatcher existente. E-mail e webhook
legados continuam subordinados à configuração já existente.

## Auditoria e integridade

Triggers registram INSERT/UPDATE/DELETE dos novos cadastros em
`auditoria_administrativa`, com valores anteriores/posteriores. A API
futura deve definir `hazardtrack.sigma_usuario_id` via `set_config` local
à transação, a partir da sessão autenticada. Operações SQL diretas
registram `sql:<session_user>`. Não é uma trilha inviolável contra o
proprietário do banco; é auditoria transacional da aplicação.

UUIDs SIGMA não têm FK entre bancos. Validade, atividade e autorização
no SIGMA precisam ser verificadas pela futura integração. Não copiar
CPF, e-mail pessoal, telefone pessoal ou senhas para estes cadastros.

As FKs locais garantem coerência institucional e fase/programa.
Vigências e quilômetros possuem validações estruturais. GeoJSON é
validado como objeto nesta fase; topologia, CRS, limites oficiais,
interseção com UAs, normalização de contatos e validação segura de
webhooks serão responsabilidade da próxima etapa, antes de habilitar
qualquer envio. Valores inativos não são excluídos do histórico; a
futura seleção de destinatários deverá filtrar atividade e vigência.

## Aplicação e validação

Executar 001, 002 e 003 em transação com o usuário proprietário do
HazardTrack. `alert_store.initialize()` e `provision-alert-db.sh` foram
atualizados no repositório para incluir 003. Não executar o script de
provisionamento apenas para esta migração em produção: ele também
configura permissões e conexão.

Antes de aplicar na base operacional: backup PostgreSQL, testes em
banco separado cujo nome comece com `pli_hazardtrack_test_`, reaplicação
e comparação de contagens das tabelas existentes. Não executar testes
de integração na base operacional.

Teste específico: `python -m unittest tests.test_operacao_schema` com
`HAZARDTRACK_TEST_DATABASE_URL` apontando para banco isolado.

Próximas etapas: interface unificada, validação SIGMA, carga documental
revisada, contrato público JSON/API/webhook e adaptação da fila atual
para múltiplos destinos. O suporte ao fogo na fila histórica também
permanece para essa etapa. Nenhum envio foi implementado aqui.

## Execução em 12/11/2026

- Aplicada e commitada no banco operacional `pli_hazardtrack` da VM.
- Resultado: 7 tabelas em `dominios`, 26 em `hazardtrack` (10 anteriores
  e 16 novas); versão do esquema 3.
- Sete testes passaram em `pli_hazardtrack_test_operacao_20261112`.
  Esse banco isolado foi mantido para verificações futuras, sem dados
  reais; os registros das operações de teste foram revertidos.
- Contagens anteriores preservadas na transação: 56 alertas, 112
  eventos, 2456 ciclos, 4630 registros de telemetria, 2463 produtos,
  zero notificações e zero tentativas de entrega. Auditoria recebeu
  somente o registro da migração; versão recebeu somente a versão 3.
- Chave geral falsa; canais legados de e-mail e webhook desabilitados.
  `/api/health` retornou `ok` depois do commit.
- Backup anterior no servidor:
  `/home/ubuntu/pli-hazardtrack-backups/pre-migracao-003-20261112-171150.dump`.
  Formato custom PostgreSQL, arquivo não vazio e catálogo conferido com
  `pg_restore --list`; restauração integral não foi testada nesta etapa.
- Aplicação não reiniciada nem republicada. Alterações no inicializador
  e provisionador estão no repositório para o próximo deploy. A migração
  foi aplicada diretamente pelo proprietário do banco, em transação.
