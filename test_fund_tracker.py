"""
fund_tracker test — manuel mantik dogrulama.
DB ile etkilesim olmadan saf fonksiyonlari test ediyoruz.
"""

from datetime import datetime, timedelta

from app.fund_tracker import (
    is_price_stale,
    get_price_age_text,
    get_tefas_url,
    PRICE_FRESHNESS_HOURS,
)

print("=" * 60)
print("FUND TRACKER — MANUEL UI MANTIGI TESTI")
print("=" * 60)

# Test 1: Tazelik
print("\n[1] Fiyat tazelik kontrolu:")
print(f"   Esik degeri: {PRICE_FRESHNESS_HOURS} saat")

test_cases = [
    ("Henuz girilmedi", None, True),
    ("10 dakika once", datetime.utcnow() - timedelta(minutes=10), False),
    ("12 saat once",   datetime.utcnow() - timedelta(hours=12), False),
    ("23 saat once",   datetime.utcnow() - timedelta(hours=23), False),
    ("25 saat once",   datetime.utcnow() - timedelta(hours=25), True),
    ("3 gun once",     datetime.utcnow() - timedelta(days=3),   True),
]

for label, ts, expected_stale in test_cases:
    stale = is_price_stale(ts)
    age_text = get_price_age_text(ts)
    status = "✓" if stale == expected_stale else "✗"
    durum = "ESKI" if stale else "TAZE"
    print(f"   {status} {label:<20} -> {age_text:<20} ({durum})")

# Test 2: TEFAS URL üretimi
print("\n[2] TEFAS URL'leri:")
for code in ["TLY", "AAK", "tly", "aak"]:
    print(f"   {code:<5} -> {get_tefas_url(code)}")

# Test 3: Bos durum
print("\n[3] Bos durum:")
print(f"   None tarih       -> {get_price_age_text(None)}")
print(f"   None stale mi?   -> {is_price_stale(None)}")

print("\n" + "=" * 60)
print("MANUEL FIYAT MANTIGI HAZIR")
print("=" * 60)