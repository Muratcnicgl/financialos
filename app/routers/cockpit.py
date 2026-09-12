"""
Cockpit endpoint (1):
- GET /api/cockpit         - Tum rules_engine snapshot + uyari motoru sonucu

Bu endpoint frontend'in ANA panel'inin tek bilgi kaynagi. Tek bir cagrida:
- Ana gostergeler (nakit/kart/kredi/yatirim/emanet/net deger/reel butce)
- Hesap detaylari (id ile listelenir)
- Yatirim K/Z (TLY +13.127 gibi)
- Yaklasan odemeler ve tahsilatlar
- Otomatik uyarilar
- Bayatlik bilgisi (Wave-1 mukemmellestirici): yatirim hesaplari icin fiyat yasi

NOT (2 Mayis 2026 fix #001): get_freshness_summary'nin gercek imzasi (db, user_id)
\u2014 onceki versiyonda (user_id, db) yazmistim, 'int has no attribute query' hatasi
veriyordu. Imza dogrulandi, fix uygulandi. Try/except yine kaldi cunku DB'de
hicbir yatirim hesabi yoksa veya beklenmedik bir sey olursa cockpit calismaya
devam etmeli.
"""

import logging
from datetime import date, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.user_prefs import user_today  # BUG #197: kullanici saat dilimi
from app.dependencies import get_db, get_current_user
from app.workspace_deps import active_workspace_id  # M43
from app.models import User, NetWorthSnapshot
from app.rules_engine import generate_cockpit, workspace_scope  # M43
from app.fund_tracker import get_freshness_summary
from typing import Optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cockpit", tags=["cockpit"])


# BUG #429 (DVIZ-005): dönem karşılaştırma bazı için "ay başı" toleransı (gün).
# Ay başında snapshot yoksa (gece işi kaçmış, kayıt ayın 1'inde başlamamış) 1'inden en çok bu
# kadar önceki son snapshot "ay başı" sayılır; o da yoksa bugünden önceki EN ESKİ snapshot
# baz olur ve etiket gerçek tarihi söyler. Baz yoksa alan None döner — sıfır değil (L45).
AY_BASI_TOLERANSI_GUN = 7

DEGISIM_ALANLARI = (
    ("nakit_kasa", "cash"),
    ("kart_borcu", "card_debt"),
    ("kredi_borcu", "loan_debt"),
    ("yatirim_deger", "investment_value"),
    ("net_deger", "net_worth_seen"),
    ("net_deger_tam", "net_worth_full"),
)


def _baz_snapshot(db: Session, user_id: int, workspace_id: Optional[int], today: date):
    """Dönem karşılaştırmasının bazı: (snapshot, ay_basi_mi) — ay başı (toleranslı), yoksa en eski."""
    ay_basi = today.replace(day=1)
    q = db.query(NetWorthSnapshot)
    q = q.filter(NetWorthSnapshot.workspace_id == workspace_id) if workspace_id is not None         else q.filter(NetWorthSnapshot.user_id == user_id)  # scope-exempt: snapshot legacy fallback (ws_id None branch)
    # Bugün ayın 1'iyse bugünün (ilk istekte yazılan) snapshot'ı baz olmasın → hep `< today`.
    q = q.filter(NetWorthSnapshot.snapshot_date < today)
    ay_basi_baz = (q.filter(NetWorthSnapshot.snapshot_date <= ay_basi,
                            NetWorthSnapshot.snapshot_date >= ay_basi - timedelta(days=AY_BASI_TOLERANSI_GUN))
                   .order_by(NetWorthSnapshot.snapshot_date.desc()).first())
    if ay_basi_baz is not None:
        return ay_basi_baz, True
    return q.order_by(NetWorthSnapshot.snapshot_date.asc()).first(), False


