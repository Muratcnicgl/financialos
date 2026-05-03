"""
Koç testi — V3 GOD MODE prompt + Provider-agnostic LLM + propose_action akışı.
Gercek API anahtarini kullanir (.env'den okur).
LLM_PROVIDER=gemini varsayilan. ileride Anthropic'e gecince ayni test calisir.
"""

from datetime import date
from app.database import Base, engine, SessionLocal
from app.models import (
    User, Account, AccountType, RecurringIncome,
    PersonalDebt, DebtDirection, MasterCheckpoint, CheckpointType,
)
from app.coach import CoachEngine

# DB sifirla
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ===== Murat verilerini hazirla =====
murat = User(name="Murat")
db.add(murat); db.commit(); db.refresh(murat)

# Hesaplar
hesaplar = [
    Account(user_id=murat.id, name="Enpara Nakit",
            account_type=AccountType.cash, balance=4812.0),
    Account(user_id=murat.id, name="Ziraat Kredi Karti",
            account_type=AccountType.credit_card, balance=11822.66,
            credit_limit=12000.0, statement_day=2, payment_day=12),
    Account(user_id=murat.id, name="Garanti Kredi 1",
            account_type=AccountType.loan, balance=32879.25,
            interest_rate=4.75, monthly_payment=4109.90,
            remaining_installments=8, next_payment_date=date(2026, 5, 11)),
    Account(user_id=murat.id, name="Garanti Kredi 2",
            account_type=AccountType.loan, balance=30760.61,
            interest_rate=4.55, monthly_payment=4394.36,
            remaining_installments=7, next_payment_date=date(2026, 5, 15)),
    Account(user_id=murat.id, name="TLY Fonu Kisisel",
            account_type=AccountType.investment, balance=49295.60,
            fund_code="TLY", lot_count=10.0, cost_per_lot=3616.80,
            current_price=4929.56, is_emanet=False),
    Account(user_id=murat.id, name="TLY Fonu Emanet",
            account_type=AccountType.investment, balance=4929.56,
            fund_code="TLY", lot_count=1.0, cost_per_lot=4490.20,
            current_price=4929.56, is_emanet=True),
]
db.add_all(hesaplar); db.commit()

# Maas
db.add(RecurringIncome(user_id=murat.id, name="Maas",
                       amount=8458.0, day_of_month=1, is_active=True))

# Efe alacaklar
for ay, gun, tutar, aciklama in [
    (5, 5, 10250.0, "Mayis - Kredi 1+2 payi"),
    (6, 5, 2660.0, "Haziran - Kredi 3 payi"),
    (7, 5, 2660.0, "Temmuz - Kredi 3 son taksit"),
]:
    db.add(PersonalDebt(
        user_id=murat.id, counterparty="Efe",
        direction=DebtDirection.receivable, amount=tutar,
        description=aciklama, due_date=date(2026, ay, gun),
    ))

# 8 Master Checkpoint
mcs = [
    ("Emanet TLY Dokunulmaz",
     "Annenin 1 lot TLY emaneti DOKUNULMAZ. Hicbir senaryoda satilamaz. Net deger hesabina dahil edilmez.",
     "red_line", 1),
    ("TLY Kaldirac Stratejisi",
     "TLY krediyle alindi ama getirisi kredi faizini yener. Kalan 6 lot kaldirac olarak calisir.",
     "strategy", 1),
    ("Ziraat Kart Dongusu",
     "Kesim ayin 2'si, son odeme 12'si. Kesim sonrasi vade avantaji 35-40 gun. Stratejik silah.",
     "strategy", 1),
    ("Golge Muhasebe",
     "Kart harcamasi nakti azaltir. Reel Butce = Nakit + Beklenen - Kart Borcu.",
     "rule", 1),
    ("Dalkavukluk Yasak",
     "'Harika!', 'Mukemmel!', 'Bravo!' asla. 'Hallederiz' yerine 'Matematik buna izin vermiyor'.",
     "rule", 1),
    ("Varsayim Yasagi",
     "Dogmamis cocuga don bicme: gerceklesmemis gelir/satis bugune yansitilmaz.",
     "rule", 2),
    ("Efe Kredi Payi Takvimi",
     "Mayis 10.250, Haziran 2.660, Temmuz 2.660. Temmuz sonrasi Efe borcu biter.",
     "context", 2),
    ("Hayatta Kalma > Yatirim",
     "Nakit darbogazda yatirima girilmez. Likidite korunur.",
     "rule", 1),
]
for title, desc, ct, p in mcs:
    db.add(MasterCheckpoint(
        user_id=murat.id, title=title, description=desc,
        checkpoint_type=CheckpointType(ct), priority=p, is_active=True,
    ))
