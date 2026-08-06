"""
BUG #241 — KULLANICI BİLDİRİMİ: "Efe 5000 TL borç ödendi işaretledim ama cockpit'te
bakiyem artmadı."

Aynı gerçek-dünya olayının (bir alacağın tahsil edilmesi / bir borcun ödenmesi) İKİ kod
yolu vardı ve sözleşmeleri AYRIŞMIŞTI:
  - koç yolu (`action_executor._execute_mark_debt_paid`, BUG #113) nakdi hareket ettiriyordu,
  - panel yolu (`PUT /api/debts/{id}`, "Ödendi" butonu) YALNIZ `is_paid` bayrağını çeviriyordu.
Sonuç: kullanıcı alacağı tahsil işaretleyince alacak listeden düşüyor ama nakit artmıyor —
Tam Net Değer 5000 TL DÜŞÜYOR (para buharlaşıyor). Ters yönde borç ödemesi net değeri
yükseltiyordu.

Bu dosya sözleşmeyi DAVRANIŞ seviyesinde kilitler: hangi yoldan işaretlenirse işaretlensin
nakit ayağı AYNI üretilir, geri alınınca AYNI şekilde geri sarılır, iki kez uygulanmaz.
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import (
    Base, User, Account, AccountType, PersonalDebt, DebtDirection,
    PendingAction, ActionStatus,
)
from app.action_executor import execute_pending_action
from app.rules_engine import generate_cockpit

TODAY = date(2026, 8, 6)


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="test_user"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _cash(db, balance=10000.0, name="Enpara"):
    a = Account(user_id=1, name=name, account_type=AccountType.cash, balance=balance)
    db.add(a); db.commit(); db.refresh(a)
    return a


def _debt(db, direction=DebtDirection.receivable, amount=5000.0, **kw):
    d = PersonalDebt(user_id=1, counterparty="Efe", direction=direction,
                     amount=amount, is_paid=kw.pop("is_paid", False), **kw)
    db.add(d); db.commit(); db.refresh(d)
    return d


# ============================================================
# 1) Kullanıcının bildirdiği senaryo — panel yolu
# ============================================================

def test_241_panel_alacak_tahsili_nakdi_artirir(client, db_session):
    """Kullanıcının cümlesi: 'ödendi işaretledim, bakiyem artmadı'. Artmalı."""
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    r = client.put(f"/api/debts/{d.id}", json={"is_paid": True, "paid_date": "2026-08-06"})
    assert r.status_code == 200

    db_session.refresh(cash)
    assert float(cash.balance) == 15000.0


def test_241_panel_alacak_tahsili_cockpit_nakit_kasasina_yansir(client, db_session):
    """Kanıt kullanıcının BAKTIĞI yüzeyde: cockpit nakit_kasa."""
    _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    once = generate_cockpit(1, TODAY, db_session)["nakit_kasa"]
    client.put(f"/api/debts/{d.id}", json={"is_paid": True, "paid_date": "2026-08-06"})
    sonra = generate_cockpit(1, TODAY, db_session)["nakit_kasa"]

    assert sonra == pytest.approx(once + 5000.0)


def test_241_panel_alacak_tahsili_tam_net_degeri_degistirmez(client, db_session):
    """Tahsilat net-NÖTR: alacak nakde döner, Tam Net Değer sabit kalır."""
    _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    once = generate_cockpit(1, TODAY, db_session)["net_deger_tam"]
    client.put(f"/api/debts/{d.id}", json={"is_paid": True, "paid_date": "2026-08-06"})
    sonra = generate_cockpit(1, TODAY, db_session)["net_deger_tam"]

    assert sonra == pytest.approx(once)


def test_241_panel_borc_odemesi_nakdi_azaltir(client, db_session):
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.payable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"is_paid": True, "paid_date": "2026-08-06"})

    db_session.refresh(cash)
    assert float(cash.balance) == 5000.0


def test_241_panel_sadece_paid_date_yollasa_da_nakit_hareket_eder(client, db_session):
    """Panel `is_paid` göndermeden yalnız tarih yollayabilir (BUG #106 türetimi)."""
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"paid_date": "2026-08-06"})

    db_session.refresh(cash)
    assert float(cash.balance) == 15000.0


