"""Catalogo de exportacoes geograficas com caminhos controlados."""
from pathlib import Path

from .managed_geodata import gpkg_path, zone_paths

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "uas_area_estudo": "Unidades de análise — atributos completos",
    "municipios_area_estudo": "Municípios da área de estudo",
    "regioes_estudo": "Regiões monitoradas — camada nativa",
    "auxilio_regioes_estudo": "Subtrechos rodoviários oficiais",
}


def catalog():
    import geopandas as gpd
    package = gpkg_path()
    specs = {}
    if package.exists():
        for name in gpd.list_layers(package)["name"]:
            specs["nativa-" + name] = {
                "nome": NAMES.get(name, name), "path": package,
                "layer": name, "grupo": "Camadas estruturais",
                "arquivo": name + ".geojson",
            }
    geo, hydro = zone_paths()
    files = [
        ("ua-geo", "UAs geológicas", geo),
        ("ua-hidro", "UAs hidrológicas", hydro),
        ("regioes", "Regiões monitoradas — atributos do sistema",
         ROOT / "data/regioes/regioes_estudo.geojson"),
        ("eixos", "Eixos das regiões",
         ROOT / "data/regioes/regioes_eixos.geojson"),
    ]
    for key, name, file in files:
        specs[key] = {"nome": name, "path": file, "layer": None,
                      "grupo": "Camadas estruturais", "arquivo": file.name}
    for suffix, label in (("observado", "Observado"), ("d1", "D+1"),
                          ("d2", "D+2"), ("d3", "D+3")):
        file = ROOT / "static/data/queimadas" / (
            "risco_trechos_der_" + suffix + ".geojson"
        )
        specs["fogo-" + suffix] = {
            "nome": "Risco de fogo — " + label, "path": file,
            "layer": None, "grupo": "Produtos de fogo",
            "arquivo": file.name,
        }
    return specs
