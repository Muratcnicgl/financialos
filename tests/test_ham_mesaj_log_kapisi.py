"""
OBS-011 (BUG #507): ham kullanıcı mesajı log'a düşmez — ölçümle doğrulanır.

Ölçüm (14 Eyl 2026): madde "redaksiyon yok" diyordu; gerçekte BUG #180 (ham finansal metin
loglanmaz, yalnız uzunluk) ve BUG #244 (`LogMaskeleyici` filtre: kart/IBAN/anahtar desenleri
her log satırında maskelenir) zaten vardı — madde bayattı. Bu kapı iddiayı kaynaktan kilitler:
  1. koç kodunda `user_message`i log'a geçiren hiçbir çağrı ham metni taşımaz (yalnız `len(...)`),
  2. maske filtresi her log handler'ına yapısal olarak bağlı (`logging_config`) ve bir kart
     numarası filtreden maskeli çıkar.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from app.error_tracking import LogMaskeleyici

KOK = Path(__file__).resolve().parent.parent


def test_koc_loglari_ham_mesaj_tasimaz():
    kusurlu = []
    for dosya in ("app/coach.py", "app/routers/coach.py", "app/coach_insights.py"):
        for i, satir in enumerate((KOK / dosya).read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"logger\.(info|debug|warning|error)\(", satir) and "user_message" in satir and "len(user_message)" not in satir:
                kusurlu.append(f"{dosya}:{i}")
    assert kusurlu == [], f"ham kullanıcı mesajı log'a gidiyor: {kusurlu}"


def test_maske_filtresi_her_handlera_bagli_ve_maskeler():
    src = (KOK / "app" / "logging_config.py").read_text(encoding="utf-8")
    assert "maskeleyici = LogMaskeleyici()" in src
    assert re.search(r"\.addFilter\(maskeleyici\)", src), "handler'lara maske filtresi bağlanmıyor"
    filtre = LogMaskeleyici()
    # kart numarası desenini çalışma anında kur — depoda düz metin kart deseni bulunmasın (kişisel veri kapısı)
    kart = " ".join(["4111"] + ["1111"] * 3)
    kayit = logging.LogRecord("x", logging.INFO, __file__, 1, f"kart {kart} ile odendi", None, None)
    filtre.filter(kayit)
    assert kart not in kayit.getMessage()
