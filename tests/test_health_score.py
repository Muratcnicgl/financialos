"""
FEAT-022 — finansal sağlık skoru (calculate_health_score).
0-100 şeffaf composite; veri olmayan bileşen atlanır. Deterministik saf fonksiyon.
"""
from __future__ import annotations

from app.rules_engine import calculate_health_score


def _base(**over):
    kw = dict(reel_butce=5000.0, kart_borcu=0.0, kart_limit=10000.0, aylik_faiz=0.0,
              aylik_gelir=15000.0, runway_gun=90, crunch_var=False, zarf_asan=0, zarf_var=False)
    kw.update(over)
    return calculate_health_score(**kw)


def test_saglikli_yuksek_skor():
    r = _base()
    assert r["skor"] >= 90 and r["seviye"] == "iyi"


def test_kriz_dusuk_skor():
    # crunch + negatif bütçe + dolu kart + yüksek faiz + kısa runway
    r = _base(reel_butce=-8000.0, crunch_var=True, kart_borcu=9800.0, kart_limit=10000.0,
              aylik_faiz=4500.0, runway_gun=5)
    assert r["skor"] < 40 and r["seviye"] == "kritik"


def test_bilesenler_gorunur():
    r = _base()
    adlar = [b["ad"] for b in r["bilesenler"]]
    assert "Ödeme gücü" in adlar and "Kart sağlığı" in adlar


def test_veri_yoksa_bilesen_atlanir():
    # gelir yok → faiz yükü bileşeni yok; runway None → tampon yok; zarf yok → bütçe yok
    r = calculate_health_score(reel_butce=1000.0, kart_borcu=0.0, kart_limit=0.0,
                               aylik_faiz=0.0, aylik_gelir=0.0, runway_gun=None,
                               crunch_var=False, zarf_asan=0, zarf_var=False)
    adlar = [b["ad"] for b in r["bilesenler"]]
    assert adlar == ["Ödeme gücü"]      # yalnızca her zaman hesaplanan bileşen


def test_kart_utilizasyonu_skoru():
    # kart %99 dolu → kart sağlığı ~1
    r = _base(kart_borcu=9900.0, kart_limit=10000.0)
    kart = next(b for b in r["bilesenler"] if b["ad"] == "Kart sağlığı")
    assert kart["puan"] <= 5


def test_cockpit_saglik_skoru_alani():
    from datetime import date
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models import Base, User, Account, AccountType
    from app.rules_engine import generate_cockpit
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(e)
    s = sessionmaker(bind=e)()
    s.add(User(id=1, name="m"))
    s.add(Account(user_id=1, name="E", account_type=AccountType.cash, balance=5000.0))
    s.commit()
    c = generate_cockpit(1, date(2026, 5, 15), s)
    assert "saglik_skoru" in c
    assert 0 <= c["saglik_skoru"]["skor"] <= 100
    s.close()
