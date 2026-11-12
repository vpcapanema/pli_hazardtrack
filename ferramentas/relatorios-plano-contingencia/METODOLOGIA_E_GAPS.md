# Metodologia e limites atuais

Atualizado em 12/11/2026. Este documento substitui o diagnóstico antigo
que descrevia RA fixo, polígonos legados, ausência de pluviômetros,
Open-Meteo como previsão e autenticação SRA.

## Base metodológica

Relatórios REGEA-NIPPON de 2021, Produtos 1–7 e manual do sistema
original SAMAEG fundamentam as regras geodinâmicas. O HazardTrack
implementa CPC, ICC e matriz RA × ICC em `core/risk.py`.

A notação RA × ICC significa combinação pela matriz oficial; não é
multiplicação aritmética simples. O resultado global usa o máximo entre
os componentes geológico e hidrológico, respeitando dados disponíveis.

CPC usa intensidade e envoltória `K * Ac96h^(-0.9)`. Os parâmetros
regionais vêm dos GeoJSONs de regiões. A composição atual combina
72 horas observadas com 24 previstas e 18 observadas com 6 previstas.
Sem WRF, usa janelas integralmente observadas e informa a origem.

## Implementação atual

- UAs: 809, base oficial adotada pelo projeto, com RAGEO/RAHID nativos.
- Fontes observadas: pluviômetros SIBH prioritários quando a cobertura
  é suficiente; MERGE nas demais UAs, com correção de solo disponível.
- Previsão: WRF/CPTEC-INPE horário; não é placeholder Open-Meteo.
- Histórico e Linha do Tempo: MERGE observado; sem reconstrução do WRF
  ou dos pluviômetros usados no ciclo original.
- Fogo: produto oficial INPE independente da matriz geodinâmica.
- Plataforma: Flask, frontend de mapa, Docker na VM; PostgreSQL próprio.
- Autenticação: SIGMA, via API no ambiente de produção verificado.
- Persistência: ciclos, produtos, telemetria, episódios e auditoria.
- Comunicação externa: desligada por decisão de escopo do protótipo.

O sistema original sobre TerraMA²/ArcGIS usava uma arquitetura e fontes
distintas. Isso é referência histórica, não instrução para o runtime
atual. Tabelas transcritas estão em `ra_official.py` nesta pasta;
o runtime lá RA persistido na camada geográfica.

## Limites e trabalho pendente

1. Validar fidelidade entre código e metodologia ao alterar regras.
   A relação entre ações orientativas por RD e faixas de ICC descritas
   nos documentos originais deve ser revisada tecnicamente, sem mudar
   a metodologia por decisão de interface.
2. Preservar a proveniência da reconstrução das UAs sem substituir a
   base adotada. Inclusão de novas UAs ainda exige preparar/exportar
   dados; não há cadastro geográfico pela interface.
3. Não tratar previsões meteorológicas como antecedência garantida de
   deslizamento, inundação ou ignição.
4. Não interpretar os sete testes da migração institucional como
   validação científica ou teste de entrega ponta a ponta.
5. Gestão institucional: estrutura SQL aplicada; interface, validação
   SIGMA, API de alertas, assinatura webhook e roteamento pendentes.
6. Histórico de alertas atual suporta geo/hidro; integrar fogo exige
   adaptação que preserve sua classificação própria.
7. Validar competências e abrangências em fontes atuais antes da carga.
   Normas locais apoiam a atuação estadual, não a substituem.

A gestão de equipes e resposta pertence à instituição destinatária.
A futura entrega deverá conter resumo, JSON e instruções de integração.
A API pública de camadas existente não equivale a esse serviço de alertas.

Ver [dados atuais](DADOS_OFICIAIS_STATUS.md),
[gestão institucional](../../docs/GESTAO_INSTITUCIONAL.md) e
[referências pesquisadas](../referencias-operacao/README.md).
