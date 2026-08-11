"""
FinancialOS Davranissal Hafiza - Tetikleme Altyapisi
====================================================

Sektor temeli:
- AsyncIOScheduler FastAPI lifespan ile ayni event loop'u paylasir (GitHub
  apscheduler discussion #830, nashruddinamin.com 2024).
- BackgroundScheduler thread overhead yaratir, gerekmiyorsa kacin.
- Olay-tetikli extractor'lar fire-and-forget asyncio.create_task ile - Coach
  response gecikmemeli.

Iki tetikleme hatti:
1. Periyodik (gece batch) - APScheduler cron jobs
   - 03:00 Istanbul: breakthrough, setback, mc_reference_frequency,
                     question_typology, category_account_preference
   - 03:30 Istanbul: explicit_red_line_k2 (K1 olay-tetiklemesinden sonra)
2. Olay-tetikli (anlik)
   - Yeni user mesaji: explicit_red_line_k1, decision_rhythm
   - PendingAction status degisikligi (rejected/executed): action_rejection_pattern

Multi-user destegi: gece batch tum aktif user'lari DB'den cekip her biri icin
extractor'lari sirayla calistirir. Bir extractor cokerse digerleri etkilenmez.

GUNCELLEMELER
-------------
BUG #240 fix (D24): planlanan 5 isten 3'u (k2_batch, nightly_trace_cleanup,
weekly_smoke_test) hicbir SchedulerRun kaydi acmiyordu — cunku kayit cagrilari iki
job'in GOVDESINE elle yazilmisti. `/api/ops/scheduler` is adlarini o tablodan
turettigi icin bu uc is UCTA HIC GORUNMUYORDU: KVKK'da soz verilen 90-gun saklama
isi haftalarca olu kalsa kimse fark etmezdi. Kayit artik yapisal — `PLANLI_ISLER`
tek kaynagi + `_izlenen_is` sarmalayicisi; govdeye tek satir yazilmasa da her
calisma kaydedilir ve planli-ama-hic-calismamis is uctan gorunur.
"""

from __future__ import annotations

import functools
import logging
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Iterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.error_tracking import temizle  # BUG #258: kalıcı çalışma kaydı maskeli yazılır
from sqlalchemy import delete
from app.models import User, ReasoningTrace, Workspace
from app.rules_engine import workspace_scope  # M73: batch job'ları personal-workspace kapsamında koşar
from app.coach_insights import (
    extract_breakthrough,
    extract_setback,
    extract_mc_reference_frequency,
    extract_question_typology,
    extract_category_account_preference,
    extract_explicit_red_line_k2,
    extract_explicit_red_line_k1,
    extract_decision_rhythm,
    extract_action_rejection_pattern,
)

logger = logging.getLogger(__name__)

# Singleton scheduler - lifespan tarafindan baslatilip durdurulacak
_scheduler: AsyncIOScheduler | None = None

# Periyodik batch icin extractor isimlerinin sirasi
NIGHTLY_BATCH_EXTRACTORS = [
    "breakthrough",
    "setback",
    "mc_reference_frequency",
    "question_typology",
    "category_account_preference",
]

# K2 ayri job - K1 olay-tetiklemesinden sonra calismali (zaman gecikmeli)
K2_BATCH_EXTRACTOR = "explicit_red_line_k2"

# Olay-tetikli extractor'lar
EVENT_TRIGGERED_AFTER_USER_MESSAGE = [
    "explicit_red_line_k1",
    "decision_rhythm",
]
EVENT_TRIGGERED_AFTER_ACTION_RESOLUTION = [
    "action_rejection_pattern",
]


