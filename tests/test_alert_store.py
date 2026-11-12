"""Integracao PostgreSQL isolada: nunca executar contra banco operacional."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from psycopg import sql

from core import alert_store
from core.notifier import Notifier

TEST_DSN = os.environ.get("HAZARDTRACK_TEST_DATABASE_URL", "")


@unittest.skipUnless(TEST_DSN, "Configure banco PostgreSQL exclusivo de teste")
class TestAlertStore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ, {
            "HAZARDTRACK_DATABASE_URL": TEST_DSN,
            "HAZARDTRACK_DATABASE_REQUIRED": "1",
        })
        cls.env.start()
        cls.addClassCleanup(cls.env.stop)
        cls.addClassCleanup(alert_store.close)
        with alert_store.connection() as conn:
            db = conn.execute("SELECT current_database() AS db").fetchone()
            if db is None or not db["db"].startswith("pli_hazardtrack_test_"):
                raise RuntimeError("Recusando banco nao exclusivo de teste")
        alert_store.initialize()

    def setUp(self):
        with alert_store.connection() as conn:
            conn.execute(
                "TRUNCATE hazardtrack.tentativa_entrega,"
                " hazardtrack.notificacao, hazardtrack.evento_alerta,"
                " hazardtrack.alerta, hazardtrack.ciclo RESTART IDENTITY",
            )
        self.now = datetime(2026, 10, 26, 16, tzinfo=timezone.utc)
        self.point = {
            "ua_id": "UA-1", "hazard": "geo", "rd": 3,
            "source": "MERGE/INPE", "RAGEO": 4,
            "sigla_rodovia": "SP-055", "ac24h_mm": 100,
        }

    def observe(self, rd=3, minutes=0, transports=None, **extra):
        point = {**self.point, "rd": rd, **extra}
        alert_store.observe(
            [point], {}, self.now + timedelta(minutes=minutes),
            "geo", 3, transports or [], timedelta(hours=6),
        )

    def rows(self, table):
        allowed = {
            "alerta", "ciclo", "evento_alerta",
            "notificacao", "tentativa_entrega",
        }
        self.assertIn(table, allowed)
        with alert_store.connection() as conn:
            return conn.execute(
                sql.SQL("SELECT * FROM hazardtrack.{} ORDER BY id").format(
                    sql.Identifier(table)
                ),
            ).fetchall()

    def notifier(self):
        notifier = Notifier()
        notifier.enabled_email = False
        notifier.enabled_webhook = True
        notifier._send_webhook = lambda *a, **k: True
        return notifier

    def test_lifecycle_without_transports(self):
        self.observe()
        self.observe(4, 10)
        self.observe(3, 20)
        self.observe(1, 30)
        self.assertEqual(
            [r["tipo"] for r in self.rows("evento_alerta")],
            ["abertura", "escalada", "reducao", "encerramento"],
        )
        episode = self.rows("alerta")[0]
        self.assertEqual(episode["rd_maximo"], 4)
        self.assertIsNotNone(episode["encerrado_em"])
        self.assertEqual(self.rows("notificacao"), [])
        self.assertEqual(len(self.rows("ciclo")), 4)

    def test_no_data_does_not_close_episode(self):
        self.observe()
        self.observe(0, 10, source="NO_DATA")
        self.observe(0, 20, source="NO_DATA")
        self.observe(3, 30)
        self.assertEqual(
            [r["tipo"] for r in self.rows("evento_alerta")],
            ["abertura", "sem_dados", "retomada"],
        )
        self.assertIsNone(self.rows("alerta")[0]["encerrado_em"])

    def test_reopen_creates_new_episode(self):
        self.observe()
        self.observe(0, 10)
        self.observe(3, 20)
        self.assertEqual(len(self.rows("alerta")), 2)

    def test_duplicate_and_older_observations_are_ignored(self):
        self.observe(3, 10, transports=["webhook"])
        self.observe(3, 10, transports=["webhook"])
        self.observe(0, 0)
        self.assertEqual(len(self.rows("evento_alerta")), 1)
        self.assertEqual(len(self.rows("notificacao")), 1)
        self.assertIsNone(self.rows("alerta")[0]["encerrado_em"])

    def test_restart_preserves_transport_cooldown(self):
        first = self.notifier()
        self.assertEqual(first.evaluate(
            [self.point], {}, self.now, "geo",
        ), 1)
        restarted = self.notifier()
        self.assertEqual(restarted.evaluate(
            [self.point], {}, self.now + timedelta(minutes=10), "geo",
        ), 0)
        self.assertEqual(restarted.evaluate(
            [self.point], {}, self.now + timedelta(hours=7), "geo",
        ), 1)
        self.assertEqual(len(self.rows("tentativa_entrega")), 2)

    def test_failed_delivery_is_retried_and_audited(self):
        notifier = self.notifier()
        notifier._send_webhook = lambda *a, **k: False
        self.assertEqual(notifier.evaluate(
            [self.point], {}, self.now, "geo",
        ), 0)
        notifier = self.notifier()
        self.assertEqual(notifier.evaluate(
            [self.point], {}, self.now + timedelta(minutes=10), "geo",
        ), 1)
        self.assertEqual(
            [r["sucesso"] for r in self.rows("tentativa_entrega")],
            [False, True],
        )
        self.assertEqual(len(self.rows("notificacao")), 1)

    def test_transports_have_independent_cooldowns(self):
        self.observe(transports=["webhook", "email"])
        token, jobs = alert_store.claim("geo", "webhook", self.now)
        alert_store.finish(jobs, token, self.now, True, None)
        self.observe(3, 10, transports=["webhook", "email"])
        self.assertEqual(len(self.rows("notificacao")), 2)
        self.assertEqual(
            len(alert_store.claim("geo", "email", self.now)[1]), 1,
        )

    def test_lease_is_exclusive_and_recoverable(self):
        self.observe(transports=["webhook"])
        token, jobs = alert_store.claim("geo", "webhook", self.now)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(
            alert_store.claim("geo", "webhook", self.now)[1], [],
        )
        next_time = self.now + timedelta(minutes=6)
        next_token, recovered = alert_store.claim("geo", "webhook", next_time)
        self.assertEqual(len(recovered), 1)
        alert_store.finish(jobs, token, next_time, True, None)
        self.assertEqual(self.rows("tentativa_entrega"), [])
        alert_store.finish(recovered, next_token, next_time, True, None)
        self.assertEqual(len(self.rows("tentativa_entrega")), 1)

    def test_obsolete_failed_job_is_cancelled(self):
        self.observe(transports=["webhook"])
        self.observe(4, 10, transports=["webhook"])
        self.assertEqual(
            [r["estado"] for r in self.rows("notificacao")],
            ["cancelada", "pendente"],
        )

    def test_channels_and_ua_ids_are_independent(self):
        self.observe()
        alert_store.observe(
            [{**self.point, "ua_id": "UA-2"}, self.point],
            {}, self.now, "hidro", 3, [], timedelta(hours=6),
        )
        self.assertEqual(len(self.rows("alerta")), 3)

    def test_invalid_point_rolls_back_whole_cycle(self):
        with self.assertRaises(ValueError):
            alert_store.observe(
                [self.point, {**self.point, "ua_id": "UA-2", "rd": 9}],
                {}, self.now, "geo", 3, [], timedelta(hours=6),
            )
        self.assertEqual(self.rows("alerta"), [])
        self.assertEqual(self.rows("ciclo"), [])

    def test_history_paginates_and_uses_iso_dates(self):
        self.observe()
        self.observe(0, 10)
        self.observe(4, 20)
        page = alert_store.history(limit=1, channel="geo")
        self.assertEqual(len(page["alerts"]), 1)
        self.assertIn("+00:00", page["alerts"][0]["aberto_em"])
        older = alert_store.history(before=page["next_before"])
        self.assertEqual(len(older["alerts"]), 1)
        self.assertLess(
            older["alerts"][0]["id"], page["alerts"][0]["id"],
        )

    def test_history_contains_delivery_audit(self):
        self.notifier().evaluate([self.point], {}, self.now, "geo")
        history = alert_store.history()
        self.assertEqual(history["notifications"][0]["estado"], "enviada")
        self.assertTrue(history["attempts"][0]["sucesso"])

    def test_expired_obsolete_lease_does_not_block_escalation(self):
        self.observe(transports=["webhook"])
        alert_store.claim("geo", "webhook", self.now)
        self.observe(4, 10, transports=["webhook"])
        jobs = alert_store.claim(
            "geo", "webhook", self.now + timedelta(minutes=10),
        )[1]
        self.assertEqual([job["rd"] for job in jobs], [4])

    def test_disabled_transports_still_record_alerts(self):
        notifier = self.notifier()
        notifier.enabled_webhook = False
        self.assertEqual(
            notifier.evaluate([self.point], {}, self.now, "geo"), 0,
        )
        self.assertEqual(len(self.rows("alerta")), 1)
        self.assertEqual(self.rows("notificacao"), [])

    def test_monitoring_cycle_persists_and_marks_loss_of_data(self):
        from core.aggregator import State, notifier

        state = State()
        point = {
            **self.point, "ua_id": state.points_geo[0]["ua_id"],
        }

        def publish(_now):
            state.snapshot["timestamp_utc"] = _now.isoformat()
            state.snapshot["points_geo"] = [point]
            state.snapshot["points_hidro"] = []
            state.snapshot["summary"] = {"data_status": "ok"}
            return True

        def unavailable(now):
            state._publish_no_data(now)
            return True

        with patch("core.alert_controls.is_geo_enabled", return_value=True), \
                patch.object(notifier, "enabled_email", False), \
                patch.object(notifier, "enabled_webhook", False), \
                patch("core.admin_telemetry.record"):
            with patch("core.aggregator._resolve_now", return_value=self.now), \
                    patch.object(state, "_do_update", side_effect=publish):
                state.update()
            with patch(
                "core.aggregator._resolve_now",
                return_value=self.now + timedelta(minutes=10),
            ), patch.object(state, "_do_update", side_effect=unavailable):
                state.update()
        self.assertEqual(len(self.rows("ciclo")), 2)
        self.assertEqual(
            [r["tipo"] for r in self.rows("evento_alerta")],
            ["abertura", "sem_dados"],
        )
        self.assertFalse(self.rows("alerta")[0]["observavel"])


class TestAlertHistoryAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {"SAMAEG_DISABLE_BOOTSTRAP": "1"}):
            from app import app
        cls.app = app

    def setUp(self):
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_user"] = {
                "username": "teste", "tipo_usuario": "GESTOR",
            }

    def test_history_requires_login(self):
        self.assertEqual(
            self.client.get("/admin/api/alerts").status_code, 401,
        )

    def test_database_not_configured_is_explicit(self):
        self.login()
        with patch("core.alert_store.configured", return_value=False):
            self.assertEqual(
                self.client.get("/admin/api/alerts").status_code, 503,
            )

    def test_pagination_is_validated(self):
        self.login()
        with patch("core.alert_store.configured", return_value=True):
            for query in ("limit=0", "limit=201", "before=-1", "channel=bad"):
                self.assertEqual(
                    self.client.get("/admin/api/alerts?" + query).status_code,
                    400,
                )

    def test_filters_and_shape(self):
        self.login()
        result = {
            "alerts": [], "events": [], "notifications": [],
            "attempts": [], "next_before": None,
        }
        with patch("core.alert_store.configured", return_value=True), \
                patch("core.alert_store.history", return_value=result) as call:
            response = self.client.get(
                "/admin/api/alerts?channel=geo&limit=5&before=12&ua_id=UA-1",
            )
            self.assertEqual(response.get_json(), result)
            call.assert_called_once_with(
                limit=5, before=12, ua_id="UA-1", channel="geo",
            )
