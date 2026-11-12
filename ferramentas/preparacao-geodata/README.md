# Preparacao de dados geograficos

Scripts **one-shot** para baixar, converter e publicar camadas em `data/`.
Executados manualmente quando a malha ou camadas administrativas precisam
ser atualizadas. Nao fazem parte do ciclo de refresh da aplicacao.

Para UAs e regioes, usar [geracao-geopackage/](../geracao-geopackage/).
Os utilitarios historicos nao devem sobrescrever as camadas operacionais.

## Scripts

| Script | Entrada | Saida em `data/` |
|--------|---------|------------------|
| `process_der_shapefile.py` | `der_sistema_rodoviario/MALHA_RODOVIARIA.shp` | `malha_der/malha_der_oficial.geojson` |
| `build_road_network.py` | malha DER oficial + regioes PLI | `static/data/malha_der.geojson` (estado inteiro, flag `monitored`) |
| `build_regions_shp.py` | Historico: poligonos aproximados | Descontinuado; nao usar em operacao |
| `build_sp_boundary.py` | shapefile estado SP | contorno para mapa |
| `build_admin_layers.py` | municipios, sedes DER | camadas administrativas |
| `export_hazard_layers.py` | camadas de risco | `export/` |
| `add_ra_to_hazard_layers.py` | camadas + `ferramentas/relatorios-plano-contingencia/ra_official.py` | enriquecimento RA |
| `update_road_stats.py` | malha DER | estatisticas por rodovia |
| `download_leaflet.ps1` | CDN Leaflet | assets estaticos (se necessario) |

## Uso tipico

```cmd
python ferramentas/preparacao-geodata/process_der_shapefile.py
```

Todos os scripts assumem execucao a partir da raiz do repositorio e
resolvem caminhos via `Path(__file__).resolve().parents[2]`.

## Relacao com UAs

A malha DER (`data/der_sistema_rodoviario/`) e insumo obrigatorio de
`ferramentas/geracao-geopackage/03_uas_area_estudo.py`.

Fonte oficial: [dadosabertos.sp.gov.br — Sistema Rodoviario Estadual](https://dadosabertos.sp.gov.br/dataset/sistema-rodoviario-estadual).
