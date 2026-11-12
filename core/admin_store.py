"""Persistencia dos dados administrativos, sem substituir saude ao vivo."""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

from . import alert_store

log = logging.getLogger("admin_store")
ROOT = Path(__file__).resolve().parent.parent
FIRE_DIR = ROOT / "static" / "data" / "queimadas"
FIRE_FILES = {
    "stats": "risco_trechos_der_stats.json",
    "snapshot": "risco_trechos_der_latest.json",
    "observado": "risco_trechos_der_observado.geojson",
    "D+1": "risco_trechos_der_d1.geojson",
    "D+2": "risco_trechos_der_d2.geojson",
    "D+3": "risco_trechos_der_d3.geojson",
}


def _timestamp(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError("Timestamp administrativo sem fuso horario")
    return dt


def record_telemetry(entries: list[dict[str, Any]]) -> None:
    alert_store.initialize()
    with alert_store.connection() as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO hazardtrack.telemetria_ciclo VALUES (%s,%s)"
                " ON CONFLICT (iniciado_em) DO UPDATE SET dados=EXCLUDED.dados",
                [(_timestamp(e["started_at"]), Jsonb(e)) for e in entries],
            )


def telemetry(
    hours: float | None = None, limit: int | None = None,
) -> list[dict[str, Any]]:
    cutoff = datetime.min.replace(tzinfo=timezone.utc)
    if hours:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with alert_store.connection() as conn:
        rows = conn.execute(
            "SELECT dados FROM hazardtrack.telemetria_ciclo"
            " WHERE iniciado_em >= %s ORDER BY iniciado_em DESC LIMIT %s",
            (cutoff, limit),
        ).fetchall()
    return [r["dados"] for r in reversed(rows)]


def telemetry_count() -> int:
    with alert_store.connection() as conn:
        row = conn.execute(
            "SELECT count(*) AS n FROM hazardtrack.telemetria_ciclo",
        ).fetchone()
        if row is None:
            raise RuntimeError("Contagem de telemetria sem retorno do banco")
        return row["n"]


def seed_controls(data: dict[str, Any]) -> None:
    with alert_store.connection() as conn:
        conn.execute(
            "INSERT INTO hazardtrack.controle_monitoramento (dados)"
            " VALUES (%s) ON CONFLICT DO NOTHING", (Jsonb(data),),
        )


def controls() -> dict[str, Any]:
    with alert_store.connection() as conn:
        row = conn.execute(
            "SELECT dados FROM hazardtrack.controle_monitoramento",
        ).fetchone()
    if row is None:
        raise RuntimeError("Controles administrativos nao inicializados")
    return row["dados"]


