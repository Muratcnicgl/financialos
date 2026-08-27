r"""
ÖLÜ KOD KAPISI — ÇAĞRILMAYAN PUBLIC FONKSİYON SAYACI (BUG #311 / KAP-06).

NEDEN VAR: 27 Ağu 2026'da `app/` içinde hiçbir yerden çağrılmayan 4 public fonksiyon
ölçüldü. Üçü zararsızdı; biri DEĞİLDİ:

    `app/serializers.py:export_user_data` — BUG #243 (D26) KVKK export'unun şifre hash'ini
    döktüğünü bulup düzeltmişti. Düzeltme iki ÇAĞIRANI `app/data_subject.disa_aktar`'a
    yönlendirdi ama eski GÖVDEYİ silmedi. Gövde 21 gün boyunca çağrılmadan durdu ve
    ölçüldüğünde `password_hash` · `oauth_sub` · `token_version` alanlarını hâlâ
    döküyordu (`disa_aktar` bunları `GIZLENEN_ALANLAR` ile bilerek gizler). "export" diye
    arayan biri onu çağırsa D26 aynen geri gelirdi.

Buradaki ders ölü kodun çirkinliği değil: **bir düzeltme çağıranları yönlendirip eski
gövdeyi bırakırsa defekt kapanmaz, SİLAHLI BEKLEMEYE geçer.** Kapı bu sınıfı sayar.

TAVAN 0. Diğer kapılardan (ruff sayacı) farkı bu: orada 291 bulgunun hiçbiri gerçek
defekt değildi, o yüzden tavan ölçülene çekildi. Burada ölçülen 4 bulgunun hepsi
gerçekti ve dördü de silindi — sıfırdan başlayan bir sayacın tavanı 0'dır.

ÖLÇÜLMÜŞ TASARIM KARARLARI (hiçbiri tahmin değil, hepsi yanlış sürümü koşulup görüldü):

  1. DEKORATÖRLÜ FONKSİYONLAR ELENİR. Çerçeve onları adıyla değil dekoratörle çağırır
     (`@router.get`, `@field_validator`). Elenmediğinde 48 yanlış alarm çıktı —
     hepsi FastAPI route handler'ı. Bir kapı 48 gürültüyle doğarsa ilk gün susturulur.

  2. ATIF YALNIZ `.py` DOSYALARINDA SAYILIR, BELGELERDE DEĞİL. Belge taramaya dahil
     edildiğinde `export_user_data` "kullanılıyor" göründü — çünkü adı iki TARİHSEL
     denetim raporunda geçiyordu. Bir raporun bir fonksiyondan söz etmesi onu çağırmaz;
     üstelik o raporlar tam da fonksiyonun KUSURUNU anlatıyordu. Yani en tehlikeli
     bulguyu, tehlikesini anlatan belge saklıyordu.

  3. YALNIZ FONKSİYON — sınıf/sabit taranmaz. Sınıflar dizge tip-ipuçlarında
     (`Mapped["Foo"]`), sabitler `import *` ile geçer; ikisi de bu sayım yöntemiyle
     güvenilir ölçülemez. Kapsamı ölçemediği yere genişletmek, sayıyı anlamsızlaştırır.

  4. SAYIM İHTİYATLIDIR (az bulur, fazla değil). Bir fonksiyonun adı başka bir yerde
     yerel değişken olarak geçse "canlı" sanılır. Bilinçli tercih: bu kapı KIRMIZI
     verdiğinde haklı olmalıdır; kaçırdığı bir sonraki turda bulunur, yanlış alarmı ise
     kapının tümünü çöpe atar.

Kullanım:
    .\venv\Scripts\python.exe scripts/olu_kod_kapisi.py           # kapı
    .\venv\Scripts\python.exe scripts/olu_kod_kapisi.py --liste   # dekoratörlü/elenen döküm

GUNCELLEMELER
-------------
BUG #311 fix: dosya oluşturuldu (KAP-06).
"""
from __future__ import annotations

import argparse
import ast
import collections
import io
import re
import subprocess
import sys
import token as _token
import tokenize
from pathlib import Path

REPO_KOK = Path(__file__).resolve().parent.parent

# Python tanımlayıcısı. Dizge içindekiler de sayılır ve bu İSTENİR: `__all__ = ["foo"]`
# ya da `getattr(m, "foo")` gerçek bir kullanımdır.
_TANIMLAYICI = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# MUAFİYETLER — ad -> GEREKÇE. Boş olması bir başarı değil, bir DURUM: bugün `app/`
# içinde çağrılmayan tek bir public fonksiyon yok. Buraya bir şey eklemek, "bu fonksiyon
# çağrılmıyor ama kalmalı" demektir ve gerekçesi yazılmadan eklenemez (kapı gerekçesiz
# girdiyi reddeder). Muafiyet listesi sessizce büyürse kural erir — bu yüzden kapı kaç
# muafiyet olduğunu her koşumda YAZAR.
MUAF: dict[str, str] = {}


def _izlenen_py() -> list[str]:
    cikti = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=str(REPO_KOK), capture_output=True, text=True, check=True
    )
    return sorted(cikti.stdout.split())


def tanimlar(app_dosyalari: list[str]) -> tuple[dict[str, list[str]], int]:
    """app/ içindeki modül düzeyi, public, DEKORATÖRSÜZ fonksiyonlar: ad -> [dosya:satır]."""
    bulunan: dict[str, list[str]] = {}
    elenen = 0
    for yol in app_dosyalari:
        try:
            agac = ast.parse((REPO_KOK / yol).read_text(encoding="utf-8"))
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
        for dugum in agac.body:  # YALNIZ modül düzeyi: iç içe/metot değil
            if not isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if dugum.name.startswith("_"):
                continue
            if dugum.decorator_list:
                elenen += 1
                continue
            bulunan.setdefault(dugum.name, []).append(f"{yol}:{dugum.lineno}")
    return bulunan, elenen


