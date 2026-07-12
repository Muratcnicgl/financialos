"""
Fiyat zaman damgası yönetimi — Manuel + Akıllı UI mantığı.

İlke: TEFAS doğrudan API'si F5 Bot Defense ile koruma altında.
Fiyatları kullanıcı manuel girer, sistem 'tazelik' takibi yapar.

V2'de: borsa-mcp proxy denemesi eklenecek (try_auto_fetch_fund_price).
       BIST hisseleri için yedek otomatik kanal.

Bu modül:
1. Fiyatın 'taze' olup olmadığını söyler (24 saat kuralı)
2. TEFAS sayfasının URL'ini üretir (frontend butonu için)
3. Manuel fiyat güncellemesini DB'ye yazar (timestamp ile)
4. TEFAS otomatik fiyat çekme: try_auto_fetch_fund_price (pytefas 0.3.0)
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Dict
import logging
from sqlalchemy.orm import Session

from app.models import Account, AccountType
from app.money import D  # ADR-030: para Decimal coercion

logger = logging.getLogger(__name__)


# ============================================================
# 1. TAZELİK KONTROLÜ — 24 saat kuralı
# ============================================================

# Fiyatın 'taze' sayılacağı eşik (saat)
PRICE_FRESHNESS_HOURS = 24


def is_price_stale(last_update: Optional[datetime], threshold_hours: int = PRICE_FRESHNESS_HOURS) -> bool:
    """
    Fiyat eski mi? 24 saatten eski ise True döner.
    None olan (hiç girilmemiş) fiyatlar da 'eski' sayılır.
    """
    if last_update is None:
        return True
    age = datetime.utcnow() - last_update
    return age > timedelta(hours=threshold_hours)


def get_price_age_text(last_update: Optional[datetime]) -> str:
    """
    Fiyat ne kadar eski? İnsan-okur formatı döner.
    Örn: 'az önce', '3 saat önce', 'dün', '3 gün önce', 'henüz girilmedi'
    """
    if last_update is None:
        return "henüz girilmedi"

    age = datetime.utcnow() - last_update
    seconds = age.total_seconds()

    if seconds < 60:
        return "az önce"
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} dakika önce"
    if seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} saat önce"
    if seconds < 172800:
        return "dün"
    days = int(seconds / 86400)
    return f"{days} gün önce"


# ============================================================
# 2. TEFAS LİNK ÜRETİMİ — Frontend "Aç" butonu için
# ============================================================

def get_tefas_url(fund_code: str) -> str:
    """
    Fonun TEFAS analiz sayfası URL'i.
    Frontend bu URL'i yeni sekmede açar, kullanıcı fiyatı oradan kopyalar.
    """
    return f"https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod={fund_code.upper()}"


# ============================================================
# 3. MANUEL FİYAT GÜNCELLEME
# ============================================================

def update_fund_price_manual(
    db: Session,
    account_id: int,
    new_price: float,
    user_id: Optional[int] = None,   # BUG #115: sahiplik kapsamı (verilirse zorunlu filtre)
) -> Dict:
    """
    Yatırım hesabının fiyatını manuel olarak günceller.
    last_price_update otomatik 'şimdi' olur.

    Returns:
        {
            "success": bool,
            "account_id": int,
            "old_price": float | None,
            "new_price": float,
            "lot_count": float,
            "old_value": float,
            "new_value": float,
            "timestamp": ISO datetime,
            "message": str,
        }
    """
    # BUG #115 fix: diğer tüm handler'lar gibi user_id ile kapsamla (verildiyse). Tek-kullanıcı
    # MVP'de zararsızdı ama bu, user_id filtresi OLMAYAN tek mutasyon handler'ıydı (multi-user
    # geçişinde crafted account_id başka kullanıcının fonunu güncelleyebilirdi).
    q = db.query(Account).filter(Account.id == account_id)
    if user_id is not None:
        q = q.filter(Account.user_id == user_id)
    account = q.first()
    if not account:
        return {"success": False, "message": f"Hesap bulunamadi: id={account_id}"}

    if account.account_type != AccountType.investment:
        return {
            "success": False,
            "message": f"'{account.name}' yatirim hesabi degil — fiyat guncellenemez."
        }

    if new_price <= 0:
        return {"success": False, "message": "Fiyat sifirdan buyuk olmali."}

    old_price = account.current_price
    lot_count = account.lot_count or 0

    old_value = round(D(old_price or 0) * D(lot_count), 2)  # ADR-030: fiyat(Decimal)*lot(float)→D
    new_value = round(D(new_price) * D(lot_count), 2)

    # Güncelle
    account.current_price = D(new_price)
    account.last_price_update = datetime.utcnow()
    # balance'ı da güncelle (yatırım için balance = lot * fiyat)
    account.balance = new_value

    db.commit()
    db.refresh(account)

    return {
        "success": True,
        "account_id": account.id,
        "account_name": account.name,
        "fund_code": account.fund_code,
        "old_price": old_price,
        "new_price": new_price,
        "lot_count": lot_count,
        "old_value": old_value,
        "new_value": new_value,
        "value_diff": round(new_value - old_value, 2),
        "timestamp": account.last_price_update.isoformat(),
        "message": f"{account.name}: {old_price or 0:.4f} -> {new_price:.4f} TL (deger: {old_value:.2f} -> {new_value:.2f} TL)",
    }


# ============================================================
# 4. TÜM YATIRIMLARIN TAZELİK ÖZETİ
# ============================================================

def get_freshness_summary(db: Session, user_id: int) -> Dict:
    """
    Kullanıcının tüm yatırım hesaplarının fiyat tazelik durumu.
    Cockpit panelinde 'Fiyat eski' rozetini göstermek için.
    """
    investments = (
        db.query(Account)
        .filter(
            Account.user_id == user_id,
            Account.account_type == AccountType.investment,
        )
        .all()
    )

    items = []
    stale_count = 0
    never_set_count = 0

    for inv in investments:
        stale = is_price_stale(inv.last_price_update)
        never_set = inv.last_price_update is None

        if stale and not inv.is_emanet:  # Emanet için uyarı çıkarmıyoruz
            stale_count += 1
        if never_set:
            never_set_count += 1

        items.append({
            "account_id": inv.id,
            "name": inv.name,
            "fund_code": inv.fund_code,
            "is_emanet": inv.is_emanet,
            "current_price": inv.current_price,
            "last_update": inv.last_price_update.isoformat() if inv.last_price_update else None,
            "age_text": get_price_age_text(inv.last_price_update),
            "is_stale": stale,
            "tefas_url": get_tefas_url(inv.fund_code) if inv.fund_code else None,
        })

    return {
        "total_investments": len(items),
        "stale_count": stale_count,
        "never_set_count": never_set_count,
        "items": items,
    }


# ============================================================
# 5. V2 PLACEHOLDER — Otomatik fiyat çekme (yarın denenecek)
# ============================================================

def try_auto_fetch_fund_price(fund_code: str) -> Optional[Decimal]:
    """TEFAS'tan fon fiyatı çeker (pytefas resmi API, HTML scraping yok).

    Bugünün verisi TEFAS'ta ~18:00'de yayınlandığından son 5 günü dener
    (hafta sonu günleri atlanır). YAT başarısız olursa EMK olarak tekrar dener.
    Tüm hata durumlarında None döner → kullanıcı manuel girişe yönlendirilir.
    """
    if not fund_code:
        return None
    try:
        from pytefas import Crawler
        from pytefas import TefasAPIError, TefasRateLimitError, TefasInvalidParameterError
        from datetime import date
        import time

        crawler = Crawler()
        today = date.today()

        for offset in range(0, 5):
            check_date = today - timedelta(days=offset)
            if check_date.weekday() >= 5:   # Cumartesi=5, Pazar=6
                continue
            try:
                df = crawler.fetch(
                    check_date.isoformat(),
                    kind="YAT",
                    fund_code=fund_code,
                    columns="info",
                )
                if df is not None and not df.empty:
                    price = Decimal(str(float(df.iloc[0]["price"]))).quantize(Decimal("0.0001"))
                    logger.info(f"TEFAS fiyat (YAT): {fund_code} = {price} ({check_date})")
                    return price
            except TefasInvalidParameterError:
                # Emeklilik fonu olabilir, EMK olarak tekrar dene
                try:
                    df = crawler.fetch(
                        check_date.isoformat(),
                        kind="EMK",
                        fund_code=fund_code,
                        columns="info",
                    )
                    if df is not None and not df.empty:
                        price = Decimal(str(float(df.iloc[0]["price"]))).quantize(Decimal("0.0001"))
                        logger.info(f"TEFAS fiyat (EMK): {fund_code} = {price} ({check_date})")
                        return price
                except Exception:
                    continue
            except TefasRateLimitError:
                time.sleep(2)
                continue
            except TefasAPIError:
                continue

        logger.warning(f"TEFAS fiyat bulunamadi: {fund_code} (son 5 gun bos)")
        return None
    except Exception as e:
        logger.error(f"TEFAS fiyat cekme hatasi {fund_code}: {type(e).__name__}: {e}")
        return None


def try_auto_fetch_stock_price(ticker: str) -> Optional[Dict]:
    """
    BIST hissesi otomatik fiyat çekme denemesi.

    İş Yatırım hisse endpoint'i çalışıyordu (D1 testi geçti):
    https://www.isyatirim.com.tr/_layouts/15/Isyatirim.Website/Common/Data.aspx/HisseTekil
    Tarih formatı: yyyy-MM-dd

    V2'de aktive edilecek. Şu an None döner.
    """
    logger.info(f"try_auto_fetch_stock_price({ticker}): henuz aktif degil (V2)")
    return None