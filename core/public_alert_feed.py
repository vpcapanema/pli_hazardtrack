"""Feed publico incremental: apenas dados de risco, sem destinatarios."""
from datetime import datetime

from flask import Blueprint, jsonify, request, url_for
import psycopg
from psycopg_pool import PoolTimeout

from . import alert_store

public_alerts_bp = Blueprint("public_alerts", __name__)


@public_alerts_bp.route("/api/public/alerts")
def feed():
    try:
        after = int(request.args.get("after", 0))
        limit = int(request.args.get("limit", 100))
        if after < 0 or not 1 <= limit <= 200:
            raise ValueError
    except ValueError:
        return jsonify(error="Cursor ou limite inválido."), 400
    if not alert_store.configured():
        return jsonify(error="Histórico indisponível."), 503
    try:
        with alert_store.connection() as conn:
            rows = conn.execute(
                "SELECT e.id AS cursor, e.alerta_id, a.ua_id, a.canal, "
                "e.tipo, e.ocorrido_em, e.rd_anterior, e.rd, a.aberto_em "
                "FROM hazardtrack.evento_alerta e "
                "JOIN hazardtrack.alerta a ON a.id=e.alerta_id "
                "WHERE e.id>%s ORDER BY e.id LIMIT %s", (after, limit),
            ).fetchall()
    except (psycopg.Error, PoolTimeout):
        return jsonify(error="Histórico temporariamente indisponível."), 503
    for row in rows:
        for key, value in row.items():
            if isinstance(value, datetime):
                row[key] = value.isoformat()
            elif key in ("cursor", "alerta_id"):
                row[key] = str(value)
    cursor = rows[-1]["cursor"] if rows else str(after)
    response = jsonify(
        versao="1", eventos=rows, proximo_cursor=cursor,
        proxima_consulta=url_for(
            "public_alerts.feed", after=cursor, limit=limit, _external=True,
        ),
        consulta_recomendada_segundos=60,
    )
    response.headers["Cache-Control"] = "public, max-age=30"
    return response