@contextmanager
def _db_session() -> Iterator[Session]:
    """Scheduler job'larinin kendi DB session'i. Lifecycle scope kontrollu."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_extractor(name: str, db: Session, user_id: int) -> dict:
    """
    Tek extractor calistir, imza farklarini hide et, hata izolasyonu sagla.
    9 extractor 3 farkli imza tipi:
    - 7 tanesi: (db, user_id) -> dict
    - decision_rhythm: (db, user_id) -> None
    - explicit_red_line_k2: (db, user_id, provider=None) -> dict
    """
    try:
        if name == "breakthrough":
            return extract_breakthrough(db, user_id) or {}
        elif name == "setback":
            return extract_setback(db, user_id) or {}
        elif name == "mc_reference_frequency":
            return extract_mc_reference_frequency(db, user_id) or {}
        elif name == "question_typology":
            return extract_question_typology(db, user_id) or {}
        elif name == "category_account_preference":
            return extract_category_account_preference(db, user_id) or {}
        elif name == "explicit_red_line_k1":
            return extract_explicit_red_line_k1(db, user_id) or {}
        elif name == "explicit_red_line_k2":
            return extract_explicit_red_line_k2(db, user_id, provider=None) or {}
        elif name == "decision_rhythm":
            extract_decision_rhythm(db, user_id)
            return {"status": "completed"}  # decision_rhythm None doner, normalize
        elif name == "action_rejection_pattern":
            return extract_action_rejection_pattern(db, user_id) or {}
        else:
            return {"error": f"unknown_extractor: {name}"}
    except Exception as e:
        # BUG #062 fix (SC-001): hatada session'i temizle. Yoksa bir extractor commit'te
        # patlarsa paylaşılan db "PendingRollback"a düşer ve sonraki extractor'lar/Coach'un
        # _save_message'i sessizce/patlayarak çalışmaz (docstring'in "izolasyon" vaadi ihlaliydi).
        db.rollback()
        logger.exception(f"Extractor {name} failed for user {user_id}: {e}")
        return {"error": str(e)[:200], "extractor": name}


def _personal_workspace_id(db: Session, user_id: int) -> int | None:
    """M73: user'ın personal workspace id'si (yoksa None → köprü legacy user_id yolu).

    Coach insight'ları USER-SEVİYELİ (CoachInsight/CoachMemory'de workspace_id YOK). Batch
    bunları kişinin KENDİ finansal hayatı (personal workspace) üzerinden üretmeli; ileride
    paylaşımlı (aile) workspace eklenince o verinin kişisel insight'lara karışmaması için.
    None fallback: personal ws yoksa (test/legacy) _scope user_id'ye düşer → mevcut testler korunur."""
    ws = (db.query(Workspace)
          .filter(Workspace.owner_user_id == user_id, Workspace.is_personal.is_(True))
          .order_by(Workspace.id.asc())
          .first())
    return ws.id if ws else None


def run_periodic_batch_for_user(db: Session, user_id: int) -> dict:
    """Tek user icin gece batch extractor'larini sirayla calistir.
    Bir extractor coker diger 4'u devam eder.
    M73: personal-workspace kapsamında — scoped-model okumaları (snapshot/hesap/işlem) kişinin
    kendi verisini görür, paylaşımlı workspace verisi karışmaz."""
    results = {}
    with workspace_scope(_personal_workspace_id(db, user_id)):  # M73
        for name in NIGHTLY_BATCH_EXTRACTORS:
            results[name] = run_extractor(name, db, user_id)
    return results


def run_k2_batch_for_user(db: Session, user_id: int) -> dict:
    """K2 ayri job - K1 olay-tetikleme sonrasi calismali. M73: personal-workspace kapsamında."""
    with workspace_scope(_personal_workspace_id(db, user_id)):  # M73
        return {K2_BATCH_EXTRACTOR: run_extractor(K2_BATCH_EXTRACTOR, db, user_id)}


def _get_active_user_ids(db: Session) -> list[int]:
    """Aktif user'lari getir. Su an User tablosu is_active filtresi yok,
    tum kayitli user'lari dondur."""
    users = db.query(User).all()
    return [u.id for u in users]


def _kayit_basla(job_name: str):
    """P5.3 (BUG #203): is basladi kaydi. Izleme ASLA isi dusurmemeli -> hatalar yutulur."""
    from app.models import SchedulerRun
    try:
        db = SessionLocal()
        try:
            k = SchedulerRun(job_name=job_name,
                             started_at=datetime.utcnow())
            db.add(k)
            db.commit()
            return k.id
        finally:
            db.close()
    except Exception:
        logger.exception("[scheduler] calisma kaydi acilamadi (%s)", job_name)
        return None


def _kayit_bitir(kayit_id, ok: bool, detail: str = "") -> None:
    """Isi kapat + o is icin son 50 kaydi birak (tablo sismesin)."""
    from app.models import SchedulerRun
    if kayit_id is None:
        return
    try:
        db = SessionLocal()
        try:
            k = db.get(SchedulerRun, kayit_id)
            if k is None:
                return
            k.finished_at = datetime.utcnow()
            k.ok = ok
            # BUG #258: iş özeti hata metni taşıyabilir (dış API cevabı, bağlantı dizesi).
            # KALICI kayıt → maskeden geçer (kısaltmak maskelemek değildir).
            k.detail = temizle(detail, max_uzunluk=300) if detail else ""
            db.commit()
            eski = (db.query(SchedulerRun)
                    .filter(SchedulerRun.job_name == k.job_name)
                    .order_by(SchedulerRun.id.desc())
                    .offset(50).all())
            for e in eski:
                db.delete(e)
            if eski:
                db.commit()
        finally:
            db.close()
    except Exception:
        logger.exception("[scheduler] calisma kaydi kapatilamadi")


