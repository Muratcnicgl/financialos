"""
Cockpit Snapshot Helper — Wave-2 H2G3 ikinci alt is
Premortem ve DecisionJournal icin ortak snapshot kaynagi.
Bridgewater pattern: karar hangi state'de alindi, hash ile saklanir.

GUNCELLEMELER:
- BUG #239 fix (D23): snapshot artik `investment_price_stale`/`investment_price_age`
  tasiyor. Premortem "net degerin X TL" derken X'in yatirim kismi 30 gunluk fiyattan
  geliyorsa senaryo uretimi bunu bilmeli — aksi halde "portfoyu sat" tavsiyesi olmayan
  bir fiyata dayanir. (Yeni alanlar snapshot hash'ini degistirir: eski premortem
  onbellek kayitlari bir kez gecersizlesir, dogru davranis.)
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from typing import Optional, TypedDict

from sqlalchemy.orm import Session

from app.cashflow import generate_forecast
from app.rules_engine import generate_cockpit
from app.user_prefs import user_today_by_id  # BUG #237 (D17)

logger = logging.getLogger(__name__)


class CockpitSnapshot(TypedDict):
    """Premortem LLM context icin standart snapshot dict."""
    snapshot_at: str               # ISO 8601
    net_worth_tl: float
    cash_tl: float
    card_debt_tl: float
    loan_debt_tl: float
    investment_tl: float
    investment_price_stale: bool        # BUG #239 (D23): yatırım fiyatları bayat mı
    investment_price_age: Optional[str]  # en eski fiyat yaşı ("30 gün önce") veya None
    cashflow_30d_tl: float
    cashflow_60d_tl: float
    lowest_balance_tl: float
    lowest_balance_date: Optional[str]  # ISO date veya None
    crunch_count: int
    daily_limit_tl: float


def build_cockpit_snapshot(db: Session, user_id: int) -> CockpitSnapshot:
    """
    Mevcut cockpit + 30g/60g forecast'i tek snapshot dict'inde toplar.
    Premortem prompt'una somut TL degerleri verir, LLM hallucination'i azaltir.

    Hata durumunda partial snapshot doner (generate_cockpit/generate_forecast
    cagri basina try/except), kritik alanlar 0.0 olur.
    """
    today = user_today_by_id(db, user_id)  # BUG #237 (D17): premortem kullanıcının gününden

    try:
        cockpit = generate_cockpit(user_id, today, db)
    except Exception as e:
        logger.error("build_cockpit_snapshot: generate_cockpit fail user=%s err=%s", user_id, e)
        cockpit = {}

    try:
        flow_30 = generate_forecast(db, user_id, horizon_days=30)
    except Exception as e:
        logger.error("build_cockpit_snapshot: forecast 30 fail user=%s err=%s", user_id, e)
        flow_30 = {"summary": {}}

    try:
        flow_60 = generate_forecast(db, user_id, horizon_days=60)
    except Exception as e:
        logger.error("build_cockpit_snapshot: forecast 60 fail user=%s err=%s", user_id, e)
        flow_60 = {"summary": {}}

    summary_30 = flow_30.get("summary", {})
    summary_60 = flow_60.get("summary", {})

    # lowest_date date objesi veya ISO string olabilir — normalize et
    lowest_date_raw = summary_30.get("lowest_date")
    lowest_date_iso: Optional[str] = None
    if lowest_date_raw is not None:
        if isinstance(lowest_date_raw, (date, datetime)):
            lowest_date_iso = lowest_date_raw.isoformat()
        else:
            lowest_date_iso = str(lowest_date_raw)

    snapshot: CockpitSnapshot = {
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "net_worth_tl": float(cockpit.get("net_deger") or 0.0),
        "cash_tl": float(cockpit.get("nakit_kasa") or 0.0),
        "card_debt_tl": float(cockpit.get("kart_borcu") or 0.0),
        "loan_debt_tl": float(cockpit.get("kredi_borcu") or 0.0),
        "investment_tl": float(cockpit.get("yatirim_deger") or 0.0),
        # BUG #239 (D23): premortem "net değerin X TL" der; X'in yatırım kısmı bayat fiyattan
        # geliyorsa senaryo üretimi bunu bilmeli (aynı sınıf: değer var, tazelik yok).
        "investment_price_stale": bool((cockpit.get("fiyat_tazeligi") or {}).get("bayat_var")),
        "investment_price_age": (cockpit.get("fiyat_tazeligi") or {}).get("en_eski_yas"),
        "cashflow_30d_tl": float(summary_30.get("net_flow") or 0.0),
        "cashflow_60d_tl": float(summary_60.get("net_flow") or 0.0),
        "lowest_balance_tl": float(summary_30.get("lowest_balance") or 0.0),
        "lowest_balance_date": lowest_date_iso,
        "crunch_count": int(summary_30.get("crunch_count") or 0),
        "daily_limit_tl": float(cockpit.get("daily_limit") or 0.0),
    }
    return snapshot


def compute_snapshot_hash(snapshot: CockpitSnapshot) -> str:
    """
    Snapshot'in deterministik SHA256 hash'i — Bridgewater pattern.
    Karar journal'ina yazilir; ileride backtesting icin kullanilir.
    Hash 16 char'a kisaltilir (commit short hash gibi).

    snapshot_at hash'e DAHIL EDILMEZ — ayni mali durum icin ayni hash uretilsin.
    """
    hashable = {k: v for k, v in snapshot.items() if k != "snapshot_at"}
    payload = json.dumps(hashable, sort_keys=True, separators=(",", ":"), default=float)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
