"""
BUG #242 (denetim D25) — VERİ-İŞLEYEN ENVANTERİ KODLA GERÇEKTEN KİLİTLENİR.

Envanter dosyası kendi hakkında *"kodda tanımlı LLM sağlayıcıları ve fiyat kaynakları bu
dosyada listelenmiş olmalıdır — `tests/test_legal_docs.py` ile kilitlenir"* diyordu. Bu
iddia YANLIŞTI: kapı dört ismi (`gemini`, `groq`, `anthropic`, `ollama`) SABİT kodluyor ve
`app.coach`'u hiç okumuyordu. Sonuç: fallback zincirine 2026-07-13'te eklenen **Together AI**
ve **DeepInfra** envantere hiç girmedi, envanter 3 hafta SONRA yazıldığı halde eksik kaldı ve
test yeşil kaldı. Aynı körlük OAuth sağlayıcıları için de vardı (Google/GitHub kimlik
sağlayıcısına kullanıcı verisi gider; envanterin §4'ü *"harici kimlik sağlayıcı YOK"* diyordu).

KVKK m.10 alıcı GRUPLARININ, m.9 yurt dışı aktarımda alıcının bilinmesini ister. "Envanter
kodla kilitli" iddiasını ancak kodu OKUYAN bir kapı kapatır (KURAL R3).

Kapı iki bağımsız türetme kullanır — biri diğerinin kör noktasını kapatır:
  (A) **Sınıf türetmesi:** `LLMProvider` alt sınıfları (SDK ile konuşanlar URL literali
      taşımaz — Gemini/Anthropic/Groq bu yolla görünür).
  (B) **Host türetmesi:** `app/` içindeki URL literallerinin host'ları (yeni bir HTTP
      entegrasyonu — fiyat kaynağı, OAuth, webhook — bu yolla görünür).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
APP = KOK / "app"
ENVANTER_YOLU = KOK / "docs" / "legal" / "veri-isleyen-envanteri.md"


def _envanter() -> str:
    return ENVANTER_YOLU.read_text(encoding="utf-8").lower()


# ============================================================
# (A) KOD → LLM SAĞLAYICI SINIFLARI
# ============================================================

def _llm_saglayici_adlari() -> list[str]:
    """Somut `LLMProvider` alt sınıflarının envanter adları (zincir sarmalayıcısı hariç)."""
    from app.coach import LLMProvider

    adlar = []

    def gez(sinif):
        for alt in sinif.__subclasses__():
            gez(alt)
            if getattr(alt, "__abstractmethods__", None):
                continue
            if alt.__name__ == "FallbackProvider":
                continue    # zincir sarmalayıcısı: kendi başına veri işleyen değil
            adlar.append(getattr(alt, "NAME", alt.__name__.replace("Provider", "")))

    gez(LLMProvider)
    return sorted(set(adlar))


def test_kapsam_tabani_llm_saglayicilari_bulunuyor():
    """L11/L23: tarama boş dönerse kapı sessizce 'her şey yolunda' der."""
    adlar = _llm_saglayici_adlari()
    assert len(adlar) >= 6, f"Yalnız {len(adlar)} sağlayıcı bulundu ({adlar}) — tarama bozuk"


def _envanterde_beyan_edilen_llm_satirlari() -> list[str]:
    """§1 tablosundaki sağlayıcı adları (ilk hücre). Serbest metinde geçen isim SAYILMAZ —
    aksi halde zincir sırasını anlatan bir cümle ya da host adı ("api.together.xyz")
    beyanın yerine geçer ve kapı sessizce gevşer (mutasyonla ölçüldü)."""
    metin = ENVANTER_YOLU.read_text(encoding="utf-8")
    bolum = metin.split("## 1. LLM sağlayıcıları")[1].split("\n## ")[0]
    adlar = []
    for satir in bolum.splitlines():
        if not satir.strip().startswith("|"):
            continue
        ilk = satir.strip().strip("|").split("|")[0].strip().strip("*").strip()
        if not ilk or set(ilk) <= set("-: ") or ilk.lower() == "sağlayıcı":
            continue
        adlar.append(ilk.lower())
    return adlar


def test_koddaki_her_llm_saglayicisi_envanter_TABLOSUNDA_yazili():
    beyan = _envanterde_beyan_edilen_llm_satirlari()
    eksik = [ad for ad in _llm_saglayici_adlari()
             if not any(ad.split()[0].lower() in satir for satir in beyan)]
    assert not eksik, (
        f"Bu LLM sağlayıcıları kodda AKTİF ama envanter tablosunda satırı yok: {eksik}. "
        f"(Tabloda beyan edilenler: {beyan}) KVKK m.9/m.10: kullanıcı verisinin hangi "
        "alıcıya gittiğini görebilmeli."
    )


def test_envanter_tablosunda_kodda_olmayan_saglayici_yok():
    """Ters yön: kaldırılan sağlayıcı beyanda kalırsa envanter yanıltıcı olur (bayat beyan)."""
    kod = [ad.split()[0].lower() for ad in _llm_saglayici_adlari()]
    fazla = [satir for satir in _envanterde_beyan_edilen_llm_satirlari()
             if not any(ad in satir for ad in kod)]
    assert not fazla, f"Envanterde kodda karşılığı olmayan LLM sağlayıcısı satırı var: {fazla}"


# ============================================================
# (B) KOD → DIŞARI ÇIKAN HOST'LAR
# ============================================================

_URL = re.compile(r"""["']https?://([a-zA-Z0-9.\-]+)""")

