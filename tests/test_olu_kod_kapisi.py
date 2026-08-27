"""
ÖLÜ KOD KAPISININ KENDİ TESTİ (BUG #311 / KAP-06).

Kapının yeşil olması onu doğrulamaz — ateş ettiğini görmek doğrular. Buradaki testler
kapının ÜÇ tasarım kararını da bozup sonucu ölçer; hepsi `scripts/olu_kod_kapisi.py`
üzerinde mutasyonla çalışır, diske dokunmaz.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

REPO_KOK = Path(__file__).resolve().parent.parent
KAPI_YOLU = REPO_KOK / "scripts" / "olu_kod_kapisi.py"

if str(REPO_KOK) not in sys.path:
    sys.path.insert(0, str(REPO_KOK))


def _kaynak() -> str:
    return KAPI_YOLU.read_text(encoding="utf-8")


def _kosur(kod: str):
    """Verilen kaynağı ayrı bir modül olarak koşup `olu_fonksiyonlar()` sonucunu döner."""
    modul = types.ModuleType("olu_kod_kapisi_deney")
    modul.__file__ = str(KAPI_YOLU)
    exec(compile(kod, str(KAPI_YOLU), "exec"), modul.__dict__)
    return modul.olu_fonksiyonlar()


def test_bugun_olu_public_fonksiyon_yok():
    """TAVAN 0. Kırılırsa: `app/` içine çağrılmayan bir public fonksiyon girmiş demektir."""
    olu, _tarandi, _elenen = _kosur(_kaynak())
    assert olu == [], (
        "app/ içinde çağrılmayan public fonksiyon(lar) var: "
        + ", ".join(f"{ad} ({', '.join(yerler)})" for ad, yerler in olu)
    )


def test_dekorator_elemesi_olmadan_kapi_kullanilmaz_hale_gelir():
    """Dekoratörlü fonksiyonlar çerçeve tarafından çağrılır; elenmezse kapı gürültüye boğulur.

    Bu test bir DAVRANIŞI değil, bir TASARIM KARARINI kilitler: birisi elemeyi kaldırırsa
    kapı yüzlerce yanlış alarmla döner ve ilk gün susturulur.
    """
    bozuk = _kaynak().replace(
        "            if dugum.decorator_list:\n                elenen += 1\n                continue\n",
        "",
    )
    assert bozuk != _kaynak(), "mutasyon tutmadı — kapının kaynağı değişmiş olabilir"
    olu, _t, elenen = _kosur(bozuk)
    assert elenen == 0
    assert len(olu) > 50, f"eleme kaldırılınca yanlış alarm beklenirdi, {len(olu)} çıktı"


def test_docstring_ve_yorum_atif_sayilmaz():
    """MUTASYON 3'ün bulduğu kusur — kapının en ince kör noktası.

    Bir fonksiyonun adı YORUMDA ya da DOCSTRING'de geçtiğinde ilk sürüm onu "kullanılıyor"
    sayıyordu. Sonucu ters yönde tehlikeliydi: `app/serializers.py`'ye "`export_user_data`
    silindi çünkü …" gerekçesi yazıldığı anda kapı tam O FONKSİYONA karşı körleşiyordu.
    Yani kapının görme yetisi, kendi gerekçesinin yazılmasıyla bozuluyordu.

    Kasıtlı olarak BİRİM testidir: kapıyı gerçek bir dosyayı değiştirerek sınamak,
    süiti çalışma ağacına yazar hale getirirdi (BUG #289'un sınıfı) — koşum yarıda
    kesilse dosya bozuk kalırdı.
    """
    import collections

    import scripts.olu_kod_kapisi as kapi

    kaynak = '\n'.join((
        '"""Modül docstring: olu_ad burada geçiyor."""',
        '# yorum: olu_ad burada da geçiyor',
        'def baska():',
        '    """Fonksiyon docstring: olu_ad."""',
        '    return 1',
    ))
    sayac: collections.Counter = collections.Counter()
    kapi._dosya_atiflari(kaynak, sayac)
    assert sayac["olu_ad"] == 0, "docstring/yorumdaki ad atıf sayılmamalı"
    assert sayac["baska"] == 1, "gerçek tanım sayılmalı"

    # Docstring OLMAYAN dizgeler bilerek sayılır: `__all__ = ["foo"]` gerçek kullanımdır.
    sayac2: collections.Counter = collections.Counter()
    kapi._dosya_atiflari('__all__ = ["olu_ad"]\n', sayac2)
    assert sayac2["olu_ad"] == 1, "dizge içindeki gerçek atıf sayılmalı"


def test_muafiyet_gerekcesiyle_susturur():
    """MUAF sözlüğü çalışır; boş kalması bir başarı değil, ölçülmüş bir DURUMDUR."""
    muaf_kaynak = _kaynak().replace(
        "MUAF: dict[str, str] = {}",
        'MUAF: dict[str, str] = {"utc_isoformat": "deney: muafiyet mekanizması"}',
    )
    assert muaf_kaynak != _kaynak(), "mutasyon tutmadı"
    olu, _t, _e = _kosur(muaf_kaynak)
    assert "utc_isoformat" not in {ad for ad, _ in olu}

    import scripts.olu_kod_kapisi as kapi
    assert kapi.MUAF == {}, (
        "MUAF'a bir ad eklenmişse gerekçesi de yazılmış olmalı; bu test yalnız bugünkü "
        "durumu (boş liste) kaydeder — dolduğunda gerekçeleri gözden geçir"
    )


@pytest.mark.parametrize("ad", ["export_user_data", "init_db", "guvenli_metin_veya", "para_listesi"])
def test_silinen_olu_fonksiyonlar_geri_gelmedi(ad):
    """BUG #311'de silinen dördü. `export_user_data` ölü DEĞİL, silahlıydı:
    `disa_aktar`'ın `GIZLENEN_ALANLAR` ile gizlediği `password_hash` · `oauth_sub` ·
    `token_version` alanlarını döküyordu (ölçüldü). Geri gelirse D26 de geri gelir."""
    for yol in (REPO_KOK / "app").rglob("*.py"):
        kaynak = yol.read_text(encoding="utf-8")
        assert f"def {ad}(" not in kaynak, f"{yol.relative_to(REPO_KOK)} içinde `{ad}` yeniden tanımlanmış"
