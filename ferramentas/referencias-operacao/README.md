# Referências para gestão operacional do HazardTrack

Coleta realizada em **12/11/2026**, a partir de portais oficiais e links publicados por eles. Material de pesquisa; não é consumido pelo backend e não constitui carga aprovada dos domínios. A coleta não alterou o banco. Posteriormente, a migração
003 criou a estrutura institucional, sem cadastrar instituições ou jurisdições.
Ver [estado implementado](../../docs/GESTAO_INSTITUCIONAL.md).

## Documentos prioritários

| Arquivo em `coleta-2026-11-12/` | Aplicação e limite |
|---|---|
| [Protocolo de Governança 2026](coleta-2026-11-12/semil-governanca-2026.pdf) | Competências institucionais no SP Sem Fogo; coordenação varia por fase. Seções 3 e seguintes. |
| [Plano Anual de Trabalho 2026](coleta-2026-11-12/semil-pat-2026.pdf) | Programas, instituições, ações e planejamento anual; não substitui jurisdição territorial. O sumário contém referência a 2025 apesar do título 2026: preservar essa inconsistência editorial para revisão. |
| [Portaria SPI/SEMIL/ARTESP 04/2026](coleta-2026-11-12/rodovias-portaria-04-2026.pdf) | Programa de prevenção, preparação, monitoramento e combate a incêndios em rodovias, incluindo concedidas e DER. Publicada em 06/05/2026. |
| [Resolução SEMIL 91/2023](coleta-2026-11-12/semil-polos-91-2023.pdf) | Organização dos polos regionais, PPCIF e boletins de ocorrência. Continua referenciada pelo portal SP Sem Fogo; verificar alterações antes da carga. O PDF reúne páginas do Diário Oficial com outros atos. |
| [Guia de orientações sobre incêndios 2026](coleta-2026-11-12/semil-guia-incendios-2026.pdf) | Material orientativo complementar. Arquivo baixado; conteúdo integral ainda não analisado. |
| [Fundação Florestal: unidades, 2025](coleta-2026-11-12/ff-unidades-2025.pdf) | Identificação de unidades e núcleos. Endereços não comprovam os limites da jurisdição. |
| [DER: Plano de Segurança Viária](coleta-2026-11-12/der-seguranca-viaria-alternativo.pdf) | Estrutura regional e contexto operacional; conferir a edição no documento antes de usar como cadastro vigente. |
| [DER: Plano de Contingência, 2017](coleta-2026-11-12/der-contingencia-2017-alternativo.pdf) | Histórico de UBAs e articulação operacional. Não usar isoladamente para atribuir jurisdição atual após concessões. |
| [Caraguatatuba: PPDC 2025–2026](coleta-2026-11-12/caraguatatuba-ppdc-2025-2026.pdf) | Decreto 2.381/2025, competências municipais e organização da resposta. Vigência expressa de 01/12/2025 a 31/03/2026, prorrogável; não foi confirmada prorrogação até a data desta coleta. |

## Páginas oficiais arquivadas

- `semil-sp-sem-fogo.html`: página de origem dos documentos 2026 e polos regionais.
- `semil-adesoes-2026.html`: cadastro público de adesões municipais; adesão não equivale a contato operacional autorizado.
- `der-coi.html`: fluxo COI → CCO da UBA → equipe operacional.
- `bombeiros-lc-1257-2015.html`: competências legais do Corpo de Bombeiros; consultar alterações legislativas na implantação.
- `bombeiros-caraguatatuba-2025.html`: evidência institucional de unidade local, sem delimitação completa de atendimento.
- `ff-nucleo-sao-sebastiao.html`: descrição territorial do núcleo; não substitui camada oficial de limites.
- `cnl-institucional.html`: portal da concessionária; necessário obter contrato/anexos e bases por trecho antes de fechar abrangências.
- `caraguatatuba-planos.html`: catálogo oficial que aponta o PPDC arquivado.

