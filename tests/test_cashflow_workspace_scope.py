"""
P1 (Wave-9) — BUG #165: `app/cashflow.generate_forecast` workspace kapsamını yok sayıyordu.

Zincir: routers/coach.py + routers/actions.py `with workspace_scope(ws_id)` bloğu içinde
`generate_cockpit` çağırır → `rules_engine._detect_cashflow_crunch` → `cashflow.generate_forecast`.
rules_engine kendi sorgularını `_scope(...)` ile workspace'e kapsarken cashflow ham
`Model.user_id == user_id` kullanıyordu. Sonuç: paylaşımlı (aile) workspace görünümünde
nakit krizi / güvenli-harcama rakamları KİŞİSEL workspace verisinden hesaplanıyor,
workspace'in kendi gelir/gider/kredi kalemleri hiç sayılmıyordu (ADR-036 ihlali).

Kapsam notu: bu bir çapraz-KULLANICI ifşası değil; kapsam-tutarsızlığı defektidir
(kullanıcı kendi verisini yanlış bağlamda görür, karar rakamları yanlış çıkar).
"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, AccountType, RecurringIncome,
)
from app.cashflow import generate_forecast
from app.rules_engine import workspace_scope


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def iki_workspace(db):
    """Bir kullanıcı, iki workspace: kişisel (10.000 TL) ve aile (50.000 TL)."""
    u = User(name="murat")
    db.add(u)
    db.commit()

    kisisel = Workspace(owner_user_id=u.id, name="Kişisel", is_personal=True)
    aile = Workspace(owner_user_id=u.id, name="Aile", is_personal=False)
    db.add_all([kisisel, aile])
    db.commit()
    for ws in (kisisel, aile):
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner))
    db.add_all([
        Account(user_id=u.id, workspace_id=kisisel.id, name="Kişisel kasa",
                account_type=AccountType.cash, balance=10000.0),
        Account(user_id=u.id, workspace_id=aile.id, name="Aile kasası",
                account_type=AccountType.cash, balance=50000.0),
        RecurringIncome(user_id=u.id, workspace_id=aile.id, name="Aile kirası",
                        amount=7000.0, day_of_month=5, is_active=True),
    ])
    db.commit()
    return u, kisisel, aile


def test_forecast_aktif_workspace_bakiyesini_kullanir(db, iki_workspace):
    """BUG #165: aile workspace'inde projeksiyon aile kasasından başlamalı (kişiselden değil)."""
    u, kisisel, aile = iki_workspace

    with workspace_scope(aile.id):
        fc = generate_forecast(db, u.id, horizon_days=30, today=date(2026, 8, 4))

    acilis = float(fc["summary"]["opening_balance"])
    assert acilis == pytest.approx(50000.0), (
        f"Aile workspace'inde açılış bakiyesi {acilis} — kişisel kasa (10.000) sızmış olabilir"
    )


def test_forecast_kisisel_workspace_te_aileyi_saymaz(db, iki_workspace):
    """Simetrik kontrol: kişisel görünümde aile kasası sayılmamalı."""
    u, kisisel, aile = iki_workspace

    with workspace_scope(kisisel.id):
        fc = generate_forecast(db, u.id, horizon_days=30, today=date(2026, 8, 4))

    assert float(fc["summary"]["opening_balance"]) == pytest.approx(10000.0)


def test_forecast_workspace_gelirini_dahil_eder(db, iki_workspace):
    """Aile workspace'inin düzenli geliri projeksiyona girmeli."""
    u, kisisel, aile = iki_workspace

    with workspace_scope(aile.id):
        fc = generate_forecast(db, u.id, horizon_days=60, today=date(2026, 8, 4))
    with workspace_scope(kisisel.id):
        fc_kisisel = generate_forecast(db, u.id, horizon_days=60, today=date(2026, 8, 4))

    aile_gelir = float(fc["summary"]["total_receivable"])
    kisisel_gelir = float(fc_kisisel["summary"]["total_receivable"])
    assert aile_gelir > 0, "Aile workspace'inin düzenli geliri projeksiyona girmedi"
    assert kisisel_gelir == 0, "Aile geliri kişisel projeksiyona sızdı"


def test_workspace_yoksa_legacy_user_id_yolu_calisir(db, iki_workspace):
    """Köprü-desen regresyonu: kapsam yokken kullanıcının TÜM verisi sayılır (eski davranış)."""
    u, kisisel, aile = iki_workspace
    fc = generate_forecast(db, u.id, horizon_days=30, today=date(2026, 8, 4))
    assert float(fc["summary"]["opening_balance"]) == pytest.approx(60000.0)
