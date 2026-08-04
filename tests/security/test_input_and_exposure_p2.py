"""
P2 (Wave-9) — girdi sınırları, yetki boşlukları ve iç-detay sızıntısı kapıları.

Denetimde doğrulanan ve bu dosyada kilitlenen açıklar:

  BUG #173 — `subscriptions` ve `fund_price` router'larında `require_write` YOKTU:
             paylaşılan (aile) workspace'ine **viewer** rolüyle davet edilen kullanıcı
             o workspace'e düzenli gider yazabiliyor ve yatırım fiyatını (dolayısıyla
             bakiyeyi/net değeri) değiştirebiliyordu. ADR-036 izin matrisi ihlali.

  BUG #174 — `POST /api/user` kimlik doğrulaması olmadan kullanıcı yaratıyordu
             (tek-kullanıcı kurulum kalıntısı). Kayıt akışı `/api/auth/register`.

  BUG #175 — Ham exception metni HTTP gövdesine dönüyordu (`detail=f"...{e}"`):
             SQLAlchemy hatası SQL cümlesini/kolon adlarını, diğer hatalar iç dosya
             yolunu kullanıcıya ifşa eder. Doğru desen `routers/coach.py`'de vardı
             (logla, sabit metin dön) ama 4 uçta uygulanmamıştı.

  BUG #176 — Goal tutarlarında üst sınır/sonluluk kontrolü yoktu (`Decimal` serbest):
             `1E+308` veya `Infinity` ile ilerleme/projeksiyon hesabı bozulur (SEC-032
             ailesinin Goal'da atlanmış hali).

  BUG #177 — Master Checkpoint `description` alanı SINIRSIZDI ve içeriği **sistem
             prompt'una** gömülüyor: dev metin hem DB'yi şişirir hem her koç çağrısında
             token maliyetini/bağlamı patlatır (kural bastırma yüzeyi).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole, Account, AccountType,
)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-p2-input-exposure-0123456789abcd")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def paylasimli_workspace(db):
    """owner + viewer aynı (aile) workspace'te. Viewer YALNIZ OKUMA yetkisine sahip."""
    owner = User(name="owner")
    viewer = User(name="viewer")
    db.add_all([owner, viewer])
    db.commit()
    ws = Workspace(owner_user_id=owner.id, name="Aile", is_personal=False)
    db.add(ws)
    db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=ws.id, user_id=owner.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=ws.id, user_id=viewer.id, role=WorkspaceRole.viewer),
    ])
    db.add(Account(user_id=owner.id, workspace_id=ws.id, name="Aile fonu",
                   account_type=AccountType.investment, balance=10000.0,
                   fund_code="TLY", lot_count=10.0, current_price=1000.0))
    db.commit()
    acc = db.query(Account).filter(Account.workspace_id == ws.id).first()
    return owner, viewer, ws, acc


@pytest.fixture
def client(db, paylasimli_workspace):
    owner, viewer, ws, acc = paylasimli_workspace
    app.dependency_overrides[get_db] = lambda: db
    state = {"user": owner}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    c = TestClient(app)
    c._state = state
    yield c
    app.dependency_overrides.clear()


def _as(client, user):
    client._state["user"] = user


# ── BUG #173: viewer paylaşılan workspace'e YAZAMAZ ──────────────────────────

def test_viewer_abonelik_yazamaz(client, paylasimli_workspace):
    owner, viewer, ws, acc = paylasimli_workspace
    _as(client, viewer)
    r = client.post("/api/subscriptions/to-recurring",
                    headers={"X-Workspace-Id": str(ws.id)},
                    json={"isim": "Netflix", "aylik_tutar": 200.0, "hesap_id": acc.id,
                          "gun": 5})
    assert r.status_code == 403, (
        f"Viewer paylaşılan workspace'e düzenli gider yazabildi → {r.status_code} {r.text[:160]}"
    )


def test_viewer_fiyat_guncelleyemez(client, paylasimli_workspace):
    owner, viewer, ws, acc = paylasimli_workspace
    _as(client, viewer)
    r = client.post("/api/fund-price/update",
                    headers={"X-Workspace-Id": str(ws.id)},
                    json={"account_id": acc.id, "new_price": 5.0})
    assert r.status_code == 403, (
        f"Viewer paylaşılan yatırım hesabının fiyatını/bakiyesini değiştirebildi → {r.status_code}"
    )


def test_owner_hala_yazabilir(client, paylasimli_workspace):
    """Pozitif kontrol: sertleştirme owner'ı engellemez."""
    owner, viewer, ws, acc = paylasimli_workspace
    _as(client, owner)
    r = client.post("/api/fund-price/update",
                    headers={"X-Workspace-Id": str(ws.id)},
                    json={"account_id": acc.id, "new_price": 1100.0})
    assert r.status_code == 200, r.text[:200]


