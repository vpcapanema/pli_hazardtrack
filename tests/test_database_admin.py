"""Contrato HTTP e integracao das interfaces tabulares."""
import os
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch
from uuid import uuid4

from flask import Flask, Blueprint
import psycopg
from psycopg.conninfo import conninfo_to_dict

from core import alert_store
from core.database_admin import database_bp
from core.database_labels import COLUMN_LABELS, TABLE_LABELS

ROOT = Path(__file__).resolve().parents[1]
DSN = os.environ.get("HAZARDTRACK_TEST_DATABASE_URL", "")


def test_app():
    app = Flask(__name__, template_folder=str(ROOT / "templates"))
    app.secret_key = "test-only-secret"
    app.config["TESTING"] = True
    admin = Blueprint("admin", __name__)
    admin.add_url_rule("/admin/login", "login_page", lambda: "login")
    admin.add_url_rule("/admin/status", "status_page", lambda: "status")
    admin.add_url_rule("/admin/logout", "logout", lambda: "logout")
    app.add_url_rule("/", "index", lambda: "index")
    app.register_blueprint(admin)
    workspace = Blueprint("workspace", __name__)
    workspace.add_url_rule("/admin/central", "page", lambda: "central")
    app.register_blueprint(workspace)
    app.register_blueprint(database_bp)
    return app


class TestDatabaseAccess(unittest.TestCase):
    def setUp(self):
        self.app = test_app()
        self.client = self.app.test_client()

    def login(self, role="GESTOR"):
        with self.client.session_transaction() as session:
            session["admin_user"] = {
                "id": "test-actor", "tipo_usuario": role,
                "username": "teste", "full_name": "Gestor de teste",
            }
            session["database_csrf"] = "test-token"

    def test_unauthenticated_and_role(self):
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get("/admin/tabelas").status_code, 302)
        self.assertEqual(
            self.client.get("/admin/api/database").status_code, 401,
        )
        self.login("OPERADOR")
        self.assertEqual(
            self.client.get("/admin/api/database").status_code, 403,
        )

    def test_csrf_before_database(self):
        self.login()
        with patch.object(alert_store, "connection") as conn:
            for method in ("post", "patch", "delete"):
                result = getattr(self.client, method)(
                    "/admin/api/database/dominios/natureza_risco", json={},
                )
                self.assertEqual(result.status_code, 403)
            conn.assert_not_called()

    def test_page_order_and_private_cache(self):
        self.login()
        response = self.client.get("/admin/tabelas")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        text = response.get_data(as_text=True)
        markers = [
            'id="db-title"', 'class="db-table-shell"', 'id="db-filter"',
            'class="db-data-table"', 'class="db-actions"',
            'class="db-table-footer"', 'id="db-counter"',
        ]
        positions = [text.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions))

    def test_labels_cover_all_migrations(self):
        for path in (ROOT / "scripts" / "sql").glob("*.sql"):
            text = path.read_text("utf-8")
            for table, block in re.findall(
                r"CREATE TABLE IF NOT EXISTS \w+\.(\w+) \((.*?)\n\);",
                text, re.S,
            ):
                self.assertIn(table, TABLE_LABELS)
                for column in re.findall(
                    r"^    (\w+) (?:text|bigint|integer|boolean|uuid|jsonb|"
                    r"timestamptz|date|numeric|double|smallint)", block, re.M,
                ):
                    self.assertIn(column, COLUMN_LABELS)