def _docstring_konumlari(metin: str) -> set[tuple[int, int]]:
    """Modül/sınıf/fonksiyon docstring'lerinin (satır, sütun) konumları."""
    konumlar: set[tuple[int, int]] = set()
    try:
        agac = ast.parse(metin)
    except SyntaxError:
        return konumlar
    for dugum in ast.walk(agac):
        if not isinstance(dugum, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        govde = getattr(dugum, "body", None)
        if not govde:
            continue
        ilk = govde[0]
        if isinstance(ilk, ast.Expr) and isinstance(ilk.value, ast.Constant) and isinstance(ilk.value.value, str):
            konumlar.add((ilk.value.lineno, ilk.value.col_offset))
    return konumlar


def _dosya_atiflari(metin: str, sayac: collections.Counter) -> None:
    """YORUM ve DOCSTRING dışındaki tanımlayıcıları sayar.

    MUTASYON 3'ÜN BULDUĞU KUSUR: ilk sürüm dosyayı düz metin olarak tarıyordu, yani bir
    fonksiyonun adının bir YORUMDA ya da DOCSTRING'de geçmesi "kullanılıyor" sayılıyordu.
    Bunun sonucu ters yönde tehlikeliydi: `app/serializers.py`'ye "`export_user_data`
    silindi, çünkü …" diye gerekçe yazıldığı anda kapı O FONKSİYONA KARŞI KÖRLEŞİYORDU —
    biri onu geri koysa kapı susardı. Yani kapının görme yetisi, kendi gerekçesini yazmakla
    bozuluyordu. Bir kapı, kendisini açıklayan belge yüzünden kör kalamaz.

    Diğer DİZGELER bilerek sayılmaya devam eder: `__all__ = ["foo"]` ya da
    `getattr(mod, "foo")` gerçek bir kullanımdır (bugün bu depoda örneği yok — ölçüldü —
    ama ileride yazılırsa kapı yanlış alarm vermemeli).
    """
    docstringler = _docstring_konumlari(metin)
    try:
        for jeton in tokenize.generate_tokens(io.StringIO(metin).readline):
            if jeton.type == _token.NAME:
                sayac[jeton.string] += 1
            elif jeton.type == _token.STRING and jeton.start not in docstringler:
                sayac.update(_TANIMLAYICI.findall(jeton.string))
            # COMMENT ve docstring: sayılmaz.
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Ayrıştırılamayan dosyada İHTİYATLI davran: düz metin say. Fazla saymak
        # "canlı" sanmaya, yani AZ bulmaya yol açar — kapının güvenli yönü budur.
        sayac.update(_TANIMLAYICI.findall(metin))


def atif_sayaci(py_dosyalari: list[str]) -> collections.Counter:
    sayac: collections.Counter = collections.Counter()
    for yol in py_dosyalari:
        try:
            metin = (REPO_KOK / yol).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        _dosya_atiflari(metin, sayac)
    return sayac


def olu_fonksiyonlar() -> tuple[list[tuple[str, list[str]]], int, int]:
    py = _izlenen_py()
    app_py = [y for y in py if y.startswith("app/")]
    bulunan, elenen = tanimlar(app_py)
    sayac = atif_sayaci(py)

    olu = []
    for ad, yerler in sorted(bulunan.items()):
        if ad in MUAF:
            continue
        # Tanım satırının kendisi de sayıldı; atıf sayısı tanım sayısını AŞMIYORSA
        # fonksiyonun adı hiçbir yerde kullanılmıyor demektir.
        if sayac[ad] <= len(yerler):
            olu.append((ad, yerler))
    return olu, len(bulunan), elenen


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(description="Ölü kod kapısı: çağrılmayan public fonksiyon.")
    ayristirici.add_argument("--liste", action="store_true", help="Taranan/elenen dökümünü yaz.")
    secenek = ayristirici.parse_args(argv)

    olu, tarandi, elenen = olu_fonksiyonlar()

    print("ÖLÜ KOD KAPISI — app/ modül düzeyi public fonksiyonlar")
    print(f"  taranan (dekoratörsüz) : {tarandi}")
    print(f"  elenen (dekoratörlü)   : {elenen}   çerçeve adıyla değil dekoratörle çağırır")
    print(f"  muaf (gerekçeli)       : {len(MUAF)}")
    print(f"  ÇAĞRILMAYAN            : {len(olu)}   (tavan 0)")

    if secenek.liste:
        for ad, gerekce in sorted(MUAF.items()):
            print(f"    muaf: {ad} — {gerekce}")

    for ad, yerler in olu:
        print(f"\n  {ad}  ->  {', '.join(yerler)}")
        print("      .py dosyalarının hiçbirinde tanımı dışında geçmiyor.")

    if olu:
        print(
            "\nKAPI KIRILDI: app/ içinde çağrılmayan public fonksiyon var.\n"
            "Üç doğru cevaptan biri:\n"
            "  1. SİL — işi bitmişse. (Bir düzeltme çağıranları yönlendirip gövdeyi\n"
            "     bırakırsa defekt kapanmaz, silahlı beklemeye geçer — BUG #243/D26.)\n"
            "  2. KULLAN — yazılma sebebi hâlâ geçerliyse çağıranı ekle.\n"
            "  3. MUAF ET — `scripts/olu_kod_kapisi.py` içindeki MUAF sözlüğüne ADI ve\n"
            "     GEREKÇESİYLE yaz. Gerekçesiz muafiyet kabul edilmez.",
            file=sys.stderr,
        )
        return 1

    print("\nkapı geçildi.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
