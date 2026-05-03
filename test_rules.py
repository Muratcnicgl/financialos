"""
Rules Engine hızlı doğrulama testi.
Kurulum sırasında Rules Engine matematiğini kontrol eder.
"""

from app.rules_engine import (
    parse_gg_command,
    simulate_partial_sale,
    apply_shadow_accounting,
    calculate_daily_limit,
    get_month_remaining_days,
    turkish_date,
)
from datetime import date

print("=" * 60)
print("RULES ENGINE DOGRULAMA TESTI")
print("=" * 60)

# Test 1: gg parser - üç format
print("\n[1] gg parser:")
print("  ", parse_gg_command("gg 50 yemek"))
print("  ", parse_gg_command("gg nakit 120 ulasim"))
print("  ", parse_gg_command("gg kart 199.90 market"))
print("  ", parse_gg_command("gg kart 250,75 fatura"))  # virgüllü ondalık

# Test 2: TLY satış matematiği
print("\n[2] TLY 4 lot satis simulasyonu:")
sim = simulate_partial_sale(
    lot_count=10,
    cost_per_lot=3616.80,
    current_price=4929.56,
    lots_to_sell=4,
)
print(f"   Satis tutari    : {sim['satis_tutari']:>12,.2f} TL  (beklenen 19.718,24)")
print(f"   Brut kar        : {sim['brut_kar']:>12,.2f} TL")
print(f"   Stopaj (%17.5)  : {sim['stopaj']:>12,.2f} TL")
print(f"   Net eline gecen : {sim['net_eline_gecen']:>12,.2f} TL")
print(f"   Kalan lot       : {sim['kalan_lot']:>12} lot")

# Test 3: Gölge Muhasebe (Reel Bütçe)
print("\n[3] Reel Butce (Golge Muhasebe MC4):")
reel = apply_shadow_accounting(
    cash=4812.00,
    expected_income=8458.00,
    card_debt=11822.66,
)
print(f"   Nakit + Beklenen - Kart Borcu = {reel:,.2f} TL")
print(f"   (4.812 + 8.458 - 11.822,66 = 1.447,34 olmali)")

# Test 4: Günlük limit
print("\n[4] Gunluk limit:")
today = date.today()
days = get_month_remaining_days(today)
limit = calculate_daily_limit(reel, days)
print(f"   Bugun           : {turkish_date(today)}")
print(f"   Ay sonuna kalan : {days} gun")
print(f"   Gunluk limit    : {limit:,.2f} TL")

print("\n" + "=" * 60)
print("TUM TESTLER TAMAMLANDI")
print("=" * 60)