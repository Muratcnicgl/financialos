"""
evaluate_credit_card_strategy (MC3) — Ziraat kart kesim/ödeme döngüsü karakterizasyonu.
Bu fonksiyon test edilmemişti; Murat'ın gerçek kartı (kesim=2, son ödeme=12) için üç durumu
ve türev alanları (kullanım oranı, kalan limit, ay-sonu clamp) kilitler.

Tasarım notu: kesimden SONRAKİ tüm günler vade_avantaji (float mantığı); son ödeme hazırlığı
ayrı olarak _collect_upcoming_reminders (BUG #096) tarafından uyarılır. Bu davranış bilinçlidir.
"""
from __future__ import annotations

from datetime import date

from app.rules_engine import evaluate_credit_card_strategy as evaluate


# Murat'ın Ziraat kartı
KESIM = 2       # statement_day
ODEME = 12      # payment_day
BORC = 11976.0
LIMIT = 12000.0


def _s(day, **kw):
    return evaluate(date(2026, 5, day),
                    statement_day=kw.get("kesim", KESIM),
                    payment_day=kw.get("odeme", ODEME),
                    current_debt=kw.get("borc", BORC),
                    credit_limit=kw.get("limit", LIMIT))


def test_gun1_kesim_dikkat():
    r = _s(1)
    assert r["durum"] == "kesim_dikkat"
    assert "Kesim tarihine" in r["mesaj"]


def test_gun2_odeme_dikkat():
    """Kesim günü (2): ekstre kesildi, son ödemeye hazırlık penceresi."""
    r = _s(2)
    assert r["durum"] == "odeme_dikkat"
    assert "Son ödeme" in r["mesaj"]


def test_kesimden_sonra_vade_avantaji():
    """Kesimden sonraki her gün (3..ay sonu) float avantajı — son ödeme günü dâhil."""
    for d in (3, 5, 10, 12, 13, 20, 28):
        r = _s(d)
        assert r["durum"] == "vade_avantaji", f"gün {d} vade_avantaji bekleniyordu"
        assert "sonraki ekstre" in r["mesaj"]


def test_kullanim_orani_ve_kalan_limit():
    r = _s(5)
    assert r["kullanim_orani"] == round(BORC / LIMIT * 100, 1)   # ~99.8
    assert r["kalan_limit"] == round(LIMIT - BORC, 2)            # 24.0
    assert r["mevcut_borc"] == BORC


def test_sifir_limit_bolme_hatasi_yok():
    r = _s(5, limit=0.0)
    assert r["kullanim_orani"] == 0.0     # ZeroDivision guard


def test_ay_sonu_clamp_kesim_odeme_gunu():
    """statement_day/payment_day ay uzunluğunu aşarsa kısa ayda clamp'lenir (kesim_gunu)."""
    # Şubat 2026 (28 gün): kesim=31 -> 28, ödeme=30 -> 28
    r = evaluate(date(2026, 2, 15), statement_day=31, payment_day=30,
                 current_debt=1000.0, credit_limit=5000.0)
    assert r["kesim_gunu"] == 28
    assert r["odeme_gunu"] == 28


def test_donen_anahtarlar_tam():
    r = _s(5)
    for k in ("durum", "kesim_gunu", "odeme_gunu", "gun_to_kesim", "gun_to_odeme",
              "kullanim_orani", "kalan_limit", "mevcut_borc", "mesaj"):
        assert k in r
