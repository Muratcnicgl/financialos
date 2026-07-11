"""
Fiyat tazelik gösterim mantığı (cockpit "fiyat eski" rozeti) — deterministik.
is_price_stale / get_price_age_text / get_tefas_url.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.fund_tracker import is_price_stale, get_price_age_text, get_tefas_url


def _ago(**kw):
    return datetime.utcnow() - timedelta(**kw)


def test_is_price_stale_none_eski():
    assert is_price_stale(None) is True


def test_is_price_stale_taze_ve_eski():
    assert is_price_stale(_ago(hours=1)) is False           # 1 saat < 24
    assert is_price_stale(_ago(hours=30)) is True            # 30 saat > 24
    assert is_price_stale(_ago(hours=1), threshold_hours=0) is True   # esik 0 → her sey eski


def test_price_age_text_none():
    assert get_price_age_text(None) == "henüz girilmedi"


def test_price_age_text_az_once():
    assert get_price_age_text(_ago(seconds=10)) == "az önce"


def test_price_age_text_dakika():
    assert get_price_age_text(_ago(minutes=15)) == "15 dakika önce"


def test_price_age_text_saat():
    assert get_price_age_text(_ago(hours=3)) == "3 saat önce"


def test_price_age_text_dun():
    assert get_price_age_text(_ago(hours=30)) == "dün"       # 24-48 saat


def test_price_age_text_gun():
    assert get_price_age_text(_ago(days=4)) == "4 gün önce"


def test_tefas_url_uppercase():
    assert get_tefas_url("tly") == "https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod=TLY"
