"""Contratos das paginas novas, SIGMA, geodados e simulacao."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from flask import Flask, Blueprint

from core.admin_workspace import workspace_bp, PAGES
from core.database_admin import database_bp
from core.institution_directory import validate
from core.managed_geodata import import_uas, active_dir
from core.public_alert_feed import public_alerts_bp
from core.operational_routing import in_scope

ROOT = Path(__file__).resolve().parents[1]


class WorkspacePages(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder=str(ROOT / "templates"))
        self.app.secret_key = "test-only"
        self.app.config["TESTING"] = True
        admin = Blueprint("admin", __name__)
        for route in ("login_page", "logout", "status_page"):
            admin.add_url_rule("/" + route, route, lambda: "ok")
        self.app.add_url_rule("/", "index", lambda: "ok")
        self.app.register_blueprint(admin)
        self.app.register_blueprint(workspace_bp)
        self.app.register_blueprint(database_bp)
        self.app.register_blueprint(public_alerts_bp)
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_user"] = {
                "id": "teste", "username": "teste",
                "tipo_usuario": "GESTOR", "full_name": "Gestor",
            }
            session["database_csrf"] = "csrf-test"

    def test_all_pages_and_auth(self):
        for page in PAGES:
            url = "/admin/central/" + page
            self.assertEqual(self.client.get(url).status_code, 302)
        self.login()
        for page in PAGES:
            response = self.client.get("/admin/central/" + page)
            self.assertEqual(response.status_code, 200)
            self.assertIn('id="panel-' + page + '"',
                          response.get_data(as_text=True))
        self.assertEqual(self.client.get(
            "/admin/central/inexistente"
        ).status_code, 404)

    def test_sigma_only_minimal_data(self):
        self.login()
        with patch("core.alert_store.configured", return_value=True), patch(
            "core.institution_directory.search",
            return_value=[{"id": "123", "nome": "Instituição"}],
        ):
            response = self.client.get(
                "/admin/api/workspace/sigma/instituicao?q=teste"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                set(response.get_json()["items"][0]), {"id", "nome"},
            )

    def test_import_requires_csrf(self):
        self.login()
        response = self.client.post(
            "/admin/api/workspace/territory/import", json={}
        )
        self.assertEqual(response.status_code, 403)

    def test_public_feed_validation(self):
        for query in ("after=-1", "limit=9999", "after=abc"):
            self.assertEqual(self.client.get(
                "/api/public/alerts?" + query
            ).status_code, 400)

    def test_layer_downloads_and_native_attributes(self):
        route = "/admin/api/workspace/layers"
        self.assertEqual(self.client.get(route).status_code, 401)
        self.login()
        with patch("core.alert_store.configured", return_value=True):
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            assert isinstance(payload, dict)
            items = {item["id"]: item for item in payload["items"]}
            for key, total in (("nativa-uas_area_estudo", 809),
                               ("nativa-regioes_estudo", 4),
                               ("nativa-municipios_area_estudo", 7)):
                result = self.client.get(items[key]["download_url"])
                self.assertEqual(result.status_code, 200)
                self.assertIn("attachment", result.headers[
                    "Content-Disposition"
                ])
                features = json.loads(result.data)["features"]
                self.assertEqual(len(features), total)
                self.assertIsNotNone(features[0]["geometry"])
                if key == "nativa-uas_area_estudo":
                    self.assertIn("RAGEO", features[0]["properties"])
                    self.assertIn("RAHID", features[0]["properties"])
            package = self.client.get(route + "/geopackage/export")
            self.assertEqual(package.status_code, 200)
            self.assertTrue(package.data.startswith(b"SQLite format 3"))
            package.close()
            self.assertEqual(self.client.get(
                route + "/arquivo-inexistente/export"
            ).status_code, 404)


class ReferenceValidation(unittest.TestCase):
    def test_sigma_missing_reference_rejected(self):
        with patch("core.institution_directory.search", return_value=[]):
            with self.assertRaises(ValueError):
                validate({"sigma_instituicao_id": "unknown"})

    def test_routing_scope(self):
        ua = {"ua_id": "UA-1", "regiao_id": 1,
              "sigla_rodovia": "SP-055", "km_inicial": 100,
              "km_final": 101, "lat": -23, "lon": -45}
        self.assertTrue(in_scope({"referencia_territorial": "estado:SP"}, ua))
        self.assertFalse(in_scope({"referencia_territorial": "regiao:2"}, ua))
        self.assertTrue(in_scope({"sigla_rodovia": "SP-055",
                                  "km_inicial": 99, "km_final": 102}, ua))
        self.assertFalse(in_scope({"sigla_rodovia": "SP-098",
                                   "km_inicial": 99, "km_final": 102}, ua))


class GeodataImport(unittest.TestCase):
    def test_isolated_import_and_duplicate_rejection(self):
        import geopandas as gpd
        from core.managed_geodata import gpkg_path
        with tempfile.TemporaryDirectory() as folder, patch.dict(
            os.environ, {"PLI_RUNTIME_DIR": folder}
        ):
            original = gpkg_path()
            frame = gpd.read_file(original, layer="uas_area_estudo")
            payload = json.loads(frame.iloc[:1].to_json())
            payload["features"][0]["properties"]["ua_id"] = "UA-TESTE-ISOLADO"
            for feature in payload["features"]:
                feature.pop("id", None)
            before = original.stat().st_mtime_ns
            result = import_uas(payload, "Fonte de teste isolado", "teste")
            self.assertTrue(result["validado"])
            self.assertIsNone(active_dir())
            with patch("core.alert_store.connection") as connection:
                connection.return_value.__enter__.return_value = MagicMock()
                result = import_uas(
                    payload, "Fonte de teste isolado", "teste", confirm=True,
                )
            self.assertEqual(result["total"], len(frame) + 1)
            self.assertEqual(original.stat().st_mtime_ns, before)
            activated = active_dir()
            assert activated is not None
            self.assertTrue((activated / "ua_geo.geojson").exists())
            self.assertTrue((activated / "ua_hidro.geojson").exists())
            with self.assertRaises(ValueError):
                import_uas(payload, "Fonte de teste isolado", "teste")


if __name__ == "__main__":
    unittest.main()
