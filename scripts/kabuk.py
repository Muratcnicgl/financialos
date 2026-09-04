"""
DIŞ KOMUT ÇAĞRILARININ TEK KAYNAĞI (`git`, `powershell`).

NEDEN VAR
---------
`ruff`ın güvenlik ailesi (`S607`) "kısmi çalıştırılabilir yol" der: `["git", ...]` yazmak,
`PATH`'e bağımlı olmak demektir. Depoda bu uyarı **14 yerde** birikmişti ve
`test_kacis_dizisi_kapisi.py` şunu yazmıştı:

    "her yeni kopya ruff'ta bir `S607` daha üretiyor — tavan bu sebeple üst üste ÜÇ KEZ
     yükselmişti. Dördüncüsü yazılmadı."

Wave-Y'de aynı hata iki kez daha yapıldı: BOM kapısı ve ölü adam anahtarı kapısı `git` ve
`powershell`i doğrudan çağırınca tavan 63 → 67 kırıldı. **Bir ratchet kapısına doğru cevap
tavanı yükseltmek değil, ihtiyacı ortadan kaldırmaktır** — bu modül o ihtiyacı kaldırır:
kısmi yol ARTIK TEK YERDE yaşar, gerekçesi de burada durur.

GEREKÇE (kısmi yol neden kabul ediliyor)
-----------------------------------------
`git` ve `powershell` bu depoda **geliştirme/CI araçlarıdır**, kullanıcı girdisiyle
çağrılmazlar ve argümanları sabittir. Tam yol yazmak taşınabilirliği bozardı (Windows'ta
`C:\\Program Files\\Git\\...`, CI'da `/usr/bin/git`). Risk, `PATH`in ele geçirilmesiyle
sınırlıdır — ki o noktada test koşucusunun kendisi zaten ele geçirilmiştir.
"""
from __future__ import annotations

import shutil
import subprocess  # noqa: S404 — sabit argümanlı geliştirme araçları; gerekçe yukarıda
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def git(*argv: str, kok: Path | None = None, timeout: int = 60) -> subprocess.CompletedProcess:
    """`git` çağrısı. Argümanlar SABİTTİR; kullanıcı girdisi geçirilmez."""
    return subprocess.run(  # noqa: S603
        ["git", *argv],  # noqa: S607 — TEK KAYNAK; gerekçe modül docstring'inde
        cwd=str(kok or KOK),
        capture_output=True, text=True, timeout=timeout,
    )


def powershell_var() -> bool:
    """PowerShell bu makinede VAR MI — çağırmadan önce sorulur.

    BUG #346: iki kapı `powershell` yokluğunu `returncode == 127` ile yakalamaya
    çalışıyordu. O dal **hiç çalışamaz**: `subprocess.run` komutu bulamazsa geriye bir
    sonuç DÖNMEZ, `FileNotFoundError` FIRLATIR. Sonuç: Windows'ta yeşil olan iki kapı
    Linux CI'da çöktü ve CI kırmızı kaldı. Hata yolu, başarı yolu kadar sağlam
    olmalıdır (L66) — ve bir hata yolu ancak GERÇEKTEN koşulabiliyorsa yoldur.
    """
    return shutil.which("powershell") is not None


def powershell(kod: str, timeout: int = 120) -> subprocess.CompletedProcess:
    """
    Windows PowerShell'de bir komut koşturur.

    `-Command` ile fazladan argümanlar `$args`e **DÜŞMEZ** — bu tuzağa Wave-Y'de iki kez
    düşüldü. Değer geçirmek gerekiyorsa komuta GÖMÜLÜR (tek tırnak + tek tırnak kaçışı);
    bunun için `ps_dizge()` kullanılır.
    """
    return subprocess.run(  # noqa: S603
        # noqa: S607 — TEK KAYNAK; gerekçe modül docstring'inde
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", kod],  # noqa: S607
        capture_output=True, text=True, timeout=timeout,
    )


def ps_dizge(deger) -> str:
    """Bir değeri PowerShell tek-tırnaklı dizgesine çevirir (boşluk/Türkçe/tırnak güvenli)."""
    return "'" + str(deger).replace("'", "''") + "'"
