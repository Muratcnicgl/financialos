"""
`--bekle` KAPISI — "sağlayıcı cevap vermedi" ile "çok hızlı sordum" AYNI ŞEY DEĞİLDİR.

ÖLÇÜLEN DURUM (11 Eyl 2026)
---------------------------
Koç kalitesi 2 Eylül'den beri hiç geçerli ölçülememişti. Sebeplerden biri kotaydı ama
asıl tuzak daha incedir: Groq'un tavanı GÜNLÜK değil DAKİKALIKTIR (8.000 token/dk,
1.000 istek/gün). Koşucu istekleri arka arkaya atınca ikinci istek 413/429 alır,
`run_eval` bunu "llm_olu_cagri" sayar ve koşum GEÇERSİZ damgalanır — oysa kota
tükenmemiştir, yalnız HIZ aşılmıştır.

Ölçüm: beklemesiz koşumda 8 kanonik senaryodan 3'ü ölü çağrı verdi; aynı senaryolar
50 sn beklemeyle cevap verdi. Yani `--bekle`, bir konfor ayarı değil, ÖLÇÜMÜN
GEÇERLİLİK KOŞULUDUR.

BU KAPI DÖRT ŞEYİ ÖLÇER:
  1. Varsayılan (0) hiçbir şeyi değiştirmiyor mu?   (ürün yolu yavaşlamamalı)
  2. Bekleme GERÇEKTEN uygulanıyor mu?              (yoksa bayrak süstür)
  3. İLK istek beklemiyor mu?                       (gereksiz gecikme de bir kusurdur)
  4. Zincirdeki HER sağlayıcı ayrı ayrı sarılıyor mu? (FallbackProvider'ın `_raw_chat`i
     yoktur; yalnız ona bakan bir uygulama hiçbir şey sınırlamazdı — sessiz kusur)
"""
from __future__ import annotations

import scripts.eval_runner as er


class SahteSaglayici:
    """`_raw_chat` taşıyan asgari sağlayıcı — ağ yok, gerçek SDK yok."""

    NAME = "Sahte"

    def __init__(self):
        self.cagri = 0

    def _raw_chat(self, *args, **kwargs):
        self.cagri += 1
        return f"cevap-{self.cagri}"


class SahteZincir:
    """`FallbackProvider` gibi: kendi `_raw_chat`i YOK, alt sağlayıcıları var."""

    NAME = "SahteZincir"

    def __init__(self, altlar):
        self.providers = altlar


class _Saat:
    """Beklemeyi GERÇEKTEN uyumadan ölçer: `sleep` çağrılarını kaydeder ve saati ilerletir."""

    def __init__(self, baslangic: float = 1000.0):
        self.simdi = baslangic
        self.uykular = []

    def monotonic(self):
        return self.simdi

    def sleep(self, sure):
        self.uykular.append(sure)
        self.simdi += sure

    def ilerlet(self, sn):
        self.simdi += sn


def _saati_tak(monkeypatch, baslangic: float = 1000.0) -> _Saat:
    saat = _Saat(baslangic)
    monkeypatch.setattr(er.time, "monotonic", saat.monotonic)
    monkeypatch.setattr(er.time, "sleep", saat.sleep)
    return saat


# ── 1. VARSAYILAN HİÇBİR ŞEYİ DEĞİŞTİRMEZ ────────────────────────────────────
def test_bekle_sifirken_SARMALAMA_YOK(monkeypatch):
    """Ürünün ve varsayılan koşumun yolu yavaşlamamalı; bayrak verilmedikçe kod aynı."""
    saat = _saati_tak(monkeypatch)
    p = SahteSaglayici()
    onceki = p.__dict__.get("_raw_chat")
    er.hiz_sinirla(p, 0.0)
    assert p.__dict__.get("_raw_chat") is onceki, "bekle=0 iken sarmalama yapıldı"
    p._raw_chat(); p._raw_chat()
    assert saat.uykular == [], "bekle=0 iken uyunmuş"


# ── 2 + 3. BEKLEME GERÇEK, AMA İLK İSTEK BEKLEMEZ ────────────────────────────
def test_ILK_istek_beklemez_IKINCISI_bekler(monkeypatch):
    saat = _saati_tak(monkeypatch)
    p = SahteSaglayici()
    er.hiz_sinirla(p, 50.0)

    p._raw_chat()
    assert saat.uykular == [], "ilk istek gereksiz yere bekletildi"

    p._raw_chat()
    assert saat.uykular == [50.0], f"ikinci istek beklemedi: {saat.uykular}"
    assert p.cagri == 2, "sarmalayıcı asıl çağrıyı yutmuş"


