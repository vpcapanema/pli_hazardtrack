"""Consulta minima, somente leitura, ao cadastro central SIGMA."""
from uuid import UUID
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg import sql

from .sigma_auth import sigma_database_dsn, SigmaConnectionError


def search(kind, query="", identifier=None):
    if kind not in ("instituicao", "pessoa"):
        raise ValueError("Cadastro inválido.")
    if identifier:
        identifier = str(UUID(str(identifier)))
    field = "nome" if kind == "instituicao" else "nome_completo"
    dsn = sigma_database_dsn()
    if not dsn:
        raise SigmaConnectionError("Conexão de consulta ao SIGMA ausente.")
    try:
        with psycopg.Connection[dict[str, Any]].connect(
            dsn, row_factory=dict_row, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=5000",
        ) as conn:
            return conn.execute(sql.SQL(
                "SELECT id::text, {} AS nome FROM cadastro.{} "
                "WHERE ativa AND (%s::uuid IS NULL OR id=%s::uuid) "
                "AND (%s='' OR {} ILIKE %s) ORDER BY {} LIMIT 50"
            ).format(sql.Identifier(field), sql.Identifier(kind),
                     sql.Identifier(field), sql.Identifier(field)),
                (identifier, identifier, query, "%" + query[:120] + "%"),
            ).fetchall()
    except psycopg.Error as exc:
        raise SigmaConnectionError(
            "O cadastro central está temporariamente indisponível."
        ) from exc


def validate(values):
    """Nao aceita identidades externas inexistentes ou inativas."""
    for field, kind in (
        ("sigma_instituicao_id", "instituicao"),
        ("sigma_pessoa_id", "pessoa"),
    ):
        if field in values and values[field] is not None:
            if not search(kind, identifier=values[field]):
                raise ValueError(
                    "Cadastro não encontrado ou inativo no SIGMA."
                )