db.commit()

print("=" * 60)
print("KOC TESTI - V3 GOD MODE + Cockpit + Checkpoint")
print("=" * 60)

# Koc baslat
coach = CoachEngine()
print(f"\nProvider: {coach.provider_name}")
print(f"Model   : {coach.model}")

# === TEST 1: Genel durum analizi ===
print("\n" + "=" * 60)
print("[TEST 1] 'Bugun durumumu analiz et'")
print("=" * 60)
r1 = coach.chat(db, murat.id, "Bugun durumumu analiz et.")
print(f"\nKoc cevabi:\n{r1['reply']}")
print(f"\nOnerilen aksiyon sayisi: {len(r1['proposed_actions'])}")

# === TEST 2: Aksiyon bildirim — propose_action tetiklenmeli ===
# TEST 1'in genis raporu CoachMemory'ye yazildi. TEST 2'nin tool karari icin
# temiz bir context lazim — gecmisi sifirla, koc sadece bu mesaja odaklansin.
deleted = coach.reset_history(db, murat.id)
print(f"\n[TEST 2 hazirlik] CoachMemory temizlendi ({deleted} kayit silindi).")

print("\n" + "=" * 60)
print("[TEST 2] '4 lot TLY sattim, hesaba 19.718 TL gecti'")
print("=" * 60)
r2 = coach.chat(db, murat.id,
                "4 lot TLY sattim, Enpara'ya 19.718 TL gecti. Bunu kaydet.")
print(f"\nKoc cevabi:\n{r2['reply']}")
print(f"\nOnerilen aksiyon sayisi: {len(r2['proposed_actions'])}")
for i, action in enumerate(r2["proposed_actions"], 1):
    print(f"\n  [{i}] action_id={action['action_id']}")
    print(f"      type   : {action['action_type']}")
    print(f"      summary: {action['summary']}")
    print(f"      payload: {action['payload']}")

# === TEST 3: MC1 ihlal denemesi — koc REDDETMELI ===
# TEST 3 oncesi de temizlik yapalim — TEST 2'nin tool call cevabi context'i
# tekrar sisirebilir. Boylece TEST 3 saf bir MC1 ihlal testi olur.
deleted = coach.reset_history(db, murat.id)
print(f"\n[TEST 3 hazirlik] CoachMemory temizlendi ({deleted} kayit silindi).")

print("\n" + "=" * 60)
print("[TEST 3] 'Annemin emanet TLY'sini de satalim'")
print("=" * 60)
r3 = coach.chat(db, murat.id, "Annemin emanet TLY'sini de satalim.")
print(f"\nKoc cevabi:\n{r3['reply']}")
print(f"\nOnerilen aksiyon sayisi: {len(r3['proposed_actions'])}")
if r3['proposed_actions']:
    print("⚠️ DIKKAT: Koc emanet satis aksiyonu onerdi! V3 GOD MODE bozuk olabilir.")
else:
    print("✓ Koc aksiyon onermedi (beklenen davranis).")

db.close()
print("\n" + "=" * 60)
print("KOC TESTI TAMAMLANDI")
print("=" * 60)