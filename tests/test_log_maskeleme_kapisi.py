"""
BUG #244 (denetim D29) — MASKELEME VARDI AMA (a) EKSİKTİ, (b) LOG DOSYASINA HİÇ UYGULANMIYORDU.

`app/error_tracking.py` docstring'i *"PII/sır temizliği zorunlu"* diye güvence veriyordu.
Gerçekte iki ayrı boşluk vardı:

1. **Desen eksikliği:** TCKN (11 hane), Türk telefonu, boşluksuz IBAN (`TR33...`), bcrypt
   hash (`$2b$...`), tırnaklı şifre değeri ve opak (JWT olmayan) Bearer token'ı maskeden
   GEÇİYORDU. Denetimin çalıştırdığı 12 örneğin 6'sı hiç değişmeden çıktı.
2. **Tüketici körlüğü (L21 sınıfı):** `temizle()` YALNIZ DB kaydına uygulanıyordu;
   `app/main.py`'deki global yakalayıcı `logger.exception(..., exc_info=True)` ile HAM
   traceback'i (SQLAlchemy'nin `[parameters: ('Ali Veli', '$2b$12$...')]` metni dahil)
   `logs/financialos.log` dosyasına maskesiz yazıyordu. Yani sinyal (maskeleme) vardı ama
   asıl sızdıran yüzeye hiç ulaşmıyordu.

Üçüncü kök: SQLAlchemy istisna metinleri **bound parameter** taşıyor (`hide_parameters`
ayarlanmamıştı) — yani ad, e-posta ve şifre hash'i istisnanın İÇİNE giriyordu. En sağlam
savunma kaynakta: parametreler istisnaya hiç girmesin.

Log dosyası operatörün, yedek alan sistemlerin ve olası bir log-toplama zincirinin
gördüğü yüzeydir (KVKK m.12 veri minimizasyonu + güvenlik).
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest

from app.error_tracking import temizle, LogMaskeleyici

KOK = Path(__file__).resolve().parent.parent


# ============================================================
# 1. DESEN KAPSAMI — denetimin kaçan örnekleri
# ============================================================

KACANLAR = [
    ("TCKN", "TCKN 12345678901 gecersiz", "12345678901"),
    ("telefon", "telefon 05321234567 kayitli", "05321234567"),
    ("telefon-uluslararasi", "ara +905321234567 hemen", "+905321234567"),
    ("IBAN", "IBAN TR330006100519786457841326 hatali", "TR330006100519786457841326"),
    ("IBAN-bosluklu", "IBAN TR33 0006 1005 1978 6457 8413 26", "TR33 0006"),
    ("bcrypt", "hash $2b$12$KIXQK0dQ9lJ0Zp1mQzMOne kaydedildi", "$2b$12$"),
    ("opak-token", "Authorization: Bearer abc123XYZopaquetoken-9f8a7b6c5d4e3f2a1b",
     "abc123XYZopaquetoken"),
    ("tirnakli-sifre", "PASSWORD 'Sifre123!' gecersiz", "Sifre123!"),
]


@pytest.mark.parametrize("ad,girdi,sizan", KACANLAR, ids=[k[0] for k in KACANLAR])
def test_maskeleme_pii_sizdirmaz(ad, girdi, sizan):
    cikti = temizle(girdi)
    assert sizan not in cikti, f"{ad} maskelenmedi: {cikti!r}"


def test_sqlalchemy_parametre_metni_maskeleniyor():
    """Denetimin kanıtı: e-posta maskeleniyordu ama AD ve bcrypt HASH kalıyordu."""
    metin = ("(sqlite3.IntegrityError) UNIQUE constraint failed: users.email "
             "[SQL: INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)] "
             "[parameters: ('Ali Veli', 'ali@example.com', '$2b$12$KIXQK0dQ9lJ0Zp1mQzMOne')]")
    cikti = temizle(metin, max_uzunluk=2000)
    assert "ali@example.com" not in cikti
    assert "$2b$12$" not in cikti
    assert "Ali Veli" not in cikti, "Bound parameter listesi ham kaldı (ad sızıyor)"


def test_maskeleme_hata_teshisini_oldurmez():
    """L6: kapı ürünü kıramaz — tip/dosya/satır bilgisi teşhis için KALMALI."""
    metin = ('Traceback (most recent call last):\n  File "app/routers/user.py", line 42, '
             'in guncelle\n    raise ValueError("gecersiz tutar")\nValueError: gecersiz tutar')
    cikti = temizle(metin, max_uzunluk=2000)
    assert "user.py" in cikti and "line 42" in cikti and "ValueError" in cikti


# ============================================================
# 2. LOG DOSYASI — maskeleme tüketiciye ULAŞIYOR mu (L21)
# ============================================================

def test_log_kaydi_pii_tasimaz(caplog):
    """Filtre logging zincirine bağlı: mesaj + exc_info maskeden geçer."""
    kayitci = logging.getLogger("test.maskeleme")
    kayitci.addFilter(LogMaskeleyici())
    with caplog.at_level(logging.ERROR, logger="test.maskeleme"):
        try:
            raise ValueError("kullanici ali@example.com TCKN 12345678901 hash $2b$12$ABCDEFGHIJ")
        except ValueError:
            kayitci.exception("Beklenmedik hata: %s %s", "POST", "/api/users")

    kayit = caplog.records[-1]
    tam_metin = kayit.getMessage() + str(getattr(kayit, "exc_text", "") or "")
    for sizinti in ("ali@example.com", "12345678901", "$2b$12$"):
        assert sizinti not in tam_metin, f"Log kaydında sızıntı: {sizinti} → {tam_metin!r}"


def test_json_formatter_ciktisinda_pii_yok():
    """Prod formatı `exc` alanını ayrıca yazıyor — orası da maskeli olmalı."""
    from app.logging_config import JsonFormatter
    try:
        raise ValueError("kart 4111111111111111 ve mail ali@example.com")
    except ValueError:
        import sys
        kayit = logging.LogRecord("x", logging.ERROR, __file__, 1, "hata: %s", ("ali@example.com",),
                                  sys.exc_info())
    LogMaskeleyici().filter(kayit)
    satir = JsonFormatter().format(kayit)
    govde = json.loads(satir)
    assert "ali@example.com" not in json.dumps(govde, ensure_ascii=False)
    assert "4111111111111111" not in json.dumps(govde, ensure_ascii=False)


def test_setup_logging_maskeleyiciyi_baglar():
    """Kapı yapısal: filtre elle eklenmeye bırakılmaz (unutulur — L24)."""
    kaynak = (KOK / "app" / "logging_config.py").read_text(encoding="utf-8")
    assert "LogMaskeleyici" in kaynak and "addFilter" in kaynak, (
        "Log maskeleyicisi logging zincirine bağlanmamış — dosyaya ham PII düşer"
    )


# ============================================================
# 3. KAYNAKTA SAVUNMA — SQLAlchemy parametreleri istisnaya girmesin
# ============================================================

def test_engine_hide_parameters_uygulaniyor():
    kaynak = (KOK / "app" / "database.py").read_text(encoding="utf-8")
    assert "hide_parameters" in kaynak, (
        "SQLAlchemy istisna metinleri bound parameter (ad/e-posta/hash) taşıyor — "
        "en sağlam savunma kaynakta: hide_parameters"
    )


def test_kullanici_metni_log_a_dusmuyor():
    """BUG #180 ilkesi: ham finansal/kişisel metin log'a yazılmaz (koç içgörüsü dahil)."""
    kaynak = (KOK / "app" / "coach.py").read_text(encoding="utf-8")
    sizdiran = [s for s in kaynak.splitlines()
                if re.search(r"logger\.(info|debug|warning)\(.*result\.content", s)]
    assert not sizdiran, f"Koç içgörü metni log'a yazılıyor: {sizdiran}"
