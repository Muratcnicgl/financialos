"""
FEAT-032: Koç için CANLI döviz kuru (USD/TRY, EUR/TRY) — keyless.

Koçun "dolar kuru kaç?" sorusunda UYDURMAMASI için gerçek veri sağlar (ADR-001 grounding).
Kaynak: open.er-api.com (ücretsiz, API-key GEREKMEZ — EVDS'in aksine). Kapsam SCOPED: yalnız
döviz (açık web araması DEĞİL → koç "finansal danışman" kalır, egemenlik korunur).

Graceful degradation (proje deseni): ağ/servis/parse hatası → None. Koç None'da "canlı veri
alamadım" der, UYDURMAZ. 30 dk in-process TTL cache (döviz gün içi değişir; kaynağı hammer'lamaz).

BUG #211 (H16 / P8) — SON BİLİNEN DEĞER + BAYAT İŞARETİ:
Eski davranışta sağlayıcı düştüğü an kur bilgisi TAMAMEN kayboluyordu: 31 dakika önce
başarıyla çekilmiş bir kur elde dururken koç "çekemedim, bankana bak" diyordu. Ücretsiz
sağlayıcının birkaç saatlik kesintisi rutindir; bu süre boyunca ürün kur konusunda tümüyle
sessizleşiyordu — kullanıcı için "sistem bozuk" demek. Diğer uç (bayat değeri sessizce
"şu anki kur" diye sunmak) daha da kötüdür: kullanıcı eski kura göre karar verir.

Çözüm iki-uçtan kaçınır: son BAŞARILI değer saklanır ve **açıkça bayat işaretlenerek**
(`bayat=True`, `yas_dakika`) döner; koç onu "X saat önceki kur" diye verir, "şu anki" DEMEZ.
`_BAYAT_TAVAN_DK` üstündeki değer hiç dönmez (o yaştan sonra yanıltıcılık faydayı geçer).
"""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

_URL = "https://open.er-api.com/v6/latest/USD"
_TIMEOUT = 8
_TTL = 30 * 60  # 30 dk — bu yaşa kadar TAZE sayılır (ağa gidilmez)
_BAYAT_TAVAN_DK = 12 * 60  # BUG #211: 12 saatten eski değer artık sunulmaz
_CACHE: Dict[str, tuple] = {}  # {"fx": (data, epoch_ts)} — son BAŞARILI çekim


def _bayat_kopya(now: float) -> Optional[Dict]:
    """Son başarılı değeri BAYAT işaretiyle döndür (tavanı aşmışsa None)."""
    cached = _CACHE.get("fx")
    if not cached:
        return None
    data, ts = cached
    yas_dk = int((now - ts) / 60)
    if yas_dk > _BAYAT_TAVAN_DK:
        logger.warning("[fx_live] son bilinen kur çok eski (%s dk) — sunulmuyor", yas_dk)
        return None
    kopya = dict(data)
    kopya["bayat"] = True
    kopya["yas_dakika"] = yas_dk
    return kopya


def get_live_fx() -> Optional[Dict]:
    """Canlı döviz döner ya da None (uydurma değil).

    Dönüş: {"usd_try": Decimal, "eur_try": Decimal, "guncelleme": str, "kaynak": str,
            "bayat": bool, "yas_dakika": int}
    open.er-api base=USD verir: rates.TRY = 1 USD kaç TL; rates.EUR = 1 USD kaç EUR
    → EUR/TRY = rates.TRY / rates.EUR.
    """
    now = time.time()
    cached = _CACHE.get("fx")
    if cached and now - cached[1] < _TTL:
        return cached[0]
    try:
        resp = requests.get(_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") != "success":
            logger.warning("[fx_live] beklenmeyen result=%s", payload.get("result"))
            return _bayat_kopya(now)          # BUG #211: elde son bilinen değer varsa sus(ma)
        rates = payload.get("rates") or {}
        usd_try = rates.get("TRY")
        usd_eur = rates.get("EUR")
        if not usd_try or not usd_eur:
            logger.warning("[fx_live] TRY/EUR oranı eksik")
            return _bayat_kopya(now)
        data = {
            "usd_try": round(Decimal(str(usd_try)), 4),
            "eur_try": round(Decimal(str(usd_try)) / Decimal(str(usd_eur)), 4),
            "guncelleme": payload.get("time_last_update_utc", "?"),
            "kaynak": "open.er-api.com",
            "bayat": False,
            "yas_dakika": 0,
        }
        _CACHE["fx"] = (data, now)
        return data
    except Exception as e:  # noqa: BLE001 — dış API; grounding gereği hata→bayat/None (uydurma yok)
        logger.warning("[fx_live] canlı döviz alınamadı: %s", e)
        return _bayat_kopya(now)
