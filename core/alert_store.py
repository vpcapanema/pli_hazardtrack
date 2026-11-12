"""Historico operacional e fila transacional de alertas PostgreSQL."""
from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Iterator
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool, PoolTimeout

log = logging.getLogger("alert_store")
_SQL = Path(__file__).resolve().parent.parent / "scripts" / "sql"
_lock = Lock()
_pool_lock = Lock()
_pool: ConnectionPool[psycopg.Connection[dict[str, Any]]] | None = None
_pool_dsn: str | None = None
_initialized_dsn: str | None = None
_status: dict[str, Any] = {"connected": False, "last_error": None}


def database_url() -> str:
    raw = os.environ.get("HAZARDTRACK_DATABASE_URL", "").strip()
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


def configured() -> bool:
    return bool(database_url())


def required() -> bool:
    return os.environ.get("HAZARDTRACK_DATABASE_REQUIRED", "0") == "1"


def close() -> None:
    global _pool, _pool_dsn
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _pool_dsn = None


def _connection_pool() -> ConnectionPool[psycopg.Connection[dict[str, Any]]]:
    global _pool, _pool_dsn
    dsn = database_url()
    if not dsn:
        raise RuntimeError("HAZARDTRACK_DATABASE_URL nao configurada")
    with _pool_lock:
        if _pool is None or _pool_dsn != dsn:
            if _pool is not None:
                _pool.close()
            _pool = ConnectionPool[psycopg.Connection[dict[str, Any]]](
                dsn, min_size=1, max_size=4, timeout=10, open=True,
                check=(
                    ConnectionPool[psycopg.Connection[dict[str, Any]]]
                    .check_connection
                ),
                kwargs={
                    "row_factory": dict_row, "connect_timeout": 5,
                    "application_name": "pli-hazardtrack",
                    "options": (
                        "-c statement_timeout=15000 -c lock_timeout=5000"
                    ),
                },
            )
            _pool_dsn = dsn
        return _pool


@contextmanager
def connection() -> Iterator[psycopg.Connection[dict[str, Any]]]:
    try:
        with _connection_pool().connection() as conn:
            yield conn
        _status.update(connected=True, last_error=None)
    except (psycopg.Error, PoolTimeout) as exc:
        # DSNs, enderecos de canais e credenciais nunca vao a telemetria.
        _status.update(connected=False, last_error=type(exc).__name__)
        log.error("Banco operacional indisponivel: %s", type(exc).__name__)
        raise


def initialize() -> None:
    global _initialized_dsn
    if not configured():
        if required():
            raise RuntimeError("Banco operacional obrigatorio sem conexao")
        log.warning("Banco operacional nao configurado (modo local em RAM)")
        return
    with _lock:
        if _initialized_dsn == database_url():
            return
        with connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(572043001)")
            conn.execute((_SQL / "001_alertas.sql").read_bytes())
            conn.execute((_SQL / "002_administracao.sql").read_bytes())
            conn.execute(
                (_SQL / "003_gestao_institucional.sql").read_bytes()
            )
        _initialized_dsn = database_url()


def status() -> dict[str, Any]:
    return {
        "configured": configured(), "required": required(),
        **_status,
    }


def _evidence(point: dict[str, Any]) -> dict[str, Any]:
    return {
        k: v for k, v in point.items()
        if k not in ("geometry", "history") and not k.startswith("_")
    }


def _cycle(conn, now: datetime, data: dict[str, Any]) -> int:
    row = conn.execute(
        "INSERT INTO hazardtrack.ciclo (iniciado_em, dados) VALUES (%s,%s)"
        " ON CONFLICT (iniciado_em) DO UPDATE"
        " SET dados = hazardtrack.ciclo.dados || EXCLUDED.dados"
        " RETURNING id",
        (now, Jsonb(data)),
    ).fetchone()
    return row["id"]


def record_cycle(now: datetime, data: dict[str, Any]) -> None:
    initialize()
    with connection() as conn:
        _cycle(conn, now, data)


