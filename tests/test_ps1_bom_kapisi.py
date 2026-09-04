"""
BUG #339 YAN KAPISI — BOM'SUZ BİR `.ps1`, TÜRKÇE YÜZÜNDEN SESSİZCE AYRIŞMAZ.

ÖLÇÜLEN OLAY (4 Eylül 2026, Wave-Y/Y1)
--------------------------------------
`deploy/windows/guncelle.ps1` yazıldı ve koşturulunca PowerShell şunu verdi:

    ExpressionsMustBeFirstInPipeline: satir 69
    UnexpectedToken: Unexpected token '" } ... ' in expression or statement.

Hata satırı, hatanın olduğu yer DEĞİLDİ. Sebep: **Windows PowerShell 5.1, BOM'suz bir
dosyayı UTF-8 değil ANSI (cp1254) sayar.** Dosyadaki `—`, `ç`, `ğ`, `İ` gibi karakterler
çok baytlı okununca dizge sınırları kayıyor ve ayrıştırıcı alakasız bir satırda patlıyor.
Ölçüm: BOM eklendi → `[Parser]::ParseFile` **AYRIŞTIRMA TEMİZ**; tek değişiklik 3 bayt.

Depodaki diğer üç betiğin üçünde de BOM VARDI (`efbbbf`) — yani konvansiyon zaten
buydu, yazılı değildi. Yazılı olmayan konvansiyon, bir sonraki dosyada tutmaz.

NEDEN KAPI (ve neden ruff'a bırakılamaz)
-----------------------------------------
`kalite_kapisi` ruff'ın dar kümesini (E9,F,B,S) koşar — ruff Python içindir, `.ps1`
görmez. Bu dosyalar **canlı betanın açılış, sağlık ve güncelleme yolunu** taşıyor: sessizce
ayrışmayan bir betik, zamanlanmış görevde çıkış kodu 1 verir ve kimse bakmaz (B6'nın
24,5 saatlik sessiz kesintisi tam bu sınıftı — L61).

Bir sonraki `.ps1` BOM'suz eklenirse burada düşer; hata mesajı sebebi de söyler.

MUTASYON 2/2 — BOM kaldirildi -> ikisi de kirmizi (nedensellik) · BOM dururken ayrisma hatasi sokuldu -> yalniz ayrisma testi kirmizi (kapsam)
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

# `git ls-files` BEŞİNCİ kez yeniden yazılmaz — tek kaynak (BUG #338'in dersi).
from scripts.sir_taramasi import izlenen_dosyalar as _izlenen  # noqa: E402
from scripts.kabuk import powershell as _ps, powershell_var as _ps_var  # noqa: E402

BOM = b"\xef\xbb\xbf"


def _ps1_dosyalari() -> list[Path]:
    return [KOK / y for y in _izlenen()
            if y.lower().endswith(".ps1") and (KOK / y).is_file()]


def test_HER_ps1_BOM_ile_baslar():
    """
    Windows PowerShell 5.1 BOM'suz dosyayı ANSI sayar; Türkçe karakter taşıyan her betik
    bozulur. Depodaki betiklerin tamamı Türkçe yorum taşıyor, yani bu kural onların
    HEPSİ için geçerlidir — istisna yazılacaksa gerekçesi burada durmalı.
    """
    dosyalar = _ps1_dosyalari()
    assert dosyalar, "izlenen .ps1 bulunamadı — tarayıcı bozuk (vakumsal yeşil)"
    bomsuz = [p.relative_to(KOK).as_posix() for p in dosyalar
              if not p.read_bytes().startswith(BOM)]
    assert not bomsuz, (
        "Bu PowerShell betikleri UTF-8 BOM ile başlamıyor; PowerShell 5.1 onları ANSI "
        "okur ve Türkçe karakterler yüzünden ALAKASIZ bir satırda ayrıştırma hatası "
        f"verir:\n  {bomsuz}\n"
        "Düzelt: dosyanın başına \\ufeff ekle (3 bayt), içerik değişmez."
    )


def test_HER_ps1_AYRISTIRILABILIR():
    """
    BOM gerekli ama YETERLİ değil — asıl sözleşme "bu betik ayrışıyor mu". BOM'u
    ölçüp ayrıştırmayı ölçmemek, kapıyı belirtiye bağlayıp nedene bağlamamak olurdu.

    `[Parser]::ParseFile` betiği KOŞTURMAZ, yalnız okur — canlıya dokunmaz.
    """
    dosyalar = _ps1_dosyalari()
    # `-Command` ile fazladan argümanlar `$args`e DÜŞMEZ (ölçüldü: liste boş kalıp
    # komutun kendisi ayrışma hatası verdi). Liste komuta gömülür; yollarda boşluk ve
    # Türkçe karakter var, o yüzden tek tırnak + tek tırnak kaçışı.
    liste = ",".join("'" + str(p).replace("'", "''") + "'" for p in dosyalar)
    kod = (
        f"$h=0; foreach ($f in @({liste})) {{ $e=$null; $t=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile($f,[ref]$t,[ref]$e)|Out-Null; "
        "if ($e.Count -gt 0) { $h=1; "
        "Write-Output ($f + ' :: satir ' + $e[0].Extent.StartLineNumber + ' :: ' "
        "+ $e[0].Message) } }; exit $h"
    )
    if not _ps_var():
        pytest.skip("powershell yok (Windows dışı ortam) — BOM testi yine de koştu")
    sonuc = _ps(kod)
    assert sonuc.returncode == 0, (
        "PowerShell betiği AYRIŞMIYOR — zamanlanmış görevde sessizce çıkış 1 verir:\n"
        + (sonuc.stdout or sonuc.stderr)[:1500]
    )


def test_WINDOWSTA_ayristirma_kapisi_ATLANAMAZ():
    """BUG #346 — atlama, kapının SESSİZCE yok olma yolu olmamalı.

    Ayrıştırma testi PowerShell yoksa atlanır; bu Linux CI için doğru (orada `.ps1`
    koşmaz). Ama `.ps1` dosyalarının GERÇEKTEN koştuğu makine Windows'tur — orada
    atlama olursa kapı vardır ama korumaz. Bu test tam olarak onu yasaklar.
    """
    if platform.system() != "Windows":
        pytest.skip("bu iddia yalnız Windows için anlamlı")
    assert _ps_var(), (
        "Windows'ta powershell bulunamadı — ayrıştırma kapısı atlanıyor demektir. "
        "Kapının atlanması yalnız .ps1'in hiç koşmadığı ortamlarda meşrudur."
    )