# ============================================================
# 2) Simetri ve tek-uygulama (para üretilmez / kaybolmaz)
# ============================================================

def test_241_geri_alinca_nakit_geri_saril(client, db_session):
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    client.put(f"/api/debts/{d.id}", json={"is_paid": False})

    db_session.refresh(cash)
    assert float(cash.balance) == 10000.0


def test_241_iki_kez_isaretlemek_nakdi_cift_uygulamaz(client, db_session):
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    client.put(f"/api/debts/{d.id}", json={"is_paid": True, "description": "not"})

    db_session.refresh(cash)
    assert float(cash.balance) == 15000.0


def test_241_odenmis_kaydin_tutari_duzeltilirse_nakit_farki_kadar_duzelir(client, db_session):
    """5000 yerine 4500 tahsil edilmiş: düzeltme nakde de yansımalı (yoksa 500 TL hayalet)."""
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    client.put(f"/api/debts/{d.id}", json={"amount": 4500.0})

    db_session.refresh(cash)
    assert float(cash.balance) == 14500.0


def test_241_odenmemis_kaydin_tutari_degisince_nakit_dokunulmaz(client, db_session):
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"amount": 7000.0})

    db_session.refresh(cash)
    assert float(cash.balance) == 10000.0


def test_241_eski_odenmis_kayit_geri_alinirsa_hayalet_para_dusmez(client, db_session):
    """Fix ÖNCESİ ödenmiş işaretlenen kayıtların nakit ayağı hiç uygulanmamıştı.
    Geri alma o kayıtlardan para DÜŞMEMELİ (uygulanmamış ayak geri sarılamaz)."""
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0,
              is_paid=True, paid_date=date(2026, 8, 1))  # legacy: ayak uygulanmadı

    client.put(f"/api/debts/{d.id}", json={"is_paid": False})

    db_session.refresh(cash)
    assert float(cash.balance) == 10000.0


def test_241_nakit_hesap_yoksa_istek_patlamaz(client, db_session):
    d = _debt(db_session, DebtDirection.receivable, 5000.0)
    r = client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    assert r.status_code == 200
    assert r.json()["is_paid"] is True


def test_241_odenmis_kayit_silinince_nakit_etkisi_de_geri_saril(client, db_session):
    """Silinen kaydın arkasında sahipsiz bakiye etkisi kalamaz."""
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    client.delete(f"/api/debts/{d.id}")

    db_session.refresh(cash)
    assert float(cash.balance) == 10000.0


def test_241_eski_odenmis_kayit_silinince_nakit_dokunulmaz(client, db_session):
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0,
              is_paid=True, paid_date=date(2026, 8, 1))  # legacy: ayak uygulanmadı

    client.delete(f"/api/debts/{d.id}")

    db_session.refresh(cash)
    assert float(cash.balance) == 10000.0


def test_241_emanet_nakit_hesabina_dokunulmaz(client, db_session):
    """MC1: emanet bakiyesi otomatik hiçbir yoldan değişmez (id sırasında ÖNDE olsa bile)."""
    emanet = Account(user_id=1, name="Emanet", account_type=AccountType.cash,
                     balance=20000.0, is_emanet=True)
    db_session.add(emanet); db_session.commit()
    kendi = _cash(db_session, 10000.0, name="Enpara")
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    client.put(f"/api/debts/{d.id}", json={"is_paid": True})

    db_session.refresh(emanet); db_session.refresh(kendi)
    assert float(emanet.balance) == 20000.0     # dokunulmadı
    assert float(kendi.balance) == 15000.0


def test_241_hedef_hesap_kayitta_iz_birakir(client, db_session):
    """Bakiye sessizce değişmez: kapanışın nereye işlendiği uçtan görünür."""
    cash = _cash(db_session, 10000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0)

    r = client.put(f"/api/debts/{d.id}", json={"is_paid": True})
    assert r.json()["settlement_account_id"] == cash.id

    r2 = client.put(f"/api/debts/{d.id}", json={"is_paid": False})
    assert r2.json()["settlement_account_id"] is None


