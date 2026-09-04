"""
LOG YALITIMI KAPISI (BUG #349 — 5 Eylül 2026).

ÖLÇÜLEN OLAY
------------
Canlı betanın uygulama log'u **01:08:18'de dondu.** Dosya tam `10.485.727` bayttaydı
(rotasyon tavanı 10 MB), `/api/health` 200 dönüyordu, `uvicorn.out.log` yazılmaya devam
ediyordu — ama `logs/financialos.log`'a tek satır daha düşmedi. Son satır cümlenin
ortasında kesilmişti (`[decision_rhythm] started` ... `completed` yok).

KÖK NEDEN — SÜİT, ÖLÇTÜĞÜ SİSTEMİ BOZUYORDU
--------------------------------------------
`app/main.py:73` `setup_logging()`'i **import anında** çağırır. Yani `app.main`'i içe
aktaran her süreç — 3.500 testlik pytest koşumu dahil — canlı betanın log dosyasına kendi
`RotatingFileHandler`'ını bağlar. `RotatingFileHandler` rotasyonu `os.rename` ile yapar ve
**Windows'ta başka bir süreç dosyayı açık tuttuğu sürece bu imkânsızdır** (`WinError 32`).
Dosya bu gece tavana dayandı, rotasyon her denemede düştü ve uygulama-seviyesi logging
tamamen kayboldu. `logs/financialos.log.1` hiç oluşmamıştı — yani rotasyon **bir kez bile**
tamamlanmamış.

Bu, `BUG #286` ile AYNI SINIFTIR (süit `.env`'den yalıtıldı): test ortamı, ölçtüğü canlı
sistemden ayrılmalıdır. Farkı şu — #286'da kirlenen TESTTİ, burada kirlenen **ÜRETİM**.
Ve arıza sessizdi: uygulama sağlam görünüyordu, körleşen yalnız gözlemdi (L61'in tersi —
orada ölçüyorduk ama haber vermiyorduk, burada haber verecek şeyin kendisi sustu).

NE ZORLAR
---------
Hiçbir test süreci, deponun canlı log dosyasına tutunan bir handler taşıyamaz. Ayrıca
kapı kendi vakumunu da yasaklar: hiç dosya handler'ı YOKSA birinci iddia bedavaya yeşil
olurdu, o yüzden "en az bir dosya handler'ı var" ayrıca ölçülür.

MUTASYON 2/2 — conftest'teki LOG_DIR kaldirildi -> yalitim testi kirmizi (nedensellik) ·
dosya handler'lari tamamen kapatildi -> yalniz vakum testi kirmizi (kapsam)
"""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

import app.main  # noqa: F401  — setup_logging() import anında koşar; ölçtüğümüz şey bu

KOK = Path(__file__).resolve().parent.parent
CANLI_LOG = (KOK / "logs" / "financialos.log").resolve()


def _dosya_handlerlari() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers
            if isinstance(h, logging.FileHandler)]


def test_SUIT_CANLI_LOG_dosyasina_TUTUNMAZ():
    """Bir test süreci canlı log'u açık tutarsa, canlı uygulama onu DÖNDÜREMEZ."""
    suclular = [Path(h.baseFilename).resolve() for h in _dosya_handlerlari()
                if Path(h.baseFilename).resolve() == CANLI_LOG]
    assert not suclular, (
        f"Test süreci canlı log dosyasını açık tutuyor: {CANLI_LOG}\n"
        "Windows'ta bu, canlı uygulamanın log rotasyonunu İMKÂNSIZ kılar (WinError 32) ve "
        "uygulama sessizce loglamayı bırakır — 5 Eyl 2026'da tam olarak bu oldu.\n"
        "Düzelt: `tests/conftest.py`'deki `LOG_DIR` sabiti app import'undan ÖNCE koşmalı."
    )


def test_LOG_DIR_test_icin_AYRILMIS():
    """Yalıtımın kaynağı ölçülür — davranışın 'şu an öyle' olması yetmez."""
    log_dir = os.environ.get("LOG_DIR", "")
    assert log_dir, "LOG_DIR ayarlanmamış; süit canlı log dizinine düşer (varsayılan 'logs')."
    assert Path(log_dir).resolve() != (KOK / "logs").resolve(), (
        f"LOG_DIR canlı log dizinini gösteriyor ({log_dir}); test ayrı bir dizine yazmalı."
    )


def test_KAPI_VAKUMDA_YESIL_OLAMAZ():
    """Hiç dosya handler'ı yoksa yalıtım testi bedavaya geçerdi — o yüzden varlığı ölçülür.

    Ayrıca dönen handler gerçekten döner tipte olmalı: rotasyonu olmayan bir handler,
    bu kapının anlattığı arızayı hiç üretmez ve kapı yanlış şeyi koruyor olurdu.
    """
    handlerlar = _dosya_handlerlari()
    assert handlerlar, (
        "Kök logger'da hiç dosya handler'ı yok — bu durumda yalıtım testi hiçbir şey "
        "ölçmez (vakumsal yeşil). `setup_logging()` çağrılmıyorsa kapı yanlış varsayım "
        "üzerine kurulu demektir."
    )
    assert any(isinstance(h, RotatingFileHandler) for h in handlerlar), (
        "Dosya handler'ı var ama hiçbiri DÖNER değil; bu kapının anlattığı rotasyon "
        "çakışması o hâlde oluşamaz — kapı gerçeği yansıtmıyor."
    )
