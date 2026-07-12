"""
Grounding check (LLM-003) birim testleri — deterministik, LLM/DB gerektirmez.
Kök vizyon: koçun söylediği her TL tutarı cockpit'e izlenebilir olmalı (varsayım/halüsinasyon yasak).
"""
from app.grounding import check_grounding, _to_float_tr


def test_tr_sayi_parse():
    assert _to_float_tr("31.342,86") == 31342.86
    assert _to_float_tr("268") == 268.0
    assert _to_float_tr("1.000") == 1000.0


def test_dogru_tutar_grounded():
    cockpit = {"kart_borcu": 42100.50, "nakit_kasa": 4276.14}
    r = check_grounding("Kart borcun 42.100,50 TL, nakit 4.276,14 TL.", cockpit)
    assert r["ok"] is True
    assert r["checked"] == 2
    assert r["unverified"] == []


def test_halusinasyon_tutar_yakalanir():
    cockpit = {"kart_borcu": 42100.50}
    r = check_grounding("Kart borcun 47.800 TL civarında.", cockpit)
    assert r["ok"] is False
    assert 47800.0 in r["unverified"]


def test_kucuk_sayi_ve_yuzde_atlanir():
    cockpit = {"daily_limit": 62.0}
    # 62 TL (min_magnitude altında) + %99.8 (TL etiketsiz) denetlenmez
    r = check_grounding("Günlük limitin 62 TL, kartın %99.8 dolu.", cockpit)
    assert r["checked"] == 0
    assert r["ok"] is True


def test_ic_ice_cockpit_degerleri_de_izlenir():
    cockpit = {"hesaplar": [{"ad": "Enpara", "bakiye": 4276.14}], "toplam": {"net": 30000.0}}
    r = check_grounding("Enpara'da 4.276,14 TL var, net değerin 30.000 TL.", cockpit)
    assert r["ok"] is True
    assert r["checked"] == 2


def test_tolerans_icinde_eslesme():
    cockpit = {"net_deger": 31342.86}
    # koç 31.343 TL yuvarlamış — tolerans içinde grounded sayılmalı
    r = check_grounding("Net değerin 31.343 TL.", cockpit)
    assert r["ok"] is True
