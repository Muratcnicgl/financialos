"""
P3.4 / H6 (Wave-9) — BUG #204: KVKK "unutulma hakkı" KIRIKTI.

`DELETE /api/users/me` yalnızca `db.delete(user)` yapıyordu ve 6 tablo (Envelope,
WishlistItem, Goal, Feedback, DemoDataMarker, ReasoningTrace) `user_id` FK'si taşımasına
rağmen User'da cascade ilişkisine sahip DEĞİLDİ. Sonuç: **verisi olan** bir kullanıcı
hesabını silmeye çalışınca `FOREIGN KEY constraint failed` alıyordu.

Yani gerçek bir beta kullanıcısı — yani zarf/hedef/istek listesi/geri bildirim üretmiş
HERKES — hesabını SİLEMİYORDU; rıza metninde (`docs/legal/kvkk-consent-v2.md`) açıkça
taahhüt edilen hak fiilen çalışmıyordu. Mevcut tek test veri OLMAYAN kullanıcıyı siliyordu,
bu yüzden yeşil görünüyordu (kapsam yanılsaması).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType, Envelope,
    WishlistItem, Goal, Feedback, DemoDataMarker, ReasoningTrace, MasterCheckpoint,
    CheckpointType, Workspace, WorkspaceMembership, WorkspaceRole,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)

    @event.listens_for(eng, "connect")
    def _fk(dbapi_conn, _rec):
        # Production (Postgres) FK'yi ZATEN dayatır; SQLite'ta açıkça açılır (BUG #060).
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def _dolu_kullanici(db, email="dolu@example.com", ad="Dolu"):
    """GERÇEK bir beta kullanıcısı gibi: her tabloda verisi olan kullanıcı."""
    u = User(name=ad, email=email, is_active=True)
    db.add(u)
    db.commit()
    ws = Workspace(owner_user_id=u.id, name=f"{ad} kişisel", is_personal=True)
    db.add(ws)
    db.commit()
    db.add(WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner))
    acc = Account(user_id=u.id, workspace_id=ws.id, name="Kasa",
                  account_type=AccountType.cash, balance=1000.0)
    db.add(acc)
    db.commit()
    db.add_all([
        Transaction(user_id=u.id, workspace_id=ws.id, account_id=acc.id,
                    transaction_type=TransactionType.expense, amount=10.0,
                    transaction_date=__import__("datetime").date.today()),
        Envelope(user_id=u.id, workspace_id=ws.id, category="market", monthly_amount=500),
        WishlistItem(user_id=u.id, workspace_id=ws.id, item="kulaklık", amount=900,
                     status="open"),
        Goal(user_id=u.id, workspace_id=ws.id, goal_type="cash_target", title="Acil fon",
             target_amount=10000, status="active"),
        Feedback(user_id=u.id, kind="oneri", message="güzel olmuş", status="new"),
        DemoDataMarker(user_id=u.id, table_name="accounts", row_id=acc.id),
        MasterCheckpoint(user_id=u.id, workspace_id=ws.id, title="Kural", description="x",
                         checkpoint_type=CheckpointType.red_line, priority=1),
        ReasoningTrace(user_id=u.id, trace_id="t1", step_index=0,
                       operation_name="final_answer"),
    ])
    db.commit()
    return u, ws


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield lambda user: _client_for(db, user)
    app.dependency_overrides.clear()


def _client_for(db, user):
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_verisi_olan_kullanici_hesabini_silebilir(db, client):
    """ASIL KAPI: gerçek kullanıcı (verisi olan) silinebilmeli."""
    u, _ws = _dolu_kullanici(db)
    r = client(u).delete("/api/users/me")
    assert r.status_code in (200, 204), f"Hesap silinemedi: {r.status_code} {r.text[:300]}"
    assert db.query(User).filter(User.id == u.id).count() == 0


def test_silme_sonrasi_hicbir_tabloda_iz_kalmaz(db, client):
    """KVKK: 'tüm veriniz kalıcı olarak silinir' taahhüdü ölçülür."""
    u, _ws = _dolu_kullanici(db)
    uid = u.id
    client(u).delete("/api/users/me")

    for M in (Account, Transaction, Envelope, WishlistItem, Goal, Feedback,
              DemoDataMarker, MasterCheckpoint, ReasoningTrace):
        kalan = db.query(M).filter(M.user_id == uid).count()
        assert kalan == 0, f"{M.__name__} tablosunda {kalan} yetim satır kaldı"
    assert db.query(Workspace).filter(Workspace.owner_user_id == uid).count() == 0


def test_baska_kullanicinin_verisi_etkilenmez(db, client):
    """Silme komşuya sıçramamalı (P1 ailesi)."""
    u1, _ = _dolu_kullanici(db, "bir@example.com", "Bir")
    u2, _ = _dolu_kullanici(db, "iki@example.com", "Iki")
    client(u1).delete("/api/users/me")

    assert db.query(User).filter(User.id == u2.id).count() == 1
    assert db.query(Account).filter(Account.user_id == u2.id).count() == 1
    assert db.query(Goal).filter(Goal.user_id == u2.id).count() == 1


def test_export_silmeden_once_tam_veri_doner(db, client):
    """KVKK sırası: önce dışa aktar, sonra sil — ikisi birlikte anlamlı."""
    u, _ = _dolu_kullanici(db)
    c = client(u)
    body = c.get("/api/user/export").json()
    assert body["accounts"] and body["goals"] and body["envelopes"]
    assert c.delete("/api/users/me").status_code in (200, 204)


# ══════════════════════════════════════════════════════════════════════════════
# H18 / BUG #206 — hesabını silen kullanıcı, BAŞKASININ verisini yok edemez
# Aile workspace'inin sahibi hesabını silince eşinin/çocuğunun tüm finansal
# kayıtları da sessizce siliniyordu (repro ile doğrulandı). Bir kullanıcının
# kendi hesabını silme hakkı, başkasının verisi üzerinde yetki vermez.
# ══════════════════════════════════════════════════════════════════════════════

def _aile_workspace(db):
    sahip = User(name="Sahip", email="sahip@example.com", is_active=True)
    uye = User(name="Es", email="es@example.com", is_active=True)
    db.add_all([sahip, uye])
    db.commit()
    ws = Workspace(owner_user_id=sahip.id, name="Aile", is_personal=False)
    db.add(ws)
    db.commit()
    db.add_all([
        WorkspaceMembership(workspace_id=ws.id, user_id=sahip.id, role=WorkspaceRole.owner),
        WorkspaceMembership(workspace_id=ws.id, user_id=uye.id, role=WorkspaceRole.editor),
        Account(user_id=uye.id, workspace_id=ws.id, name="Eşin hesabı",
                account_type=AccountType.cash, balance=50000.0),
        Goal(user_id=uye.id, workspace_id=ws.id, goal_type="cash_target",
             title="Eşin hedefi", target_amount=25000, status="active"),
    ])
    db.commit()
    return sahip, uye, ws


def test_sahip_silinince_aile_workspace_i_yok_olmaz(db, client):
    sahip, uye, ws = _aile_workspace(db)
    ws_id = ws.id
    r = client(sahip).delete("/api/users/me")
    assert r.status_code in (200, 204), r.text[:200]

    assert db.query(Workspace).filter(Workspace.id == ws_id).count() == 1, (
        "Paylaşılan workspace sahibiyle birlikte SİLİNDİ — diğer üyelerin verisi yok oldu"
    )
    assert db.query(Account).filter(Account.user_id == uye.id).count() == 1
    assert db.query(Goal).filter(Goal.user_id == uye.id).count() == 1


def test_sahiplik_kalan_uyeye_devredilir(db, client):
    """Sahipsiz workspace yönetilemez hale gelir (davet/çıkarma owner ister)."""
    sahip, uye, ws = _aile_workspace(db)
    ws_id, uye_id = ws.id, uye.id
    client(sahip).delete("/api/users/me")

    yeni = db.query(Workspace).filter(Workspace.id == ws_id).first()
    assert yeni.owner_user_id == uye_id, "Workspace SAHİPSİZ kaldı"
    m = (db.query(WorkspaceMembership)
         .filter(WorkspaceMembership.workspace_id == ws_id,
                 WorkspaceMembership.user_id == uye_id).first())
    assert m.role == WorkspaceRole.owner, "Devralan üye owner rolüne yükseltilmedi"


def test_kisisel_workspace_silinmeye_devam_eder(db, client):
    """Regresyon: üyesi olmayan kişisel workspace silinir (veri artığı kalmaz)."""
    u, ws = _dolu_kullanici(db, "tek@example.com", "Tek")
    ws_id = ws.id
    client(u).delete("/api/users/me")
    assert db.query(Workspace).filter(Workspace.id == ws_id).count() == 0
