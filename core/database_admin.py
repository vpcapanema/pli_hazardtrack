"""Administracao tabular: catalogo real, consultas e cadastros auditados."""
from __future__ import annotations

import hmac
import json
import secrets
from datetime import datetime, timezone
from functools import wraps

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb
from psycopg_pool import PoolTimeout
from werkzeug.exceptions import HTTPException
from flask import (
    Blueprint, abort, jsonify, redirect, render_template,
    request, session, url_for, Response,
)

from . import alert_store
from .database_labels import label
from . import institution_directory
from .sigma_auth import SigmaConnectionError

database_bp = Blueprint("database_admin", __name__, url_prefix="/admin")
SCHEMAS = ("hazardtrack", "dominios")
# Historico e estado do pipeline sao administrados por seus servicos.
# Novas tabelas nao recebem permissao de escrita implicitamente.
EDITABLE = {
    "dominios." + name for name in (
        "natureza_risco", "responsabilidade_operacional",
        "tipo_unidade_operacional", "tipo_abrangencia",
        "papel_institucional", "fase_operacional", "canal_envio",
    )
} | {
    "hazardtrack." + name for name in (
        "instituicao_operadora", "unidade_operacional",
        "programa_operacional", "programa_fase",
        "abrangencia_operacional", "abrangencia_componente",
        "documento_referencia", "competencia_operacional",
        "competencia_referencia", "abrangencia_referencia",
        "interlocutor_institucional", "contato_operacional",
        "regra_envio_alerta", "regra_envio_destino",
        "integracao_institucional", "configuracao_envio",
    )
}


