"""Area restrita integrada: catalogos, historico e gestao institucional."""
from __future__ import annotations

import json
import secrets
from zoneinfo import ZoneInfo
from datetime import datetime

from flask import (
    Blueprint, abort, jsonify, render_template, request, session, Response,
    send_file, url_for,
)
from psycopg import sql

from . import alert_store, institution_directory
from .database_admin import (
    restricted, metadata, catalog, database_error, pool_error,
    request_error, private_response,
)
from .sigma_auth import SigmaConnectionError
import psycopg
from psycopg_pool import PoolTimeout
from werkzeug.exceptions import HTTPException

workspace_bp = Blueprint("workspace", __name__, url_prefix="/admin")
PAGES = {
    "visao": "Visão geral", "saude": "Monitoramento",
    "territorio": "Território e camadas", "alertas": "Alertas",
    "operacao": "Gestão operacional",
    "integracoes": "Comunicação e integrações",
    "analytics": "Análises", "estatisticas": "Estatísticas",
    "relatorios": "Relatórios", "administracao": "Administração",
    "controles": "Controles de monitoramento",
    "sistema": "Diagnóstico técnico",
}
workspace_bp.register_error_handler(psycopg.Error, database_error)
workspace_bp.register_error_handler(PoolTimeout, pool_error)
workspace_bp.register_error_handler(HTTPException, request_error)
workspace_bp.after_request(private_response)


@workspace_bp.route("/central")
@workspace_bp.route("/central/<section>")
@restricted
def page(section="visao"):
    if section not in PAGES:
        abort(404)
    session.setdefault("database_csrf", secrets.token_urlsafe(32))
    return render_template(
        "admin_workspace.html", section=section,
        csrf=session["database_csrf"], pages=PAGES,
    )


@workspace_bp.route("/api/workspace/summary")
@restricted
def summary():
    with alert_store.connection() as conn:
        counts = {}
        for name in (
            "instituicao_operadora", "unidade_operacional",
            "competencia_operacional", "contato_operacional",
            "regra_envio_alerta", "documento_referencia",
        ):
            row = conn.execute(sql.SQL(
                "SELECT count(*) AS n FROM hazardtrack.{}"
            ).format(sql.Identifier(name))).fetchone()
            if row is None:
                raise RuntimeError("Contagem sem retorno do banco")
            counts[name] = row["n"]
        config = conn.execute(
            "SELECT * FROM hazardtrack.configuracao_envio"
        ).fetchone()
    return jsonify(counts=counts, config=config, external_delivery=False)


@workspace_bp.route("/api/workspace/sigma/<kind>")
@restricted
def sigma_search(kind):
    try:
        return jsonify(items=institution_directory.search(
            kind, request.args.get("q", ""), request.args.get("id"),
        ))
    except ValueError as exc:
        abort(400, description=str(exc))
    except SigmaConnectionError as exc:
        return jsonify(error=str(exc)), 503


@workspace_bp.route("/api/workspace/options/<schema>/<table>")
@restricted
def options(schema, table):
    query = request.args.get("q", "")[:120]
    with alert_store.connection() as conn:
        meta = metadata(conn, schema, table)
        names = {c["name"] for c in meta["columns"]}
        if "id" not in names:
            abort(400, description="Tabela sem identificador simples.")
        title = next((n for n in ("nome", "titulo", "rotulo", "codigo")
                      if n in names), "id")
        items = conn.execute(sql.SQL(
            "SELECT id::text, {}::text AS nome FROM {} "
            "WHERE {}::text ILIKE %s OR id::text=%s ORDER BY id LIMIT 100"
        ).format(sql.Identifier(title), sql.Identifier(schema, table),
                 sql.Identifier(title)), ("%" + query + "%", query),
        ).fetchall()
    return jsonify(items=items)


@workspace_bp.route("/api/workspace/institutions")
@restricted
def institutions():
    with alert_store.connection() as conn:
        rows = conn.execute(
            "SELECT i.*, (SELECT count(*) FROM "
            "hazardtrack.unidade_operacional u WHERE u.instituicao_id=i.id) "
            "AS unidades, (SELECT count(*) FROM "
            "hazardtrack.contato_operacional c WHERE c.instituicao_id=i.id) "
            "AS contatos FROM hazardtrack.instituicao_operadora i "
            "ORDER BY i.id"
        ).fetchall()
    # Nomes sao lidos no SIGMA, nunca copiados para o banco operacional.
    warning = None
    for row in rows:
        try:
            match = institution_directory.search(
                "instituicao", identifier=row["sigma_instituicao_id"],
            )
            row["nome"] = match[0]["nome"] if match else "Cadastro inativo"
        except SigmaConnectionError:
            row["nome"] = "Instituição " + str(row["id"])
            warning = "SIGMA indisponível; nomes não puderam ser consultados."
    return jsonify(items=rows, warning=warning)


