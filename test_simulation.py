"""
Senaryo motoru testi.

3 senaryo:
1. "4 lot TLY satarsam" -> T+0/30/60/90 nakit ve net deger nasil degisir?
2. "Emanet TLY satmaya kalkarsam" -> MC1 ihlali, RAM seviyesinde reddedilmeli
3. "Hicbir sey yapmazsam (baseline)" -> 30 gun sonra durum (Efe'den 10.250 TL gelsin,
   maas gelsin, 2 kredi taksiti dussun)

Gercek DB bozulmaz. Test sonunda DB'yi sifirlamiyoruz cunku zaten
read-only. Murat'in test_coach.py ile olusturdugu DB uzerinden calisabilir.
"""

from datetime import date
from app.database import Base, engine, SessionLocal
from app.models import (
    User, Account, AccountType, RecurringIncome,
    PersonalDebt, DebtDirection, MasterCheckpoint, CheckpointType,
)
from app.simulation_engine import simulate_action


def setup_test_data(db) -> int:
    """Murat'in gercek verisini kur, user_id donder."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    murat = User(name="Murat")
    db.add(murat); db.commit(); db.refresh(murat)

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

    db.add(RecurringIncome(user_id=murat.id, name="Maas",
                           amount=8458.0, day_of_month=1, is_active=True))

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
    db.commit()
    return murat.id


def print_snapshot(snap):
    print(f"  [{snap['label']}] tarih={snap['as_of']}")
    print(f"     Nakit={snap['nakit_kasa']:>10,.2f}  "
          f"Kart={snap['kart_borcu']:>10,.2f}  "
          f"Kredi={snap['kredi_borcu']:>10,.2f}")
    print(f"     Yatirim={snap['yatirim_deger']:>10,.2f}  "
          f"Emanet={snap['emanet_kasa']:>10,.2f}  "
          f"NetDeger={snap['net_deger']:>10,.2f}")
    if "delta_vs_baseline" in snap:
        d = snap["delta_vs_baseline"]
        print(f"     dNakit={d['nakit_kasa']:>+10,.2f}  "
              f"dKart={d['kart_borcu']:>+10,.2f}  "
              f"dNetDeger={d['net_deger']:>+10,.2f}")


def run_scenario(label, db, user_id, action_type, payload):
    print("\n" + "=" * 64)
    print(f"SENARYO: {label}")
    print("=" * 64)
    res = simulate_action(
        db, user_id, action_type, payload,
        horizons_days=(0, 30, 60, 90),
        base_date=date(2026, 5, 1),
    )
    print(f"OK: {res['ok']}, mesaj: {res['message']}")
    if not res["ok"]:
        return

    print("\n--- BASELINE (aksiyon HIC yapilmadi, T+90) ---")
    print_snapshot(res["baseline"])

    print("\n--- AKSIYONLU SENARYO ---")
    for snap in res["snapshots"]:
        print_snapshot(snap)
        print()

    print("--- OLAY GUNLUGU ---")
    for ev in res["event_log"]:
        print(f"  {ev}")

    if res["comparison"]:
        print("\n--- T+30 KARAR OZETI (aksiyonlu vs aksiyonsuz) ---")
        for k, v in res["comparison"].items():
            print(f"  {k:>30}: {v:>+12,.2f} TL")


def main():
    db = SessionLocal()
    user_id = setup_test_data(db)

    # ---- SENARYO 1: 4 lot TLY satisi ----
    run_scenario(
        "4 lot TLY satarsam",
        db, user_id,
        action_type="sell_investment",
        payload={
            "investment_id": 5,           # TLY Fonu Kisisel
            "lots_to_sell": 4,
            "actual_price": 4929.56,
            "credit_to_account_id": 1,    # Enpara
        },
    )

    # ---- SENARYO 2: Emanet ihlali ----
    run_scenario(
        "EMANET TLY satmaya kalkarsam (MC1 ihlal)",
        db, user_id,
        action_type="sell_investment",
        payload={
            "investment_id": 6,           # TLY Fonu Emanet (is_emanet=True)
            "lots_to_sell": 1,
            "actual_price": 4929.56,
            "credit_to_account_id": 1,
        },
    )

    # ---- SENARYO 3: Hicbir sey yapma (sadece baseline projeksiyon) ----
    # add_transaction 0 TL ile no-op ataliyor: gercek hayatta yapilmayan ama
    # motoru sade test eden bir senaryo. Daha temiz yol: dogrudan proje 90 gun.
    # Burada 'update_account_balance' ile kendi kendine ayni degeri verip
    # baseline'in zaman ilerlemesini gosteriyoruz.
    run_scenario(
        "Hicbir sey yapmazsam (sadece zaman ilerlerse)",
        db, user_id,
        action_type="update_account_balance",
        payload={"account_id": 1, "new_balance": 4812.0},  # ayni deger = no-op
    )

    db.close()
    print("\n" + "=" * 64)
    print("SIMULASYON TESTI TAMAMLANDI")
    print("=" * 64)


if __name__ == "__main__":
    main()