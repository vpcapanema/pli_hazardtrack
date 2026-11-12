# Administração: Tabelas do Banco

Implementação integrada à nova área restrita em 12/11/2026.

A página `/admin/tabelas` usa a sessão de Gestor ou Administrador do HazardTrack e a
identidade visual de `admin.css`: cores, fontes e componentes da área
restrita. O CICard é a referência para a disposição e os espaçamentos
dos elementos tabulares, não para a identidade visual.

## Interface

O menu expansível **Tabelas do Banco** reúne as tabelas dos esquemas
`hazardtrack` e `dominios`. A busca considera nome amigável, nome técnico
e esquema. O catálogo vem do PostgreSQL, sem cópia manual das colunas.

Ordem da página: título e identificação; contêiner único com filtros e
tabela; botões de ação; rodapé com paginação central e contador à direita.
Cada cabeçalho mostra o alias amigável e, abaixo, o nome bruto da coluna.
Os aliases ficam em `core/database_labels.py` e não renomeiam o banco.

A consulta oferece ordenação, filtro textual literal, seleção de valores
vazios, inversão do filtro, seleção de linhas e páginas de 15 registros.
Valores numéricos extensos são transportados como texto, preservando a
precisão dos identificadores. Dados estruturados permanecem em JSON.

## Operações

As 23 tabelas da migração 003 possuem inclusão, edição e exclusão.
Os formulários seguem tipos, obrigatoriedade, padrões e chaves do catálogo.
NULL e valor padrão são escolhas distintas. Campos automáticos e chaves
primárias existentes não são editáveis.

As 10 tabelas anteriores são consultáveis, mas não recebem alterações
genéricas: histórico, auditoria, fila e estado do monitoramento continuam
sob controle dos serviços responsáveis. Os botões ficam desabilitados e
a página informa a condição de somente leitura.

As alterações usam transações, parâmetros SQL, lista explícita de tabelas
editáveis, proteção CSRF e conferência da versão do registro. Alterações
concorrentes exigem recarregamento. A auditoria existente recebe o
identificador do usuário da sessão.

## Limites desta etapa

O editor é integrado à Gestão operacional por formulários contextuais.
Chaves estrangeiras possuem pesquisa de referências. Instituições e
pessoas são pesquisadas no SIGMA; seus UUIDs são validados no cadastro
central antes de gravar o vínculo, sem copiar contatos pessoais.

A chave de envio da nova tabela continua sem conexão com o notificador
legado. Esta implementação não ativa envios nem modifica os cálculos.

## Validação

`tests/test_database_admin.py` verifica acesso, perfil, CSRF, estrutura
HTML, cobertura dos aliases e, com PostgreSQL de teste, as 33 tabelas,
operações de cadastro, concorrência, auditoria e rejeição de consultas
inválidas. A integração exige `HAZARDTRACK_TEST_DATABASE_URL` com nome
de banco iniciado por `pli_hazardtrack_test_`.

A validação em navegador sem janela cobriu login real SIGMA, navegação,
pesquisa, inclusão, edição, exclusão e disposição em tela móvel.
Detalhes e limites: [Área restrita](AREA_RESTRITA.md).

Campos extensos das tabelas de histórico são carregados sob demanda pelo
link **Abrir conteúdo completo**, sem truncamento do arquivo. A lista mantém
as colunas nativas e a paginação, evitando transferir megabytes por linha.