def _izlenen_is(job_name: str, *, yeniden_firlat: bool = False):
    """BUG #240 (D24): planlanan işin çalışma kaydını YAPISAL olarak açar/kapatır.

    Önce kayıt çağrıları job gövdelerine elle yazılıyordu; beş işten üçünde yazar bunu
    unutmuştu ve unutulduğu hiçbir yerde ölçülmüyordu. Sarmalayıcı sayesinde `PLANLI_ISLER`'e
    eklenen her iş — gövdesine tek satır bile yazılmadan — görünür olur.

    İş bir özet string döndürürse kayda `detail` olarak düşer (KVKK saklama işinin sildiği
    satır sayısı gibi doğrulanabilir kanıtlar burada yaşar). Hata: kayıt `ok=False` kapanır;
    `yeniden_firlat=False` ise akış (APScheduler) düşmez.
    """
    def dekorator(fn: Callable[[], Awaitable[Any]]) -> Callable[[], Awaitable[Any]]:
        @functools.wraps(fn)
        async def sarmal(*args, **kwargs):
            kayit_id = _kayit_basla(job_name)
            try:
                sonuc = await fn(*args, **kwargs)
            except Exception as e:
                logger.exception("[scheduler] %s basarisiz", job_name)
                # BUG #248 (D37): kayda YALNIZ istisna TİPİ yazılıyordu ("RuntimeError") —
                # operatör uçtan bakınca ne olduğunu anlayamıyor, log dosyasına inmek zorunda
                # kalıyordu. Mesaj da yazılır; PII/sır maskesinden geçirilerek (BUG #244).
                from app.error_tracking import temizle
                _kayit_bitir(kayit_id, False,
                             temizle(f"{type(e).__name__}: {e}", max_uzunluk=280))
                if yeniden_firlat:
                    raise
                return None
            _kayit_bitir(kayit_id, True, sonuc if isinstance(sonuc, str) else "")
            return sonuc

        sarmal._izlenen_is_adi = job_name  # kapsam kapısı bunu okur (tests/test_scheduler_kayit_kapisi.py)
        return sarmal
    return dekorator


@_izlenen_is("nightly_batch")
async def nightly_batch_job() -> str:
    """APScheduler cron job - gece 03:00 calisir, tum user'lar icin batch."""
    logger.info(f"Nightly batch job started at {datetime.utcnow().isoformat()}")
    with _db_session() as db:
        user_ids = _get_active_user_ids(db)
        for uid in user_ids:
            results = run_periodic_batch_for_user(db, uid)
            logger.info(f"Nightly batch for user {uid}: {results}")
    logger.info(f"Nightly batch job completed at {datetime.utcnow().isoformat()}")
    return f"{len(user_ids)} kullanici"


@_izlenen_is("k2_batch")
async def k2_batch_job() -> str:
    """APScheduler cron job - gece 03:30, K2 LLM consolidation."""
    logger.info(f"K2 batch job started at {datetime.utcnow().isoformat()}")
    with _db_session() as db:
        user_ids = _get_active_user_ids(db)
        for uid in user_ids:
            results = run_k2_batch_for_user(db, uid)
            logger.info(f"K2 batch for user {uid}: {results}")
    logger.info(f"K2 batch job completed at {datetime.utcnow().isoformat()}")
    return f"{len(user_ids)} kullanici"


