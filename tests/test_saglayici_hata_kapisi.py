"""
BUG #269 — SAĞLAYICI HATA SINIFLANDIRMASI SAYININ RAKAMLARINA BAKIYORDU (LLM-012 + LLM-011).

ÖLÇÜM (8 Ağu 2026, düzeltme ÖNCESİ — 10 gerçekçi sağlayıcı hata metni): **3/10 yanlış**

| Hata metni | Doğrusu | Ölçülen |
|---|---|---|
| `The input token count (8504) exceeds the maximum...` | kalıcı/çok-büyük | **geçici** |
| `500 Internal error. request_id=req_8429fa1c`          | geçici           | **kota**   |
| `Latency budget exceeded: upstream took 4290 ms`       | kalıcı           | **kota**   |

Üçü de aynı kökten: `"504"` **8504**'ün, `"429"` ise **4290** ve **req_8429fa1c**'in içinde
geçiyor — yani fallback zincirinin kararını hatayla ilgisi olmayan bir sayının rakamları
veriyordu.

En ağırı birincisi: token limitini aşan istek KALICI bir hatadır (aynı prompt her seferinde
aynı hatayı verir), ama "geçici" sayıldığı için `_call_with_retry` onu 1sn + 2sn bekleyerek
üç kez deniyor ve `_oversized_providers` devre kesicisi HİÇ açılmıyordu: sağlayıcı her koç
isteğinde yeniden deneniyor, her denemede kullanıcının LLM kotası yazılıyordu.

Bu kapı sınıflandırmayı ölçer (her iki yön), sayı-bağışıklığını kaynaktan türetilen bir
drift kilidiyle kilitler ve geri çekilmenin jitter'lı olduğunu doğrular (LLM-011).
"""
from __future__ import annotations

import re

import pytest

from app import provider_errors as pe
from app.coach import _is_quota_exceeded, _is_request_too_large, _is_retryable_error
from app.provider_errors import (
    GECICI, ISTEK_COK_BUYUK, KALICI, KOTA, bekleme_suresi, siniflandir,
)


class SahteHata(Exception):
    def __init__(self, msg, status_code=None):
        super().__init__(msg)
        if status_code is not None:
            self.status_code = status_code


# ============================================================
# 1) ÖLÇÜLEN KORPUS
# ============================================================

KORPUS = [
    ("429 RESOURCE_EXHAUSTED. Quota exceeded for quota metric 'generate_content'", 429, KOTA),
    ("Error code: 413 - {'error': {'message': 'Request too large for model `llama-3.3-70b` "
     "on tokens per minute (TPM): Limit 8000, Requested 8429'}}", 413, ISTEK_COK_BUYUK),
    ("400 INVALID_ARGUMENT: The input token count (8504) exceeds the maximum number of "
     "tokens allowed (8192).", 400, ISTEK_COK_BUYUK),
    ("503 Service Unavailable: model overloaded, please retry", 503, GECICI),
    ("500 Internal error encountered. request_id=req_8429fa1c", 500, GECICI),
    ("504 Gateway Timeout", 504, GECICI),
    ("401 Unauthorized: invalid API key", 401, KALICI),
    ("400 Bad Request: tool 'propose_action' has invalid schema", 400, KALICI),
    ("Latency budget exceeded: upstream took 4290 ms", None, KALICI),
    ("insufficient_quota: your credit balance is too low", 402, KOTA),
]


@pytest.mark.parametrize("metin,kod,beklenen", KORPUS)
def test_siniflandirma_korpusu(metin, kod, beklenen):
    assert siniflandir(SahteHata(metin, kod)).sinif == beklenen, metin


@pytest.mark.parametrize("metin,kod,beklenen", KORPUS)
def test_geriye_uyumlu_yuzey_tutarli(metin, kod, beklenen):
    """`coach.py`'nin dışa açtığı üç ad, sınıflandırmayla çelişemez."""
    e = SahteHata(metin, kod)
    assert _is_quota_exceeded(e) is (beklenen == KOTA)
    assert _is_retryable_error(e) is (beklenen == GECICI)
    assert _is_request_too_large(e) is (beklenen == ISTEK_COK_BUYUK)


# ============================================================
# 2) SAYI BAĞIŞIKLIĞI — kararı ilgisiz bir sayının rakamları veremez
# ============================================================

@pytest.mark.parametrize("gomulu", [
    "request_id=req_8429fa1c", "took 4290 ms", "trace 15031", "latency 5040ms",
    "user 84020", "8504 tokens", "id=1429", "seq 5029",
])
def test_ilgisiz_sayilar_kota_ya_da_gecici_uretmez(gomulu):
    """Düzeltme öncesi bu satırların yarısı KOTA, yarısı GEÇİCİ üretiyordu."""
    e = SahteHata(f"Something went wrong ({gomulu})")
    s = siniflandir(e)
    assert s.sinif == KALICI, f"{gomulu} -> {s}"


def test_gercek_kod_hala_calisir():
    """Sayı bağışıklığı, GERÇEK durum kodunu görmezden gelmek demek değildir."""
    assert siniflandir(SahteHata("boom", 503)).sinif == GECICI
    assert siniflandir(SahteHata("boom", 429)).sinif == KOTA
    assert siniflandir(SahteHata("boom", 413)).sinif == ISTEK_COK_BUYUK
    assert siniflandir(SahteHata("529 overloaded")).sinif == GECICI


