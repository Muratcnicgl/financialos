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

from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_user
from app.models import User, NetWorthSnapshot
from app.rules_engine import generate_cockpit
from app.fund_tracker import get_freshness_summary

router = APIRouter(prefix="/api/cockpit", tags=["cockpit"])


def _ensure_today_snapshot(db: Session, user_id: int, cockpit: dict) -> None:
    """Bugünkü net değer snapshot'ını yaz (idempotent — günde bir kez)."""
    today = date.today()
    if db.query(NetWorthSnapshot).filter_by(user_id=user_id, snapshot_date=today).first():
        return
    receivables = max(0.0, cockpit.get("net_deger_tam", cockpit["net_deger"]) - cockpit["net_deger"])
    snap = NetWorthSnapshot(
        user_id=user_id,
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
    - upcoming_receivables (Efe takvimi, 90 gun)
    - alerts (kritik/uyari)
    - price_freshness (Wave-1 mukemmellestirici: fund fiyat yasi rozetleri)
    """
    today = date.today()
    cockpit = generate_cockpit(user.id, today, db)

    # Mukemmellestirici: fund fiyat bayatligi
    # Imza: get_freshness_summary(db, user_id)
    try:
        freshness = get_freshness_summary(db, user.id)
        cockpit["price_freshness"] = freshness
    except Exception as e:
        # fund_tracker beklenmedik hata verirse cockpit yine donsun
        cockpit["price_freshness"] = {
            "error": str(e),
            "total_investments": 0,
            "stale_count": 0,
            "never_set_count": 0,
            "items": [],
        }

    # B2: bugünkü snapshot'ı kaydet (idempotent)
    try:
        _ensure_today_snapshot(db, user.id, cockpit)
    except Exception:
        pass  # snapshot hatası cockpit'i durdurmasın

    return cockpit