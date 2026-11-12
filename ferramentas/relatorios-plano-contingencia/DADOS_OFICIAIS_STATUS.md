# Dados operacionais — situação em 12/11/2026

| Informação | Fonte e uso atual |
|---|---|
| UAs | 809 UAs em `data/pli-hazardtrack.gpkg`, camada `uas_area_estudo`; base oficial adotada pelo projeto |
| RA | `RAGEO` e `RAHID` nativos por UA; não há RA fixo nem inferência por moda de trecho no runtime |
| Regiões | Quatro polígonos/eixos exportados para `data/regioes/` |
| Chuva em solo | API SIBH/SP Águas, DAEE/CEMADEN, via `gauge_primary.py` e `gauge_correction.py` |
| Chuva satelital | MERGE/CPTEC-INPE com ingestão e cache RAM/disco |
| Previsão | WRF horário CPTEC-INPE usado nas janelas geológica/hidrológica |
| Fogo | RF oficial INPE observado e D+1 a D+3 |
| Dados institucionais | Pessoas, instituições e usuários no SIGMA |
| Histórico e gestão operacional | Banco `pli_hazardtrack`, versão 3 |

As UAs são UTBs e setores de risco complementares, abrangendo trechos
críticos e não críticos. A antiga afirmação de que todo ponto fora dos
trechos críticos não tinha RA foi retirada: o runtime lá RA por UA.
Fora da cobertura mapeada, não inventar RA nem extrapolar resultados.

Totais consolidados da base:
RAGEO {0:39, 1:396, 2:106, 3:127, 4:141};
RAHID {0:441, 1:335, 2:19, 3:14, 4:0}.
Não confundir totais por classe com validação operacional de alertas.

O histórico técnico da reconstrução das geometrias permanece nas
ferramentas e no AGENTS. A base atual é a adotada pelo projeto; futuras
UAs devem preservar identificadores, atributos e parâmetros requeridos.
A interface para inclusão de novas UAs ainda não foi implementada.

## Instituições e abrangências

A migração 003 criou a estrutura de domínio, não uma carga territorial
homologada. A coleta documental está em
[referências de operação](../referencias-operacao/README.md).
Concessões, unidades e competências exigem fonte e vigência; atributos
DER da UA não determinam sozinhos o destinatário do alerta.

## Limites

A ausência de pluviômetros, de previsão ou de RA precisa ser tratada
explicitamente conforme o pipeline. As métricas de saúde não certificam
capacidade de antecipação de eventos ou recebimento de mensagens.
Envios externos permanecem desligados no protótipo.