def test_kod_yapidan_okunur_metinden_degil():
    """Yapı varsa metindeki başka bir sayı kararı değiştiremez."""
    e = SahteHata("upstream 504 gateway mentioned in passing", 401)
    assert siniflandir(e).durum_kodu == 401


# ============================================================
# 3) ÖNCELİK SIRASI — KALICI > KOTA > GEÇİCİ
# ============================================================

def test_cok_buyuk_kotayi_yener():
    """Groq'un 413'ü 'Limit 8000, Requested 8429' der; kalıcı olan kazanmalı —
    aksi hâlde devre kesici açılmaz ve sağlayıcı her istekte yeniden denenir."""
    e = SahteHata("Request too large ... rate limit reached, Requested 8429", 413)
    s = siniflandir(e)
    assert s.sinif == ISTEK_COK_BUYUK
    assert s.kalici_kara_liste is True


def test_kota_geciciyi_yener():
    e = SahteHata("RESOURCE_EXHAUSTED: service temporarily unavailable")
    assert siniflandir(e).sinif == KOTA


def test_karar_bayraklari_tutarli():
    for _metin, _kod, beklenen in KORPUS:
        s = siniflandir(SahteHata(_metin, _kod))
        assert s.tekrar_denenir is (beklenen == GECICI)
        assert s.saglayici_atlanir is (beklenen in (KOTA, ISTEK_COK_BUYUK))
        assert s.kalici_kara_liste is (beklenen == ISTEK_COK_BUYUK)
        assert s.gerekce, "gerekce bos olamaz (log/trace okunabilirligi)"


# ============================================================
# 4) DRIFT KİLİDİ — desenler ÇIPLAK SAYI içeremez (kaynaktan türetilir, L27)
# ============================================================

_CIPLAK_SAYI = re.compile(r"(?<!\\b)(?<!\d)\d{3}(?!\d)")


def test_metin_desenleri_ciplak_sayi_icermez():
    """Bir desene `429` yazmak, `4290` ve `req_8429fa1c` ile eşleşmek demektir —
    defektin kökü buydu. Kapı desen kaynağını gezerek ölçer, liste taşımaz."""
    assert len(pe.METIN_DESENLERI) >= 3, "kapsam tabani coktu"
    kirik = {d.pattern for d in pe.METIN_DESENLERI if _CIPLAK_SAYI.search(d.pattern)}
    assert not kirik, f"desende ciplak sayi (alt-dizi tuzagi): {kirik}"


def test_kod_desenine_giden_tek_yol():
    """Durum kodu YALNIZ başta ya da açık etikette okunur — gövdedeki sayı değil."""
    assert pe.durum_kodu(SahteHata("429 quota")) == 429
    assert pe.durum_kodu(SahteHata("Error code: 413 - ...")) == 413
    assert pe.durum_kodu(SahteHata("'code': 429, 'message': ...")) == 429
    assert pe.durum_kodu(SahteHata("took 4290 ms and 504 bytes")) is None


# ============================================================
# 5) GERİ ÇEKİLME — TAM JITTER (LLM-011)
# ============================================================

def test_bekleme_jitterli_ve_tavanli():
    """Sabit üstel bekleme, aynı anda düşen istekleri AYNI anda uyandırıyordu."""
    # rastgeleliği enjekte et: üst sınır davranışı deterministik ölçülsün
    ust = bekleme_suresi(3, taban=1.0, rastgele=lambda a, b: b)
    alt = bekleme_suresi(3, taban=1.0, rastgele=lambda a, b: a)
    assert ust == 4.0 and alt == 0.0, (alt, ust)
    assert bekleme_suresi(99, taban=1.0, rastgele=lambda a, b: b) == pe.BEKLEME_TAVANI


def test_bekleme_gercek_rastgelelikle_araliktadir():
    for deneme in (1, 2, 3):
        for _ in range(20):
            v = bekleme_suresi(deneme, taban=1.0)
            assert 0.0 <= v <= min(pe.BEKLEME_TAVANI, 2 ** (deneme - 1))


def test_bekleme_ayni_deger_donmez():
    """Jitter yoksa bu koşum tek bir değer üretir (mutasyon bu testi kırar)."""
    degerler = {round(bekleme_suresi(3, taban=1.0), 6) for _ in range(40)}
    assert len(degerler) > 1, "bekleme sabit — jitter yok"


# ============================================================
# 6) ZİNCİR DAVRANIŞI — kalıcı hata sağlayıcıyı KARA LİSTEYE alır
# ============================================================

def test_token_limiti_hatasi_devre_kesiciyi_acar():
    """Düzeltme öncesi bu hata 'geçici' sayılıyor, devre kesici hiç açılmıyordu."""
    from app.coach import FallbackProvider, LLMResponse

    class Dusen:
        NAME = "Dusen"
        model = "m"

        def chat(self, system_prompt, messages, tools=None):
            raise SahteHata("400 INVALID_ARGUMENT: The input token count (8504) exceeds "
                            "the maximum number of tokens allowed (8192).", 400)

    class Calisan:
        NAME = "Calisan"
        model = "m"

        def chat(self, system_prompt, messages, tools=None):
            return LLMResponse(text="ok", tool_calls=[], usage={},
                               provider_used="calisan", model_name="m")

    zincir = FallbackProvider([Dusen(), Calisan()])
    assert zincir.chat("s", [{"role": "user", "content": "x"}], None).text == "ok"
    assert "Dusen" in zincir._oversized_providers, "kalici hata kara listeye alinmadi"
