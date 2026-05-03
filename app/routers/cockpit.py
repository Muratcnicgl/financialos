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
from app.models import User
from app.rules_engine import generate_cockpit
from app.fund_tracker import get_freshness_summary

router = APIRouter(prefix="/api/cockpit", tags=["cockpit"])


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

    return cockpit