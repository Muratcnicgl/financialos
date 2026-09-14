"""
LLM-032 (BUG #500): 429'daki bekleme süresi okunur — kısaysa aynı sağlayıcıda beklenir.

Ölçüm (14 Eyl 2026): kota/hız hatasında zincir hemen sonraki sağlayıcıya düşüyordu; sağlayıcının
söylediği saniye (`Retry-After` başlığı, "try again in 1.2s") hiç okunmuyordu. Kilitlenen:
  1. süre yapıdan (yanıt başlığı) ve metinden (s/ms) çıkarılır; yoksa None,
  2. kısa süre (≤ tavan) → aynı fonksiyon bir kez daha çağrılır (bekleme gerçek uyku ile),
  3. uzun süre ya da bilinmeyen → eskisi gibi hemen yükselir (fallback'e düşer),
  4. tavan env ile ayarlanır (`LLM_RETRY_AFTER_TAVAN_SN`).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app import coach
from app.provider_errors import retry_after_saniye, retry_after_tavani_sn


class _Kota(Exception):
    status_code = 429


def test_sure_basliktan_ve_metinden_okunur():
    e = _Kota("rate limit"); e.response = SimpleNamespace(headers={"retry-after": "2"})
    assert retry_after_saniye(e) == 2.0
    assert retry_after_saniye(_Kota("Rate limit reached. Please try again in 1.234s.")) == pytest.approx(1.234)
    assert retry_after_saniye(_Kota("quota exceeded, retry after 750ms")) == pytest.approx(0.75)
    assert retry_after_saniye(_Kota("429 too many requests")) is None
    e2 = _Kota("x"); e2.response = SimpleNamespace(headers={"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})
    assert retry_after_saniye(e2) is None


def test_kisa_sure_ayni_saglayicida_bir_kez_beklenir(monkeypatch):
    uykular = []
    monkeypatch.setattr(coach.time, "sleep", lambda s: uykular.append(s))
    cagri = {"n": 0}

    def fn():
        cagri["n"] += 1
        if cagri["n"] == 1:
            raise _Kota("Please try again in 1.5s")
        return "tamam"

    assert coach._call_with_retry(fn) == "tamam"
    assert cagri["n"] == 2 and uykular == [1.5]


def test_uzun_ya_da_bilinmeyen_sure_hemen_yukselir(monkeypatch):
    monkeypatch.setattr(coach.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("beklenmemeli")))
    for mesaj in ("Please try again in 42s", "429 too many requests"):
        cagri = {"n": 0}

        def fn(_mesaj=mesaj, _cagri=cagri):
            _cagri["n"] += 1
            raise _Kota(_mesaj)

        with pytest.raises(_Kota):
            coach._call_with_retry(fn)
        assert cagri["n"] == 1, mesaj


def test_tavan_env_ile_ayarlanir(monkeypatch):
    assert retry_after_tavani_sn() == 5.0
    monkeypatch.setenv("LLM_RETRY_AFTER_TAVAN_SN", "0.5")
    assert retry_after_tavani_sn() == 0.5
    monkeypatch.setenv("LLM_RETRY_AFTER_TAVAN_SN", "bozuk")
    assert retry_after_tavani_sn() == 5.0
