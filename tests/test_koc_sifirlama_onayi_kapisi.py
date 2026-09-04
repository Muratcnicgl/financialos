"""
KOÇ SIFIRLAMA ONAYI KAPISI (BUG #354 — 5 Eylül 2026).

ÖLÇÜLEN OLAY
------------
`Coach.jsx`'in "Yeni sohbet" düğmesi şu onayı gösteriyordu:

    "Tüm sohbet geçmişi silinecek. Devam edilsin mi?"

Oysa `CoachEngine.reset_history` **üç tabloyu birden kalıcı siliyor**:

* `CoachMemory`   — sohbet geçmişi (onayda geçiyordu)
* `CoachInsight`  — koçun kullanıcı hakkında zamanla çıkardığı davranışsal içgörüler
* `ReasoningTrace`— muhakeme/gerekçe izleri

Canlı veritabanında ölçüldü (5 Eyl 2026): **38 + 37 + 90 = 165 satır.** Yani *"yeni bir
sohbete başlayayım"* diyen kullanıcı, koçun kendisi hakkında **öğrendiklerini** de siliyordu
ve bunu onay metninden anlaması imkânsızdı. Geri alma yok, yumuşak silme yok.

NE SİLİNECEĞİ BİR ÜRÜN KARARIDIR VE DEĞİŞTİRİLMEDİ. Değişen tek şey, onayın doğruyu
söylemesi: kullanıcı neyi kaybettiğini bilerek onaylıyor.

NE ZORLAR
---------
`reset_history` hangi modelleri siliyorsa, onay metni onların HEPSİNİ anmalı. Yarın dördüncü
bir tablo eklenirse bu test düşer ve yazan kişi onay metnini de güncellemek zorunda kalır —
yani **rıza, davranışa bağlanmıştır.**

Bu, deponun tekrar eden desenidir: bir sözleşme iki yerde yazılıysa (burada: kod ve kullanıcıya
gösterilen metin), ikisini bağlayan bir ölçüm olmadan **kaçınılmaz olarak ayrışırlar** (L78).

MUTASYON 2/2 — onay metninden "icgoru" kelimesini cikar -> kapi kirmizi ·
reset_history'ye dorduncu bir model ekle -> kapi kirmizi (yeni silinen sey anilmali)
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
COACH_PY = KOK / "app" / "coach.py"
COACH_JSX = KOK / "frontend" / "src" / "panels" / "Coach.jsx"

#: Silinen model → onay metninde geçmesi ZORUNLU olan sözcüklerden en az biri.
#: Yeni bir model eklenirse burada karşılığı da tanımlanmalı; tanımsız model, kapının
#: "bilmiyorum" demesine yol açar ve test düşer (L45: bilinmeyen ≠ sorunsuz).
MODEL_SOZCUKLERI: dict[str, tuple[str, ...]] = {
    "CoachMemory": ("sohbet",),
    "CoachInsight": ("içgörü", "icgoru", "öğrendik", "ogrendik"),
    "ReasoningTrace": ("muhakeme", "gerekçe", "gerekce"),
}


def _silinen_modeller() -> list[str]:
    """`reset_history` gövdesinde `db.query(X).…delete()` ile silinen model adları."""
    kaynak = COACH_PY.read_text(encoding="utf-8")
    m = re.search(r"def reset_history\(.*?\n(.*?)(?=\n    def |\nclass |\Z)", kaynak, re.S)
    assert m, "reset_history bulunamadı — kapı yanlış varsayım üzerine kurulu"
    govde = m.group(1)
    return sorted(set(re.findall(r"db\.query\((\w+)\)[^\n]*", govde)))


def _onay_metni() -> str:
    """`window.confirm(...)` çağrısının argüman metni (birleştirilmiş dizgeler dahil)."""
    kaynak = COACH_JSX.read_text(encoding="utf-8")
    m = re.search(r"window\.confirm\((.*?)\);", kaynak, re.S)
    assert m, "window.confirm çağrısı bulunamadı — sıfırlama akışı değişmiş olabilir"
    return m.group(1)


def test_KAPI_dogru_yeri_okuyor():
    """Vakumsal yeşil yasağı: silinen model bulunamıyorsa kapı hiçbir şey ölçmez."""
    modeller = _silinen_modeller()
    assert len(modeller) >= 3, (
        f"KAPI BOZUK: `reset_history` içinde yalnız {modeller} bulundu; en az üç model "
        "silindiği ölçülmüştü. Gövde ya da tarayıcı değişmiş."
    )


def test_ONAY_metni_SILINEN_HER_SEYI_aniyor():
    """BUG #354 regresyon kilidi — rıza, davranışa bağlıdır."""
    metin = _onay_metni().lower()
    eksik = []
    for model in _silinen_modeller():
        sozcukler = MODEL_SOZCUKLERI.get(model)
        if sozcukler is None:
            eksik.append(f"{model} (kapıda karşılığı TANIMSIZ — MODEL_SOZCUKLERI'ne ekle)")
            continue
        if not any(s.lower() in metin for s in sozcukler):
            eksik.append(f"{model} (metinde {sozcukler} geçmiyor)")
    assert not eksik, (
        "Sıfırlama onayı, silinen her şeyi anmıyor. Kullanıcı neyi kaybettiğini bilmeden "
        "onaylıyor demektir:\n  " + "\n  ".join(eksik)
        + "\n\nNE SİLİNECEĞİ bir ürün kararıdır; ama onay metni ile davranış AYRIŞAMAZ."
    )


def test_ONAYIN_GERI_ALINAMAZ_oldugu_yaziyor():
    """Kalıcı silme, kalıcı olduğunu söylemeli — yumuşak silme ya da geri alma yok."""
    metin = _onay_metni().lower()
    assert "geri alınamaz" in metin or "geri alinamaz" in metin, (
        "Onay metni işlemin GERİ ALINAMAZ olduğunu söylemiyor. `reset_history` sert siler: "
        "yumuşak silme yok, yedek yok, geri alma yok."
    )
