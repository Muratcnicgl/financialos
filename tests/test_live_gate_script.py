"""
P6 hazırlığı — `scripts/live_gate.py` statik doğrulaması.

Canlı kapı script'i sunucu olmadan koşulamaz; ama **bozuk bir script felaket anında
işe yaramaz**. Bu test script'in yüklenebilir olduğunu, kritik kapıları kapsadığını ve
sırları hiçbir yere yazmadığını doğrular (Wave-8 Blok A deseni: sunucu olmadan
doğrulanabilen her şey doğrulanır).
"""
from __future__ import annotations

import inspect
from pathlib import Path

from scripts import live_gate

_ROOT = Path(__file__).resolve().parent.parent


def test_script_yuklenebilir_ve_ana_fonksiyonlari_var():
    assert callable(live_gate.main) and callable(live_gate.kosla)


def test_kritik_kapilar_kapsaniyor():
    """Kapı listesi daralırsa (birisi 'geçici olarak' kaldırırsa) test kırılır."""
    src = inspect.getsource(live_gate.kosla)
    for beklenen in ("api/health", "Strict-Transport-Security", "Content-Security-Policy",
                     "api/cockpit", "/docs", "api/legal", "429", "user_daily_limit"):
        assert beklenen in src, f"Canlı kapıda eksik kontrol: {beklenen}"


def test_kimliksiz_erisim_kapisi_zorunlu():
    """AUTH_ENABLED kapalı deploy (BUG #171) canlıda mutlaka yakalanmalı."""
    src = inspect.getsource(live_gate.kosla)
    assert "token'sız cockpit 401" in src
    assert "AUTH_ENABLED kapalı" in src


def test_sir_hicbir_yere_yazilmaz():
    """Parola parametresi log'a/dosyaya yazılmamalı (sır chat'e/diske DÜŞMEZ kuralı)."""
    import re
    kaynak = (_ROOT / "scripts" / "live_gate.py").read_text(encoding="utf-8")
    assert "print(args.password" not in kaynak
    # Dosyaya YAZMA yok (urlopen gibi okuma çağrıları kapsam dışı)
    yazma = re.search(r"\bopen\([^)]*['\"][wa]", kaynak)
    assert not yazma, "Script dosyaya yazıyor — sır sızma riski"
    assert "logging" not in kaynak, "Script log'a yazıyor — parola sızabilir"


def test_basarisizlikta_cikis_kodu_1():
    s = live_gate.Sonuc()
    s.satirlar.append(("zorunlu kapı", False, True, ""))
    assert s.basarili() is False
    s2 = live_gate.Sonuc()
    s2.satirlar.append(("uyarı kapısı", False, False, ""))
    assert s2.basarili() is True, "Zorunlu olmayan kapı sonucu düşürmemeli"
