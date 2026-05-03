"""
action_executor testi.
Gercek DB ile (gecici) propose -> execute akisini test eder.
KRITIK TEST: MC1 emanet hesap satisi REDDEDILMELI.
"""

from datetime import date
from app.database import Base, engine, SessionLocal
from app.models import (
    User, Account, AccountType, MasterCheckpoint, CheckpointType,
)
from app.action_executor import (
    propose_action, execute_pending_action, reject_pending_action,
)

# DB'yi sifirla (sadece test icin)
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

db = SessionLocal()

print("=" * 60)
print("ACTION EXECUTOR TESTI")
print("=" * 60)

# Hazirlik: Murat + 2 yatirim hesabi (1 kisisel TLY, 1 EMANET TLY)
murat = User(name="Murat")
db.add(murat)
db.commit()
db.refresh(murat)

tly_kisisel = Account(
    user_id=murat.id,
    name="TLY Fonu Kisisel",
    account_type=AccountType.investment,
    fund_code="TLY",
    lot_count=10.0,
    cost_per_lot=3616.80,
    current_price=4929.56,
    balance=49295.60,
    is_emanet=False,
)
tly_emanet = Account(
    user_id=murat.id,
    name="TLY Fonu Emanet",
    account_type=AccountType.investment,
    fund_code="TLY",
    lot_count=1.0,
    cost_per_lot=4490.20,
    current_price=4929.56,
    balance=4929.56,
    is_emanet=True,  # MC1 — DOKUNULMAZ
)
enpara = Account(
    user_id=murat.id,
    name="Enpara Nakit",
    account_type=AccountType.cash,
    balance=4812.0,
)
db.add_all([tly_kisisel, tly_emanet, enpara])
db.commit()
for a in (tly_kisisel, tly_emanet, enpara):
    db.refresh(a)

print(f"\nHazirlik tamam:")
print(f"  Murat ID: {murat.id}")
print(f"  TLY Kisisel ID: {tly_kisisel.id} (lot={tly_kisisel.lot_count}, balance={tly_kisisel.balance})")
print(f"  TLY EMANET  ID: {tly_emanet.id}  (lot={tly_emanet.lot_count}, balance={tly_emanet.balance}, is_emanet={tly_emanet.is_emanet})")
print(f"  Enpara      ID: {enpara.id}      (balance={enpara.balance})")

# === TEST 1: TLY Kisisel'den 4 lot SAT — Gurcistan senaryosu ===
print("\n" + "=" * 60)
print("[TEST 1] TLY Kisisel — 4 lot satis (Gurcistan senaryosu)")
print("=" * 60)

pending1 = propose_action(
    db=db,
    user_id=murat.id,
    action_type="sell_investment",
    payload={
        "investment_id": tly_kisisel.id,
        "lots_to_sell": 4,
        "credit_to_account_id": enpara.id,
    },
    summary="TLY Kisisel'den 4 lot sat, nakti Enpara'ya yatir.",
)
print(f"  Pending olusturuldu: id={pending1.id}, status={pending1.status.value}")
print(f"  Ozet: {pending1.summary}")

# Onayla
result1 = execute_pending_action(db, pending1.id, murat.id)
print(f"\n  Sonuc: success={result1['success']}")
if result1["success"]:
    sim = result1["result"]["satis_simulasyonu"]
    print(f"  Satis tutari      : {sim['satis_tutari']:,.2f} TL")
    print(f"  Brut kar          : {sim['brut_kar']:,.2f} TL")
    print(f"  Stopaj            : {sim['stopaj']:,.2f} TL")
    print(f"  Net eline gecen   : {sim['net_eline_gecen']:,.2f} TL")
    print(f"  Kalan lot         : {result1['result']['kalan_lot']}")
    print(f"  Enpara yeni baki. : {result1['result']['credit_account']['yeni_bakiye']:,.2f} TL")
else:
    print(f"  HATA: {result1.get('error')}")

# === TEST 2: TLY EMANET'ten 1 lot SAT — REDDEDILMELI ===
print("\n" + "=" * 60)
print("[TEST 2] TLY EMANET — 1 lot satis (MC1 IHLALI)")
print("=" * 60)

pending2 = propose_action(
    db=db,
    user_id=murat.id,
    action_type="sell_investment",
    payload={
        "investment_id": tly_emanet.id,
        "lots_to_sell": 1,
    },
    summary="TLY Emanet'ten 1 lot sat (TEST — MC1 ihlal denemesi).",
)
print(f"  Pending olusturuldu: id={pending2.id}, status={pending2.status.value}")

result2 = execute_pending_action(db, pending2.id, murat.id)
print(f"\n  Sonuc: success={result2['success']}")
if result2["success"]:
    print(f"  ⚠️  KRITIK HATA: Emanet hesap satildi! MC1 BOZUK!")
else:
    print(f"  ✓ Beklendigi gibi REDDEDILDI: {result2.get('error')}")

# Emanet hesabin durumunu kontrol et
db.refresh(tly_emanet)
print(f"  Emanet lot kontrol: {tly_emanet.lot_count} (degismedi olmali, =1)")

# === TEST 3: Add transaction (gider) ===
print("\n" + "=" * 60)
print("[TEST 3] Gider islemi ekle (Enpara'dan 200 TL)")
print("=" * 60)

pending3 = propose_action(
    db=db,
    user_id=murat.id,
    action_type="add_transaction",
    payload={
        "transaction_type": "expense",
        "amount": 200.0,
        "category": "yiyecek",
        "description": "Market alisverisi",
        "account_id": enpara.id,
        "auto_update_balance": True,
    },
    summary="200 TL market gideri — Enpara'dan.",
)
result3 = execute_pending_action(db, pending3.id, murat.id)
print(f"  Sonuc: success={result3['success']}")
if result3["success"]:
    print(f"  Islem ID: {result3['result']['transaction_id']}")
    print(f"  Bakiye degisimi: {result3['result']['balance_diff']}")
    db.refresh(enpara)
    print(f"  Enpara yeni bakiye: {enpara.balance:,.2f} TL")

# === TEST 4: Reject akisi ===
print("\n" + "=" * 60)
print("[TEST 4] Reject akisi")
print("=" * 60)

pending4 = propose_action(
    db=db,
    user_id=murat.id,
    action_type="add_transaction",
    payload={"transaction_type": "expense", "amount": 5000, "category": "test"},
    summary="5000 TL test gideri — REDDEDILECEK",
)
print(f"  Pending: id={pending4.id}, status={pending4.status.value}")
reject_result = reject_pending_action(db, pending4.id, murat.id, reason="Test reddetme")
print(f"  Reject sonuc: {reject_result}")

# === Ozet ===
print("\n" + "=" * 60)
print("OZET")
print("=" * 60)
db.refresh(tly_kisisel)
db.refresh(tly_emanet)
db.refresh(enpara)
print(f"  TLY Kisisel  : lot={tly_kisisel.lot_count}, balance={tly_kisisel.balance:,.2f} (4 lot satildi)")
print(f"  TLY Emanet   : lot={tly_emanet.lot_count}, balance={tly_emanet.balance:,.2f} (DEGISMEMELI)")
print(f"  Enpara       : balance={enpara.balance:,.2f}")

db.close()
print("\n" + "=" * 60)
print("ACTION EXECUTOR TESTI TAMAMLANDI")
print("=" * 60)