def observe(
    points: list[dict[str, Any]], summary: dict[str, Any],
    now: datetime, channel: str, threshold: int,
    transports: list[str], cooldown: timedelta,
) -> None:
    """Persiste transicoes e enfileira envios na mesma transacao."""
    if channel not in ("geo", "hidro"):
        raise ValueError("Canal de alerta invalido")
    if not 1 <= threshold <= 4:
        raise ValueError("Limiar de alerta deve estar entre 1 e 4")
    ids = [p.get("ua_id") or p.get("id") for p in points]
    if any(not zid for zid in ids) or len(set(ids)) != len(ids):
        raise ValueError("Identificadores de UA ausentes ou duplicados")
    initialize()
    with connection() as conn:
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            ("hazardtrack:" + channel,),
        )
        cycle_id = _cycle(conn, now, {"summary": summary})
        active = {
            row["ua_id"]: row for row in conn.execute(
                "SELECT * FROM hazardtrack.alerta"
                " WHERE canal=%s AND encerrado_em IS NULL FOR UPDATE",
                (channel,),
            ).fetchall()
        }
        for zid, point in zip(ids, points):
            old = active.get(zid)
            if old and now <= old["atualizado_em"]:
                continue
            rd = point.get("rd")
            known = (
                point.get("source") != "NO_DATA"
                and point.get("nivel") != "Fora de cobertura"
                and not str(point.get("nivel", "")).startswith("SEM DADO")
                and rd is not None
            )
            if known and (
                isinstance(rd, bool) or not isinstance(rd, int)
                or not 0 <= rd <= 4
            ):
                raise ValueError("RD invalido")
            evidence = _evidence(point)
            event = None
            if not old:
                if not known or rd is None or rd < threshold:
                    continue
                old = conn.execute(
                    "INSERT INTO hazardtrack.alerta"
                    " (ua_id,canal,aberto_em,atualizado_em,"
                    " rd_atual,rd_maximo,evidencia)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *",
                    (zid, channel, now, now, rd, rd, Jsonb(evidence)),
                ).fetchone()
                if old is None:
                    raise RuntimeError("Alerta inserido sem retorno do banco")
                event = "abertura"
                previous = None
            else:
                previous = old["rd_atual"]
                if not known:
                    if old["observavel"]:
                        event = "sem_dados"
                elif rd is not None and rd < threshold:
                    event = "encerramento"
                elif rd != previous:
                    event = "escalada" if rd > previous else "reducao"
                elif not old["observavel"]:
                    event = "retomada"
                conn.execute(
                    "UPDATE hazardtrack.alerta SET atualizado_em=%s,"
                    " rd_atual=%s, rd_maximo=greatest(rd_maximo,%s),"
                    " observavel=%s, evidencia=%s, encerrado_em=%s"
                    " WHERE id=%s",
                    (now, rd if known else previous,
                     rd if known else previous, known, Jsonb(evidence),
                     now if event == "encerramento" else None, old["id"]),
                )
            if event:
                conn.execute(
                    "INSERT INTO hazardtrack.evento_alerta"
                    " (alerta_id,ciclo_id,ocorrido_em,tipo,"
                    " rd_anterior,rd,evidencia)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (old["id"], cycle_id, now, event, previous,
                     rd if known else None, Jsonb(evidence)),
                )
            # Nao comunicar dados antigos apos recuo, fechamento ou perda.
            conn.execute(
                "UPDATE hazardtrack.notificacao SET estado='cancelada'"
                " WHERE alerta_id=%s AND (estado='pendente'"
                " OR (estado='processando' AND lease_ate<=%s))"
                " AND (%s OR rd <> %s)",
                (old["id"], now,
                 not known or rd is None or rd < threshold, rd),
            )
            if not known or rd is None or rd < threshold:
                continue
            for transport in transports:
                last = conn.execute(
                    "SELECT rd,enviada_em FROM hazardtrack.notificacao"
                    " WHERE alerta_id=%s AND transporte=%s"
                    " AND estado='enviada'"
                    " ORDER BY enviada_em DESC, id DESC LIMIT 1",
                    (old["id"], transport),
                ).fetchone()
                if (last and rd <= last["rd"]
                        and now - last["enviada_em"] < cooldown):
                    continue
                conn.execute(
                    "INSERT INTO hazardtrack.notificacao"
                    " (alerta_id,transporte,rd,criada_em,"
                    " proxima_tentativa,conteudo)"
                    " VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (old["id"], transport, rd, now, now,
                     Jsonb({"point": evidence, "summary": summary})),
                )


