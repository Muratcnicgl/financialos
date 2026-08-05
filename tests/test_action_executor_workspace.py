"""
BUG #221 — KOÇ-ONAYLI KAYIT KULLANICININ KENDİ LİSTESİNDEN KAYBOLUYOR.

Denetim bulgusu (5 Ağu, `publish-dogrulama-denetimi.md` D01/D02): `execute_pending_action`
handler'ları `(db, user_id, payload)` imzasıyla çağırıyor — workspace bağlamı hiç geçmiyor.
Sonuç: `Transaction` ve `MasterCheckpoint` satırları `workspace_id=NULL` yazılıyor. Okuma
tarafı workspace kapsamlı (`scope_filter`) ve production'da her kullanıcının personal
workspace'i ZORUNLU olduğu için (`workspace_deps.active_workspace_id` prod'da fail-fast),
NULL satır kullanıcının KENDİ listesinden/raporundan/koç bağlamından elenir.

Kullanıcı açısından: koça "500 TL market harcadım" der, onaylar, **bakiyesi düşer** ama
işlem hiçbir yerde görünmez — para buharlaşmış gibi. Ürünün amiral akışı bu.

Canlı DB'de ZATEN gerçekleşmiş: `transactions` tablosundaki tek satır `workspace_id=NULL`,
tüm hesaplar `workspace_id=1`.

Bu dosya sözleşmeyi kilitler: koç yolundan yazılan her kayıt, kullanıcının kendi
görünümünde OKUNABİLİR olmalı.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, PendingAction, ActionStatus,
    Transaction, MasterCheckpoint, Workspace, WorkspaceMembership, WorkspaceRole,
)
from app.action_executor import execute_pending_action
from app.workspace_deps import scope_filter


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    u = User(id=1, name="kullanici")
    s.add(u)
    s.flush()
    ws = Workspace(id=1, name="Kişisel", is_personal=True, owner_user_id=1)
    s.add(ws)
    s.flush()
    s.add(WorkspaceMembership(workspace_id=1, user_id=1, role=WorkspaceRole.owner))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def hesap(db):
    a = Account(user_id=1, workspace_id=1, name="Kasa",
                account_type=AccountType.cash, balance=10000.0)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _pending(db, action_type, payload, workspace_id=1):
    p = PendingAction(user_id=1, action_type=action_type, payload=json.dumps(payload),
                      summary="test", status=ActionStatus.pending, workspace_id=workspace_id)
    db.add(p); db.commit(); db.refresh(p)
    return p


def test_koc_onayli_islem_kullanicinin_kendi_listesinde_gorunur(db, hesap):
    """Asıl kanıt: bakiye düşüyorsa işlem de görünmeli (ikisi ayrı düşemez)."""
    p = _pending(db, "add_transaction", {
        "transaction_type": "expense", "amount": 500.0, "account_id": hesap.id,
        "auto_update_balance": True, "category": "market",
        "transaction_date": date.today().isoformat(),
    })
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True

    db.refresh(hesap)
    assert float(hesap.balance) == 9500.0, "bakiye düşmedi — senaryo kurulmamış"

    # Kullanıcının KENDİ görünümü: aktif workspace = personal (prod'da her zaman dolu)
    gorunen = db.query(Transaction).filter(scope_filter(Transaction, 1, 1)).all()
    assert len(gorunen) == 1, (
        "Bakiye düştü ama işlem kullanıcının kendi listesinde YOK — "
        f"workspace_id={db.query(Transaction).first().workspace_id!r} yazılmış (BUG #221)"
    )


def test_koc_onayli_islem_workspace_id_tasir(db, hesap):
    """Kök-neden kilidi: satır doğrudan doğru workspace'e yazılmalı."""
    p = _pending(db, "add_transaction", {
        "transaction_type": "expense", "amount": 100.0, "account_id": hesap.id,
        "auto_update_balance": True, "category": "yemek",
    })
    execute_pending_action(db, p.id, 1)
    txn = db.query(Transaction).first()
    assert txn is not None and txn.workspace_id == 1


def test_koc_onayli_kirmizi_cizgi_kullanicinin_panelinde_gorunur(db):
    """Aynı defektin ikinci kolu: Master Checkpoint de NULL yazılıyordu (D02)."""
    p = _pending(db, "add_master_checkpoint", {
        "title": "Emanet paraya dokunma",
        "description": "Bu para benim değil.",
        "checkpoint_type": "red_line",
        "priority": 1,
    })
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True, res

    gorunen = db.query(MasterCheckpoint).filter(scope_filter(MasterCheckpoint, 1, 1)).all()
    assert len(gorunen) == 1, (
        "Koç-onaylı kırmızı çizgi kullanıcının kendi panelinde YOK — "
        f"workspace_id={db.query(MasterCheckpoint).first().workspace_id!r} (BUG #221)"
    )


def test_workspacesiz_eski_aksiyon_hesabin_workspaceine_yazilir(db, hesap):
    """Geriye uyum + veri bütünlüğü: `PendingAction.workspace_id` boş (eski kayıt) olsa bile
    işlem, hesabının workspace'ine yazılmalı — işlem hesabından farklı bir kapsamda yaşayamaz."""
    p = _pending(db, "add_transaction", {
        "transaction_type": "expense", "amount": 250.0, "account_id": hesap.id,
        "auto_update_balance": True, "category": "market",
    }, workspace_id=None)
    execute_pending_action(db, p.id, 1)
    txn = db.query(Transaction).first()
    assert txn is not None and txn.workspace_id == hesap.workspace_id


def test_workspacesiz_kurulumda_davranis_degismez(db):
    """Legacy/dev kurulumu (personal workspace YOK): eski davranış korunur, çökme olmaz."""
    db.query(WorkspaceMembership).delete()
    db.query(Workspace).delete()
    db.commit()
    a = Account(user_id=1, name="Kasa", account_type=AccountType.cash, balance=1000.0)
    db.add(a); db.commit(); db.refresh(a)

    p = _pending(db, "add_transaction", {
        "transaction_type": "expense", "amount": 100.0, "account_id": a.id,
        "auto_update_balance": True,
    }, workspace_id=None)
    res = execute_pending_action(db, p.id, 1)
    assert res["success"] is True
    txn = db.query(Transaction).first()
    assert txn is not None
    assert txn.workspace_id is None          # workspace yok → legacy user_id yolu
    assert db.query(Transaction).filter(scope_filter(Transaction, 1, None)).count() == 1
