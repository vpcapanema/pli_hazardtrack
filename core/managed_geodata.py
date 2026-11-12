"""Inclusao versionada de UAs oficiais, sem alterar atributos nativos."""
import json
import math
import os
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from shapely.geometry import shape
from pyproj import CRS

# Inicializa o contexto PROJ antes das bibliotecas nativas de diagnóstico.
WGS84 = CRS.from_epsg(4326)

ROOT = Path(__file__).resolve().parents[1]
LOCK = threading.RLock()


def storage():
    return Path(os.environ.get(
        "PLI_RUNTIME_DIR", str(ROOT / "data" / "_runtime"),
    )) / "geodata"


def active_dir():
    manifest = storage() / "active.json"
    if not manifest.exists():
        return None
    identifier = json.loads(manifest.read_text("utf-8"))["version"]
    # Identificador gerado pelo servidor; nenhuma entrada vira um caminho.
    if len(identifier) != 32 or any(c not in "0123456789abcdef"
                                    for c in identifier):
        raise ValueError("Versão geográfica inválida.")
    return storage() / identifier


def zone_paths():
    folder = active_dir() or ROOT / "data" / "ua_zones"
    return folder / "ua_geo.geojson", folder / "ua_hidro.geojson"


def gpkg_path():
    folder = active_dir()
    return ((folder / "pli-hazardtrack.gpkg") if folder
            else ROOT / "data" / "pli-hazardtrack.gpkg")


def validate(payload, current):
    if (not isinstance(payload, dict)
            or payload.get("type") != "FeatureCollection"):
        raise ValueError("Envie uma coleção GeoJSON (FeatureCollection).")
    features = payload.get("features")
    crs = payload.get("crs")
    if crs and crs.get("properties", {}).get("name") not in (
        "EPSG:4326", "urn:ogc:def:crs:OGC:1.3:CRS84",
        "urn:ogc:def:crs:EPSG::4326",
    ):
        raise ValueError("Coordenadas devem estar em WGS84 (EPSG:4326).")
    if not isinstance(features, list) or not 1 <= len(features) <= 1000:
        raise ValueError("O arquivo deve conter de 1 a 1.000 UAs.")
    known = set(current["ua_id"].astype(str))
    regions = set(current["regiao_id"].astype(int))
    columns = set(current.columns) - {"geometry"}
    seen = set()
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("Cada UA deve ser uma feição GeoJSON.")
        p = feature.get("properties", {})
        if set(p) != columns:
            raise ValueError(
                "Atributos diferentes da camada nativa. Faltam: "
                + ", ".join(sorted(columns - set(p)))
                + ". Não reconhecidos: " + ", ".join(sorted(set(p) - columns))
            )
        key = str(p.get("ua_id") or "")
        if not key or key in known or key in seen:
            raise ValueError("Identificador ausente ou duplicado: " + key)
        seen.add(key)
        if p.get("regiao_id") not in regions:
            raise ValueError("A UA deve pertencer a uma região cadastrada.")
        geometry = feature.get("geometry")
        if not isinstance(geometry, dict):
            raise ValueError("A geometria deve ser um objeto GeoJSON.")
        g = shape(geometry)
        if g.geom_type != "LineString" or g.is_empty or not g.is_valid:
            raise ValueError("A geometria deve ser uma linha válida.")
        if not all(math.isfinite(c) for c in g.bounds) or not (
            -180 <= g.bounds[0] <= g.bounds[2] <= 180
            and -90 <= g.bounds[1] <= g.bounds[3] <= 90
        ):
            raise ValueError("Coordenadas devem estar em WGS84 (EPSG:4326).")
        for key in ("RAGEO", "RAHID"):
            if (p[key] is not None
                    and (type(p[key]) is not int or p[key] not in range(5))):
                raise ValueError(
                    key + " deve ser de 0 a 4 ou NULL (sem dado)."
                )
        for key in ("icc_geo_thresholds", "icc_hid_thresholds"):
            raw = p[key]
            values = raw if isinstance(raw, list) else str(raw).split(";")
            values = [float(v) for v in values]
            if len(values) != 4 or any(
                not math.isfinite(v) or v < 0 for v in values
            ):
                raise ValueError("Limiares inválidos: " + key)
            if any(a >= b for a, b in zip(values, values[1:])):
                raise ValueError("Os limiares devem ser crescentes.")
        if not p.get("sigla_rodovia") or not (
            0 <= float(p["km_inicial"]) < float(p["km_final"])
        ):
            raise ValueError("Rodovia ou intervalo quilométrico inválido.")
    return features


def import_uas(payload, source, actor, confirm=False):
    import geopandas as gpd
    from . import alert_store
    if not isinstance(source, str) or len(source.strip()) < 15:
        raise ValueError("Informe o documento ou a fonte oficial das UAs.")
    with LOCK:
        current = gpd.read_file(gpkg_path(), layer="uas_area_estudo")
        features = validate(payload, current)
        if not confirm:
            return {"validado": True, "novas_uas": len(features),
                    "total_atual": len(current), "fonte": source}
        version = uuid4().hex
        folder = storage() / version
        folder.mkdir(parents=True)
        target = folder / "pli-hazardtrack.gpkg"
        shutil.copy2(gpkg_path(), target)
        added = gpd.GeoDataFrame.from_features(features, crs=WGS84)
        added.to_file(target, layer="uas_area_estudo", driver="GPKG", mode="a")
        combined = gpd.read_file(target, layer="uas_area_estudo")
        if len(combined) != len(current) + len(features):
            raise ValueError("Falha na conferência do GeoPackage.")
        for hazard, remove in (
            ("geo", ("RAHID", "icc_hid_thresholds", "trecho_critico_hid")),
            ("hidro", ("RAGEO", "icc_geo_thresholds", "trecho_critico_geo")),
        ):
            exported = combined.drop(columns=list(remove)).copy()
            exported["hazard"] = hazard
            exported.sort_values("ua_id").to_file(
                folder / f"ua_{hazard}.geojson", driver="GeoJSON",
            )
        manifest = {
            "version": version, "fonte": source, "ator": actor,
            "criado_em": datetime.now(timezone.utc).isoformat(),
            "novas_uas": len(features), "total": len(combined),
        }
        (folder / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False), "utf-8",
        )
        # Restaura o ponteiro se a transacao de auditoria falhar.
        pointer = storage() / "active.json"
        old = pointer.read_bytes() if pointer.exists() else None
        try:
            with alert_store.connection() as conn:
                from psycopg.types.json import Jsonb
                conn.execute(
                    "INSERT INTO hazardtrack.auditoria_administrativa "
                    "(ator,acao,dados) VALUES (%s,'importacao_ua',%s)",
                    (actor, Jsonb(manifest)),
                )
                temp = storage() / (version + ".json")
                temp.write_text(json.dumps(manifest), "utf-8")
                os.replace(temp, pointer)
        except Exception:
            if old is None:
                pointer.unlink(missing_ok=True)
            else:
                temp = storage() / (version + ".rollback")
                temp.write_bytes(old)
                os.replace(temp, pointer)
            raise
        return manifest
