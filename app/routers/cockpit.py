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
from datetime import date
from fastapi import APIRouter, Depends
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


def _ensure_today_snapshot(db: Session, user_id: int, cockpit: dict,
                           workspace_id: Optional[int] = None,
                           today: Optional[date] = None) -> None:
    """Bugünkü net değer snapshot'ını yaz (idempotent — workspace başına günde bir kez)."""
    # BUG #237 fix (D17): snapshot SUNUCU gününü damgalıyordu; aynı istekte cockpit ise
    # kullanıcının gününü kullanıyordu (istek kendi içinde tutarsız) → trend grafiği
    # kullanıcının gördüğü günle hizasız kalıyordu. Gün artık çağırandan gelir.
    today = today or date.today()  # tz-exempt: çağıran kullanıcının gününü geçirir (aşağıdaki uç)
    # M43: workspace varsa o workspace'in snapshot'ı, yoksa legacy user snapshot'ı
    q = db.query(NetWorthSnapshot).filter(NetWorthSnapshot.snapshot_date == today)
    q = q.filter(NetWorthSnapshot.workspace_id == workspace_id) if workspace_id is not None \
        else q.filter(NetWorthSnapshot.user_id == user_id)  # scope-exempt: snapshot legacy fallback (ws_id None branch)
    if q.first():
        return
    # BUG #117 fix (#116 takibi): net_deger_tam artık payable de düşüyor → (net_deger_tam −
    # net_deger) = alacak − borç olurdu (yanlış "receivables"). Alacağı doğrudan cockpit'ten al.
    receivables = cockpit.get("alacaklar_toplami",
                              max(0.0, cockpit.get("net_deger_tam", cockpit["net_deger"]) - cockpit["net_deger"]))
    snap = NetWorthSnapshot(
        user_id=user_id,
        workspace_id=workspace_id,  # M43
        snapshot_date=today,
        net_worth_seen=cockpit["net_deger"],
        net_worth_full=cockpit.get("net_deger_tam", cockpit["net_deger"]),
        cash=cockpit["nakit_kasa"],
        card_debt=cockpit["kart_borcu"],
        loan_debt=cockpit["kredi_borcu"],
        investment_value=cockpit["yatirim_deger"],
        receivables=receivables,
    )
    db.add(snap)
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

    # B2: bugünkü snapshot'ı kaydet (idempotent)
    try:
        _ensure_today_snapshot(db, user.id, cockpit, ws_id, today=today)  # BUG #237 (D17)
    except Exception:
        # BE-010: snapshot best-effort (cockpit'i durdurmaz) AMA sürekli başarısızsa görünür
        # olmalı (net-worth trendi sessizce boş kalmasın).
        logger.warning("bugünkü net-worth snapshot kaydedilemedi (cockpit devam ediyor)", exc_info=True)

    return cockpit