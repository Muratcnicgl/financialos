"""
YIKICI BETİĞİN EMNİYET KAPISI (BUG #358 — 5 Eylül 2026).

NEDEN VAR
---------
`scripts/setup_data.py` hedef veritabanındaki **TÜM veriyi siler** (`drop_all`). Onay kilidi
BUG #076'da eklenmişti ve doğru çalışıyordu. Ama 5 Eylül gecesi bütün betikler `--help` ile
taranınca iki boşluk ölçüldü:

1. **`--help` DESTEKLENMİYORDU.** argparse yok; `--help` doğrudan onay istemine düşüyordu.
   Yani *"bu betik ne yapar?"* diye soran biri, cevap yerine **veri silen bir betiğin
   istemiyle** karşılaşıyordu. Yıkıcı bir aracın ilk görevi kendini anlatmaktır.
2. **Etkileşimsiz ortamda `EOFError` ile ÇÖKÜYORDU.** Davranış GÜVENLİYDİ (silmiyordu) ama
   OKUNMUYORDU: operatör traceback görüp *"çöktü mü, sildi mi?"* diye bakmak zorundaydı.
   **Bir güvenlik kilidi, kilitlediğini SÖYLEMELİ.**

Bu kapı, ikisinin de geri gelmemesini sağlar — ve hiçbir testte gerçek veriye dokunmaz
(hedef bellek-içi DB'ye çevrilir, ayrıca iki yol da SİLMEYEN yollardır).

MUTASYON 2/2 — --help dalini kaldir -> yardim testi kirmizi ·
EOFError yakalamasini kaldir -> etkilesimsiz test kirmizi (traceback geri gelir)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent


def _kosur(*ek: str) -> subprocess.CompletedProcess:
    """Betiği ASLA gerçek veriye bakmayacak şekilde koşar."""
    ortam = dict(
        os.environ,
        PYTHONIOENCODING="utf-8",
        DATABASE_URL="sqlite:///:memory:",   # gerçek dosyaya DOKUNMAZ
        LOG_DIR="logs/arac",                 # BUG #349
    )
    ortam.pop("SETUP_DATA_FORCE", None)      # onay kilidi ölçülecek; zorlama YOK
    return subprocess.run(  # noqa: S603
        [sys.executable, "-m", "scripts.setup_data", *ek],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(KOK), timeout=180, env=ortam, stdin=subprocess.DEVNULL,
    )


def test_HELP_calisir_ve_HICBIR_SEY_degistirmez():
    """Yıkıcı bir betik, ne yaptığını sormadan ÖNCE anlatabilmeli."""
    sonuc = _kosur("--help")
    assert "Traceback" not in (sonuc.stderr or ""), (
        f"`--help` çöktü:\n{sonuc.stderr}"
    )
    assert sonuc.returncode == 0, f"çıkış {sonuc.returncode}\n{sonuc.stdout}{sonuc.stderr}"
    assert "KULLANIM" in sonuc.stdout, f"yardım metni basılmadı:\n{sonuc.stdout}"
    # En kritik iddia: yardım isteyen bir çağrı SİLME yoluna girmemeli.
    assert "DB sifirlaniyor" not in sonuc.stdout, (
        "`--help` silme yoluna girdi — yıkıcı bir betikte bu kabul edilemez"
    )


def test_ETKILESIMSIZ_ortamda_TEMIZ_iptal_eder():
    """stdin yoksa: traceback DEĞİL, ne olduğunu SÖYLEYEN bir iptal."""
    sonuc = _kosur()
    assert "Traceback" not in (sonuc.stderr or ""), (
        "onay alınamadığında betik çöküyor; güvenli ama okunmaz — bir güvenlik kilidi "
        f"kilitlediğini söylemeli:\n{sonuc.stderr}"
    )
    assert sonuc.returncode == 0, f"çıkış {sonuc.returncode}\n{sonuc.stdout}{sonuc.stderr}"
    assert "İptal edildi" in sonuc.stdout, f"iptal edildiği söylenmedi:\n{sonuc.stdout}"
    assert "DB sifirlaniyor" not in sonuc.stdout, "onaysız silme yoluna girildi"


def test_ONAY_KILIDI_hala_yerinde():
    """BUG #076 regresyon kilidi: `--force`/env olmadan silme yolu AÇILMAZ.

    Bu test, yukarıdaki iki düzeltmenin kilidi ZAYIFLATMADIĞINI ölçer — bir kolaylık
    eklerken emniyeti gevşetmek, bu depoda tekrar eden bir tuzaktır.
    """
    kaynak = (KOK / "scripts" / "setup_data.py").read_text(encoding="utf-8")
    assert '"--force" in _sys.argv' in kaynak, "`--force` kontrolü kaybolmuş"
    assert 'SETUP_DATA_FORCE' in kaynak, "env ile zorlama kontrolü kaybolmuş"
    assert "drop_all" in kaynak, "kapı yanlış dosyayı ölçüyor olabilir"
