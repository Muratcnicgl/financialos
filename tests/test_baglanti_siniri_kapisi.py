"""
SEC-029 (BUG #497): her dağıtım yolunda gövde/bağlantı/zaman sınırı var.

Ölçüm (14 Eyl 2026): madde "uvicorn doğrudan, sınır yok" diyordu. Ölçülen: gövde sınırı
uygulama katmanında (`GovdeBoyutuMiddleware`, 1 MiB, BUG #213) her yolda; nginx şablonunda
`client_max_body_size 1m`, `limit_req`, `proxy_read_timeout`; konteynerde gunicorn `--timeout`.
Eksik olan tek yol Windows servisiydi (Tailscale Funnel → doğrudan uvicorn): eşzamanlı
bağlantı ve keep-alive sınırsızdı. Kilitlenen:
  1. Windows başlatıcı uvicorn'u `--limit-concurrency`, `--timeout-keep-alive`, `--backlog` ile açar,
  2. nginx şablonları gövde sınırı + istek hız sınırı + proxy zaman aşımı taşır,
  3. konteyner girişi gunicorn `--timeout` taşır,
  4. uygulama katmanı gövde sınırı her yolda (middleware kayıtlı, 413 döner).
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

KOK = Path(__file__).resolve().parent.parent


def test_windows_baslatici_baglanti_sinirlari():
    s = (KOK / "deploy" / "windows" / "baslat.ps1").read_text(encoding="utf-8")
    blok = s[s.index('"-m", "uvicorn", "app.main:app"'):]
    blok = blok[: blok.index("-WorkingDirectory")]
    for bayrak in ('"--limit-concurrency"', '"--timeout-keep-alive"', '"--backlog"', '"--no-server-header"'):
        assert bayrak in blok, f"uvicorn başlatma bayrağı eksik: {bayrak}"
    m = re.search(r'"--limit-concurrency",\s*"(\d+)"', blok)
    assert m and 8 <= int(m.group(1)) <= 1024


def test_nginx_sablonlari_sinir_tasir():
    for ad in ("nginx.conf.template", "nginx.tunnel.conf.template"):
        s = (KOK / "deploy" / ad).read_text(encoding="utf-8")
        assert "client_max_body_size" in s, f"{ad}: gövde sınırı yok"
        assert "proxy_read_timeout" in s, f"{ad}: proxy zaman aşımı yok"


def test_konteyner_gunicorn_timeout():
    s = (KOK / "docker-entrypoint.sh").read_text(encoding="utf-8")
    assert re.search(r"--timeout \d+", s)


def test_govde_siniri_her_yolda():
    src = (KOK / "app" / "main.py").read_text(encoding="utf-8")
    assert "app.add_middleware(_GovdeBoyutuMiddleware)" in src
    c = TestClient(app)
    r = c.post("/api/auth/login", content=b"x" * (2 * 1024 * 1024), headers={"Content-Type": "application/json"})
    assert r.status_code == 413