@unittest.skipUnless(DSN, "Requer PostgreSQL exclusivo de teste")
class TestDatabaseIntegration(TestDatabaseAccess):
    @classmethod
    def setUpClass(cls):
        name = conninfo_to_dict(DSN).get("dbname", "")
        if not isinstance(name, str) or not name.startswith(
                "pli_hazardtrack_test_"):
            raise RuntimeError("Recusando banco nao exclusivo de teste")
        with psycopg.connect(DSN) as conn:
            for filename in sorted((ROOT / "scripts" / "sql").glob("*.sql")):
                conn.execute(filename.read_bytes())

    def setUp(self):
        super().setUp()
        self.env = patch.dict(os.environ, {"HAZARDTRACK_DATABASE_URL": DSN})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(alert_store.close)
        self.login()
        self.headers = {"X-CSRF-Token": "test-token"}
        self.url = "/admin/api/database/dominios/natureza_risco"

    def test_catalog_and_every_table(self):
        tables = self.client.get("/admin/api/database").get_json()["tables"]
        self.assertEqual(len(tables), 33)
        for table in tables:
            path = f"/admin/api/database/{table['schema']}/{table['name']}"
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200, result.get_json())
            self.assertLessEqual(len(result.get_json()["rows"]), 15)
            self.assertTrue(all(
                c["label"] for c in result.get_json()["columns"]
            ))

    def test_large_readonly_value_is_downloaded_without_truncation(self):
        signature = str(uuid4())
        payload = {"values": [str(uuid4()) for _ in range(1000)]}
        with psycopg.connect(DSN) as conn:
            inserted = conn.execute(
                "INSERT INTO hazardtrack.produto_monitoramento "
                "(sistema,referencia_em,assinatura,dados) "
                "VALUES ('geo',now(),%s,%s::jsonb) RETURNING id",
                (signature, json.dumps(payload)),
            ).fetchone()
            assert inserted is not None
            identifier = inserted[0]
        try:
            path = "/admin/api/database/hazardtrack/produto_monitoramento"
            response = self.client.get(path, query_string={
                "column": "assinatura", "value": signature,
            })
            self.assertEqual(response.status_code, 200)
            row = response.get_json()["rows"][0]
            self.assertIn("dados", row["__large_fields"])
            result = self.client.get(path + "/value", query_string={
                "column": "dados", "key": json.dumps({"id": str(identifier)}),
            })
            self.assertEqual(result.status_code, 200)
            self.assertEqual(json.loads(result.data), payload)
        finally:
            with psycopg.connect(DSN) as conn:
                conn.execute(
                    "DELETE FROM hazardtrack.produto_monitoramento "
                    "WHERE id=%s", (identifier,),
                )

    def test_crud_concurrency_audit_and_filter(self):
        code = "teste_" + str(uuid4())
        result = self.client.post(self.url, json={"values": {
            "codigo": code, "nome": "Teste de acentuação 100%_",
        }}, headers=self.headers)
        self.assertEqual(result.status_code, 200, result.get_json())
        args = {"column": "codigo", "value": code}
        result = self.client.get(self.url, query_string=args).get_json()
        self.assertEqual(result["total"], 1)
        row = result["rows"][0]
        descriptor = {"key": {"id": row["id"]}, "version": row["__version"]}
        update = {"records": [descriptor], "values": {"nome": "Revisão"}}
        self.assertEqual(self.client.patch(
            self.url, json=update, headers=self.headers,
        ).status_code, 200)
        self.assertEqual(self.client.patch(
            self.url, json=update, headers=self.headers,
        ).status_code, 409)
        payload = self.client.get(self.url, query_string=args).get_json()
        row = payload["rows"][0]
        self.assertEqual(row["nome"], "Revisão")
        descriptor["version"] = row["__version"]
        self.assertEqual(self.client.delete(
            self.url, json={"records": [descriptor]}, headers=self.headers,
        ).status_code, 200)
        with psycopg.connect(DSN) as conn:
            count_row = conn.execute(
                "SELECT count(*) FROM hazardtrack.auditoria_administrativa "
                "WHERE ator='test-actor' AND ("
                "dados->'anterior'->>'codigo'=%s OR "
                "dados->'posterior'->>'codigo'=%s)", (code, code),
            ).fetchone()
            assert count_row is not None
            self.assertEqual(count_row[0], 3)

    def test_invalid_inputs_and_read_only(self):
        for query in (
            {"column": "id; DROP TABLE x"}, {"sort": "id; SELECT 1"},
            {"page": "abc"},
        ):
            self.assertEqual(self.client.get(
                self.url, query_string=query,
            ).status_code, 400)
        result = self.client.get("/admin/api/database/public/pg_authid")
        self.assertEqual(result.status_code, 404)
        result = self.client.post(
            "/admin/api/database/hazardtrack/auditoria_administrativa",
            json={"values": {"acao": "x"}}, headers=self.headers,
        )
        self.assertEqual(result.status_code, 403)
        result = self.client.post(self.url, json={"values": {"id": 12}},
                                  headers=self.headers)
        self.assertEqual(result.status_code, 400)


if __name__ == "__main__":
    unittest.main()
