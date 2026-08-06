"""
KALICI HATA METNİ MASKELEME KAPISI (BUG #258 / SEC-009 + SEC-016).

ÖLÇÜLEN DEFEKT (7 Ağu 2026)
---------------------------
`error_tracking.temizle()` vardı ve BUG #244 ile LOG zincirine bağlanmıştı. Ama **DB'ye
KALICI yazan üç yol maskesizdi**:

  * `app/llm_quota.tamamla` → `ApiCallLog.error_message` (`error_message[:300]`)
  * `app/reasoning_trace` → `reasoning_traces.error` (`str(exc)[:500]`)
  * `app/scheduler._kayit_bitir` → `scheduler_runs.detail` (`(detail or "")[:300]`)

Üçü de yalnız KISALTIYORDU. **Kısaltmak maskelemek değildir** — sağlayıcı istisnaları
isteğin kendisini taşır (`...?key=AIza...`, `Bearer ...`, SMTP bağlantı dizesi). Bu metin
`ApiCallLog` üzerinden **KVKK dışa aktarımına** da giriyordu.

Aynı zamanda ikinci bir körlük: maske listesi ETİKETE bakıyordu (`api_key=`), anahtarın
KENDİ ŞEKLİNE değil. `?key=AIza...` içindeki "key" kelimesi `api_key` değildir → geçiyordu.

Bu kapı üç yazma sınırını da davranışla ölçer.
"""
from __future__ import annotations

import pytest

from app.error_tracking import temizle


# ------------------------------------------------------- 1. değerin şekli tanınıyor mu

@pytest.mark.parametrize("ham,gizlenmeli", [
    ("Gemini 400: https://generativelanguage.googleapis.com/v1/models?key=AIzaSyD1234567890abcdefghij",
     "AIzaSyD1234567890abcdefghij"),
    ("openai auth failed: sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345", "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"),
    ("groq 401 gsk_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123", "gsk_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"),
    ("cerebras: csk-ABCDEFGHIJKLMNOPQRSTUVWX0123456", "csk-ABCDEFGHIJKLMNOPQRSTUVWX0123456"),
    ("smtp baglanti hatasi: smtp://kullanici:GizliParola123@smtp-relay.example.com",
     "GizliParola123"),
    ("brevo: xsmtpsib-ABCDEFGHIJKLMNOPQRSTUVWXYZ01", "xsmtpsib-ABCDEFGHIJKLMNOPQRSTUVWXYZ01"),
])
def test_anahtar_sekli_etiketsiz_de_maskelenir(ham, gizlenmeli):
    temiz = temizle(ham)
    assert gizlenmeli not in temiz, f"sır maskelenmedi: {temiz}"


def test_masum_metin_bozulmaz():
    """L6: kapı ürünü kıramaz — teşhis için gereken bilgi kalmalı."""
    ham = "Gemini 429: quota exceeded for model gemini-2.0-flash-lite (retry in 30s)"
    temiz = temizle(ham)
    assert "429" in temiz and "gemini-2.0-flash-lite" in temiz and "quota" in temiz


# --------------------------------------------------- 2. KALICI yazma sınırları maskeli mi

def test_apicalllog_error_message_maskeli_yazilir(db_session, test_user):
    """`ApiCallLog.error_message` KVKK export'una girer — ham sır taşıyamaz."""
    from app import llm_quota
    from app.models import ApiCallLog

    log = llm_quota.rezerve_et(db_session, test_user.id, "gemini", "test-model")
    llm_quota.tamamla(
        db_session, log, provider="gemini", success=False,
        error_message="401 https://api.example.com/v1?key=AIzaSyD1234567890abcdefghij",
    )
    db_session.refresh(log)
    kayit = db_session.query(ApiCallLog).filter(ApiCallLog.id == log.id).one()
    assert "AIzaSyD1234567890abcdefghij" not in (kayit.error_message or "")
    assert "401" in (kayit.error_message or ""), "teşhis bilgisi tamamen silinmemeli"


def test_scheduler_detail_maskeli_yazilir(monkeypatch):
    """`scheduler_runs.detail` operatöre gösterilir + KVKK saklama işinin özetini taşır."""
    import app.scheduler as sch

    yazilan = {}

    class _SahteKayit:
        id = 1
        finished_at = None
        ok = None
        detail = None

    class _SahteSorgu:
        def __init__(self, kayit):
            self._k = kayit

        def filter(self, *a, **k):
            return self

        def first(self):
            return self._k

        def get(self, *a, **k):
            return self._k

        def order_by(self, *a, **k):
            return self

        def offset(self, *a, **k):
            return self

        def all(self):
            return []

    kayit = _SahteKayit()

    class _SahteDB:
        def query(self, *a, **k):
            return _SahteSorgu(kayit)

        def get(self, *a, **k):
            return kayit

        def commit(self):
            yazilan["detail"] = kayit.detail

        def rollback(self):
            pass

        def close(self):
            pass

        def delete(self, *a, **k):
            pass

    monkeypatch.setattr(sch, "SessionLocal", lambda: _SahteDB())
    sch._kayit_bitir(1, True, "fiyat cekildi: https://x/api?key=AIzaSyD1234567890abcdefghij")
    assert "AIzaSyD1234567890abcdefghij" not in (yazilan.get("detail") or kayit.detail or "")


def test_reasoning_trace_hatasi_maskeli(db_session, test_user):
    """`reasoning_traces.error` kalıcıdır ve koç hata ayıklamasında okunur."""
    from app.models import OperationName
    from app.reasoning_trace import TraceRecorder

    rec = TraceRecorder(db_session, user_id=test_user.id)
    try:
        with rec.step(OperationName.LLM_CALL, intent="test"):
            raise RuntimeError("provider hatasi: Bearer eyJabcdefghijklmnop.qrstuv.wxyz")
    except RuntimeError:
        pass

    from app.models import ReasoningTrace
    izler = db_session.query(ReasoningTrace).all()
    hatali = [i for i in izler if i.error]
    assert hatali, "iz kaydı yazılmadı — test ölçtüğünü bulamıyor"
    for iz in hatali:
        assert "eyJabcdefghijklmnop" not in iz.error, f"ham token kalıcı kayda düştü: {iz.error}"


# ----------------------------------------------------------- 3. kapsam (L11): yeni yol

def test_kalici_hata_yollarinin_hepsi_maskeden_geciyor():
    """
    Statik kapsam: KALICI hata metni yazan modüller `temizle` import etmeli. Yeni bir
    kalıcı yol eklenip maskesiz bırakılırsa bu kapı kırılır (kapsamsız kapı = ölü kapı).
    """
    from pathlib import Path

    kok = Path(__file__).resolve().parent.parent.parent
    beklenen = ["app/llm_quota.py", "app/reasoning_trace.py", "app/scheduler.py"]
    eksik = []
    for rel in beklenen:
        kaynak = (kok / rel).read_text(encoding="utf-8")
        if "temizle" not in kaynak:
            eksik.append(rel)
    assert not eksik, f"kalıcı hata yazan modül maskeden geçmiyor: {eksik}"
    assert len(beklenen) >= 3, "kapsam tabanı düştü"