def _donem_degisimi(db: Session, user_id: int, workspace_id: Optional[int],
                    cockpit: dict, today: date) -> Optional[dict]:
    """BUG #429 (DVIZ-005): kartların "ay başından beri" farkı.

    Ölçülen (12 Eyl 2026): `NetWorthSnapshot` geçmişi günlerdir birikiyordu ama kokpit
    kartları yalnız mutlak değer taşıyordu; "kart borcu geçen aya göre düştü mü" sorusunun
    cevabı yalnız Raporlar'daki eğri üzerinden okunabiliyordu. Fark burada, bugünün canlı
    değeri ile BUGÜNDEN ÖNCEKİ bir snapshot arasında hesaplanır (bugünün snapshot'ı henüz
    yazılmamış ya da bayat olabilir; canlı değer her zaman `cockpit`).
    """
    baz, ay_basi_mi = _baz_snapshot(db, user_id, workspace_id, today)
    if baz is None:
        return None
    farklar = {ck: round(float(cockpit.get(ck, cockpit["net_deger"])) - float(getattr(baz, sk)), 2)
               for ck, sk in DEGISIM_ALANLARI}
    return {
        "baz_tarih": baz.snapshot_date.isoformat(),
        "gun": (today - baz.snapshot_date).days,
        "ay_basi": ay_basi_mi,
        **farklar,
    }


def _ensure_today_snapshot(db: Session, user_id: int, cockpit: dict,
                           workspace_id: Optional[int] = None,
                           today: Optional[date] = None) -> None:
    """Bugünkü net değer snapshot'ını GÜNCEL tut — o günün SON BİLİNEN durumu (upsert).

    BUG #292 fix: eskiden `if q.first(): return` vardı — yani "o gün kayıt varsa dokunma"
    (create-once). Yeni kullanıcı paneli ilk açtığında henüz hiçbir hesabı yoktur; o günün
    snapshot'ı 0 yazılıyor, aynı gün verisini girdiğinde GÜNCELLENMİYORDU. Ertesi gün
    `catch_up_snapshots` yalnız EKSİK günleri doldurduğu için kayıt gününün net değeri
    KALICI olarak 0 kalıyordu. Canlı beta ölçümü (11 Ağu 2026): üç kullanıcının üçünde de
    grafikte 0 — gerçek değerler 7.313 / 20.354 / 10.350 TL. Yan etkisi: `coach_insights`
    trendi ve FEAT-017 borç ilerlemesi EN ESKİ snapshot'ı baz alır → sahte 0'dan bugüne
    "net değerin arttı" denebiliyordu.

    Sözleşme: bir günü temsil eden kayıt o gün BİTMEDEN yazılıyorsa create-once yanlış
    cevaptır (L53). Geçmiş günlere dokunulmaz; değer değişmediyse DB'ye yazılmaz (cockpit
    her panel açılışında çağrılır — değişmemiş değer için UPDATE boşuna yüktür).
    """
    # BUG #237 fix (D17): snapshot SUNUCU gününü damgalıyordu; aynı istekte cockpit ise
    # kullanıcının gününü kullanıyordu (istek kendi içinde tutarsız) → trend grafiği
    # kullanıcının gördüğü günle hizasız kalıyordu. Gün artık çağırandan gelir.
    today = today or date.today()  # tz-exempt: çağıran kullanıcının gününü geçirir (aşağıdaki uç)
    # M43: workspace varsa o workspace'in snapshot'ı, yoksa legacy user snapshot'ı
    q = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.snapshot_date == today)
    q = q.filter(NetWorthSnapshot.workspace_id == workspace_id) if workspace_id is not None \
        else q.filter(NetWorthSnapshot.user_id == user_id)  # scope-exempt: snapshot legacy fallback (ws_id None branch)
    mevcut = q.first()

    # BUG #117 fix (#116 takibi): net_deger_tam artık payable de düşüyor → (net_deger_tam −
    # net_deger) = alacak − borç olurdu (yanlış "receivables"). Alacağı doğrudan cockpit'ten al.
    receivables = cockpit.get("alacaklar_toplami",
                              max(0.0, cockpit.get("net_deger_tam", cockpit["net_deger"]) - cockpit["net_deger"]))
    degerler = {
        "net_worth_seen": cockpit["net_deger"],
        "net_worth_full": cockpit.get("net_deger_tam", cockpit["net_deger"]),
        "cash": cockpit["nakit_kasa"],
        "card_debt": cockpit["kart_borcu"],
        "loan_debt": cockpit["kredi_borcu"],
        "investment_value": cockpit["yatirim_deger"],
        "receivables": receivables,
    }

    if mevcut is None:
        db.add(NetWorthSnapshot(user_id=user_id, workspace_id=workspace_id,  # M43
                                snapshot_date=today, **degerler))
        try:
            db.commit()
            return
        except IntegrityError:
            # BUG #378 — BAK-SONRA-YAZ YARIŞI. Aynı gün için iki EŞ ZAMANLI kokpit isteği
            # (canlıda ölçüldü, 10 Eyl 23:30:09 ve :12, iki ayrı istek kimliği) ikisi de
            # `mevcut is None` gördü, ikisi de INSERT etti; ikincisi
            # `UNIQUE (user_id, snapshot_date)` ile düştü ve uyarı olarak loglandı.
            # Yarışı kaybetmek bir hata DEĞİLDİR: kazanan satırı yazdı, kaybeden o satırı
            # bugünün son bilinen durumuyla GÜNCELLEMELİDİR (bu fonksiyonun sözleşmesi
            # upsert — BUG #292). Uyarı kanalı gerçek arızalar için kalsın; yarış
            # gürültü üretmesin (L22: okunmayan uyarı, uyarı değildir).
            db.rollback()
            mevcut = q.first()
            if mevcut is None:  # pragma: no cover — UNIQUE düştü ama satır yok: gerçek arıza
                raise

    # BUG #292: gün içi güncelleme. Karşılaştırma float üzerinden — DB Numeric(19,4)
    # Decimal döner, cockpit float verir (B1 sınırı); tip farkı "değişti" sanılmamalı.
    degisti = any(float(getattr(mevcut, alan) or 0) != float(yeni or 0)
                  for alan, yeni in degerler.items())
    if not degisti:
        return
    for alan, yeni in degerler.items():
        setattr(mevcut, alan, yeni)
    db.commit()


