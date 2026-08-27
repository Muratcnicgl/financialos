r"""
KAÇIŞ DİZİSİ KAPISI (BUG #312).

NEDEN VAR — ölçülmüş, varsayılmamış: iki betiğin modül docstring'i **r-önekli (ham)**
değildi ve içinde Windows komutu geçiyordu:

    Kullanım:  .\venv\Scripts\python.exe scripts/test_fresh_db_migration.py

Python bu dizgede `\v`'yi **geçerli** bir kaçış dizisi olarak yorumlar — dikey sekme (0x0B).
Yani kaynakta `.\venv\Scripts\...` yazan satır, bellekte `.` + 0x0B + `env\Scripts\...`
oluyordu. Ölçüldü (`ast.get_docstring` + `repr`): docstring gerçekten bozuktu. `\S` ise
geçersizdir; bugün `DeprecationWarning`, Python 3.12'de `SyntaxWarning`, **3.14'te hata**.

İki ayrı zarar, ikisi de sessiz:
  1. Belge yalan söylüyor — komutu kaynaktan okuyan insan doğrusunu görüyor ama dizgeyi
     programla işleyen (yardım metni basan, docstring'i ayrıştıran) bozuğunu alıyor. Bu,
     BUG #305'in (L64: venv yolunu yanlış belgeleyen dosyalar) sessiz akrabasıdır.
  2. Bir Python yükseltmesinde **derleme hatası** olacak. Bugün uyarı olduğu için kimse
     görmüyor: uyarılar `-W` ayarına bağlı ve süit koşumunda kaybolur.

Kapı `ruff`a bırakılamadı: `W605` (invalid escape sequence) `W` ailesindedir ve `ruff.toml`
dar kümesi `E9,F,B,S` seçiyor — `W`yi açmak bu turda ölçülmemiş başka bulgular getirirdi.
Buradaki test tek bir şeyi ölçer ve gerekçesini taşır.
"""
from __future__ import annotations

import ast
import sys
import warnings
from pathlib import Path

REPO_KOK = Path(__file__).resolve().parent.parent
if str(REPO_KOK) not in sys.path:
    sys.path.insert(0, str(REPO_KOK))

# İzlenen dosya listesi BİLEREK yeniden yazılmadı. Ölçüm: depoda `git ls-files`'ı çağıran
# 5 ayrı yer var (`belge_denetimi` ×2, `olu_kod_kapisi`, `sir_taramasi`, ve neredeyse burası)
# ve her yeni kopya ruff'ta bir `S607` daha üretiyor — tavan bu sebeple üst üste üç kez
# yükselmişti. Dördüncüsü yazılmadı. (Beş çağrı noktasının tek yardımcıya indirilmesi ayrı
# bir iş olarak ledger'a yazıldı; burada yapılsaydı bir bugfix commit'i refactor taşırdı.)
from scripts.olu_kod_kapisi import izlenen_py as _izlenen_py  # noqa: E402


def _kacis_uyarilari(metin: str) -> list[str]:
    with warnings.catch_warnings(record=True) as kayit:
        warnings.simplefilter("always")
        try:
            ast.parse(metin)
        except SyntaxError:
            return []
    return [str(u.message) for u in kayit if "escape sequence" in str(u.message)]


def test_hicbir_kaynak_dosyasi_gecersiz_kacis_dizisi_tasimiyor():
    bulgular = []
    for yol in _izlenen_py():
        try:
            metin = (REPO_KOK / yol).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for mesaj in _kacis_uyarilari(metin):
            bulgular.append(f"{yol}: {mesaj}")

    assert bulgular == [], (
        "Geçersiz kaçış dizisi taşıyan dosya(lar) var — Python 3.14'te derleme hatası olur.\n"
        "Çözüm: dizgeyi r-önekli (ham) yap ya da ters bölüyü kaçır.\n" + "\n".join(bulgular)
    )


def test_venv_yolu_docstringlerde_bozulmamis():
    """`\\v` GEÇERLİ bir kaçıştır ve uyarı ÜRETMEZ — yani yukarıdaki test onu yakalamaz.

    Bu ayrı test tam da o sessiz yarısını ölçer: `.\\venv\\Scripts\\` yazan her docstring
    bellekte de öyle durmalı. Depoda 21 dosya bu yolu belgeliyor (BUG #305); biri ham
    olmayan bir dizgeye taşınırsa burada kırmızı olur.
    """
    bozuk = []
    for yol in _izlenen_py():
        try:
            metin = (REPO_KOK / yol).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "venv" not in metin:
            continue
        try:
            agac = ast.parse(metin)
        except SyntaxError:
            continue
        belge = ast.get_docstring(agac, clean=False) or ""
        if "\x0b" in belge or "\x0c" in belge:
            bozuk.append(yol)

    assert bozuk == [], (
        "Docstring'inde dikey sekme (0x0B) ya da sayfa başı (0x0C) var — büyük olasılıkla "
        "ham olmayan bir dizgede `\\venv` / `\\f` yazılmış:\n" + "\n".join(bozuk)
    )
