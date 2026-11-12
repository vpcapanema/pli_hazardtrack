# Gestão institucional estadual — estado implementado e próximas etapas

Atualizado em 12/11/2026. A migração 003 está aplicada no PostgreSQL
operacional. Este documento diferencia armazenamento disponível de
funcionalidades ainda não implementadas.

## Limite de atuação

O HazardTrack monitora e informa instituições responsáveis em nível
estadual. Instituições destinatárias gerenciam equipes, plantões, agentes
e ações. Unidades regionais/locais representam a estrutura dos órgãos.
Diretrizes municipais são referências complementares.

O SIGMA centraliza instituições (`cadastro.instituicao`), pessoas
(`cadastro.pessoa`) e contas (`usuarios.usuario`). O HazardTrack
referencia UUIDs; não replica dados pessoais ou credenciais SIGMA.
Os contatos locais são exclusivamente operacionais.

## Modelo aplicado

São 7 tabelas de domínio com linhas extensíveis: natureza de risco,
responsabilidade, tipo de unidade, tipo de abrangência, papel
institucional, fase operacional e canal de envio. Não são ENUMs fechados.
Valores iniciais são categorias; não atribuem competências oficiais
automaticamente a uma instituição.

As 16 tabelas operacionais novas são:

| Grupo | Tabelas no esquema hazardtrack |
|---|---|
| Instituição e organização | `instituicao_operadora`, `unidade_operacional`, `interlocutor_institucional` |
| Programa | `programa_operacional`, `programa_fase` |
| Território | `abrangencia_operacional`, `abrangencia_componente` |
| Competência e documentos | `competencia_operacional`, `documento_referencia`, `competencia_referencia`, `abrangencia_referencia` |
| Destinos e regras | `contato_operacional`, `regra_envio_alerta`, `regra_envio_destino` |
| Integração e autorização | `integracao_institucional`, `configuracao_envio` |

Interlocutores são opcionais. Não foi criada a proposta anterior de
designação individual de agentes, pois a distribuição interna pertence
à instituição.

Hierarquias e vínculos de regras/destinos devem pertencer à mesma
instituição. Competências selecionam risco, função, abrangência, programa
e fase opcional. Vigências e fontes permitem mudanças sem apagar o
histórico. Não há carga de órgãos, limites ou contatos ainda não revisados.

As 10 tabelas anteriores permanecem: `versao_esquema`, `ciclo`,
`alerta`, `evento_alerta`, `notificacao`, `tentativa_entrega`,
`telemetria_ciclo`, `produto_monitoramento`, `controle_monitoramento`
e `auditoria_administrativa`. São 33 tabelas ao todo.

## Auditoria disponível

Triggers dos novos cadastros registram antes/depois, operação, tabela,
data e ator em `auditoria_administrativa`. A API informa
o UUID do usuário SIGMA autenticado no contexto local da transação.
SQL direto é identificado pelo usuário SQL; não simula identidade humana.
O proprietário do banco continua podendo administrar esses registros.

## Interface implementada

A nova [área restrita](AREA_RESTRITA.md) inclui Gestão operacional,
Comunicação e integrações e Administração. A instituição é vinculada
por pesquisa no SIGMA; cartões abrem os cadastros contextuais de unidades,
competências, abrangências, contatos e regras. Domínios são dinâmicos.
O editor preserva chaves, validações e auditoria do banco.

## Entrega definida, ainda pendente

Cada mensagem deverá combinar resumo legível, JSON anexo (ou link se
o canal não aceitar arquivo) e instruções permanentes de integração.
A instituição poderá consultar uma API e/ou cadastrar webhook para
receber novos alertas e atualizações automaticamente.

O contrato deverá conter identidade estável do alerta, revisão,
natureza, nível, localização, horários, origem e encerramento.
Entrega técnica, confirmação humana e resposta operacional são fatos
distintos. Documentação pública não implica acesso anônimo ao cadastro
de destinos ou às credenciais.

O feed público incremental `/api/public/alerts` publica eventos geológicos
e hidrológicos sem destinatários. O JSON individual é exportável na área
restrita. Assinatura webhook, validação de destinos, SMS/WhatsApp e conexão
do cadastro institucional com a fila continuam pendentes e desativadas.

## Controles separados

- Monitoramento: `controle_monitoramento`, já utilizado.
- Autorização futura de envio institucional:
  `configuracao_envio.envio_externo_ativo`, inicialmente falsa.
- Notificador legado: continua dependente de SMTP/webhook no ambiente.

A nova chave ainda não controla o dispatcher existente. Contatos,
integrações e regras novos começam desativados. A fila atual ainda tem
unicidade por alerta/transporte, não por destinatário institucional;
precisa ser adaptada antes de conectar o novo modelo.

## Próximas entregas

Revisão da carga documental e territorial; segurança e teste de webhook; adaptação
da fila por destino; suporte a fogo no histórico de alertas; autorização
explícita e teste de entrega antes de ativar operação externa.

Novas categorias são administráveis sem alterar estrutura SQL. Novos
processamentos ou canais ainda exigem adaptadores técnicos.

## Evidência

[Migração 003](../scripts/sql/003_gestao_institucional.md) contém testes,
backup e verificação da aplicação no banco. Não houve deploy da interface
nem reinício da aplicação nessa etapa.