def restricted(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = session.get("admin_user")
        if not user:
            if "/api/" in request.path:
                abort(401, description="Sessão expirada. Entre novamente.")
            return redirect(url_for(
                "admin.login_page", next=request.path,
            ))
        if user.get("tipo_usuario") not in ("GESTOR", "ADMIN"):
            abort(403, description="Acesso restrito à gestão e administração.")
        if request.method != "GET":
            token = session.get("database_csrf", "")
            if not token or not hmac.compare_digest(
                token.encode(),
                request.headers.get("X-CSRF-Token", "").encode(),
            ):
                abort(403, description="Sessão inválida. Recarregue a página.")
        if "/api/" in request.path and not alert_store.configured():
            return jsonify(error="Banco operacional não configurado."), 503
        return view(*args, **kwargs)
    return wrapped


@database_bp.errorhandler(HTTPException)
def request_error(exc):
    return jsonify(error=exc.description), exc.code


@database_bp.errorhandler(psycopg.Error)
def database_error(exc):
    if isinstance(exc, psycopg.IntegrityError):
        message = (
            "Registro inválido: verifique campos obrigatórios, duplicidades "
            "e vínculos com outras tabelas."
        )
        return jsonify(error=message), 409
    if isinstance(exc, psycopg.DataError):
        return jsonify(error="Valor incompatível com o tipo da coluna."), 400
    return jsonify(error="Não foi possível consultar o banco."), 503


@database_bp.errorhandler(PoolTimeout)
def pool_error(exc):
    return jsonify(error="Banco temporariamente indisponível."), 503


@database_bp.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@database_bp.route("/tabelas")
@restricted
def tables_page():
    session.setdefault("database_csrf", secrets.token_urlsafe(32))
    return render_template(
        "admin_tables.html", csrf=session["database_csrf"],
    )


def catalog(conn):
    tables = conn.execute(
        """SELECT n.nspname AS schema, c.relname AS name,
                  obj_description(c.oid) AS description
           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           WHERE n.nspname = ANY(%s) AND c.relkind IN ('r', 'p')
           ORDER BY c.relname, n.nspname""", (list(SCHEMAS),),
    ).fetchall()
    for table in tables:
        table["label"] = label(table["name"], table=True)
    return tables


def metadata(conn, schema, table):
    if schema not in SCHEMAS or not any(
        t["schema"] == schema and t["name"] == table
        for t in catalog(conn)
    ):
        abort(404, description="Tabela não encontrada.")
    columns = conn.execute(
        """SELECT a.attname AS name,
                  format_type(a.atttypid, a.atttypmod) AS type,
                  t.typname AS udt, NOT a.attnotnull AS nullable,
                  pg_get_expr(d.adbin, d.adrelid) AS "default",
                  a.attidentity <> '' OR a.attgenerated <> '' AS generated,
                  col_description(c.oid, a.attnum) AS description,
                  EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid=c.oid
                    AND i.indisprimary AND a.attnum=ANY(i.indkey)) AS pk
           FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
           JOIN pg_attribute a ON a.attrelid=c.oid
           JOIN pg_type t ON t.oid=a.atttypid
           LEFT JOIN pg_attrdef d ON d.adrelid=c.oid AND d.adnum=a.attnum
           WHERE n.nspname=%s AND c.relname=%s
             AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum""",
        (schema, table),
    ).fetchall()
    writable = f"{schema}.{table}" in EDITABLE
    references = conn.execute(
        """SELECT a.attname AS column, rn.nspname AS schema,
                  rc.relname AS table, ra.attname AS key
           FROM pg_constraint fk
           JOIN pg_class c ON c.oid=fk.conrelid
           JOIN pg_namespace n ON n.oid=c.relnamespace
           JOIN pg_class rc ON rc.oid=fk.confrelid
           JOIN pg_namespace rn ON rn.oid=rc.relnamespace
           CROSS JOIN LATERAL unnest(fk.conkey, fk.confkey) k(a,b)
           JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum=k.a
           JOIN pg_attribute ra ON ra.attrelid=rc.oid AND ra.attnum=k.b
           WHERE fk.contype='f' AND n.nspname=%s AND c.relname=%s""",
        (schema, table),
    ).fetchall()
    for column in columns:
        column["label"] = label(column["name"])
        column["reference"] = next((r for r in references
                                    if r["column"] == column["name"]
                                    and r["key"] == "id"), None)
    return {
        "schema": schema, "name": table, "label": label(table, True),
        "columns": columns,
        "pk": [c["name"] for c in columns if c["pk"]],
        "writable": writable,
        "read_only_reason": "" if writable else (
            "Tabela mantida automaticamente pelo sistema; somente consulta."
        ),
    }


@database_bp.route("/api/database")
@restricted
def tables_catalog():
    if not alert_store.configured():
        return jsonify(error="Banco operacional não configurado."), 503
    with alert_store.connection() as conn:
        return jsonify(tables=catalog(conn))


def query_filter(meta):
    column = request.args.get("column", "")
    if not column:
        return sql.SQL("TRUE"), []
    if column not in {c["name"] for c in meta["columns"]}:
        abort(400, description="Coluna de filtro inválida.")
    ident = sql.Identifier(column)
    empty = request.args.get("empty") == "1"
    if empty:
        predicate = sql.SQL("({0} IS NULL OR {0}::text = '')").format(ident)
        values = []
    else:
        value = request.args.get("value", "")
        if len(value) > 1000:
            abort(400, description="Filtro muito longo.")
        # Pesquisa literal, inclusive %, _ e barras.
        value = value.replace("\\", "\\\\")
        value = value.replace("%", "\\%").replace("_", "\\_")
        predicate = sql.SQL(
            "COALESCE({}::text ILIKE %s, FALSE)"
        ).format(ident)
        values = ["%" + value + "%"]
    if request.args.get("invert") == "1":
        predicate = sql.SQL("NOT ({})").format(predicate)
    return predicate, values


@database_bp.route("/api/database/<schema>/<table>")
@restricted
def table_rows(schema, table):
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        abort(400, description="Página inválida.")
    with alert_store.connection() as conn:
        # Contagem e pagina pertencem ao mesmo snapshot.
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
        meta = metadata(conn, schema, table)
        where, params = query_filter(meta)
        relation = sql.Identifier(schema, table)
        count_row = conn.execute(sql.SQL(
            "SELECT count(*) AS n FROM {} WHERE {}"
        ).format(relation, where), params).fetchone()
        if count_row is None:
            raise RuntimeError("Contagem sem retorno do banco")
        total = count_row["n"]
        pages = max(1, (total + 14) // 15)
        page = min(page, pages)
        sort = request.args.get("sort") or (
            meta["pk"][0] if meta["pk"] else meta["columns"][0]["name"]
        )
        if sort not in {c["name"] for c in meta["columns"]}:
            abort(400, description="Ordenação inválida.")
        direction = sql.SQL(
            "DESC" if request.args.get("direction") == "desc" else "ASC"
        )
        order = sql.SQL(", ").join(
            sql.SQL("{} {}").format(sql.Identifier(c), direction)
            for c in dict.fromkeys([sort] + meta["pk"])
        )
        # Valores textuais conservam bigint/numeric/JSON sem perda no JS.
        lazy = [c["name"] for c in meta["columns"]
                if not meta["writable"] and meta["pk"]
                and c["udt"] in ("json", "jsonb", "text")
                and c["name"] not in meta["pk"]]
        fields = []
        deferred = []
        for col in meta["columns"]:
            ident = sql.Identifier(col["name"])
            if col["name"] in lazy:
                fields.append(sql.SQL(
                    "CASE WHEN pg_column_size({0}) > 4096 "
                    "THEN NULL ELSE {0}::text END AS {0}"
                ).format(ident))
                deferred.append(sql.SQL(
                    "CASE WHEN pg_column_size({}) > 4096 THEN {} END"
                ).format(ident, sql.Literal(col["name"])))
            else:
                fields.append(sql.SQL("{0}::text AS {0}").format(ident))
        fields.append(sql.SQL(
            "array_remove(ARRAY[{}]::text[],NULL) AS __large_fields"
        ).format(sql.SQL(", ").join(deferred)))
        fields = sql.SQL(", ").join(fields)
        rows = conn.execute(sql.SQL(
            "SELECT {}, xmin::text AS __version FROM {} "
            "WHERE {} ORDER BY {} LIMIT 15 OFFSET %s"
        ).format(fields, relation, where, order),
            params + [(page - 1) * 15],
        ).fetchall()
        return jsonify(
            **meta, rows=rows, page=page, pages=pages, total=total,
        )


@database_bp.route("/api/database/<schema>/<table>/value")
@restricted
def complete_value(schema, table):
    try:
        key = json.loads(request.args.get("key", "{}"))
    except ValueError:
        abort(400, description="Chave primária inválida.")
    with alert_store.connection() as conn:
        meta = metadata(conn, schema, table)
        column = request.args.get("column")
        if (not meta["pk"] or not isinstance(key, dict)
                or set(key) != set(meta["pk"])
                or not isinstance(column, str)
                or column not in {c["name"] for c in meta["columns"]}):
            abort(400, description="Coluna ou chave primária inválida.")
        where = sql.SQL(" AND ").join(
            sql.SQL("{}=%s").format(sql.Identifier(k)) for k in meta["pk"]
        )
        row = conn.execute(sql.SQL(
            "SELECT {}::text AS value FROM {} WHERE {}"
        ).format(sql.Identifier(column), sql.Identifier(schema, table),
                 where), [key[k] for k in meta["pk"]]).fetchone()
        if row is None:
            abort(404, description="Registro não encontrado.")
    return Response(row["value"] or "", mimetype="text/plain", headers={
        "Content-Disposition":
            f'attachment; filename="{table}-{column}.txt"',
    })


def payload_values(meta, data, updating=False):
    if not isinstance(data, dict) or not data:
        abort(400, description="Informe os campos do registro.")
    fields = {c["name"]: c for c in meta["columns"]}
    values = {}
    for name, value in data.items():
        col = fields.get(name)
        if col is None or col["generated"] or (
            updating and col["pk"]
        ) or name in {"criado_em", "atualizado_em", "sigma_validado_em"}:
            abort(400, description="Coluna não editável: " + name)
        if col["udt"] in {"json", "jsonb"} and value is not None:
            value = Jsonb(value)
        elif value is not None and not isinstance(value, (str, bool, int)):
            abort(400, description="Valor inválido: " + name)
        values[name] = value
    try:
        institution_directory.validate(values)
    except ValueError as exc:
        abort(400, description=str(exc))
    except SigmaConnectionError as exc:
        abort(503, description=str(exc))
    if {"sigma_instituicao_id", "sigma_pessoa_id"} & values.keys():
        values["sigma_validado_em"] = datetime.now(timezone.utc)
    return values


@database_bp.route(
    "/api/database/<schema>/<table>", methods=["POST", "PATCH", "DELETE"],
)
@restricted
def mutate_table(schema, table):
    if request.content_length and request.content_length > 1_000_000:
        abort(413, description="Registro excede o limite de tamanho.")
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400, description="Corpo JSON inválido.")
    with alert_store.connection() as conn:
        meta = metadata(conn, schema, table)
        if not meta["writable"] or not meta["pk"]:
            abort(403, description="Tabela disponível somente para consulta.")
        actor = str(session["admin_user"]["id"])
        conn.execute(
            "SELECT set_config('hazardtrack.sigma_usuario_id', %s, true)",
            (actor,),
        )
        relation = sql.Identifier(schema, table)
        if request.method == "POST":
            values = payload_values(meta, body.get("values"))
            conn.execute(sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                relation,
                sql.SQL(", ").join(map(sql.Identifier, values)),
                sql.SQL(", ").join(sql.Placeholder() for _ in values),
            ), list(values.values()))
        else:
            records = body.get("records")
            if not isinstance(records, list) or not 1 <= len(records) <= 15:
                abort(400, description="Selecione de 1 a 15 registros.")
            if request.method == "PATCH" and len(records) != 1:
                abort(400, description="Edite um registro por vez.")
            for record in records:
                if not isinstance(record, dict):
                    abort(400, description="Registro inválido.")
                key = record.get("key")
                if not isinstance(key, dict) or set(key) != set(meta["pk"]):
                    abort(400, description="Chave primária inválida.")
                version = record.get("version")
                if not isinstance(version, str) or not version.isdigit():
                    abort(400, description="Versão do registro inválida.")
                predicates: list[sql.Composable] = [
                    sql.SQL("{} = %s").format(sql.Identifier(k))
                    for k in meta["pk"]
                ]
                predicates.append(sql.SQL("xmin::text = %s"))
                where = sql.SQL(" AND ").join(predicates)
                params = [key[k] for k in meta["pk"]] + [version]
                if request.method == "DELETE":
                    result = conn.execute(sql.SQL(
                        "DELETE FROM {} WHERE {}"
                    ).format(relation, where), params)
                else:
                    values = payload_values(meta, body.get("values"), True)
                    assignments = sql.SQL(", ").join(
                        sql.SQL("{} = %s").format(sql.Identifier(k))
                        for k in values
                    )
                    result = conn.execute(sql.SQL(
                        "UPDATE {} SET {} WHERE {}"
                    ).format(relation, assignments, where),
                        list(values.values()) + params)
                if result.rowcount != 1:
                    abort(409, description=(
                        "Registro alterado por outra sessão. Recarregue."
                    ))
    return jsonify(ok=True)
