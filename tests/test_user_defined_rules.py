"""
P3.5 / H3 (Wave-9) — BUG #192: KULLANICININ KENDİ KURALI kod seviyesinde dayatılır.

Murat'ın direktifi: *"başka kullanıcıların kendi verileri, kendi öznel kurallarını
ekleyebileceği şekilde ayarlanmış tam versiyona düzeltmek lazım."*

Önceki durum — iki sınıf kural vardı:
  - **Ürünün kuralı** (MC1/emanet): `action_executor` içinde KOD seviyesinde bloklanıyordu.
  - **Kullanıcının kuralı** ("acil fonuma dokunmam"): yalnızca koça **tavsiye** olarak
    gidiyordu → dayatma LLM'in iyi niyetine kalmıştı. Kullanıcı korunduğunu SANIYORDU.

Artık kurallar veri olarak saklanır (`rule_type` + `rule_params`) ve aksiyon uygulanmadan
ÖNCE `app/user_rules.enforce_user_rules` ile dayatılır: ihlalde işlem DB'ye YAZILMAZ ve
kullanıcı kendi kuralının başlığıyla uyarılır.
"""
from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (
    Base, User, Account, AccountType, MasterCheckpoint, CheckpointType,
    PendingAction, ActionStatus, Transaction,
)
from app.action_executor import execute_pending_action
from app.user_rules import enforce_user_rules, RuleViolation


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici(db):
    u = User(name="Zeynep")
    db.add(u)
    db.commit()
    db.add(Account(user_id=u.id, name="Maaş Hesabım", account_type=AccountType.cash,
                   balance=10000.0))
    db.commit()
    return u


def _kural(db, user_id, baslik, rule_type, params, priority=1):
    cp = MasterCheckpoint(
        user_id=user_id, title=baslik, description="Kullanıcının kendi kuralı",
        checkpoint_type=CheckpointType.red_line, priority=priority, is_active=True,
        rule_type=rule_type, rule_params=json.dumps(params),
    )
    db.add(cp)
    db.commit()
    return cp


def _pending(db, user_id, action_type, payload):
    pa = PendingAction(user_id=user_id, action_type=action_type,
                       payload=json.dumps(payload), summary="test",
                       status=ActionStatus.pending)
    db.add(pa)
    db.commit()
    return pa


# ── min_cash_floor: "nakdim X'in altına düşmesin" ────────────────────────────

def test_nakit_tabani_ihlali_bloklanir(db, kullanici):
    _kural(db, kullanici.id, "Acil fonuma dokunmam", "min_cash_floor", {"amount": 8000})
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 5000, "category": "market"})

    sonuc = execute_pending_action(db, pa.id, kullanici.id)

    assert sonuc["success"] is False, "Kullanıcının kendi kuralı dayatılmadı"
    assert "Acil fonuma dokunmam" in sonuc["error"], (
        f"Uyarı kullanıcının KENDİ kural başlığını taşımıyor: {sonuc['error']}"
    )
    assert db.query(Transaction).count() == 0, "Bloklandı ama işlem yine de yazıldı!"


def test_taban_uzerinde_kalan_harcama_gecer(db, kullanici):
    """Pozitif kontrol: kural gereksiz yere engellemez."""
    _kural(db, kullanici.id, "Acil fonum", "min_cash_floor", {"amount": 8000})
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 1500, "category": "market"})
    sonuc = execute_pending_action(db, pa.id, kullanici.id)
    assert sonuc["success"] is True, sonuc.get("error")


def test_pasif_kural_dayatilmaz(db, kullanici):
    cp = _kural(db, kullanici.id, "Devre dışı kural", "min_cash_floor", {"amount": 9999})
    cp.is_active = False
    db.commit()
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 5000, "category": "market"})
    assert execute_pending_action(db, pa.id, kullanici.id)["success"] is True


# ── account_untouchable: "bu hesaba dokunma" (emanet'in kullanıcı-tanımlı hali) ──

