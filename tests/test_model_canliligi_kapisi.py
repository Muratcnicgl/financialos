"""
BUG #369 KAPISI — SABİT MODEL KİMLİĞİ ÜÇ KEZ SESSİZCE ÇÜRÜDÜ.

Ölçülen zaman çizelgesi:
    ~Ağustos  `meta-llama/llama-3.3-70b-instruct:free` katalogdan kalktı → istek ücretli
              sürüme yöneldi → **402 payment_required**. Aylarca "kredi yok" sanıldı;
              hesapta kredi sorunu yoktu. (BUG #315)
    27 May    Cerebras bir modeli deprecate etti; ancak canlı bir eval koşumunda görüldü.
    11 Eyl    `minimax/minimax-m3:free` katalogdan kalktı → **404**, üstelik OpenRouter
              cevabında doğrusunu söylüyordu ("use this slug instead: minimax/minimax-m3").

Üçünde de belirti aynı biçimde okundu: *"sağlayıcı bizi istemiyor."* Yanlış yerde arandı.
Ve üçünde de çürümeyi bulan şey bir kapı değil, AYLAR SONRA koşulan canlı bir eval oldu:
`data/eval_runs.jsonl` 10 Eylül koşumunda BEŞ sağlayıcı da `gecerli: false, pass_rate: 0.0`
yazdı, çünkü geçerli tek halkanın adı ölmüştü ve kimse ada sormamıştı.

Depoda `DEFAULT_MODEL`e dokunan testler zaten vardı (`test_saglayici_modeli_kapisi`,
`test_env_yorum_tuzagi_kapisi`) — ama hepsi ÇEVRİMDIŞI ve hepsi adın KULLANILDIĞINI
doğruluyor, VAR OLDUĞUNU değil. Ölçülmeyen şey, sessizce çürüyen şeydir.

BU KAPI DÖRT AYRI ŞEYİ ÖLÇER, ÇÜNKÜ DÖRDÜ AYRI YÖNDE BOZULUR:
  1. Çürümüş adı ÇÜRÜMÜŞ görüyor mu?          (körlük — arızanın kendisi)
  2. Yaşayan adda SUSUYOR mu?                  (gürültü → okunmayan uyarı, L22)
  3. Ağ yokken çürüme UYDURMUYOR mu?           (sahte kırmızı → `--no-verify` alışkanlığı)
  4. Hook onu ÇAĞIRIYOR mu?                    (ölü araç — BUG #328'in dersi)
Dördüncüsü olmadan ilk üçü bir vaattir: araç var olup çağrılmazsa arıza aynen tekrarlar.

BEŞİNCİSİ, DENETLEYİCİNİN KENDİSİNİ DENETLER: sağlayıcı listesi ELLE yazılmış olmamalı.
Elle tutulan bir liste, koruduğu şeyle birlikte bayatlar (L79) — yeni bir sağlayıcı
eklenir, listeye yazılmaz ve kapı sessizce onu hiç sormaz.
"""
from __future__ import annotations

from pathlib import Path

from scripts.model_canliligi import _oneri, etkin_modeller, rapor

KOK = Path(__file__).resolve().parent.parent
HOOK = KOK / ".githooks" / "pre-commit"


# ── 1. KÖRLÜK ────────────────────────────────────────────────────────────────
def test_katalogda_OLMAYAN_ad_CURUMUS_sayilir():
    """Arızanın ta kendisi: `minimax/minimax-m3:free` katalogdan kalkmıştı."""
    satirlar, curuyen = rapor(
        [("OPENROUTER", "minimax/minimax-m3:free")],
        {"minimax/minimax-m3", "google/gemma-4-31b-it:free"},
    )
    assert len(curuyen) == 1, "çürümüş ad fark edilmedi — kapı kör"
    onek, model, oneri = curuyen[0]
    assert (onek, model) == ("OPENROUTER", "minimax/minimax-m3:free")
    assert oneri == "minimax/minimax-m3", "sağlayıcının söylediği doğru ad önerilmedi"
    assert "ÇÜRÜMÜŞ" in satirlar[0]


# ── 2. GÜRÜLTÜ ───────────────────────────────────────────────────────────────
def test_YASAYAN_ad_curume_URETMEZ():
    """Yaşayan bir adda konuşan kapı, okunmayan bir kapıya dönüşür (L22)."""
    satirlar, curuyen = rapor(
        [("OPENROUTER", "minimax/minimax-m3")],
        {"minimax/minimax-m3"},
    )
    assert curuyen == []
    assert "VAR" in satirlar[0]


# ── 3. SAHTE KIRMIZI ─────────────────────────────────────────────────────────
def test_AG_YOKKEN_curume_UYDURULMAZ():
    """
    `katalog is None` = ÖLÇÜLEMEDİ. Bilinmeyeni çürüme saymak, ağsız makinede kapıyı
    yalancı yapar — ve yalancı bir kapının bedeli, hiç olmayan bir kapıdan yüksektir:
    ilk sahte kırmızıdan sonra operatör onu ciddiye almayı bırakır (L45 + L22).
    """
    satirlar, curuyen = rapor(
        [("OPENROUTER", "minimax/minimax-m3:free")], None, "URLError",
    )
    assert curuyen == [], "ağ yokluğu ÇÜRÜME sanıldı — sahte kırmızı"
    assert "ÖLÇÜLEMEDİ" in satirlar[0]
    assert "URLError" in satirlar[0], "neden ölçülemediği boş geçilemez"


