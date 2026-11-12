# PLI-HazardTrack

Protótipo estadual de monitoramento de riscos geológicos, hidrológicos
e de fogo em rodovias de São Paulo. Referência documental: 12/11/2026.

O sistema informa as instituições responsáveis. A organização de equipes,
escalas, agentes e resposta em campo pertence às instituições destinatárias.
Diretrizes municipais são referências complementares à atuação estadual.

## Estado atual

| Componente | Situação |
|---|---|
| Monitoramento geodinâmico | 809 UAs, quatro regiões; RA nativo e matriz oficial RA × ICC |
| Chuva observada | SIBH/SP Águas prioritário por cobertura; MERGE/INPE nas demais UAs |
| Previsão | WRF/CPTEC-INPE participa do cálculo atual |
| Fogo | Produtos oficiais INPE observado e D+1 a D+3 por trecho rodoviário |
| Persistência | PostgreSQL operacional `pli_hazardtrack`, esquema versão 3 |
| Gestão institucional | 7 tabelas em `dominios` e 16 novas em `hazardtrack`, aplicadas na VM |
| Área restrita e gestão institucional | `/admin/central`: 12 seções integradas, SIGMA e simulação de destinatários |
| Administração tabular | `/admin/tabelas`: 33 tabelas, aliases, filtros e cadastros auditados |
| API de alertas | Feed incremental `/api/public/alerts`; entrega webhook institucional continua desativada |
| Envio externo | Desligado intencionalmente no protótipo |

A aplicação em produção utiliza o banco próprio na instância compartilhada
`sigma_pli_db`. Pessoas, instituições e usuários são cadastros centrais do
SIGMA; o login em produção usa a API do SIGMA. Não duplicar dados pessoais.

## Documentação

- [Arquitetura e módulos](core/README.md).
- [Banco e gestão institucional](docs/GESTAO_INSTITUCIONAL.md).
- [Migrações e operação](scripts/README.md).
- [Migração 003 e evidência da aplicação](scripts/sql/003_gestao_institucional.md).
- [Dados e metodologia](ferramentas/relatorios-plano-contingencia/DADOS_OFICIAIS_STATUS.md).
- [Metodologia e limites](ferramentas/relatorios-plano-contingencia/METODOLOGIA_E_GAPS.md).
- [Referências institucionais arquivadas](ferramentas/referencias-operacao/README.md).
- [Risco de fogo](data/queimadas/README.md).
- [Ferramentas auxiliares](ferramentas/README.md).
- [Instruções de desenvolvimento](AGENTS.md).
- Ajuda, glossário e API na aplicação: `/docs/ajuda`,
  `/docs/glossario` e `/docs/api`.

## Executar e verificar

Usar Python 3.12 e o ambiente `.venv` do projeto:

```powershell
.\run.ps1 -m pip install -r requirements.txt
.\run.ps1 app.py
.\run.ps1 -m unittest discover -s tests -p "test_*.py"
.\run.ps1 -m flake8 .
```

Se o ambiente tiver sido copiado de outra instalação e o interpretador
referenciado não existir, recriar o venv com Python 3.12 antes de executar.
A convenção de novas linhas Python é 79 caracteres; a configuração
`.flake8` ainda permite 180 e contém exceções legadas.

O serviço usa a porta `PORT` (padrão 5050). Credenciais ficam no ambiente;
não registrar senhas ou URLs de conexão completas na documentação.

## Dados e processamento

1. `zones.py` lá os dois GeoJSONs exportados de `uas_area_estudo`.
   São as mesmas 809 UAs em dois canais, não 1.618 territórios distintos.
2. `merge_ingest.py` mantém a série horária MERGE em RAM e disco;
   o ciclo de risco consulta esse cache, sem baixar todos os GRIBs novamente.
3. `gauge_primary.py` usa pluviômetros SIBH onde há cobertura temporal
   suficiente. Nas demais UAs, `gauge_correction.py` pode corrigir o MERGE.
4. Com WRF disponível, as janelas são 72 h observadas + 24 h previstas
   (geológico) e 18 h observadas + 6 h previstas (hidrológico).
   Sem previsão, usa 96 h/24 h observadas e informa essa condição.