@_izlenen_is("nightly_trace_cleanup", yeniden_firlat=True)
async def nightly_trace_cleanup_job() -> str:
    """
    Reasoning trace retention job.

    Deletes ReasoningTrace rows older than 90 days. Runs at 04:00
    Istanbul daily (after nightly_batch and k2_batch). 90-day
    retention follows the warm-tier convention used by Langfuse
    and similar LLM observability stacks — long enough for audit
    and debugging, short enough to keep the single-file SQLite
    database lean. Idempotent: re-running has no effect if the
    table is already trimmed.

    BUG #240: silinen satır sayısı çalışma kaydına düşer — KVKK'da verilen 90-gün
    saklama sözü ancak SAYIYLA doğrulanabilir (log okumak kanıt değildir).
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        stmt = delete(ReasoningTrace).where(
            ReasoningTrace.created_at < cutoff
        )
        result = db.execute(stmt)
        db.commit()
        deleted = result.rowcount or 0
        logger.info(
            "[trace_cleanup] removed %d reasoning_trace rows older than %s",
            deleted,
            cutoff.isoformat(),
        )
        return f"{deleted} trace silindi (90 gun)"   # BUG #240
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("[trace_cleanup] failed; rolled back transaction")
        raise
    finally:
        db.close()


@_izlenen_is("fetch_investment_prices")
async def fetch_investment_prices_job() -> str:
    """
    Günlük yatırım fiyat çekimi (M4 / ADR-029). Tüm `investment` hesaplarının fiyatını
    çeker (fund_code → TEFAS/pytefas), `Account.current_price` + `PriceHistory` günceller.
    Idempotent (ADR-012 kompozit PK). Gece **02:45** — nightly_batch (03:00) ÖNCESİ, böylece
    batch analizi/cockpit taze fiyatla çalışır. TEFAS ~18:00 yayınladığından sabah dünün fiyatı.
    """
    from app.price_providers import fetch_for_account, record_investment_price
    from app.models import Account, AccountType
    db = SessionLocal()
    try:
        accounts = db.query(Account).filter(Account.account_type == AccountType.investment).all()  # scope-exempt: SİSTEM cron'u — piyasa fiyatı tüm kullanıcıların yatırım hesapları için tazelenir (kullanıcı verisi okunmaz/karışmaz)
        updated = 0
        for acc in accounts:
            try:
                res = fetch_for_account(acc)
            except Exception:
                logger.exception("[price] %s (%s) çekim hatası", acc.name, acc.fund_code)
                res = None
            if res:
                price, source = res
                record_investment_price(db, acc, price, source)
                updated += 1
                logger.info("[price] %s (%s) = %s [%s]", acc.name, acc.fund_code, price, source)
            else:
                logger.warning("[price] %s (%s): fiyat çekilemedi (elle giriş gerekebilir)",
                               acc.name, acc.fund_code)
        logger.info("[price] %d/%d yatırım hesabı güncellendi", updated, len(accounts))
        # BUG #248 fix (D37): "iş çökmedi" ile "iş işini yaptı" AYNI ŞEY DEĞİL. Eskiden
        # sağlayıcıların HEPSİ çökse bile (0/N) iş `ok=True` kaydediyordu → /api/ops/scheduler
        # "son başarılı: bu sabah" der, `sorunlu_isler`'e düşmez ve kesinti operatörden
        # haftalarca gizlenir (fiyatlar bayatlar, koç bayat değerle konuşur — BUG #239).
        # Hesap YOKSA (0/0) başarı meşrudur: yapılacak iş yoktu.
        if accounts and updated == 0:
            raise RuntimeError(
                f"0/{len(accounts)} hesap güncellendi — fiyat sağlayıcılarının hiçbiri "
                "yanıt vermedi (TEFAS/İş Yatırım/EVDS kesintisi ya da kod/ağ sorunu)")
        return f"{updated}/{len(accounts)} hesap guncellendi"
    except Exception:
        db.rollback()   # BUG #240: kayıt sarmalayıcıya bırakıldı, oturum temizliği burada kalır
        raise
    finally:
        db.close()


@_izlenen_is("weekly_smoke_test")
async def weekly_smoke_test_job() -> str:
    """
    M37 (Wave-4) — Haftalık dış API canlı smoke testi (pazartesi 05:00 Istanbul).

    Ders 11: "pytest yeşil ≠ canlı çalışıyor" (M19 EVDS regression'ı mock-yeşilken ölüydü).
    Her dış API'ye (EVDS/SMTP/OAuth google+github) GERÇEK smoke atar; başarısızlıkları
    `.mcp-sync-pending.log`'a `SMOKE_FAIL:<api>` olarak yakalar (scheduler MCP'ye doğrudan
    yazamaz → M24 capture→flush; asistan araci oturum başında flush eder). Akışı bozmaz.
    """
    from app.services.smoke_tests import run_all_smoke_tests, capture_smoke_failures
    logger.info("[smoke] haftalık smoke test başladı %s", datetime.utcnow().isoformat())
    results = run_all_smoke_tests()
    for r in results:
        level = logger.info if r["ok"] else logger.warning
        level("[smoke] %s %s: %s", "OK" if r["ok"] else "FAIL", r["api"], r["detail"])
    captured = capture_smoke_failures(results)
    if captured:
        logger.warning("[smoke] %d başarısızlık ledger'a yakalandı (SMOKE_FAIL)", captured)
    return f"{len(results)} api, {captured} basarisiz"


@dataclass(frozen=True)
class PlanliIs:
    """Zamanlanmış işin TEK kaynağı: hem APScheduler hem görünürlük ucu bunu okur.

    `beklenen_periyot_saat` "bu iş ne sıklıkla koşmalı" sorusunun makine-okunur cevabı —
    `/api/ops/scheduler` bayat kalmış işi (gecikti) bununla işaretler. Kayıt tek başına
    yetmez: kimse bakmazsa haftalarca koşmamış iş yine sessizce ölür.
    """
    ad: str
    fonksiyon: Callable[[], Awaitable[Any]]
    cron: dict
    beklenen_periyot_saat: float


# BUG #240 (D24): planlı işlerin TEK KAYNAĞI. Yeni iş buraya eklenir; `add_job` doğrudan
# çağrılmaz (kapsam kapısı: tests/test_scheduler_kayit_kapisi.py).
PLANLI_ISLER: tuple[PlanliIs, ...] = (
    PlanliIs("fetch_investment_prices", fetch_investment_prices_job,
             {"hour": 2, "minute": 45}, 24),
    PlanliIs("nightly_batch", nightly_batch_job, {"hour": 3, "minute": 0}, 24),
    PlanliIs("k2_batch", k2_batch_job, {"hour": 3, "minute": 30}, 24),
    PlanliIs("nightly_trace_cleanup", nightly_trace_cleanup_job, {"hour": 4, "minute": 0}, 24),
    PlanliIs("weekly_smoke_test", weekly_smoke_test_job,
             {"day_of_week": "mon", "hour": 5, "minute": 0}, 168),  # M37: haftalık dış API smoke
)


@dataclass(frozen=True)
class DisPlanliIs:
    """Uygulama SÜRECİ DIŞINDA koşan ama aynı uçtan izlenen iş (compose servisi / timer).

    BUG #240 sınıf taraması: prod yedeği de yalnız konteyner log'una yazıyordu. Yedek,
    beta verisinin tek kopyası — sessizce ölmesi cron'un ölmesinden ağırdır. Kaydı işin
    kendisi yazar (`deploy/pg_backup.sh`), burada yalnız "beklenen" tarafı tanımlıdır:
    kayıt hiç gelmiyorsa uç bunu `hic_calismadi`/`gecikti` olarak söyler.
    """
    ad: str
    beklenen_periyot_saat: float
    yazan: str


DIS_PLANLI_ISLER: tuple[DisPlanliIs, ...] = (
    DisPlanliIs("pg_backup", 24, "deploy/pg_backup.sh"),
)


def start_scheduler() -> AsyncIOScheduler:
    """Lifespan startup'tan cagirilir."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")

    for plan in PLANLI_ISLER:   # BUG #240: elle add_job YOK — liste tek kaynak
        _scheduler.add_job(
            plan.fonksiyon,
            CronTrigger(**plan.cron),
            id=plan.ad,
            replace_existing=True,
            misfire_grace_time=3600,   # 1 saat icinde gecikirse yine calistir
        )

    _scheduler.start()
    logger.info("FinancialOS scheduler started: prices 02:45, nightly_batch 03:00, k2_batch 03:30, "
                "trace_cleanup 04:00, smoke pazartesi 05:00 Istanbul")
    return _scheduler


