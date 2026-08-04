"""
P1 (Wave-9) — BUG #163: net-değer backfill/catch-up ÇOK-KULLANICI kapsamı.

Bulgu: `scripts/backfill_net_worth.run_backfill` ve `app/startup.catch_up_snapshots`
`db.query(User).order_by(User.id.asc()).first()` ile SADECE ilk kullanıcıyı işliyordu
(tek-kullanıcı MVP kalıntısı). Kapalı betada 2. kullanıcıdan itibaren net-değer geçmişi
hiç dolmuyor → trend/atıf raporları sessizce eksik. Ayrıca yazılan satırlarda
`workspace_id` NULL kalıyordu; workspace kapsamlı okumalar (scheduler `_scope`) bu
satırları GÖREMİYORDU.

Not: veri sızıntısı değil — çok-kullanıcı DOĞRULUK defekti. P1'de ele alınır çünkü
"ikinci kullanıcı geldiğinde ne bozulur" sorusunun aynı ailesinden.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Workspace, WorkspaceMembership, WorkspaceRole,
    Account, AccountType, NetWorthSnapshot,
)


@pytest.fixture
def engine_and_session():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    yield eng, Session
    eng.dispose()


@pytest.fixture
def iki_kullanici(engine_and_session, monkeypatch):
    """A ve B: her biri personal workspace + bir nakit hesabı. SessionLocal yamalanır."""
    eng, Session = engine_and_session
    db = Session()
    users = []
    for ad, bakiye in (("kullanici_a", 10000.0), ("kullanici_b", 25000.0)):
        u = User(name=ad)
        db.add(u)
        db.commit()
        ws = Workspace(owner_user_id=u.id, name=f"{ad} (Kişisel)", is_personal=True)
        db.add(ws)
        db.commit()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner))
        db.add(Account(user_id=u.id, workspace_id=ws.id, name=f"{ad} kasa",
                       account_type=AccountType.cash, balance=bakiye))
        db.commit()
        users.append((u.id, ws.id))
    db.close()

    import scripts.backfill_net_worth as bf
    import app.startup as startup_mod
    monkeypatch.setattr(bf, "SessionLocal", Session)
    monkeypatch.setattr(startup_mod, "SessionLocal", Session)
    return Session, users


def test_backfill_tum_kullanicilari_kapsar(iki_kullanici):
    """BUG #163: backfill her kullanıcı için snapshot yazmalı — yalnız ilki değil."""
    from scripts.backfill_net_worth import run_backfill

    Session, users = iki_kullanici
    dun = date.today() - timedelta(days=1)
    run_backfill(dun, dun, verbose=False)

    db = Session()
    try:
        for uid, _ws in users:
            n = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.user_id == uid).count()
            assert n >= 1, f"user {uid} için snapshot yazılmadı (çok-kullanıcı kapsamı eksik)"
    finally:
        db.close()


def test_backfill_workspace_id_yazar(iki_kullanici):
    """BUG #163 (b): satırlar personal workspace'e bağlanmalı — NULL kalırsa
    workspace-kapsamlı okumalar bu geçmişi göremez."""
    from scripts.backfill_net_worth import run_backfill

    Session, users = iki_kullanici
    dun = date.today() - timedelta(days=1)
    run_backfill(dun, dun, verbose=False)

    db = Session()
    try:
        for uid, ws_id in users:
            rows = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.user_id == uid).all()
            assert rows, f"user {uid} snapshot yok"
            assert all(r.workspace_id == ws_id for r in rows), (
                f"user {uid}: workspace_id yazılmadı → workspace kapsamlı sorgular göremez"
            )
    finally:
        db.close()


def test_catch_up_tum_kullanicilari_kapsar(iki_kullanici):
    """BUG #163 (c): açılış catch-up'ı da her kullanıcının boşluğunu doldurmalı."""
    from app.startup import catch_up_snapshots

    Session, users = iki_kullanici
    db = Session()
    try:
        # Her iki kullanıcıya 3 gün önce bir başlangıç snapshot'ı koy (catch-up'ın referansı)
        for uid, ws_id in users:
            db.add(NetWorthSnapshot(
                user_id=uid, workspace_id=ws_id,
                snapshot_date=date.today() - timedelta(days=3),
                net_worth_seen=1.0, net_worth_full=1.0, cash=1.0,
                card_debt=0.0, loan_debt=0.0, investment_value=0.0, receivables=0.0,
            ))
        db.commit()
    finally:
        db.close()

    catch_up_snapshots()

    db = Session()
    try:
        for uid, _ws in users:
            n = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.user_id == uid).count()
            assert n >= 2, (
                f"user {uid}: catch-up boşluğu doldurmadı ({n} satır) — çok-kullanıcı kapsamı eksik"
            )
    finally:
        db.close()