# Envanterde ARANMAYAN host'lar — her biri gerekçeli (kullanıcı verisi taşımaz).
_MUAF_HOSTLAR = {
    "localhost": "yerel (Ollama/dev sunucu) — veri makineden çıkmaz",
    "127.0.0.1": "yerel CORS/dev",
    "financialos.local": "örnek/self-host alan adı (kendi sunucusu)",
}


def _dis_hostlar() -> dict[str, set[str]]:
    bulunan: dict[str, set[str]] = {}
    for yol in sorted(APP.rglob("*.py")):
        for m in _URL.finditer(yol.read_text(encoding="utf-8")):
            bulunan.setdefault(m.group(1), set()).add(yol.relative_to(KOK).as_posix())
    return bulunan


def test_kapsam_tabani_dis_hostlar_bulunuyor():
    hostlar = {h for h in _dis_hostlar() if h not in _MUAF_HOSTLAR}
    assert len(hostlar) >= 6, f"Yalnız {len(hostlar)} dış host bulundu ({hostlar}) — tarama bozuk"


def test_disari_cikan_her_host_envanterde_yazili():
    """Host ADI birebir yazılı olmalı — insan-okunur marka adı eşleştirmesi belirsizdir
    ("İş Yatırım" ↔ `isyatirim.com.tr`), belirsizlik de kapıyı gevşetir."""
    envanter = _envanter()
    eksik = {host: sorted(dosyalar) for host, dosyalar in _dis_hostlar().items()
             if host not in _MUAF_HOSTLAR and host not in envanter}
    assert not eksik, (
        f"Bu üçüncü taraflara kod DIŞARI çıkıyor ama envanterde host olarak yazılı değiller: "
        f"{eksik}. Yeni entegrasyon eklendiğinde envanter aynı commit'te güncellenmeli."
    )


def test_muaf_host_listesi_bayat_degil():
    mevcut = set(_dis_hostlar())
    bayat = sorted(set(_MUAF_HOSTLAR) - mevcut)
    assert not bayat, f"Muaf listesinde artık kodda geçmeyen host'lar var: {bayat}"


# ============================================================
# TARAMANIN KENDİSİ ÖLÇÜLÜR (L11 meta-test)
# ============================================================

def test_tarama_yeni_bir_host_u_yakalar(tmp_path):
    """Kapı yeni bir entegrasyonu gerçekten görüyor mu (yoksa hep-yeşil bir tören olur)."""
    ornek = 'BASE_URL = "https://api.yeni-saglayici.example/v1"\n'
    hostlar = {m.group(1) for m in _URL.finditer(ornek)}
    assert hostlar == {"api.yeni-saglayici.example"}
    assert "api.yeni-saglayici.example" not in _envanter()   # yazılmamış host kapıya takılır


def test_envanter_kendi_dogrulama_iddiasini_bu_kapiya_baglar():
    """Belgenin 'kodla kilitlenir' iddiası, onu ÖLÇEN dosyayı adıyla göstermeli (R3)."""
    metin = ENVANTER_YOLU.read_text(encoding="utf-8")
    assert "test_veri_isleyen_envanteri_kapisi" in metin, (
        "Envanter hâlâ kendisini ölçmeyen bir teste atıf yapıyor — iddia kanıta bağlı değil"
    )


# ============================================================
# OAUTH — kimlik sağlayıcı da veri işleyendir
# ============================================================

def test_oauth_saglayicilari_envanterde():
    """Girişte e-posta/kimlik dış sağlayıcıyla değişilir; envanter bunu saklayamaz."""
    from app.services.oauth import _PROVIDERS
    envanter = _envanter()
    eksik = [ad for ad in _PROVIDERS if ad.lower() not in envanter]
    assert not eksik, f"OAuth sağlayıcıları envanterde yok: {eksik}"


def test_envanter_harici_kimlik_saglayici_yok_demiyor():
    """Eski §4 iddiası ('harici kimlik sağlayıcı YOK') Google/GitHub girişiyle ÇELİŞİYORDU."""
    envanter = _envanter()
    assert "harici kimlik sağlayıcı (firebase/auth0):** yok" not in envanter, (
        "Envanter hâlâ 'harici kimlik sağlayıcı yok' diyor ama OAuth girişi aktif"
    )