async def kacirilan_isleri_telafi_et() -> str:
    """Açılışta: beklenen periyodunu aşmış planlı işleri ŞİMDİ koştur.

    BUG #302 — NEDEN GEREKLİ: `misfire_grace_time=3600` bir işi yalnız **1 saat**
    gecikmeye kadar kurtarır; daha fazlası sessizce atlanır ve bir daha koşmaz. Bu,
    7/24 açık bir sunucuda makul bir varsayımdır — ama kapalı beta **kişisel bir Windows
    makinesinde** koşuyor ve o makine her gece açık kalmaz. Gece 02:45–04:00 penceresi
    uykuda geçtiğinde şunlar o gün HİÇ koşmuyordu:
      · yatırım fiyatları güncellenmiyor → kullanıcı bayat fiyattan net değer görüyor
        (BUG #239 sınıfı: sayı yanlış değil ama DAYANAĞI bayat)
      · gece batch'i (uyarılar, periyodik hesaplar) atlanıyor
      · iz temizliği atlanmıyor → 90 günlük saklama sözü kendiliğinden tutulmuyor (KVKK)

    Veri zaten vardı ama kimse EYLEM almıyordu: `beklenen_periyot_saat` tanımlı ve
    `/api/ops/scheduler` işi "gecikti" diye işaretliyordu — bakan olmadıkça hiçbir şey
    değişmiyor (bu turun tekrar eden dersi). Telafi o ölçümü eyleme çevirir.

    Tasarım kararları:
      · Açılışı BLOKLAMAZ (çağıran `create_task` ile arka plana atar) — kullanıcı
        uygulamayı açtığında gece işini bekliyor olmamalı.
      · İşler SIRAYLA koşar: dördü aynı anda DB havuzunu zorlar (BUG #263 kapasite).
      · Ölçüt son BAŞARILI koşumdur; başarısız deneme işi "koşmuş" saymaz.
      · Her iş `_izlenen_is` ile sarılı olduğu için telafi koşumu da deftere yazılır ve
        hatası yutulur — biri patlarsa diğerleri koşmaya devam eder.
      · İdempotenslik çağıranın değil işlerin sorumluluğu; recurring tetikleyicileri
        `last_triggered_year_month` ile zaten korumalı, fiyat/temizlik yazımı tekrarlanabilir.
    """
    from sqlalchemy import func
    from app.models import SchedulerRun

    simdi = datetime.utcnow()
    kosulan: list[str] = []
    with _db_session() as db:
        gecikenler = []
        for plan in PLANLI_ISLER:
            son_ok = (db.query(func.max(SchedulerRun.finished_at))
                      .filter(SchedulerRun.job_name == plan.ad,
                              SchedulerRun.ok.is_(True))
                      .scalar())
            if son_ok is None or (simdi - son_ok) > timedelta(hours=plan.beklenen_periyot_saat):
                gecikenler.append((plan, son_ok))

    for plan, son_ok in gecikenler:
        yas = "hiç koşmamış" if son_ok is None else f"{(simdi - son_ok).total_seconds() / 3600:.1f} saat önce"
        logger.info("[telafi] %s gecikmiş (%s) — şimdi koşuyor", plan.ad, yas)
        try:
            await plan.fonksiyon()      # `_izlenen_is` kaydı açar/kapatır, hatayı yutar
            kosulan.append(plan.ad)
        except Exception:               # yeniden-fırlatan bir iş diğerlerini düşürmesin
            logger.exception("[telafi] %s koşulamadı", plan.ad)

    ozet = f"{len(kosulan)}/{len(PLANLI_ISLER)} is telafi edildi" + (
        f": {', '.join(kosulan)}" if kosulan else " (hepsi guncel)")
    logger.info("[telafi] %s", ozet)
    return ozet