@workspace_bp.route("/api/workspace/territory")
@restricted
def territory():
    from . import zones
    features = {}
    for channel in (zones.get_zones_geo(), zones.get_zones_hidro()):
        for item in channel:
            key = str(item["ua_id"])
            features.setdefault(key, {}).update({
                k: v for k, v in item.items() if k != "hazard"
            })
    return jsonify(items=list(features.values()))


@workspace_bp.route("/api/workspace/layers")
@restricted
def layers():
    from .layer_exports import catalog as export_catalog
    return jsonify(items=[{
        "id": key, "nome": spec["nome"], "arquivo": spec["arquivo"],
        "grupo": spec["grupo"], "disponivel": spec["path"].is_file(),
        "download_url": url_for("workspace.export_layer", layer_id=key),
    } for key, spec in export_catalog().items()])


@workspace_bp.route("/api/workspace/layers/<layer_id>/export")
@restricted
def export_layer(layer_id):
    from .layer_exports import catalog as export_catalog
    from .managed_geodata import gpkg_path
    if layer_id == "geopackage":
        return send_file(
            gpkg_path(), as_attachment=True,
            download_name="hazardtrack-camadas-estruturais.gpkg",
            mimetype="application/geopackage+sqlite3",
        )
    spec = export_catalog().get(layer_id)
    if spec is None:
        abort(404, description="Camada não encontrada.")
    if not spec["path"].is_file():
        abort(404, description="Camada ainda não disponível.")
    if spec["layer"]:
        import geopandas as gpd
        frame = gpd.read_file(spec["path"], layer=spec["layer"])
        return Response(frame.to_json(), mimetype="application/geo+json",
                        headers={"Content-Disposition":
                                 'attachment; filename="'
                                 + spec["arquivo"] + '"'})
    return send_file(spec["path"], as_attachment=True,
                     download_name=spec["arquivo"],
                     mimetype="application/geo+json")


@workspace_bp.route("/api/workspace/alert/<int:alert_id>/json")
@restricted
def alert_json(alert_id):
    with alert_store.connection() as conn:
        row = conn.execute(
            "SELECT * FROM hazardtrack.alerta WHERE id=%s", (alert_id,),
        ).fetchone()
        events = conn.execute(
            "SELECT * FROM hazardtrack.evento_alerta WHERE alerta_id=%s "
            "ORDER BY id", (alert_id,),
        ).fetchall()
    if not row:
        abort(404, description="Alerta não encontrado.")
    payload = {"versao": "1", "sistema": "PLI-HazardTrack",
               "alerta": row, "eventos": events}
    return Response(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition":
                 f'attachment; filename="alerta-{alert_id}.json"'},
    )


@workspace_bp.route("/api/workspace/simulate", methods=["POST"])
@restricted
def simulate():
    """Simulacao explicita; nao chama notifier nem cria filas de entrega."""
    from .operational_routing import simulate_routing
    body = request.get_json(silent=True) or {}
    try:
        result = simulate_routing(
            str(body.get("ua_id", "")), str(body.get("natureza", "")),
            int(body.get("nivel", -1)), body.get("fase_id"),
            datetime.now(ZoneInfo("America/Sao_Paulo")).date(),
        )
    except (ValueError, TypeError) as exc:
        abort(400, description=str(exc))
    return jsonify(result)


@workspace_bp.route("/api/workspace/territory/import", methods=["POST"])
@restricted
def import_uas():
    from .managed_geodata import import_uas as perform_import
    if not request.content_length or request.content_length > 20_000_000:
        abort(413, description="O arquivo deve ter até 20 MB.")
    body = request.get_json(silent=True) or {}
    try:
        return jsonify(perform_import(
            body.get("geojson"), body.get("fonte"),
            str(session["admin_user"]["id"]), body.get("confirmar") is True,
        ))
    except (ValueError, TypeError, KeyError) as exc:
        abort(400, description=str(exc))


@workspace_bp.route("/api/workspace/territory/export")
@restricted
def export_uas():
    import geopandas as gpd
    from .managed_geodata import gpkg_path
    frame = gpd.read_file(gpkg_path(), layer="uas_area_estudo")
    return Response(frame.to_json(), mimetype="application/geo+json", headers={
        "Content-Disposition":
            'attachment; filename="uas-area-estudo.geojson"',
    })