# ── BUG #174: POST /api/user kimliksiz kullanıcı yaratamaz ──────────────────

def test_auth_acikken_kimliksiz_user_yaratilamaz(monkeypatch):
    """TAZE instance (hiç kullanıcı yok) + AUTH açık → yabancı id=1'i kapamamalı."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    bos_db = sessionmaker(bind=eng)()
    app.dependency_overrides[get_db] = lambda: bos_db
    try:
        c = TestClient(app)
        r = c.post("/api/user", json={"name": "sizinti"})
        assert r.status_code == 403, (
            f"AUTH açıkken kimliksiz kullanıcı yaratıldı → {r.status_code} {r.text[:160]}"
        )
        assert bos_db.query(User).count() == 0, "Kimliksiz istek kullanıcı yarattı"
    finally:
        app.dependency_overrides.clear()
        bos_db.close()


# ── BUG #175: iç hata detayı kullanıcıya sızmaz ─────────────────────────────

def test_ham_exception_metni_govdeye_sizmaz(client, monkeypatch, paylasimli_workspace):
    """Motor patlarsa kullanıcı sabit Türkçe mesaj görür; SQL/dosya yolu görmez."""
    owner, viewer, ws, acc = paylasimli_workspace
    _as(client, owner)

    def patla(*a, **k):
        raise RuntimeError("SELECT accounts.balance FROM accounts WHERE user_id=42 -- gizli")

    import app.routers.debt_strategy as ds
    monkeypatch.setattr(ds, "compare_strategies", patla)
    r = client.get("/api/debt-strategy/compare")
    assert r.status_code == 500
    detay = str(r.json().get("detail", ""))
    assert "SELECT" not in detay and "gizli" not in detay, (
        f"Ham exception metni kullanıcıya döndü: {detay[:200]}"
    )


# ── BUG #176/#177: girdi sınırları ──────────────────────────────────────────

def test_goal_tutari_sonsuz_olamaz(client, paylasimli_workspace):
    owner, *_ = paylasimli_workspace
    _as(client, owner)
    for deger in ("Infinity", "NaN", "1E+308"):
        r = client.post("/api/goals", json={
            "goal_type": "cash_target", "title": "Sınır testi", "target_amount": deger})
        assert r.status_code == 422, f"target_amount={deger} kabul edildi ({r.status_code})"


def test_goal_allocation_tutari_sinirli(client, paylasimli_workspace):
    owner, *_ = paylasimli_workspace
    _as(client, owner)
    r = client.post("/api/goals", json={
        "goal_type": "cash_target", "title": "Hedef", "target_amount": 1000})
    assert r.status_code in (200, 201)
    goal_id = r.json()["id"]
    r = client.post(f"/api/goals/{goal_id}/allocations",
                    json={"transaction_id": 1, "amount": "Infinity"})
    assert r.status_code == 422, f"allocation amount=Infinity kabul edildi ({r.status_code})"


def test_checkpoint_aciklamasi_sinirli(client, paylasimli_workspace):
    """Sınırsız açıklama sistem prompt'una gömülüyor → hem maliyet hem bağlam taşması."""
    owner, *_ = paylasimli_workspace
    _as(client, owner)
    r = client.post("/api/checkpoints", json={
        "title": "Dev kural", "description": "A" * 50_000,
        "checkpoint_type": "red_line"})
    assert r.status_code == 422, f"50.000 karakterlik checkpoint kabul edildi ({r.status_code})"


def test_makul_checkpoint_kabul_edilir(client, paylasimli_workspace):
    """Pozitif kontrol: gerçek kullanım (uzunca bir kural metni) geçer."""
    owner, *_ = paylasimli_workspace
    _as(client, owner)
    r = client.post("/api/checkpoints", json={
        "title": "Acil fon", "description": "B" * 1500, "checkpoint_type": "red_line"})
    assert r.status_code in (200, 201), r.text[:200]


# ── CORS: production'da localhost'a düşülmez ────────────────────────────────

def test_production_cors_localhosta_dusmez(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    from app.main import _compute_cors_origins
    origins = _compute_cors_origins()
    assert not any("localhost" in o or "127.0.0.1" in o for o in origins), (
        f"Production CORS listesinde localhost var: {origins}"
    )


def test_dev_cors_localhost_icerir(monkeypatch):
    """Regresyon: geliştirme akışı bozulmaz."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    from app.main import _compute_cors_origins
    assert any("localhost" in o for o in _compute_cors_origins())