# ============================================================
# 3) İKİ YOL PARİTESİ — sözleşme tek kaynaktan gelir
# ============================================================

def _koc_yolu_isaretle(db, debt_id: int) -> None:
    p = PendingAction(user_id=1, action_type="mark_debt_paid", summary="test",
                      payload=f'{{"debt_id": {debt_id}}}', status=ActionStatus.pending)
    db.add(p); db.commit(); db.refresh(p)
    execute_pending_action(db, p.id, 1)


# ============================================================
# 4) ONARIM — fix ÖNCESİ kapanışların eksik ayağı (scripts/repair_debt_settlements.py)
# ============================================================

def test_241_onarim_eski_kapanisin_eksik_ayagini_uygular(db_session):
    from scripts.repair_debt_settlements import onar
    cash = _cash(db_session, 1963.52)
    _debt(db_session, DebtDirection.receivable, 5000.0,
          is_paid=True, paid_date=date(2026, 8, 6))

    onar(db_session, uygula=True)

    db_session.refresh(cash)
    assert float(cash.balance) == pytest.approx(6963.52)


def test_241_onarim_kuru_calismada_hicbir_sey_yazmaz(db_session):
    from scripts.repair_debt_settlements import onar
    cash = _cash(db_session, 1000.0)
    _debt(db_session, DebtDirection.receivable, 5000.0,
          is_paid=True, paid_date=date(2026, 8, 6))

    onar(db_session, uygula=False)

    db_session.refresh(cash)
    assert float(cash.balance) == 1000.0


def test_241_onarim_koc_yolundan_kapatilani_atlar_cift_saymaz(db_session):
    """Koç yolu nakdi ZATEN hareket ettirmişti (BUG #113) — ikinci kez uygulanamaz."""
    from scripts.repair_debt_settlements import onar
    cash = _cash(db_session, 15000.0)
    d = _debt(db_session, DebtDirection.receivable, 5000.0,
              is_paid=True, paid_date=date(2026, 8, 6))
    db_session.add(PendingAction(
        user_id=1, action_type="mark_debt_paid", summary="test",
        payload=f'{{"debt_id": {d.id}}}', status=ActionStatus.executed))
    db_session.commit()

    onar(db_session, uygula=True)

    db_session.refresh(cash)
    assert float(cash.balance) == 15000.0


def test_241_onarim_idempotent(db_session):
    from scripts.repair_debt_settlements import onar
    cash = _cash(db_session, 1000.0)
    _debt(db_session, DebtDirection.receivable, 5000.0,
          is_paid=True, paid_date=date(2026, 8, 6))

    onar(db_session, uygula=True)
    ikinci = onar(db_session, uygula=True)

    db_session.refresh(cash)
    assert float(cash.balance) == 6000.0
    assert "onarılacak bir şey yok" in ikinci[0]


# ============================================================
# 5) İKİ YOL PARİTESİ (devam) — parametrik
# ============================================================

@pytest.mark.parametrize("direction", [DebtDirection.receivable, DebtDirection.payable])
def test_241_koc_yolu_ve_panel_yolu_ayni_nakit_etkisini_uretir(client, db_session, direction):
    """L21/L11 sınıfı: aynı olayın iki yolu ayrışamaz — nakit etkisi TEK kaynaktan gelir."""
    cash = _cash(db_session, 10000.0)
    panel_debt = _debt(db_session, direction, 5000.0)
    koc_debt = _debt(db_session, direction, 5000.0)

    client.put(f"/api/debts/{panel_debt.id}", json={"is_paid": True})
    db_session.refresh(cash)
    panel_etkisi = float(cash.balance) - 10000.0

    _koc_yolu_isaretle(db_session, koc_debt.id)
    db_session.refresh(cash)
    koc_etkisi = float(cash.balance) - 10000.0 - panel_etkisi

    assert panel_etkisi == koc_etkisi != 0.0