def test_OLCULEMEYEN_saglayici_GECTI_yazmaz():
    """
    Katalog ucu 403/401 dönen dört sağlayıcı için "VAR" yazmak, kapsamı olduğundan
    geniş göstermek olurdu. Bir aracın kapsamı, KAPSAMADIĞINI söylediği kadar dürüsttür.
    """
    satirlar, curuyen = rapor([("GROQ", "openai/gpt-oss-120b")], set())
    assert curuyen == []
    assert "ÖLÇÜLEMEDİ" in satirlar[0]
    assert "VAR" not in satirlar[0].replace("ÖLÇÜLEMEDİ", "")


# ── 4. ÖLÜ ARAÇ ──────────────────────────────────────────────────────────────
def _hook_komut_satirlari(ad: str) -> list[str]:
    """Hook'ta `ad`ı GEÇEN ÇAĞRI satırları — yorumlar elenir.

    BUG #370'in dersi burada peşinen uygulanıyor: kardeş kapı (`test_canli_durum_kapisi`)
    adı geçen HER satırı çağrı sayıyordu ve hook'a yazılan bir GEREKÇE cümlesi onu
    kırmızıya düşürdü. `#` ile başlayan satır kabukta hiç çalışmaz; commit'i düşürmesi
    de mümkün değildir, dolayısıyla kapının konusu değildir.
    """
    metin = HOOK.read_text(encoding="utf-8")
    return [s for s in metin.splitlines()
            if ad in s and not s.lstrip().startswith("#")]


def test_HOOK_model_canliligini_CAGIRIYOR():
    """Kapının çekirdeği: araç var olup çağrılmazsa üç çürüme de aynen tekrarlar."""
    assert _hook_komut_satirlari("model_canliligi"), (
        "pre-commit model adını hiç sormuyor — araç ölü "
        "(yalnız yorumda anılmak çağrı değildir)"
    )


def test_HOOK_COMMITI_ENGELLEMEZ():
    """
    Bilinçli sınır: bu bir KAPI değil UYARIDIR. Araç AĞA ÇIKAR; ağsız bir makinede
    commit'i düşürmesi, ölçtüğü şeyi değil bağlantıyı ölçmek olurdu — ve ilk sahte
    kırmızıdan sonra operatör `--no-verify` alışkanlığı edinir, yani kapı yalnız
    kendini değil KOMŞULARINI da kör eder.
    """
    for s in _hook_komut_satirlari("model_canliligi"):
        assert "|| true" in s, f"çağrı commit'i düşürebilir: {s.strip()}"
        assert "--sessiz" in s, f"ad sağlamken de konuşuyor (gürültü): {s.strip()}"


# ── 5. DENETLEYİCİYİ DENETLE ─────────────────────────────────────────────────
def test_saglayici_listesi_ELLE_YAZILMAZ_koddan_TURETILIR():
    """
    L79: bir denetleyiciyi bayatlamaktan koruyan şey disiplin değil, TÜRETİLMİŞ olmasıdır.
    `etkin_modeller()` sağlayıcıları `SAGLAYICI_ONEKLERI` + `LLMProvider` alt sınıf
    ağacından üretir. Elle bir beyaz liste tutulsaydı, yeni bir sağlayıcı eklendiğinde
    kapı onu SESSİZCE hiç sormazdı — koruduğu şeyle birlikte çürürdü.
    """
    from app.coach import SAGLAYICI_ONEKLERI

    onekler = [o for o, _ in etkin_modeller()]
    assert set(onekler) == set(SAGLAYICI_ONEKLERI), (
        "etkin_modeller() sağlayıcı kümesi SAGLAYICI_ONEKLERI'nden ayrıştı — "
        f"eksik: {set(SAGLAYICI_ONEKLERI) - set(onekler)}, "
        f"fazla: {set(onekler) - set(SAGLAYICI_ONEKLERI)}"
    )
    assert len(onekler) == len(set(onekler)), "aynı sağlayıcı iki kez sayıldı"


def test_ENV_ezmesi_denetlenen_addir(monkeypatch):
    """
    Denetlenen şey, GERÇEKTEN KOŞACAK addır. `.env`de bayat bir `OPENROUTER_MODEL`
    varken sınıfın `DEFAULT_MODEL`ine bakan bir kapı yeşil kalır ve tam da BUG #317'nin
    yaptığını yapar: yanlış ad sağlayıcıya gider, arıza "kota" gibi okunur.
    """
    monkeypatch.setenv("OPENROUTER_MODEL", "uydurma/olmayan-model:free")
    model = dict(etkin_modeller())["OPENROUTER"]
    assert model == "uydurma/olmayan-model:free", "env ezmesi denetlenmiyor"


# ── ÖNERİ ÜRETİMİ ────────────────────────────────────────────────────────────
def test_free_dusunce_UCRETLI_hali_onerilir():
    """BUG #315 ve #369'da olan tam olarak buydu: `:free` kalktı, ücretlisi kaldı."""
    assert _oneri({"minimax/minimax-m3"}, "minimax/minimax-m3:free") == "minimax/minimax-m3"


def test_karsiligi_YOKSA_uydurulmaz():
    """Boş öneri, yanlış öneriden iyidir — uydurulmuş bir ad yeni bir çürümedir."""
    assert _oneri({"baska/model"}, "kalkmis/model:free") == ""