def test_dokunulmaz_hesap_korunur(db, kullanici):
    hesap = db.query(Account).first()
    _kural(db, kullanici.id, "Çocuğumun hesabı", "account_untouchable",
           {"account_id": hesap.id})
    pa = _pending(db, kullanici.id, "update_account_balance",
                  {"account_id": hesap.id, "new_balance": 50.0})

    sonuc = execute_pending_action(db, pa.id, kullanici.id)
    assert sonuc["success"] is False
    assert "Çocuğumun hesabı" in sonuc["error"]
    db.refresh(hesap)
    assert float(hesap.balance) == 10000.0, "Dokunulmaz hesabın bakiyesi değişti!"


def test_baska_hesap_etkilenmez(db, kullanici):
    korunan = db.query(Account).first()
    diger = Account(user_id=kullanici.id, name="Günlük", account_type=AccountType.cash,
                    balance=3000.0)
    db.add(diger)
    db.commit()
    _kural(db, kullanici.id, "Korunan", "account_untouchable", {"account_id": korunan.id})
    pa = _pending(db, kullanici.id, "update_account_balance",
                  {"account_id": diger.id, "new_balance": 2500.0})
    assert execute_pending_action(db, pa.id, kullanici.id)["success"] is True


# ── max_single_expense: "tek seferde X'ten fazla harcamam" ───────────────────

def test_tek_harcama_tavani(db, kullanici):
    _kural(db, kullanici.id, "Dürtüsel alışveriş freni", "max_single_expense",
           {"amount": 1000})
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 2500, "category": "alisveris"})
    sonuc = execute_pending_action(db, pa.id, kullanici.id)
    assert sonuc["success"] is False
    assert "Dürtüsel alışveriş freni" in sonuc["error"]


# ── izolasyon: kural SAHİBİNİ bağlar ────────────────────────────────────────

def test_baska_kullanicinin_kurali_beni_baglamaz(db, kullanici):
    """Kurallar kişiseldir — B'nin kuralı A'nın işlemini engellememeli (P1 ailesi)."""
    b = User(name="baska")
    db.add(b)
    db.commit()
    _kural(db, b.id, "B'nin katı kuralı", "min_cash_floor", {"amount": 999999})

    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 100, "category": "market"})
    assert execute_pending_action(db, pa.id, kullanici.id)["success"] is True


# ── dayanıklılık: bozuk kural sistemi kilitlemez ────────────────────────────

def test_bozuk_kural_parametresi_islemi_kilitlemez(db, kullanici):
    cp = MasterCheckpoint(user_id=kullanici.id, title="Bozuk", description="x",
                          checkpoint_type=CheckpointType.rule, priority=2, is_active=True,
                          rule_type="min_cash_floor", rule_params="{bozuk json")
    db.add(cp)
    db.commit()
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 100, "category": "market"})
    assert execute_pending_action(db, pa.id, kullanici.id)["success"] is True


def test_bilinmeyen_kural_tipi_atlanir(db, kullanici):
    cp = MasterCheckpoint(user_id=kullanici.id, title="Gelecek sürümden", description="x",
                          checkpoint_type=CheckpointType.rule, priority=2, is_active=True,
                          rule_type="henuz_olmayan_tip", rule_params="{}")
    db.add(cp)
    db.commit()
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 100, "category": "market"})
    assert execute_pending_action(db, pa.id, kullanici.id)["success"] is True


def test_serbest_metin_kirmizi_cizgi_islem_engellemez(db, kullanici):
    """Geriye uyum: rule_type'ı olmayan klasik kırmızı çizgiler koça bağlam olarak gider."""
    cp = MasterCheckpoint(user_id=kullanici.id, title="Serbest metin",
                          description="Gereksiz harcama yapma", priority=1,
                          checkpoint_type=CheckpointType.red_line, is_active=True)
    db.add(cp)
    db.commit()
    pa = _pending(db, kullanici.id, "add_transaction", {
        "transaction_type": "expense", "amount": 100, "category": "market"})
    assert execute_pending_action(db, pa.id, kullanici.id)["success"] is True


def test_dogrudan_cagri_ihlalde_yukselir(db, kullanici):
    _kural(db, kullanici.id, "Taban", "min_cash_floor", {"amount": 9000})
    with pytest.raises(RuleViolation):
        enforce_user_rules(db, kullanici.id, "add_transaction",
                           {"transaction_type": "expense", "amount": 5000})
