"""
BUG #317 KAPISI — BOŞ BİR AYARIN NOTU, AYARIN DEĞERİ OLAMAZ.

ÖLÇÜLEN DEFEKT (2 Eyl 2026): `.env`de satır `LLM_MODEL=   # bos: LLM_PROVIDER ...` idi.
python-dotenv, değer VARSA satır sonu yorumunu ayıklar (`GEMINI_MODEL=x  # not` → `x`), ama
değer BOŞSA ayıklamaz — satırın kalanını değer sayar. Sonuç:
`LLM_MODEL == "# bos: LLM_PROVIDER degistiginde yanlis modele gitmesin"`.

Zarar sessizdi ve yanlış teşhise götürdü: `LLM_PROVIDER` tek bir sağlayıcıyı adlandıran her
koşumda bu METİN model adı olarak gitti; **OpenRouter/Cerebras/Groq altın senaryo setinde
%0 aldı ve arıza "kota/erişim" gibi göründü.** Aynı sınıf BUG #315'te de yaşandı: model
adı çürüdüğünde belirti daima "sağlayıcı bizi istemiyor" biçiminde okunur.

Ve bu bir YEREL yazım hatası değildi: `.env.example`de **13 değişken** aynı biçimde
yazılmıştı — `ANTHROPIC_API_KEY` dahil. Şablonu kopyalayan herkes tuzağı da kopyalıyordu.

ÖLÇÜT NEDEN REGEX DEĞİL, GERÇEK AYRIŞTIRICI: tuzağın kaynağı python-dotenv'in davranışıdır.
Kapıyı kendi regex'imle kurarsam, dotenv yarın davranışını değiştirdiğinde kapı yanlış
yerde nöbet tutar. Ürünün okuduğu değeri, ürünün okuduğu ayrıştırıcıyla ölçüyorum (L21).

GİZLİLİK: bu testler `.env`i de tarar ama **hiçbir DEĞER yazdırmaz** — yalnız değişken ADI
raporlanır. Değer basmak, kırmızı bir CI çıktısında API anahtarını sızdırırdı.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import dotenv_values

from app.coach import _gecerli_model, saglayici_modeli

KOK = Path(__file__).resolve().parent.parent


def _yorum_tasiyan_degiskenler(yol: Path) -> list[str]:
    """Değeri `#` ile başlayan değişkenlerin ADLARI (değer ASLA döndürülmez)."""
    return sorted(ad for ad, deger in dotenv_values(yol).items()
                  if deger and deger.strip().startswith("#"))


# ---- 1) ŞABLON: kopyalayan herkes tuzağı almasın -------------------------------

def test_ornek_sablonda_hicbir_degisken_yorum_tasimiyor():
    ornek = KOK / ".env.example"
    assert ornek.is_file(), ".env.example bulunamadı — kapı kör kalır"
    ihlal = _yorum_tasiyan_degiskenler(ornek)
    assert not ihlal, (
        "`.env.example`de değeri satır sonu yorumu olan değişken(ler) var — bu şablonu "
        "kopyalayan HERKES tuzağı alır. Notu satırın ÜSTÜNE taşı:\n  " + "\n  ".join(ihlal))


def test_ornek_sablon_gercekten_taraniyor():
    """Meta-test (L11): ayrıştırma boşalırsa üstteki kapı 'her şey temiz' der."""
    degerler = dotenv_values(KOK / ".env.example")
    assert len(degerler) >= 20, f"Yalnız {len(degerler)} değişken okundu — ayrıştırma bozuk"
    assert "LLM_MODEL" in degerler


def test_kapi_tuzagi_gercekten_yakaliyor(tmp_path):
    """Kapının kendisi sınanır: tuzaklı bir şablon YAZILSA yakalanır mı?"""
    sahte = tmp_path / ".env.example"
    sahte.write_text("IYI_DEGER=abc  # bu not ayiklanir\nTUZAK=   # bu not deger olur\n",
                     encoding="utf-8")
    assert _yorum_tasiyan_degiskenler(sahte) == ["TUZAK"], (
        "Kapı tuzağı görmüyor ya da sağlam satırı yanlışlıkla suçluyor")


# ---- 2) YEREL .env: varsa o da temiz olmalı ------------------------------------

def test_yerel_env_dosyasi_temiz():
    yerel = KOK / ".env"
    if not yerel.is_file():
        pytest.skip(".env yok (CI) — şablon kapısı yeterli")
    ihlal = _yorum_tasiyan_degiskenler(yerel)
    assert not ihlal, (
        "`.env`de değeri satır sonu yorumu olan değişken(ler): " + ", ".join(ihlal)
        + " — notu satırın ÜSTÜNE taşı (değerler bilinçli olarak yazdırılmadı).")


# ---- 3) ÜRÜN SAVUNMASI: geçersiz model adı sağlayıcıya GİTMEZ ------------------
# Şablonu düzeltmek yetmez: ayarı elle yazan operatör aynı tuzağa düşebilir. Kod, kendine
# gelen değeri doğrular — ama SESSİZCE düzeltmez (sessiz düzeltme, sessiz arızanın diğer
# yüzüdür): hata seviyesinde loglar ve sağlayıcının DEFAULT_MODEL'ine düşer.

@pytest.mark.parametrize("gecerli", [
    "gemini-2.5-flash-lite", "openai/gpt-oss-120b", "claude-opus-5",
    "minimax/minimax-m3:free", "qwen2.5:7b-instruct", "gpt-oss-120b",
    "meta-llama/llama-3.3-70b-instruct:free",
])
def test_gercek_model_adlari_kabul_edilir(gecerli):
    """Kapı gerçek model adlarını reddederse ürünü kırar — asıl risk budur."""
    assert _gecerli_model(gecerli, "X_MODEL") == gecerli


@pytest.mark.parametrize("gecersiz", [
    "# bos: LLM_PROVIDER degistiginde yanlis modele gitmesin",  # ölçülen defektin ta kendisi
    "# opsiyonel (default: gemini-2.5-flash-lite)",
    "gemini 2.5 flash",          # boşluk: model adı olamaz
    "  # not",
    "-baslangicta-tire",
    "#",
])
def test_yorum_ve_bozuk_degerler_reddedilir(gecersiz):
    assert _gecerli_model(gecersiz, "X_MODEL") is None


def test_bos_deger_sessizce_none_doner_uyarmaz(caplog):
    """Boş ayar NORMALDİR (opsiyonel alan) — uyarı basmak gürültü üretir ve kapı okunmaz."""
    with caplog.at_level("ERROR"):
        assert _gecerli_model("", "X_MODEL") is None
        assert _gecerli_model("   ", "X_MODEL") is None
    assert not caplog.records


def test_gecersiz_deger_SESSIZCE_yutulmaz(caplog):
    """Asıl ders: arıza gizlendiği için yanlış teşhis edildi. Kod bir daha susmayacak."""
    with caplog.at_level("ERROR"):
        assert _gecerli_model("# not", "LLM_MODEL") is None
    assert caplog.records, "Geçersiz model adı sessizce yok sayıldı — arıza yine gizlenir"
    assert "LLM_MODEL" in caplog.text


def test_saglayici_modeli_yorum_degerini_saglayiciya_GECIRMEZ(monkeypatch):
    """Uçtan uca: ölçülen defektin birebir kurgusu."""
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LLM_MODEL", "# bos: LLM_PROVIDER degistiginde yanlis modele gitmesin")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)
    assert saglayici_modeli("OPENROUTER") is None, (
        "Yorum metni model adı olarak sağlayıcıya gidiyor — BUG #317 geri geldi")


def test_saglayici_modeli_ozel_alanda_da_dogrular(monkeypatch):
    """`<ÖNEK>_MODEL` yolu da aynı tuzağa açıktır; ikisi de aynı doğrulamadan geçer."""
    monkeypatch.setenv("GEMINI_MODEL", "# opsiyonel (default: gemini-2.5-flash-lite)")
    monkeypatch.setenv("LLM_PROVIDER", "fallback")
    assert saglayici_modeli("GEMINI") is None
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
    assert saglayici_modeli("GEMINI") == "gemini-2.5-flash-lite"


def test_env_dosyalari_kaynak_kontrolunde_degil():
    """`.env` gerçek anahtar taşır; bu kapı onu okuduğu için sızmadığı bir kez daha kilitli."""
    gitignore = (KOK / ".gitignore").read_text(encoding="utf-8")
    assert any(s.strip() in {".env", "*.env", "/.env"} for s in gitignore.splitlines()), \
        ".env `.gitignore`da değil — bu testin okuduğu dosya repoya girebilir"
    assert os.path.basename(str(KOK / ".env")) == ".env"