## Achados para o modelo (proposta, não carga)

1. Separar natureza do risco, função operacional, tipo de unidade e tipo de abrangência em tabelas de domínio extensíveis. Não usar ENUM fechado para cadastros administrativos.
2. A governança do fogo é sazonal: o protocolo 2026 diferencia coordenação SEMIL/DPFA nas fases verde/amarela e Defesa Civil na vermelha. Prever fase operacional e vigência na competência, sem confundir fase com nível de risco da UA.
3. A Fundação Florestal atua nas áreas protegidas e, conforme ameaça à unidade, no entorno. Não restringir automaticamente sua responsabilidade à fronteira municipal.
4. Polos do SP Sem Fogo, núcleos de parques, REPDECs, UBAs e bases de concessionárias são estruturas diferentes. Não impor uma hierarquia territorial única.
5. A Portaria 04/2026 inclui DER e rodovias concedidas no programa de incêndios. Separar operador, regulador, coordenação e executor de resposta.
6. O PPDC municipal exemplifica funções distintas de coordenação, seção administrativa, seção operacional e secretarias de apoio. Extrair funções, não importar automaticamente nomes ou telefones de pessoas.
7. Instituições e pessoas continuam no SIGMA. No HazardTrack ficam referências, competências, territórios e contatos exclusivamente operacionais.
8. Domínios permitem inclusão, edição controlada, inativação e histórico. Abrangências concretas precisam de fonte, início/fim de vigência e revisão; não são texto livre nem valores eternos.

## Lacunas explícitas

- Os portais estaduais da Defesa Civil e parte dos portais SPI/Casa Civil devolveram bloqueio automatizado. A busca pública identificou a Resolução CMIL 031/610/26 (15/10/2026, comissão executiva dos PLANCONs) e a 045/610/25 (eventos extremos), mas seus textos integrais não foram arquivados. Não converter esses resultados de busca em atribuições homologadas.
- PDFs do DER no domínio `www.der.sp.gov.br` redirecionaram para HTML genérico; as cópias PDF válidas foram recuperadas em `dersp.der.sp.gov.br`.
- Falta consolidar limites atuais por UBA/CCO, subgrupamento/posto de Bombeiros, unidade da Polícia Ambiental, REPDEC e bases da concessionária, incluindo documentos municipais dos demais municípios monitorados.
- Os códigos RC presentes em `uba_codigo` na camada do projeto não comprovam, sozinhos, equivalência com UBA operacional. Conferir sem alterar os atributos nativos.
- Não foram baixadas camadas oficiais de jurisdição nem homologada uma matriz completa UA × órgão × unidade × responsabilidade.
- Pesquisa documental não é confirmação de destinatários: nenhum contato foi cadastrado e nenhum alerta enviado.

## Proveniência e reprodução

`fontes.json` e `fontes-complementares.json` registram URLs selecionadas. O coletor Node.js (`node coletar.mjs`) faz requisições GET, no máximo quatro simultâneas, e extrai links candidatos sem executá-los. Não executa JavaScript dos sites. Registros já presentes no manifesto são preservados, inclusive falhas; uma nova pesquisa deve usar outro diretório de coleta.

O [manifesto](coleta-2026-11-12/manifesto.json) contém URL original/final, momento da consulta, HTTP, tamanho, SHA-256 e resultado. `links-descobertos.json` contém candidatos, não documentos automaticamente validados. Respostas de bloqueio e HTML no lugar de PDF estão em `falhas/`, fora do conjunto de referências válidas. PDFs foram verificados pela assinatura `%PDF-`; os documentos prioritários SEMIL e PPDC também tiveram o texto consultado. Não foi feita revisão visual integral de todas as páginas.

A data de download não é a data de publicação nem prova de vigência. A coleção constitui levantamento inicial verificável, não certificação de que todas as fontes sejam as últimas versões existentes.