@router.get("")
def get_cockpit(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    ws_id: Optional[int] = Depends(active_workspace_id),  # M43
) -> dict:
    """
    Frontend'in tek bilgi kaynagi. Cockpit panel + birkac diger panel buradan beslenir.

    Iceren bolumler:
    - Ana gostergeler (nakit_kasa, kart_borcu, kredi_borcu, yatirim_deger,
      emanet_kasa, beklenen_gelir, reel_butce, net_deger)
    - Statu cumlesi (likidite durumunu tek satirda)
    - Hesap detaylari (id ile, frontend kart paneli)
    - investment_pnl (TLY brut kar % getiri)
    - upcoming_payments (60 gun horizon)
    - upcoming_receivables (alacak takvimi, 90 gun)
    - alerts (kritik/uyari)
    - price_freshness (Wave-1 mukemmellestirici: fund fiyat yasi rozetleri)
    """
    today = user_today(user)  # BUG #197: kullanicinin saat dilimi
    with workspace_scope(ws_id):  # M43: cockpit aktif workspace verisinden üretilir
        cockpit = generate_cockpit(user.id, today, db)

    # Mukemmellestirici: fund fiyat bayatligi
    # Imza: get_freshness_summary(db, user_id)
    try:
        freshness = get_freshness_summary(db, user.id)
        cockpit["price_freshness"] = freshness
    except Exception:
        # fund_tracker beklenmedik hata verirse cockpit yine donsun.
        # BUG #175: detay YALNIZ log'a (kullanıcıya iç hata metni sızmaz).
        logger.exception("price_freshness hesaplanamadi user_id=%s", user.id)
        cockpit["price_freshness"] = {
            "error": "fiyat tazeligi hesaplanamadi",  # BUG #175: ham exception metni sızmaz
            "total_investments": 0,
            "stale_count": 0,
            "never_set_count": 0,
            "items": [],
        }

    # BUG #429 (DVIZ-005): dönem farkı, bugünün snapshot'ı YAZILMADAN önce (baz = önceki gün)
    try:
        cockpit["donem_degisimi"] = _donem_degisimi(db, user.id, ws_id, cockpit, today)
    except Exception:
        logger.warning("dönem değişimi hesaplanamadı (cockpit devam ediyor)", exc_info=True)
        cockpit["donem_degisimi"] = None

    # B2: bugünkü snapshot'ı kaydet (idempotent)
    try:
        _ensure_today_snapshot(db, user.id, cockpit, ws_id, today=today)  # BUG #237 (D17)
    except Exception:
        # BE-010: snapshot best-effort (cockpit'i durdurmaz) AMA sürekli başarısızsa görünür
        # olmalı (net-worth trendi sessizce boş kalmasın).
        logger.warning("bugünkü net-worth snapshot kaydedilemedi (cockpit devam ediyor)", exc_info=True)

    return cockpit