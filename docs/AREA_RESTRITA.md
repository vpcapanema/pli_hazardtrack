# Área restrita — 12/11/2026

Entrada: `/admin/central`. Login SIGMA com perfil **Gestor** ou
**Administrador**, conferido no provedor. A seleção não concede perfil.
O painel anterior `/admin/status` permanece compatível.

## Navegação e funções

- Visão geral, Monitoramento, Análises e Estatísticas: indicadores,
  gráficos e dados reais dos serviços e do PostgreSQL.
- Território e camadas: mapa das UAs, pesquisa, detalhes nativos,
  inventário de camadas e importação/exportação GeoJSON.
- Alertas: episódios geológicos/hidrológicos, eventos, notificações,
  tentativas e exportação JSON. Fogo é exibido nos painéis próprios;
  não há episódios persistentes de fogo no histórico atual.
- Gestão operacional: vínculos SIGMA, unidades, programas, abrangências,
  competências, documentos, interlocutores e contatos operacionais.
- Comunicação e integrações: regras, destinos, integrações e simulação
  por UA, natureza, nível e fase. A simulação não cria fila nem envia.
- Relatórios: exportações dos serviços administrativos, com auditoria.
- Administração: domínios dinâmicos, auditoria e acesso às 33 tabelas.
- Controles de monitoramento: ativação dos pipelines existentes.
- Diagnóstico técnico: serviços, bibliotecas, persistência e ambiente.

Os formulários institucionais abrem o editor tabular com o contexto da
instituição. Referências locais e SIGMA possuem pesquisa. O SIGMA é
consultado somente para identificação, nome e situação ativa; dados
pessoais de contato não são copiados. A gravação verifica UUIDs SIGMA.

## UAs oficiais

Em **Território e camadas → Exportação das camadas**, cada camada possui
o botão **Baixar GeoJSON**: UAs completas, municípios, regiões, subtrechos
oficiais, UAs por natureza, eixos e produtos de fogo observado/D+1/D+2/D+3.
**Baixar GeoPackage estrutural** fornece o pacote completo das camadas
estruturais. A exportação usa a versão ativa, inclusive UAs adicionadas,
e preserva geometrias e atributos nativos. Não aplica o filtro da lista
de UAs: exporta a camada inteira. Camadas indisponíveis ficam sinalizadas.

A inclusão exige GeoJSON WGS84, atributos nativos completos, identificador
inédito, região existente, RA oficial (ou NULL) e limiares válidos. Primeiro
valida, depois confirma. A fonte documental é obrigatória. O sistema
valida estrutura; a autenticidade do documento cabe ao responsável.

Cada inclusão produz uma versão completa em
`PLI_RUNTIME_DIR/geodata/<versao>/`, com GeoPackage e dois GeoJSONs.
`active.json` seleciona a versão consumida; `core/zones.py` detecta sua
alteração. O GeoPackage original não é sobrescrito. A auditoria registra
fonte, usuário e totais. Os demais estratos geográficos são preservados.
Reversão administrativa exige selecionar uma versão anterior íntegra
no manifesto; não existe botão de exclusão de UAs.

## API de integração

`GET /api/public/alerts?after=0&limit=100` retorna `versao`, `eventos`,
`proximo_cursor`, `proxima_consulta` e intervalo recomendado de 60 segundos.
O consumidor persiste o cursor após processar os eventos; consulta o
próximo lote até esvaziá-lo. Identificadores são texto para evitar perda
de precisão. O limite é 1–200. Eventos contêm UA, canal, tipo, horários e
RD anterior/atual, sem contatos ou dados pessoais. É consulta periódica,
não assinatura de webhook. Geometria pode ser obtida no feed de UAs.

O JSON individual, disponível no histórico restrito, inclui o episódio
e seus eventos. As opções de JSON e instruções de API ficam armazenadas
nas regras. A entrega externa institucional continua desativada: a chave
preparatória não liga SMTP, WhatsApp, SMS nem o dispatcher legado.

## Segurança e verificação

Sessão autenticada, perfis explícitos, CSRF nas mutações, consultas
parametrizadas, controle de concorrência por versão de registro e auditoria.
Histórico e tabelas controladas pelo pipeline são somente leitura no editor.

Testes Python cobrem contratos, persistência, regras, permissões, auditoria
e importação geográfica isolada. `tests/workspace_browser.cjs` usa Edge
sem janela e banco exclusivo de teste: login SIGMA, 12 páginas, consulta
institucional, CRUD, exportações, simulação e responsividade.
Nenhum teste de escrita deve apontar para o banco operacional.

## Publicação verificada

Publicada em 12/11/2026 no container `pli_hazardtrack_app`:
`https://56.125.163.194/pli-hazardtrack/admin/central`.

- 251 testes Python aprovados em PostgreSQL exclusivo de testes.
- Teste de navegador sem janela aprovado, incluindo operações cadastrais
  no ambiente isolado; teste DOM cobre aliases, XSS e precisão numérica.
- No endereço público: login SIGMA real, 12 páginas, consulta das 33
  tabelas, APIs e download integral de JSON histórico extenso aprovados.
- 809 UAs disponíveis; configuração institucional de envio permanece falsa.
- Backup anterior: diretório
  `/home/ubuntu/pli-hazardtrack-backups/pre-workspace-20261112T184207/`,
  com dump PostgreSQL e catálogo conferido, fontes e identificação da imagem.
  Imagem anterior preservada como `pli-hazardtrack-app:pre-workspace-20261112`.
  Não foi executado ensaio de restauração integral do banco.
- Pacote publicado preservado em
  `/home/ubuntu/pli-hazardtrack-releases/workspace-20261112/`.

`tests/workspace_smoke.cjs` repete a conferência de leitura no endereço
definido por `HAZARDTRACK_SMOKE_BASE`, usando credenciais por caminho de
arquivo externo (`HAZARDTRACK_E2E_CREDENTIALS`). Não contém senhas.