def set_control(system: str, enabled: bool, actor: str) -> dict[str, Any]:
    with alert_store.connection() as conn:
        row = conn.execute(
            "SELECT dados FROM hazardtrack.controle_monitoramento"
            " FOR UPDATE",
        ).fetchone()
        if row is None:
            raise RuntimeError("Controles administrativos nao inicializados")
        previous = row["dados"]
        data = {
            **previous, system: enabled, "updated_by": actor,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        conn.execute(
            "UPDATE hazardtrack.controle_monitoramento SET dados=%s",
            (Jsonb(data),),
        )
        conn.execute(
            "INSERT INTO hazardtrack.auditoria_administrativa"
            " (ator,acao,dados) VALUES (%s,'controle',%s)",
            (actor, Jsonb({
                "system": system, "before": previous.get(system, True),
                "after": enabled,
            })),
        )
    return data


def audit(action: str, actor: str, data: dict[str, Any]) -> None:
    with alert_store.connection() as conn:
        conn.execute(
            "INSERT INTO hazardtrack.auditoria_administrativa"
            " (ator,acao,dados) VALUES (%s,%s,%s)",
            (actor, action, Jsonb(data)),
        )


def database_details() -> dict[str, Any]:
    with alert_store.connection() as conn:
        row = conn.execute(
            "SELECT max(versao) AS n FROM hazardtrack.versao_esquema",
        ).fetchone()
        if row is None:
            raise RuntimeError("Versao do esquema sem retorno do banco")
        version = row["n"]
        products = conn.execute(
            "SELECT sistema,max(referencia_em) AS latest,count(*) AS total"
            " FROM hazardtrack.produto_monitoramento GROUP BY sistema",
        ).fetchall()
    return {
        **alert_store.status(), "schema_version": version,
        "products": [
            {**r, "latest": r["latest"].isoformat()} for r in products
        ],
    }


def save_product(
    system: str, reference: datetime, data: dict[str, Any],
) -> None:
    encoded = json.dumps(data, sort_keys=True, allow_nan=False)
    signature = hashlib.sha256(encoded.encode()).hexdigest()
    with alert_store.connection() as conn:
        conn.execute(
            "INSERT INTO hazardtrack.produto_monitoramento"
            " (sistema,referencia_em,assinatura,dados) VALUES (%s,%s,%s,%s)"
            " ON CONFLICT (sistema,assinatura) DO NOTHING",
            (system, reference, signature, Jsonb(data)),
        )


def product(
    system: str, at: datetime | None = None,
) -> dict[str, Any] | None:
    with alert_store.connection() as conn:
        row = conn.execute(
            "SELECT dados FROM hazardtrack.produto_monitoramento"
            " WHERE sistema=%s AND referencia_em <= %s"
            " ORDER BY referencia_em DESC,id DESC LIMIT 1",
            (system, at or datetime.now(timezone.utc)),
        ).fetchone()
    return row["dados"] if row else None


def record_geo(snapshot: dict[str, Any], hourly: dict[str, Any]) -> None:
    # Geometrias e arrays duplicados ficam nas camadas oficiais, nao no banco.
    snap = {
        k: v for k, v in snapshot.items()
        if k not in ("points", "points_geo", "points_hidro")
    }
    snap["regions"] = [
        {k: v for k, v in r.items() if k not in ("polygon", "geometry")}
        for r in snapshot.get("regions", [])
    ]
    for channel in ("geo", "hidro"):
        snap[f"points_{channel}"] = [
            {k: v for k, v in p.items()
             if k not in ("geometry", "history") and not k.startswith("_")}
            for p in snapshot.get(f"points_{channel}", [])
        ]
    levels = [
        [p["ua_id"], p["hazard"], p.get("rd")]
        for ch in ("geo", "hidro") for p in snap[f"points_{ch}"]
        if p.get("source") != "NO_DATA" and p.get("rd") is not None
    ]
    save_product("geo", _timestamp(snapshot["timestamp_utc"]), {
        "snapshot": snap, "hourly": hourly, "levels": levels,
    })


def snapshot(at: datetime | None = None) -> dict[str, Any]:
    stored = product("geo", at)
    if stored is None:
        return {"points": [], "summary": {"data_status": "loading"}}
    snap = dict(stored["snapshot"])
    snap["points"] = (
        snap.get("points_geo", []) + snap.get("points_hidro", [])
    )
    return snap


def point_history(
    at: datetime,
) -> dict[str, list[dict[str, Any]]]:
    with alert_store.connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT ON (referencia_em)"
            " referencia_em,dados->'levels' AS levels"
            " FROM hazardtrack.produto_monitoramento"
            " WHERE sistema='geo' AND referencia_em BETWEEN %s AND %s"
            " ORDER BY referencia_em,id DESC",
            (at - timedelta(hours=4, minutes=10), at),
        ).fetchall()
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        for ua_id, channel, rd in row["levels"] or []:
            out.setdefault(f"{ua_id}:{channel}", []).append({
                "ts": row["referencia_em"].isoformat(), "rd": rd,
            })
    return out


def import_fire() -> bool:
    paths = {k: FIRE_DIR / name for k, name in FIRE_FILES.items()}
    if not paths["stats"].exists() or not paths["snapshot"].exists():
        log.warning("Produtos de fogo ausentes; importacao nao realizada")
        return False
    data: dict[str, Any] = {}
    for key, path in paths.items():
        if not path.exists():
            log.warning("Horizonte de fogo ausente: %s", key)
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        if key not in ("stats", "snapshot"):
            raw = {
                str(f["properties"]["trecho_id"]):
                f["properties"].get("rf_classe") or "SEM_DADO"
                for f in raw.get("features", [])
                if f.get("properties", {}).get("trecho_id") is not None
            }
        data[key] = raw
    reference = datetime.fromtimestamp(
        paths["stats"].stat().st_mtime, timezone.utc,
    )
    save_product("fire", reference, data)
    return True


def bootstrap() -> None:
    """Importa legados idempotentemente; nunca apaga os arquivos originais."""
    if not alert_store.configured():
        return
    from . import admin_telemetry, alert_controls

    alert_store.initialize()
    raw = {}
    if alert_controls.CONTROLS_PATH.exists():
        raw = json.loads(alert_controls.CONTROLS_PATH.read_text("utf-8"))
        if not isinstance(raw, dict) or any(
            key in raw and not isinstance(raw[key], bool)
            for key in alert_controls._DEFAULTS
        ):
            raise ValueError("Controles legados invalidos; importacao abortada")
    seed_controls({
        **alert_controls._DEFAULTS, **raw,
    })
    entries = []
    if admin_telemetry.TELEMETRY_PATH.exists():
        for n, line in enumerate(
            admin_telemetry.TELEMETRY_PATH.read_text("utf-8").splitlines(), 1,
        ):
            try:
                entry = json.loads(line)
                _timestamp(entry["started_at"])
            except (ValueError, KeyError, TypeError):
                log.warning("Telemetria legada invalida na linha %d", n)
                continue
            entries.append(entry)
    if entries:
        record_telemetry(entries)
    import_fire()
    log.info("Persistencia administrativa pronta: %d ciclos importados",
             len(entries))
