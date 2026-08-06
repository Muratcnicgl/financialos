"""
M11 (ADR-033) — SMTP şifre sıfırlama e-postası testleri (gerçek gönderim, mock SMTP).

smtplib.SMTP mock'lanır (gerçek ağ yok). send_email STARTTLS+login+sendmail çağırır mı;
send_password_reset_email içerik + link; endpoint SMTP yapılandırılınca BackgroundTask
ile gönderir mi + dev-token DÖNMEZ.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db
from app.models import Base, User
import app.services.email as email_mod
import app.routers.auth as auth_mod


@pytest.fixture(autouse=True)
def _smtp_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASS", "secret-key")
    monkeypatch.setenv("SMTP_FROM", "noreply@example.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "FinancialOS")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def mock_smtp(monkeypatch):
    server = MagicMock(name="smtp_server")
    cm = MagicMock()
    cm.__enter__.return_value = server
    cm.__exit__.return_value = False
    factory = MagicMock(return_value=cm)
    monkeypatch.setattr("smtplib.SMTP", factory)
    return factory, server


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    auth_mod._RATE.clear()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


# --- email modülü ---

def test_smtp_configured_true():
    assert email_mod.smtp_configured() is True


def test_send_email_starttls_login_sendmail(mock_smtp):
    factory, server = mock_smtp
    ok = email_mod.send_email("to@x.com", "Konu", "text", "<b>html</b>")
    assert ok is True
    factory.assert_called_once_with("smtp-relay.example.com", 587, timeout=20)
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("user@example.com", "secret-key")
    server.sendmail.assert_called_once()
    # sendmail(from, [to], body) — from + alıcı doğru
    args = server.sendmail.call_args[0]
    assert args[0] == "noreply@example.com"
    assert args[1] == ["to@x.com"]


def test_send_password_reset_email_icerik(mock_smtp):
    import email as _email
    factory, server = mock_smtp
    link = "http://localhost:5173/auth/reset?token=ABC123"
    ok = email_mod.send_password_reset_email("murat@x.com", link)
    assert ok is True
    raw = server.sendmail.call_args[0][2]
    msg = _email.message_from_string(raw)
    # MIME base64-encoded → parça parça decode et
    decoded = "".join(
        part.get_payload(decode=True).decode("utf-8", "replace")
        for part in msg.walk() if part.get_content_type() in ("text/plain", "text/html")
    )
    assert "ABC123" in decoded          # link gövdede
    assert "30 dakika" in decoded       # süre bilgisi (KVKK)
    assert "görmezden" in decoded       # "sen istemediysen görmezden gel" (KVKK)
    assert msg["Subject"] and "Şifre" in _email.header.make_header(
        _email.header.decode_header(msg["Subject"])).__str__()


def test_send_email_smtp_yoksa_false(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    assert email_mod.send_email("to@x.com", "s", "t", "h") is False


def test_send_email_hata_false(monkeypatch):
    boom = MagicMock(side_effect=OSError("connection refused"))
    monkeypatch.setattr("smtplib.SMTP", boom)
    assert email_mod.send_email("to@x.com", "s", "t", "h") is False


# --- endpoint entegrasyonu ---

def _register(client, email="murat@x.com"):
    return client.post("/api/auth/register", json={
        "email": email, "password": "Kirmizi-Fener-2026", "name": "M", "kvkk_consent": True})


def test_reset_request_smtp_ile_gonderir_dev_token_yok(client, db_session, monkeypatch):
    _register(client)
    sent = {}
    # BUG #233: imza `ilk_kez` bayragi aldi (sifresi hic olmamis hesaba "sifirlama" degil
    # "belirleme" yazilir). Sifreli hesapta bayrak False kalmali.
    def _fake_send(to, link, ilk_kez=False):
        sent["to"] = to
        sent["link"] = link
        sent["ilk_kez"] = ilk_kez
        return True
    monkeypatch.setattr(auth_mod, "send_password_reset_email", _fake_send)
    r = client.post("/api/auth/password-reset-request", json={"email": "murat@x.com"})
    assert r.status_code == 200
    assert "_dev_token" not in r.json()   # SMTP varken token SIZMAZ
    # BackgroundTask TestClient'ta yanıt sonrası koşar
    assert sent["to"] == "murat@x.com"
    assert "/auth/reset?token=" in sent["link"]
    assert sent["ilk_kez"] is False   # BUG #233: sifresi olan hesap "sifirlama" metnini alir


def test_reset_request_olmayan_email_generic(client, monkeypatch):
    monkeypatch.setattr(auth_mod, "send_password_reset_email", lambda *a: True)
    r = client.post("/api/auth/password-reset-request", json={"email": "yok@x.com"})
    assert r.status_code == 200
    assert "_dev_token" not in r.json()   # enumeration önleme
