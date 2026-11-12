"""Persistencia administrativa em PostgreSQL exclusivo de testes."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg.types.json import Jsonb

from core import admin_store, admin_telemetry, alert_controls, alert_store
from core import admin_analytics, admin_dashboard

TEST_DSN = os.environ.get("HAZARDTRACK_TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_DSN, "Configure banco PostgreSQL exclusivo de teste")
class TestAdminStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ, {
            "HAZARDTRACK_DATABASE_URL": TEST_DSN,
            "HAZARDTRACK_DATABASE_REQUIRED": "1",
            "SAMAEG_DISABLE_BOOTSTRAP": "1",
        })
        cls.env.start()
        cls.addClassCleanup(cls.env.stop)
        cls.addClassCleanup(alert_store.close)
        with alert_store.connection() as conn:
            name = conn.execute("SELECT current_database() AS n").fetchone()
            if name is None or not name["n"].startswith(
                    "pli_hazardtrack_test_"):
                raise RuntimeError("Recusando banco nao exclusivo de teste")
        alert_store.initialize()
        from app import app
        cls.app = app

    def setUp(self):
        with alert_store.connection() as conn:
            conn.execute(
                "TRUNCATE hazardtrack.telemetria_ciclo,"
                " hazardtrack.produto_monitoramento,"
                " hazardtrack.controle_monitoramento,"
                " hazardtrack.auditoria_administrativa",
            )
        admin_store.seed_controls({
            "geo_monitoring": True, "fire_monitoring": True,
        })
        self.now = datetime.now(timezone.utc) - timedelta(hours=5)
        self.client = self.app.test_client()
        with self.client.session_transaction() as session:
            session["admin_user"] = {
                "username": "gestor-teste", "tipo_usuario": "GESTOR",
            }
            session["database_csrf"] = "test-csrf"
        self.client.environ_base["HTTP_X_CSRF_TOKEN"] = "test-csrf"

    def sample(self, at=None, rd=2):
        geo = {
            "ua_id": "UA-1", "hazard": "geo", "rd": rd, "RAGEO": 4,
            "sigla_rodovia": "SP-055", "km_inicial": 100,
            "regiao_id": 1, "source": "MERGE/INPE",
            "ac24h_mm": 75, "ac96h_mm": 90, "intensity_mmh": 3,
            "geometry": {"type": "Point", "coordinates": [-45, -23]},
        }
        hydro = {**geo, "hazard": "hidro", "RAHID": 1}
        return {
            "timestamp_utc": (at or self.now).isoformat(),
            "regions": [{
                "regiao_id": 1, "regiao_nome": "R1",
                "hid24h_breaks": [70, 80, 120, 143],
            }],
            "summary": {"max_rd": rd, "data_status": "ok"},
            "points_geo": [geo], "points_hidro": [hydro],
            "points": [geo, hydro],
        }

    def test_migration_is_idempotent(self):
        with alert_store.connection() as conn:
            sql = alert_store._SQL / "002_administracao.sql"
            conn.execute(sql.read_bytes())
            conn.execute(sql.read_bytes())
            versions = conn.execute(
                "SELECT versao FROM hazardtrack.versao_esquema"
                " ORDER BY versao",
            ).fetchall()
        self.assertEqual([r["versao"] for r in versions], [1, 2, 3])

    def test_controls_survive_restart_and_are_audited(self):
        alert_controls.set_system("geo_monitoring", False, actor="gestor")
        alert_store.close()
        self.assertFalse(alert_controls.is_geo_enabled())
        with alert_store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM hazardtrack.auditoria_administrativa",
            ).fetchone()
        assert row is not None
        self.assertEqual(row["ator"], "gestor")
        self.assertEqual(row["dados"], {
            "system": "geo_monitoring", "before": True, "after": False,
        })
        admin_store.seed_controls({"geo_monitoring": True})
        self.assertFalse(alert_controls.is_geo_enabled())

    def test_control_and_audit_rollback_together(self):
        with patch.object(admin_store, "Jsonb", side_effect=[
            Jsonb({"geo_monitoring": False}),
            RuntimeError("audit error"),
        ]):
            with self.assertRaises(RuntimeError):
                admin_store.set_control("geo_monitoring", False, "gestor")
        self.assertTrue(alert_controls.is_geo_enabled())

    def test_telemetry_is_ordered_filtered_and_idempotent(self):
        entries = [
            {"started_at": (self.now + timedelta(minutes=n)).isoformat(),
             "outcome": "ok", "max_rd": n}
            for n in (20, 0, 10)
        ]
        admin_store.record_telemetry(entries)
        admin_store.record_telemetry(entries)
        self.assertEqual(admin_telemetry.count(), 3)
        self.assertEqual(
            [e["max_rd"] for e in admin_telemetry.load(limit=2)], [10, 20],
        )
        self.assertEqual(admin_telemetry.load(hours=1), [])

    def test_snapshot_preserves_native_attributes_without_geometry(self):
        snap = self.sample()
        admin_store.record_geo(snap, {"available": False})
        admin_store.record_geo(snap, {"available": False})
        alert_store.close()
        out = admin_store.snapshot()
        self.assertEqual(len(out["points"]), 2)
        self.assertEqual(out["points_geo"][0]["RAGEO"], 4)
        self.assertNotIn("geometry", out["points_geo"][0])
        self.assertEqual(out["points_hidro"][0]["RAHID"], 1)
        self.assertEqual(
            admin_store.database_details()["products"][0]["total"], 1,
        )

    def test_old_products_do_not_replace_latest_and_can_be_retrieved(self):
        later = self.now + timedelta(hours=1)
        admin_store.record_geo(self.sample(later, 4), {})
        admin_store.record_geo(self.sample(self.now, 1), {})
        self.assertEqual(admin_store.snapshot()["summary"]["max_rd"], 4)
        self.assertEqual(
            admin_store.snapshot(at=self.now)["summary"]["max_rd"], 1,
        )

    def test_escalation_uses_elapsed_time_not_seven_rows(self):
        for minutes, rd in ((0, 0), (61, 2), (241, 4)):
            admin_store.record_geo(
                self.sample(self.now + timedelta(minutes=minutes), rd), {},
            )
        out = admin_analytics._escalation(admin_store.snapshot())
        self.assertEqual(out["up_1h"], 2)
        self.assertEqual(out["up_4h"], 2)
        self.assertEqual(out["cycles_tracked"], 3)

    def test_no_data_is_not_a_false_reduction(self):
        admin_store.record_geo(self.sample(rd=4), {})
        snap = self.sample(self.now + timedelta(minutes=10), 0)
        for pt in snap["points"]:
            pt["source"] = "NO_DATA"
        admin_store.record_geo(snap, {"available": False})
        history = admin_store.point_history(self.now + timedelta(minutes=10))
        self.assertEqual(len(history["UA-1:geo"]), 1)
        result = admin_analytics._escalation(admin_store.snapshot())
        self.assertEqual(result["down_1h"], 0)

    def test_analytics_reads_database_without_runtime_history(self):
        admin_store.record_geo(
            self.sample(), {"available": True, "source": "MERGE bruto"},
        )
        admin_telemetry.record({
            "started_at": self.now.isoformat(), "outcome": "ok",
            "by_level": [0, 0, 2, 0, 0], "max_rd": 2,
        })
        with patch.object(admin_analytics.state, "get_snapshot",
                          side_effect=AssertionError("RAM")), \
                patch.object(admin_analytics.state, "get_point_history",
                             side_effect=AssertionError("RAM")):
            out = admin_analytics.build_analytics({}, 24)
        self.assertEqual(out["ops"]["storage"], "PostgreSQL")
        self.assertEqual(out["series"]["count"], 1)
        self.assertEqual(out["hourly"]["source"], "MERGE bruto")
        self.assertEqual(out["distributions"]["ac24h"]["max"], 75)

    def test_fire_import_and_horizons_survive_source_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / admin_store.FIRE_FILES["stats"]).write_text(
                json.dumps({"total_trechos": 1, "classes": {"alto": 1}}),
                encoding="utf-8",
            )
            (root / admin_store.FIRE_FILES["snapshot"]).write_text(
                json.dumps({"trechos": [{
                    "trecho_id": 1, "rf_valor": 0.8, "rf_classe": "alto",
                }]}), encoding="utf-8",
            )
            for name, cls in (("observado", "alto"), ("D+1", "critico")):
                (root / admin_store.FIRE_FILES[name]).write_text(
                    json.dumps({"features": [{"properties": {
                        "trecho_id": 1, "rf_classe": cls,
                    }}]}), encoding="utf-8",
                )
            with patch.object(admin_store, "FIRE_DIR", root):
                self.assertTrue(admin_store.import_fire())
                self.assertTrue(admin_store.import_fire())
        stats = admin_dashboard._fire_stats()
        horizons = admin_analytics._fire_horizons()
        self.assertEqual(stats["total_trechos"], 1)
        self.assertEqual(horizons["transitions"][0]["worsen"], 1)
        self.assertEqual(
            admin_store.database_details()["products"][0]["total"], 1,
        )

    def test_legacy_import_preserves_disabled_controls_and_skips_bad_lines(self):
        with alert_store.connection() as conn:
            conn.execute("TRUNCATE hazardtrack.controle_monitoramento")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controls = root / "alert_controls.json"
            telemetry = root / "cycle_telemetry.jsonl"
            controls.write_text(
                '{"geo_monitoring":false,"updated_by":"legado"}', "utf-8",
            )
            telemetry.write_text(json.dumps({
                "started_at": self.now.isoformat(), "outcome": "ok",
            }) + "\n{broken\n", "utf-8")
            with patch.object(alert_controls, "CONTROLS_PATH", controls), \
                    patch.object(admin_telemetry, "TELEMETRY_PATH", telemetry), \
                    patch.object(admin_store, "import_fire"):
                admin_store.bootstrap()
                admin_store.bootstrap()
            self.assertTrue(controls.exists())
            self.assertTrue(telemetry.exists())
        self.assertFalse(alert_controls.is_geo_enabled())
        self.assertEqual(alert_controls.get_state()["updated_by"], "legado")
        self.assertEqual(admin_telemetry.count(), 1)

    def test_controls_api_requires_boolean_and_audits_actor(self):
        response = self.client.post("/admin/api/alert-controls", json={
            "system": "geo_monitoring", "enabled": "false",
        })
        self.assertEqual(response.status_code, 400)
        self.assertTrue(alert_controls.is_geo_enabled())
        with patch("core.admin.alert_controls.apply_to_scheduler"):
            response = self.client.post("/admin/api/alert-controls", json={
                "system": "geo_monitoring", "enabled": False,
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["updated_by"], "gestor-teste")
        self.assertFalse(response.get_json()["geo_monitoring"])

    def test_invalid_legacy_controls_are_not_silently_enabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "controls.json"
            path.write_text('{"geo_monitoring":"false"}', "utf-8")
            with patch.object(alert_controls, "CONTROLS_PATH", path):
                with self.assertRaisesRegex(ValueError, "invalidos"):
                    admin_store.bootstrap()

    def test_report_is_stored_exactly_as_downloaded(self):
        response = self.client.get("/admin/api/reports/export?type=alertas")
        self.assertEqual(response.status_code, 200)
        self.assertIn("alerts", response.get_json())
        with alert_store.connection() as conn:
            row = conn.execute(
                "SELECT * FROM hazardtrack.auditoria_administrativa",
            ).fetchone()
        assert row is not None
        self.assertEqual(row["ator"], "gestor-teste")
        self.assertEqual(row["dados"]["body"], response.get_data(as_text=True))

    def test_database_failure_is_explicit_not_disk_fallback(self):
        with patch.object(admin_store, "controls",
                          side_effect=psycopg.OperationalError("offline")):
            response = self.client.get("/admin/api/alert-controls")
        self.assertEqual(response.status_code, 503)
        self.assertIn("indisponivel", response.get_json()["error"])

    def test_geo_statistics_use_native_database_snapshot(self):
        admin_store.record_geo(self.sample(), {})
        with patch.object(admin_dashboard.state, "get_snapshot",
                          side_effect=AssertionError("RAM")):
            stats = admin_dashboard._geo_stats()
        self.assertEqual(stats["uas_unique"], 1)
        self.assertEqual(stats["uas_total"], 2)
        self.assertEqual(stats["top_uas_geo"][0]["RAGEO"], 4)

    def test_pages_analytics_and_every_report_keep_their_shapes(self):
        admin_store.record_geo(self.sample(), {"available": False})
        admin_telemetry.record({
            "started_at": self.now.isoformat(), "outcome": "ok",
        })
        with patch("core.fire_pipeline.get_runner_status", return_value={}), \
                patch("core.admin._check_url", return_value={"ok": True}), \
                patch("core.admin.admin_auth.auth_backend_diag",
                      return_value={}):
            page = self.client.get("/admin/status")
            self.assertEqual(page.status_code, 200)
            for panel in (
                "visao", "saude", "estatisticas", "analytics", "relatorios",
                "controles", "sistema",
            ):
                self.assertIn(
                    f'id="panel-{panel}"', page.get_data(as_text=True),
                )
            dashboard = self.client.get("/admin/api/dashboard")
            self.assertEqual(dashboard.status_code, 200)
            self.assertEqual(
                dashboard.get_json()["stats"]["geodinamico"]["uas_unique"], 1,
            )
            diagnostics = self.client.get("/admin/api/diagnostics")
            self.assertEqual(diagnostics.status_code, 200)
            self.assertEqual(
                diagnostics.get_json()["database"]["schema_version"], 3,
            )
            for hours in (6, 24, 72, 168):
                response = self.client.get(
                    f"/admin/api/analytics?hours={hours}",
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["window_hours"], hours)
            for report in (
                "operacional", "overview", "geodinamico", "fogo", "alertas",
            ):
                response = self.client.get(
                    f"/admin/api/reports/export?type={report}",
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn("attachment", response.headers[
                    "Content-Disposition"
                ])