def shutdown_scheduler() -> None:
    """Lifespan shutdown'tan cagirilir."""
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("FinancialOS scheduler shut down")
        _scheduler = None


# ============================================================
# Olay-tetikli extractor cagrilari (Coach + ActionExecutor'dan kullanilacak)
# ============================================================

def trigger_after_user_message(db: Session, user_id: int) -> None:
    """
    Coach._save_message user role kaydi sonrasinda cagrilir.
    explicit_red_line_k1 + decision_rhythm sirayla calistirir, sync.
    Hata izolasyonu: cokerse Coach response'u etkilemez.

    NOT: Su an sync, Coach.chat() icinden cagrilacak. Performance sorunu olursa
    asyncio.create_task ile fire-and-forget'e cevirilebilir.
    """
    for name in EVENT_TRIGGERED_AFTER_USER_MESSAGE:
        try:
            run_extractor(name, db, user_id)
        except Exception as e:
            logger.warning(f"Event-triggered {name} failed for user {user_id}: {e}")


def trigger_after_action_resolution(db: Session, user_id: int) -> None:
    """
    PendingAction status degisikligi (rejected/executed) sonrasinda cagrilir.
    action_rejection_pattern calistirir.
    """
    for name in EVENT_TRIGGERED_AFTER_ACTION_RESOLUTION:
        try:
            run_extractor(name, db, user_id)
        except Exception as e:
            logger.warning(f"Event-triggered {name} failed for user {user_id}: {e}")
