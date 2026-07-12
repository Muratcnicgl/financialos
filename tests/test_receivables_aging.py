"""
FEAT-027 — alacak yaşlandırma (AR aging). Ödenmemiş alacakları vade-yaşına göre gruplar.
calculate_receivables_aging (saf) + cockpit + koç context (13 dağınık alacak senaryosu).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, PersonalDebt, DebtDirection
from app.rules_engine import calculate_receivables_aging

TODAY = date(2026, 7, 12)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


def _rec(kim, amount, due_offset=None, paid=False):
    """due_offset: today'den gün farkı (negatif = geçmiş/gecikmiş, None = tarihsiz)."""
    due = None if due_offset is None else TODAY + timedelta(days=due_offset)
    return PersonalDebt(user_id=1, counterparty=kim, direction=DebtDirection.receivable,
                        amount=amount, due_date=due, is_paid=paid)


def _payable(kim, amount, due_offset=-10):
    return PersonalDebt(user_id=1, counterparty=kim, direction=DebtDirection.payable,
                        amount=amount, due_date=TODAY + timedelta(days=due_offset), is_paid=False)


# ---- calculate_receivables_aging (saf) -------------------------------------

def test_alacak_yoksa_none(db):
    assert calculate_receivables_aging(1, TODAY, db) is None


def test_odenmis_ve_borc_haric(db):
    db.add(_rec("Efe", 1000, due_offset=-50, paid=True))   # ödenmiş → sayılmaz
    db.add(_payable("Banka", 5000, due_offset=-50))         # payable → sayılmaz
    db.commit()
    assert calculate_receivables_aging(1, TODAY, db) is None


def test_kova_siniflandirma(db):
    db.add(_rec("Efe", 2500, due_offset=-75))     # 75 gün gecikmiş → 60+
    db.add(_rec("Can", 1200, due_offset=-45))     # 45 → 31-60
    db.add(_rec("Ali", 800, due_offset=-10))      # 10 → 1-30
    db.add(_rec("Veli", 600, due_offset=5))       # gelecek → vadesi gelmemiş
    db.add(_rec("Deniz", 400, due_offset=None))   # tarihsiz
    db.commit()
    r = calculate_receivables_aging(1, TODAY, db)
    assert r["adet"] == 5
    assert r["gecikmis_adet"] == 3                       # Efe+Can+Ali
    assert r["toplam"] == 5500.0
    assert r["toplam_gecikmis"] == 4500.0                # 2500+1200+800
    etiketler = [k["etiket"] for k in r["kovalar"]]
    # en çok geciken kova önce (öncelik sırası korunur)
    assert etiketler == ["60+ gün gecikmiş", "31-60 gün gecikmiş", "1-30 gün gecikmiş",
                         "vadesi gelmemiş", "tarihsiz"]
    assert r["en_riskli"][0]["kim"] == "Efe"            # en çok geciken
    assert r["en_riskli"][0]["gecikme_gun"] == 75


def test_kova_sinir_gunleri(db):
    # sınır: 60+ = >=61; 31-60 = [31,60]; 1-30 = [1,30]; 0/negatif = vadesi gelmemiş
    db.add(_rec("A", 100, due_offset=-61))   # 61 → 60+
    db.add(_rec("B", 100, due_offset=-60))   # 60 → 31-60
    db.add(_rec("C", 100, due_offset=-31))   # 31 → 31-60
    db.add(_rec("D", 100, due_offset=-30))   # 30 → 1-30
    db.add(_rec("E", 100, due_offset=0))     # bugün → vadesi gelmemiş (henüz gecikmedi)
    db.commit()
    r = calculate_receivables_aging(1, TODAY, db)
    by = {k["etiket"]: k["adet"] for k in r["kovalar"]}
    assert by["60+ gün gecikmiş"] == 1
    assert by["31-60 gün gecikmiş"] == 2
    assert by["1-30 gün gecikmiş"] == 1
    assert by["vadesi gelmemiş"] == 1
    assert r["gecikmis_adet"] == 4                        # bugün vadeli gecikmiş sayılmaz


def test_bos_kova_atlanir(db):
    db.add(_rec("Efe", 1000, due_offset=-90))
    db.commit()
    r = calculate_receivables_aging(1, TODAY, db)
    assert len(r["kovalar"]) == 1
    assert r["kovalar"][0]["etiket"] == "60+ gün gecikmiş"


# ---- cockpit + koç entegrasyonu --------------------------------------------

def test_cockpit_alacak_yaslanma_alani(db):
    from app.rules_engine import generate_cockpit
    from app.models import Account, AccountType
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=1000.0))
    db.add(_rec("Efe", 2500, due_offset=-75))
    db.commit()
    c = generate_cockpit(1, TODAY, db)
    assert c["alacak_yaslanma"] is not None
    assert c["alacak_yaslanma"]["gecikmis_adet"] == 1


def test_koc_contextine_duser(db):
    from app.coach import _build_context_message
    from app.models import Account, AccountType
    today = date.today()
    db.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=1000.0))
    # bugüne göre gecikmiş (context date.today() kullanır)
    db.add(PersonalDebt(user_id=1, counterparty="Efe", direction=DebtDirection.receivable,
                        amount=2500, due_date=today - timedelta(days=75), is_paid=False))
    db.commit()
    context, cockpit = _build_context_message(db, 1)
    assert "ALACAK YAŞLANDIRMA" in context
    assert "Efe" in context
    # grounding: gecikmiş toplam _coach_extra_numbers'a tanıtılmış
    assert any(abs(n - cockpit["alacak_yaslanma"]["toplam_gecikmis"]) < 0.01
               for n in cockpit.get("_coach_extra_numbers", []))