def test_SAAT_SIFIRA_YAKINKEN_de_ilk_istek_beklemez(monkeypatch):
    """
    MUTASYON BULGUSU (11 Eyl 2026): `if son[0] and gecen < bekle` içindeki `son[0] and`
    korumasını silmek, yukarıdaki testi KIRMADI — çünkü sahte saat 1000'den başlıyordu ve
    `1000 - 0 = 1000 > 50` olduğu için ilk çağrı zaten uyumuyordu. Yani test, korumanın
    VARLIĞINI değil sahte saatin BAŞLANGIÇ DEĞERİNİ ölçüyordu.

    Bu teorik değil: `time.monotonic()` Windows'ta açılıştan beri geçen süredir ve makine
    yeni açılmışsa KÜÇÜKTÜR. O durumda koruma olmadan ilk istek boş yere `bekle` kadar
    gecikirdi — 8 senaryoluk bir koşumda tek başına ~50 sn.

    Bu test saati kasten 1.0'a çeker: koruma silinirse KIRILIR.
    """
    saat = _saati_tak(monkeypatch, baslangic=1.0)
    p = SahteSaglayici()
    er.hiz_sinirla(p, 50.0)

    p._raw_chat()
    assert saat.uykular == [], (
        "saat sıfıra yakınken ilk istek bekletildi — `son[0] and` koruması yok"
    )


def test_ARADA_GECEN_SURE_dusulur(monkeypatch):
    """Çağrının kendisi 30 sn sürdüyse yalnız KALAN 20 sn beklenir — toplam yine 50."""
    saat = _saati_tak(monkeypatch)
    p = SahteSaglayici()
    er.hiz_sinirla(p, 50.0)

    p._raw_chat()
    saat.ilerlet(30.0)
    p._raw_chat()
    assert saat.uykular == [20.0], f"geçen süre düşülmedi: {saat.uykular}"


def test_YETERINCE_beklendiyse_HIC_uyunmaz(monkeypatch):
    saat = _saati_tak(monkeypatch)
    p = SahteSaglayici()
    er.hiz_sinirla(p, 50.0)

    p._raw_chat()
    saat.ilerlet(120.0)
    p._raw_chat()
    assert saat.uykular == [], "zaten yeterince beklenmişken uyundu"


# ── 4. ZİNCİRİN HER HALKASI SARILIR ──────────────────────────────────────────
def test_ZINCIRDE_her_alt_saglayici_AYRI_sarilir(monkeypatch):
    """
    `FallbackProvider`ın kendi `_raw_chat`i YOKTUR. Yalnız üst nesneye bakan bir uygulama
    sessizce HİÇBİR ŞEYİ sınırlamazdı — ve bu, tam da bu depodaki tekrar eden arıza
    sınıfıdır (mekanizma var, bağlanmamış).
    """
    saat = _saati_tak(monkeypatch)
    a, b = SahteSaglayici(), SahteSaglayici()
    zincir = SahteZincir([a, b])
    er.hiz_sinirla(zincir, 50.0)

    assert "_raw_chat" in a.__dict__ and "_raw_chat" in b.__dict__, "alt sağlayıcı sarılmadı"

    # Saatler AYRI: tavan HESAP başınadır, zincir başına değil.
    a._raw_chat(); b._raw_chat()
    assert saat.uykular == [], "farklı sağlayıcılar birbirini bekletti"
    a._raw_chat()
    assert saat.uykular == [50.0], "aynı sağlayıcının ikinci isteği beklemedi"


def test_RAW_CHATI_OLMAYAN_nesne_COKMEZ(monkeypatch):
    """Bir ölçüm aracı, tanımadığı bir sağlayıcı tipinde çökemez — sessizce dokunmaz."""
    _saati_tak(monkeypatch)

    class Yabanci:
        NAME = "Yabanci"

    y = Yabanci()
    assert er.hiz_sinirla(y, 50.0) is y


# ── BAYRAK GERÇEKTEN BAĞLI MI ────────────────────────────────────────────────
def test_CLI_bayragi_VAR_ve_varsayilani_SIFIR():
    """Araç var olup çağrılmazsa ölüdür: `--bekle` gerçekten ayrıştırılıyor mu?"""
    import argparse
    import inspect

    kaynak = inspect.getsource(er.main)
    assert '"--bekle"' in kaynak, "--bekle argparse'a hiç eklenmemiş"
    assert "hiz_sinirla" in inspect.getsource(er._tek_kosum), (
        "hiz_sinirla tanımlı ama koşum yolunda ÇAĞRILMIYOR — ölü mekanizma"
    )
    assert isinstance(argparse.ArgumentParser, type)  # importun kullanıldığını göster
