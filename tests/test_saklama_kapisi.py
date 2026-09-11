"""
DATA-032 / BUG #383 KAPISI — BÜYÜYEN TABLOLARIN SAKLAMA KURALI YOKTU.

Ölçülen (11 Eyl 2026, canlı beta DB'si, 40 günlük veri): `revoked_tokens` 103 satır,
**74'ü süresi dolmuş** — `expires_at` sütunu "temizlik için" konmuş (auth.py docstring'i
öyle der) ama hiçbir kod okumuyordu. `api_call_log` 311, `scheduler_runs` 127 satır,
ikisinde de retention yok. Yalnız `reasoning_traces` 90 günde budanıyordu; backlog bunu
60+ gündür "kısmen" taşıyordu.

Kilitlenen: `SAKLAMA_KURALLARI` tek kaynak; gece işi her kuralı uygular ve tablo başına
silinen SAYIYI çalışma kaydına yazar (BUG #240). Kural kümesi ölçülen dört tabloyu kapsar;
muaf tablolar (kendi penceresini budayan `rate_limit_hits`, parmak iziyle birleşen
`error_logs`) gerekçesiyle burada yazılıdır — sessiz muafiyet yok (L45).
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import scheduler
from app.models import (
    ApiCallLog, ApiCallStatus, Base, OperationName, ReasoningTrace, RevokedToken, SchedulerRun, User,
)

SIMDI = datetime(2026, 9, 11, 12, 0, 0)
# Zaman sütunu taşıyıp kural gerektirmeyen tablolar — gerekçesiz eklenmez.
MUAF = {
    "rate_limit_hits": "kendi penceresini kendisi budar (app/rate_limit.py)",
    "error_logs": "parmak iziyle birleşir; satır sayısı farklı hata sayısıyla sınırlı",
}


@pytest.fixture
def Session(monkeypatch):
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    fabrika = sessionmaker(bind=eng)
    monkeypatch.setattr(scheduler, "SessionLocal", fabrika)
    return fabrika


def _tohum(s, simdi=SIMDI):
    """Her tablo için eşiğin iki yanında birer satır; `simdi` gerçek saatle de çağrılabilir."""
    u = User(name="u1"); s.add(u); s.commit()
    eski, taze = simdi - timedelta(days=91), simdi - timedelta(days=89)
    s.add_all([
        ReasoningTrace(user_id=u.id, trace_id="t-eski", step_index=0,
                       operation_name=OperationName.LLM_CALL, created_at=eski),
        ReasoningTrace(user_id=u.id, trace_id="t-taze", step_index=0,
                       operation_name=OperationName.LLM_CALL, created_at=taze),
        ApiCallLog(user_id=u.id, provider="gemini", model="m", status=ApiCallStatus.success, called_at=eski),
        ApiCallLog(user_id=u.id, provider="gemini", model="m", status=ApiCallStatus.success, called_at=taze),
        SchedulerRun(job_name="x", started_at=eski, ok=True),
        SchedulerRun(job_name="x", started_at=taze, ok=True),
        # süresi dolmuş / dolmamış token: gün=0 → yalnız `expires_at < şimdi` silinir
        RevokedToken(jti="dolmus", revoked_at=eski, expires_at=simdi - timedelta(hours=1)),
        RevokedToken(jti="canli", revoked_at=taze, expires_at=simdi + timedelta(hours=1)),
    ])
    s.commit()


def test_kurallar_olculen_dort_tabloyu_kapsar():
    assert {k.tablo for k in scheduler.SAKLAMA_KURALLARI} == {
        "reasoning_traces", "api_call_log", "scheduler_runs", "revoked_tokens", "audit_log"}
    assert {k.gun for k in scheduler.SAKLAMA_KURALLARI if k.tablo not in ("revoked_tokens", "audit_log")} == {90}, (
        "90 gün KVKK metnindeki akıl-yürütme sözüyle aynı — değişecekse metin de değişir")
    assert next(k for k in scheduler.SAKLAMA_KURALLARI if k.tablo == "audit_log").gun == 365   # BUG #408: bir mali yıl
    assert next(k for k in scheduler.SAKLAMA_KURALLARI if k.tablo == "revoked_tokens").gun == 0


def test_her_kural_yalniz_esigi_asan_satiri_siler(Session):
    s = Session(); _tohum(s)
    silinen = scheduler.saklama_uygula(s, simdi=SIMDI); s.commit()
    assert silinen == {"reasoning_traces": 1, "api_call_log": 1,
                       "scheduler_runs": 1, "revoked_tokens": 1, "audit_log": 0}, silinen
    assert [t.trace_id for t in s.query(ReasoningTrace).all()] == ["t-taze"]
    assert s.query(ApiCallLog).count() == 1
    assert s.query(SchedulerRun).count() == 1
    assert [t.jti for t in s.query(RevokedToken).all()] == ["canli"]
    # idempotent
    assert set(scheduler.saklama_uygula(s, simdi=SIMDI).values()) == {0}
    s.close()


def test_gece_isi_sayilari_calisma_kaydina_yazar(Session):
    """BUG #240: KVKK sözü sayıyla kanıtlanır — dönen metin her tabloyu sayısıyla anar."""
    # İş gerçek saati kullanır → tohum da gerçek saate göre (sabit tarih zamanla bayatlar)
    s = Session(); _tohum(s, simdi=datetime.utcnow()); s.close()
    ozet = asyncio.run(scheduler.nightly_trace_cleanup_job())
    for tablo in ("reasoning_traces=1", "api_call_log=1", "scheduler_runs=1", "revoked_tokens=1"):
        assert tablo in ozet, ozet
    s = Session()
    kayit = s.query(SchedulerRun).filter(SchedulerRun.job_name == "nightly_trace_cleanup").one()
    assert kayit.ok is True and "revoked_tokens=1" in (kayit.detail or "")
    s.close()


def test_zaman_sutunlu_her_tablo_ya_kuralda_ya_gerekceli_muaf():
    """Yeni bir günlük tablosu (örn. `*_log`, `*_runs`, `*_hits`) sessizce sınırsız büyümesin."""
    kuralli = {k.tablo for k in scheduler.SAKLAMA_KURALLARI}
    adaylar = {
        t.name for t in Base.metadata.sorted_tables
        if t.name.endswith(("_log", "_logs", "_runs", "_hits", "_traces", "_tokens"))
    }
    assert adaylar, "aday tablo bulunamadı — desen bozuk (L45)"
    eksik = adaylar - kuralli - set(MUAF)
    assert eksik == set(), f"saklama kuralı olmayan günlük tablosu: {eksik} — kural ya da gerekçeli muafiyet ekle"
    assert set(MUAF) <= {t.name for t in Base.metadata.sorted_tables}, "muaf listesinde olmayan tablo var"