def claim(
    channel: str, transport: str, now: datetime,
) -> tuple[str, list[dict[str, Any]]]:
    token = str(uuid4())
    with connection() as conn:
        rows = conn.execute(
            "WITH jobs AS ("
            " SELECT n.id FROM hazardtrack.notificacao n"
            " JOIN hazardtrack.alerta a ON a.id=n.alerta_id"
            " WHERE a.canal=%s AND n.transporte=%s"
            " AND a.encerrado_em IS NULL AND a.observavel"
            " AND a.rd_atual=n.rd AND ("
            " (n.estado='pendente' AND n.proxima_tentativa<=%s)"
            " OR (n.estado='processando' AND n.lease_ate<=%s))"
            " ORDER BY n.id LIMIT 100 FOR UPDATE OF n SKIP LOCKED)"
            " UPDATE hazardtrack.notificacao n SET estado='processando',"
            " lease_token=%s, lease_ate=%s FROM jobs"
            " WHERE n.id=jobs.id RETURNING n.*",
            (channel, transport, now, now, token,
             now + timedelta(minutes=5)),
        ).fetchall()
    return token, rows


def finish(
    jobs: list[dict[str, Any]], token: str, now: datetime,
    success: bool, error: str | None,
) -> None:
    with connection() as conn:
        for job in jobs:
            row = conn.execute(
                "UPDATE hazardtrack.notificacao SET estado=%s,"
                " enviada_em=%s, proxima_tentativa=%s,"
                " lease_token=NULL, lease_ate=NULL"
                " WHERE id=%s AND lease_token=%s"
                " AND estado='processando' RETURNING id",
                ("enviada" if success else "pendente",
                 now if success else None, now + timedelta(minutes=5),
                 job["id"], token),
            ).fetchone()
            if row:
                conn.execute(
                    "INSERT INTO hazardtrack.tentativa_entrega"
                    " (notificacao_id,ocorrido_em,sucesso,erro)"
                    " VALUES (%s,%s,%s,%s)",
                    (job["id"], now, success, error),
                )


def history(
    *, limit: int = 100, before: int | None = None,
    ua_id: str | None = None, channel: str | None = None,
) -> dict[str, Any]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT * FROM hazardtrack.alerta"
            " WHERE (%s::bigint IS NULL OR id < %s)"
            " AND (%s::text IS NULL OR ua_id=%s)"
            " AND (%s::text IS NULL OR canal=%s)"
            " ORDER BY id DESC LIMIT %s",
            (before, before, ua_id, ua_id, channel, channel, limit),
        ).fetchall()
        ids = [r["id"] for r in rows]
        events = conn.execute(
            "SELECT * FROM hazardtrack.evento_alerta"
            " WHERE alerta_id=ANY(%s) ORDER BY id", (ids,),
        ).fetchall() if ids else []

        notifications = conn.execute(
            "SELECT id,alerta_id,transporte,rd,criada_em,enviada_em,"
            " estado,proxima_tentativa FROM hazardtrack.notificacao"
            " WHERE alerta_id=ANY(%s) ORDER BY id", (ids,),
        ).fetchall() if ids else []
        notification_ids = [r["id"] for r in notifications]
        attempts = conn.execute(
            "SELECT * FROM hazardtrack.tentativa_entrega"
            " WHERE notificacao_id=ANY(%s) ORDER BY id",
            (notification_ids,),
        ).fetchall() if notification_ids else []

    def serialize(row):
        return {
            key: value.isoformat() if isinstance(value, datetime) else value
            for key, value in row.items()
        }

    return {"alerts": [serialize(row) for row in rows],
            "events": [serialize(row) for row in events],
            "notifications": [serialize(row) for row in notifications],
            "attempts": [serialize(row) for row in attempts],
            "next_before": rows[-1]["id"] if len(rows) == limit else None}
