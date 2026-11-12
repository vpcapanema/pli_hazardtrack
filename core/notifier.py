"""
Servico de notificacao de alertas (e-mail / webhook).

Dispara quando uma ZONA atinge Risco Dinamico (RD) >= limiar, com politica
anti-spam (cooldown por zona + reenvio so em escalada de nivel).

Canais (configurados por ambiente; sem config -> servico DESABILITADO, nunca
mock):
- E-mail (SMTP):   SAMAEG_SMTP_HOST, SAMAEG_SMTP_PORT, SAMAEG_SMTP_USER,
                   SAMAEG_SMTP_PASS, SAMAEG_ALERT_EMAIL_FROM,
                   SAMAEG_ALERT_EMAIL_TO (lista separada por virgula).
- Webhook (HTTP):  SAMAEG_ALERT_WEBHOOK_URL  (POST JSON; serve Slack/Telegram/
                   gateway de SMS/etc).

Parametros:
- SAMAEG_RD_ALERT_THRESHOLD (default 3 = "Alto")
- SAMAEG_ALERT_COOLDOWN_H   (default 6 h)

Politica de dados: nunca inventa. Se um canal falha, registra erro e segue;
falha de notificacao NUNCA interrompe o ciclo de monitoramento.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from threading import Lock
from typing import Dict, List, Optional, Tuple, Any
import logging
import os
import smtplib

from . import alert_store

log = logging.getLogger("notifier")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _emails_to() -> List[str]:
    raw = _env("SAMAEG_ALERT_EMAIL_TO")
    return [e.strip() for e in raw.split(",") if e.strip()]


@dataclass
class NotifierStatus:
    enabled_email: bool = False
    enabled_webhook: bool = False
    threshold: int = 3
    cooldown_h: float = 6.0
    sent_total: int = 0
    last_sent_at: Optional[str] = None
    last_error: Optional[str] = None
    last_error_at: Optional[str] = None
    last_alert_count: int = 0
    channels_ok: Dict[str, bool] = field(default_factory=dict)


class Notifier:
    def __init__(self):
        self._lock = Lock()
        self._evaluate_lock = Lock()
        self.threshold = int(_env("SAMAEG_RD_ALERT_THRESHOLD", "3"))
        self.cooldown = timedelta(
            hours=float(_env("SAMAEG_ALERT_COOLDOWN_H", "6"))
        )
        # e-mail
        self.smtp_host = _env("SAMAEG_SMTP_HOST")
        self.smtp_port = int(_env("SAMAEG_SMTP_PORT", "587") or "587")
        self.smtp_user = _env("SAMAEG_SMTP_USER")
        self.smtp_pass = _env("SAMAEG_SMTP_PASS")
        self.email_from = _env("SAMAEG_ALERT_EMAIL_FROM") or self.smtp_user
        self.email_to = _emails_to()
        # webhook
        self.webhook_url = _env("SAMAEG_ALERT_WEBHOOK_URL")

        self.enabled_email = bool(self.smtp_host and self.email_to)
        self.enabled_webhook = bool(self.webhook_url)

        # estado anti-spam: zone_id -> (nivel_alertado, quando)
        self._last_alert: Dict[str, Tuple[int, datetime]] = {}
        # telemetria
        self.sent_total = 0
        self.last_sent_at: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.last_error_at: Optional[datetime] = None
        self.last_alert_count = 0
        self.last_channels_ok: Dict[str, bool] = {}

        if not (self.enabled_email or self.enabled_webhook):
            log.info("Notifier DESABILITADO (nenhum canal configurado).")
        else:
            log.info(
                "Notifier ativo: email=%s webhook=%s limiar=RD%d cooldown=%sh",
                self.enabled_email, self.enabled_webhook,
                self.threshold, self.cooldown.total_seconds() / 3600,
            )

    # ----------------------------------------------------------------- API
    def evaluate(self, points: List[Dict[str, Any]], summary: Dict[str, Any],
                 now: Optional[datetime] = None,
                 channel: Optional[str] = None) -> int:
        """Avalia o snapshot e dispara notificacoes se necessario.

        channel: 'geo' (encosta) ou 'hidro' (inundacao) — anti-spam
        separado por canal. Retorna o numero de zonas alertadas (0 se nada).
        """
        now = now or datetime.now(timezone.utc)
        with self._evaluate_lock:
            try:
                if alert_store.configured():
                    if channel not in ("geo", "hidro"):
                        raise ValueError("Persistencia exige canal explicito")
                    return self._evaluate_persistent(
                        points, summary, now, channel,
                    )
                if alert_store.required():
                    raise RuntimeError("Banco obrigatorio nao configurado")
                if not (self.enabled_email or self.enabled_webhook):
                    return 0
                alerts = self._select_alerts(points, now, channel=channel)
                self.last_alert_count = len(alerts)
                if not alerts:
                    return 0
                channels_ok = self._dispatch(
                    alerts, summary, now, channel=channel,
                )
                if any(channels_ok.values()):
                    with self._lock:
                        for p in alerts:
                            key = self._alert_key(p, channel)
                            self._last_alert[key] = (p["rd"], now)
                    return len(alerts)
                return 0
            except Exception as e:  # noqa: BLE001
                self.last_error = type(e).__name__
                self.last_error_at = now
                log.exception("falha ao registrar/notificar alertas")
                return 0

    def _evaluate_persistent(self, points, summary, now, channel) -> int:
        transports = []
        if self.enabled_email:
            transports.append("email")
        if self.enabled_webhook:
            transports.append("webhook")
        alert_store.observe(
            points, summary, now, channel, self.threshold,
            transports, self.cooldown,
        )
        sent_ids = set()
        channels_ok: Dict[str, bool] = {}
        for transport in transports:
            while True:
                token, jobs = alert_store.claim(channel, transport, now)
                if not jobs:
                    break
                alerts = [j["conteudo"]["point"] for j in jobs]
                job_summary = jobs[0]["conteudo"]["summary"]
                subject, body = self._format(
                    alerts, job_summary, now, channel=channel,
                )
                self.last_error = None
                if transport == "email":
                    ok = self._send_email(subject, body)
                else:
                    ok = self._send_webhook(subject, body, alerts, now)
                alert_store.finish(
                    jobs, token, now, ok,
                    None if ok else f"Falha no transporte {transport}",
                )
                channels_ok[transport] = (
                    channels_ok.get(transport, True) and ok
                )
                if ok:
                    sent_ids.update(j["alerta_id"] for j in jobs)
        with self._lock:
            self.last_channels_ok = channels_ok
            self.last_alert_count = len(sent_ids)
            if sent_ids:
                self.sent_total += 1
                self.last_sent_at = now
        return len(sent_ids)

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            st = NotifierStatus(
                enabled_email=self.enabled_email,
                enabled_webhook=self.enabled_webhook,
                threshold=self.threshold,
                cooldown_h=self.cooldown.total_seconds() / 3600,
                sent_total=self.sent_total,
                last_sent_at=(self.last_sent_at.isoformat()
                              if self.last_sent_at else None),
                last_error=self.last_error,
                last_error_at=(self.last_error_at.isoformat()
                               if self.last_error_at else None),
                last_alert_count=self.last_alert_count,
                channels_ok=dict(self.last_channels_ok),
            )
            return {**st.__dict__, "database": alert_store.status()}

    @staticmethod
    def _alert_key(point, channel):
        zid = point.get("ua_id") or point.get("id")
        if not zid:
            raise ValueError("UA sem identificador")
        return f"{channel or point.get('hazard', 'geo')}:{zid}"

    # ------------------------------------------------------------- internos
    def _select_alerts(self, points: List[Dict[str, Any]],
                       now: datetime,
                       channel: Optional[str] = None) -> List[Dict[str, Any]]:
        """Decide quais zonas alertar (novo / escalada / lembrete pos-cooldown)
        e limpa zonas que retornaram abaixo do limiar."""
        alerts: List[Dict[str, Any]] = []
        with self._lock:
            active_ids = set()
            for p in points:
                rd = p.get("rd")
                alert_key = self._alert_key(p, channel)
                if p.get("source") == "NO_DATA" or rd is None:
                    active_ids.add(alert_key)
                    continue
                if rd >= self.threshold:
                    active_ids.add(alert_key)
                    prev = self._last_alert.get(alert_key)
                    fire = (
                        prev is None                       # novo
                        or rd > prev[0]                    # escalada
                        or (now - prev[1]) >= self.cooldown  # lembrete
                    )
                    if fire:
                        alerts.append(p)
            prefix = f"{channel}:" if channel else None
            for key in list(self._last_alert):
                if prefix and not key.startswith(prefix):
                    continue
                if key not in active_ids:
                    del self._last_alert[key]
        # pior caso primeiro
        alerts.sort(key=lambda p: (p.get("rd", 0), p.get("ac96h_mm", 0)),
                    reverse=True)
        return alerts

    def _dispatch(self, alerts: List[Dict[str, Any]],
                  summary: Dict[str, Any], now: datetime,
                  channel: Optional[str] = None) -> Dict[str, bool]:
        subject, body = self._format(alerts, summary, now, channel=channel)
        channels_ok: Dict[str, bool] = {}
        if self.enabled_email:
            channels_ok["email"] = self._send_email(subject, body)
        if self.enabled_webhook:
            channels_ok["webhook"] = self._send_webhook(
                subject, body, alerts, now)

        with self._lock:
            self.last_channels_ok = channels_ok
            if any(channels_ok.values()):
                self.sent_total += 1
                self.last_sent_at = now
        log.warning("ALERTA: %d zona(s) RD>=%d | canais=%s",
                    len(alerts), self.threshold, channels_ok)
        return channels_ok

    def _format(self, alerts: List[Dict[str, Any]],
                summary: Dict[str, Any], now: datetime,
                channel: Optional[str] = None) -> Tuple[str, str]:
        n = len(alerts)
        ch_label = {
            "geo": "Encosta",
            "hidro": "Inundacao",
        }.get(channel or "", "")
        ch_tag = f"[{ch_label}] " if ch_label else ""
        subject = (f"[HazardTrack]{ch_tag} {n} UA(s) em risco "
                   f"(RD>={self.threshold}) - max RD{summary.get('max_rd', 0)}")
        linhas = [
            "Sistema de Alerta - Plano de Contingencia (rodovias SP-055/SP-098)",
            f"Canal: {ch_label or 'geral'}",
            f"Horario (UTC): {now.isoformat(timespec='seconds')}",
            f"Fonte de chuva: {summary.get('data_source', '-')} "
            f"(status: {summary.get('data_status', '-')})",
            "",
            f"{n} zona(s) com Risco Dinamico >= {self.threshold}:",
            "",
        ]
        for p in alerts:
            km = p.get("km_inicial", p.get("km"))
            km_txt = f" km {km}" if km is not None else ""
            zid = p.get("ua_id") or p.get("id")
            road = p.get("sigla_rodovia", p.get("rodovia", ""))
            ra = p.get("RAGEO") if channel == "geo" else p.get("RAHID")
            linhas.append(
                f"- [{zid}] {road}"
                f"{km_txt} | RD{p.get('rd')} ({p.get('nivel', '')}) "
                f"| RA{ra if ra is not None else p.get('ra')} "
                f"| chuva24h={p.get('ac24h_mm')}mm 96h={p.get('ac96h_mm')}mm "
                f"| {p.get('regiao_nome', p.get('region_name', ''))}"
            )
        return subject, "\n".join(linhas)

    def _send_email(self, subject: str, body: str) -> bool:
        try:
            msg = EmailMessage()
            msg["Subject"] = subject
            msg["From"] = self.email_from
            msg["To"] = ", ".join(self.email_to)
            msg.set_content(body)
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port,
                                      timeout=20) as s:
                    if self.smtp_user:
                        s.login(self.smtp_user, self.smtp_pass)
                    s.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port,
                                  timeout=20) as s:
                    s.ehlo()
                    try:
                        s.starttls()
                        s.ehlo()
                    except smtplib.SMTPException:
                        pass
                    if self.smtp_user:
                        s.login(self.smtp_user, self.smtp_pass)
                    s.send_message(msg)
            return True
        except Exception as e:  # noqa: BLE001
            self.last_error = f"email: {e}"
            self.last_error_at = datetime.now(timezone.utc)
            log.error("falha email: %s", e)
            return False

    def _send_webhook(self, subject: str, body: str,
                      alerts: List[Dict[str, Any]], now: datetime) -> bool:
        try:
            import requests
            payload = {
                "text": subject + "\n" + body,   # Slack/Telegram-friendly
                "subject": subject,
                "timestamp": now.isoformat(),
                "count": len(alerts),
                "threshold": self.threshold,
                "zones": [
                    {
                        "ua_id": p.get("ua_id") or p.get("id"),
                        "id": p.get("ua_id") or p.get("id"),
                        "nome": p.get("ua_id") or p.get("nome"),
                        "rodovia": p.get("sigla_rodovia", p.get("rodovia")),
                        "km": p.get("km_inicial", p.get("km")),
                        "km_inicial": p.get("km_inicial"),
                        "km_final": p.get("km_final"),
                        "hazard": p.get("hazard"),
                        "RAGEO": p.get("RAGEO"),
                        "RAHID": p.get("RAHID"),
                        "rd": p.get("rd"), "nivel": p.get("nivel"),
                        "ra": p.get("ra"),
                        "lat": p.get("lat"), "lon": p.get("lon"),
                        "ac24h_mm": p.get("ac24h_mm"),
                        "ac96h_mm": p.get("ac96h_mm"),
                        "region": p.get("regiao_nome", p.get("region_name")),
                    } for p in alerts
                ],
            }
            r = requests.post(self.webhook_url, json=payload, timeout=15)
            if not 200 <= r.status_code < 300:
                self.last_error = f"webhook: HTTP {r.status_code}"
                self.last_error_at = datetime.now(timezone.utc)
                log.error("falha webhook: HTTP %d", r.status_code)
                return False
            return True
        except Exception as e:  # noqa: BLE001
            self.last_error = f"webhook: {e}"
            self.last_error_at = datetime.now(timezone.utc)
            log.error("falha webhook: %s", e)
            return False


# Singleton
notifier = Notifier()
