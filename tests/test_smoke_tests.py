"""
M37 (Wave-4) — Dış API smoke test framework birim testleri.

Ağ çağrıları mock'lanır (deterministik). Smoke fonksiyonlarının başarı/başarısızlık
sınıflandırması + capture_smoke_failures ledger yakalaması + weekly_smoke_test_job'ın
akışı bozmaması test edilir.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

import app.services.smoke_tests as sm


# --- smoke_evds ---

def test_smoke_evds_ok(monkeypatch):
    import app.price_providers.evds_client as ev
    monkeypatch.setattr(ev, "fetch_currency_rate",
                        lambda code, target=None: {"buy": Decimal("46.9"), "sell": Decimal("47.0"), "date": "14-07-2026"})
    r = sm.smoke_evds()
    assert r["ok"] is True and r["api"] == "EVDS" and "46.9" in r["detail"]


def test_smoke_evds_bos_fail(monkeypatch):
    import app.price_providers.evds_client as ev
    monkeypatch.setattr(ev, "fetch_currency_rate", lambda code, target=None: None)
    r = sm.smoke_evds()
    assert r["ok"] is False and "boş" in r["detail"]


def test_smoke_evds_exception_yakalar(monkeypatch):
    import app.price_providers.evds_client as ev
    def _boom(code, target=None):
        raise RuntimeError("ağ koptu")
    monkeypatch.setattr(ev, "fetch_currency_rate", _boom)
    r = sm.smoke_evds()
    assert r["ok"] is False and "exception" in r["detail"]


# --- smoke_smtp ---

def test_smoke_smtp_yapilandirilmamis(monkeypatch):
    import app.services.email as em
    monkeypatch.setattr(em, "smtp_configured", lambda: False)
    r = sm.smoke_smtp()
    assert r["ok"] is False and "yapılandırılmamış" in r["detail"]


# --- smoke_oauth ---

def test_smoke_oauth_ok(monkeypatch):
    import app.services.oauth as oa
    monkeypatch.setattr(oa, "provider_configured", lambda p: True)
    monkeypatch.setattr(oa, "get_auth_url",
                        lambda p, s: "https://accounts.google.com/o/oauth2/v2/auth?state=" + s)
    r = sm.smoke_oauth("google")
    assert r["ok"] is True and "accounts.google.com" in r["detail"]


def test_smoke_oauth_yapilandirilmamis(monkeypatch):
    import app.services.oauth as oa
    monkeypatch.setattr(oa, "provider_configured", lambda p: False)
    r = sm.smoke_oauth("github")
    assert r["ok"] is False and "credential eksik" in r["detail"]


def test_smoke_oauth_yanlis_host_fail(monkeypatch):
    import app.services.oauth as oa
    monkeypatch.setattr(oa, "provider_configured", lambda p: True)
    monkeypatch.setattr(oa, "get_auth_url", lambda p, s: "https://evil.example.com/auth")
    r = sm.smoke_oauth("google")
    assert r["ok"] is False and "beklenen host" in r["detail"]


# --- capture_smoke_failures ---

def test_capture_yalniz_failleri_yakalar(tmp_path):
    ledger = tmp_path / "ledger.log"
    results = [
        {"api": "EVDS", "ok": True, "detail": "ok"},
        {"api": "SMTP", "ok": False, "detail": "login reddedildi"},
        {"api": "OAuth-google", "ok": False, "detail": "credential eksik"},
    ]
    n = sm.capture_smoke_failures(results, ledger=ledger)
    assert n == 2
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert all(ln.startswith("SMOKE_FAIL|smoke|") for ln in lines)
    assert "SMTP: login reddedildi" in lines[0]


def test_capture_hepsi_ok_ledger_yazmaz(tmp_path):
    ledger = tmp_path / "ledger.log"
    results = [{"api": "EVDS", "ok": True, "detail": "ok"}]
    assert sm.capture_smoke_failures(results, ledger=ledger) == 0
    assert not ledger.exists()


# --- run_all + job akış bozmaz ---

def test_run_all_dort_api(monkeypatch):
    monkeypatch.setattr(sm, "smoke_evds", lambda: {"api": "EVDS", "ok": True, "detail": "x"})
    monkeypatch.setattr(sm, "smoke_smtp", lambda: {"api": "SMTP", "ok": True, "detail": "x"})
    monkeypatch.setattr(sm, "smoke_oauth", lambda p: {"api": f"OAuth-{p}", "ok": True, "detail": "x"})
    results = sm.run_all_smoke_tests()
    assert len(results) == 4
    assert {r["api"] for r in results} == {"EVDS", "SMTP", "OAuth-google", "OAuth-github"}


def test_weekly_job_akis_bozmaz(monkeypatch):
    import asyncio
    from app.scheduler import weekly_smoke_test_job
    monkeypatch.setattr(sm, "run_all_smoke_tests",
                        lambda: [{"api": "EVDS", "ok": False, "detail": "ölü"}])
    captured = {}
    monkeypatch.setattr(sm, "capture_smoke_failures", lambda results: captured.setdefault("n", 1))
    # exception raise etmemeli (coroutine'i senkron çalıştır — pytest-asyncio yok)
    asyncio.run(weekly_smoke_test_job())
    assert captured.get("n") == 1