5. CPC/ICC e RA alimentam a matriz de `risk.py`. RA ausente não recebe
   valor inventado. A notação RA × ICC representa a matriz, não simples
   multiplicação numérica.
6. Snapshot, produtos, telemetria e episódios são persistidos no PostgreSQL.
   Linha do Tempo e consulta histórica continuam baseadas no MERGE
   observado, sem reproduzir retrospectivamente WRF ou pluviômetros.
7. Fogo tem pipeline independente: `fire_pipeline.py` executa 05 → 06 → 07
   de `ferramentas/queimadas/`, publicando RF oficial INPE.

As camadas estruturais permanecem em `data/pli-hazardtrack.gpkg`,
`data/ua_zones/` e `data/regioes/`. Não foram migradas para PostGIS.
Produtos de fogo também possuem arquivos públicos e versões no banco.

## Persistência e operação

O banco contém 33 tabelas: 26 em `hazardtrack` e 7 em `dominios`.
O cadastro institucional novo ainda não alimenta o notificador legado.
Sua chave `configuracao_envio.envio_externo_ativo` começa falsa; ela
ainda não substitui os controles SMTP/webhook do código existente.

Sem DSN, há modos locais de desenvolvimento em RAM/arquivos.
Na VM, `HAZARDTRACK_DATABASE_REQUIRED=1` exige PostgreSQL.
Falhas de persistência são registradas; APIs administrativas retornam 503,
sem troca silenciosa para arquivo. Episódios podem ser registrados mesmo
sem canais de entrega. Perda de dados torna o alerta não observável,
em vez de encerrá-lo como se o risco tivesse desaparecido.

O notificador existente suporta e-mail/webhook e fila persistente por
alerta/transporte, com lease e tentativas. Isso não comprova recebimento
humano. A adaptação para múltiplos destinos institucionais, SMS, WhatsApp
e fogo ainda está pendente.

## Implantação

A implantação verificada é Docker na VM AWS, usando
`docker-compose.vm.yml`, container `pli_hazardtrack_app` e banco
`pli_hazardtrack` em `sigma_pli_db`. O container de banco legado
`pli_hazzardtracker_db` ainda aparece no Compose, mas não é o destino
operacional. Não remover volumes como parte de uma atualização documental.

Volumes persistem MERGE, runtime e produtos de fogo. Volume não substitui
backup; testar restauração faz parte da operação de banco.
`render.yaml` e arquivos em `deploy-legado/` não descrevem a produção
verificada. A aplicação usa um worker Gunicorn com threads e scheduler.

A migração 003 foi aplicada diretamente ao banco sem reiniciar ou
republicar a aplicação. O inicializador e provisionador atualizados
estão no repositório para o próximo deploy.

## APIs existentes

| Rota | Finalidade |
|---|---|
| `GET /api/snapshot` | Estado do monitoramento |
| `GET /api/public` | Catálogo de feeds |
| `GET /api/public/ua-layers` | GeoJSON geológico/hidrológico |
| `GET /api/public/fire-risk/layers` | GeoJSON de risco de fogo |
| `GET /api/public/fire-risk/snapshot` | Resumo de fogo |
| `GET /api/public/fire-risk/trecho/<trecho_id>` | Detalhe do trecho |
| `GET /api/forecast` | Previsão por UA |
| `GET /api/timeline` | Série histórica observada |
| `GET /api/health` | Saúde técnica e diagnóstico |
| `GET /admin/api/alerts` | Histórico restrito de episódios/entregas |
| `POST /api/refresh` | Solicitação de atualização; sujeita aos controles da aplicação |

Saúde técnica `ok` não significa envio autorizado ou entrega confirmada.
Os feeds públicos não são a futura API de assinatura de alertas.

## Níveis geodinâmicos

0 Monitoramento; 1 Observação; 2 Atenção; 3 Alerta; 4 Alerta Máximo.
Fogo usa classificação RF INPE própria, não a matriz RD.

Documentação da nova administração: [Área restrita](docs/AREA_RESTRITA.md).
