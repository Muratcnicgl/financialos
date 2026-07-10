"""
FinancialOS Rules Engine — Sistem Matematiği

İlke: LLM hesap yapmaz. Tüm matematiksel kararlar burada.
Her fonksiyon saf (pure) — sadece girdiye bakar, çıktıyı döner.

İçerik:
1. Tarih yardımcıları         (turkish_date, get_month_remaining_days)
2. Bütçe matematiği           (apply_shadow_accounting, calculate_daily_limit)
3. ZikZak (devreden bakiye)   (calculate_carried_forward)
4. Kart stratejisi            (evaluate_credit_card_strategy)
5. Yatırım K/Z                (calculate_investment_pnl, simulate_partial_sale)
6. Cockpit                    (generate_cockpit, detect_alerts)
7. Komut çözümleme            (parse_gg_command)

GÜNCELLEMELER:
- BUG #086 fix: _calculate_expected_income_until_eom, bu ay tetiklenmiş (nakde geçmiş)
  geliri beklenen'e saymaz (çift-sayım önlendi — kurucu "çift sayma yasak").
- BUG #096 (A1 tamamlama): _collect_upcoming_reminders artık kredi kartı SON ÖDEME
  gününü de proaktif hatırlatır (payment_day 0-7 gün + kart borcu > 0). Kurucu vizyonun
  en kritik proaktif uyarısı — kart %99.8 doluyken hayati.
- 2 May 2026 BUG #006 fix: generate_cockpit artık iki net değer metriği döner.
  net_deger        = Görülen Net Değer (operasyonel, alacaksız, MC8 ruhuna uygun)
  net_deger_tam    = Tam Net Değer (stratejik, sözleşmeli alacaklar dahil)
  alacaklar_toplami = ödenmemiş receivable toplamı (transparency için)
- 3 May 2026 BUG #029 fix: beklened_gelir artık PersonalDebt direction=receivable +
  is_paid=False + due_date<=ay sonu olan alacakları da kapsar (display only;
  reel_butce hesabına dahil değil — muhatap kontrolünde).
- 3 May 2026 BUG #030 fix: reel_butce artık ay sonu kredi taksitlerini düşürerek
  hesaplanır. apply_shadow_accounting loan_payments_this_month parametresi aldı.
"""

import os
from datetime import date, datetime, timedelta
from calendar import monthrange
from typing import List, Dict, Optional, Tuple
import re

from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.models import (
    Account, AccountType, RecurringIncome, RecurringExpense, Transaction,
    TransactionType, PersonalDebt, DebtDirection, MasterCheckpoint,
)

# ============================================================
# A3 ROLLING PATTERN SABİTLERİ
# ============================================================

# %40 artış eşiği — .env ANOMALY_THRESHOLD ile override edilebilir
ANOMALY_THRESHOLD: float = float(os.getenv("ANOMALY_THRESHOLD", "1.4"))

# Minimum transaction sayısı (curr_30d'de) — daha az → gürültü
PATTERN_MIN_TRANSACTIONS: int = 3

# Hariç tutulan kategoriler (kişisel harcama paterni değil, muhasebe işlemi):
#   kredi_taksiti : kredi taksit ödeme (loan type action'dan)
#   borc_odeme    : kişisel borç ödeme (mark_debt_paid'dan)
#   transfer      : hesaplar arası transfer (add_transaction type=transfer'dan)
_PATTERN_EXCLUDED_CATEGORIES: set = {
    "kredi_taksiti", "loan_payment", "debt_payment", "borc_odeme",
    "borc", "kredi", "transfer",
}
# SQL IN cümlesi — sabit set, güvenli string interpolasyon
_EXCLUDED_SQL: str = ",".join(f"'{c}'" for c in _PATTERN_EXCLUDED_CATEGORIES)


# ============================================================
# 1. TARİH YARDIMCILARI
# ============================================================

TURKISH_MONTHS = {
    1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran",
    7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık",
}

TURKISH_WEEKDAYS = {
    0: "Pazartesi", 1: "Salı", 2: "Çarşamba", 3: "Perşembe",
    4: "Cuma", 5: "Cumartesi", 6: "Pazar",
}


def turkish_date(d: date) -> str:
    """Tarihi Türkçe formatta döner. Örn: '29 Nisan 2026 Çarşamba'"""
    return f"{d.day} {TURKISH_MONTHS[d.month]} {d.year} {TURKISH_WEEKDAYS[d.weekday()]}"


def get_month_remaining_days(today: date) -> int:
    """Ay sonuna kalan gün sayısı (bugün dahil)."""
    last_day = monthrange(today.year, today.month)[1]
    return last_day - today.day + 1


def get_next_occurrence(day_of_month: int, today: date) -> date:
    """
    Verilen ayın gününün bir sonraki gerçekleşme tarihini döner.
    Örn: bugün 29 Nisan, day_of_month=5 → 5 Mayıs
    """
    last_day_this_month = monthrange(today.year, today.month)[1]
    target_day = min(day_of_month, last_day_this_month)

    if today.day < target_day:
        return date(today.year, today.month, target_day)

    # Sonraki aya geç
    if today.month == 12:
        next_year, next_month = today.year + 1, 1
    else:
        next_year, next_month = today.year, today.month + 1

    last_day_next_month = monthrange(next_year, next_month)[1]
    return date(next_year, next_month, min(day_of_month, last_day_next_month))


# ============================================================
# 2. BÜTÇE MATEMATİĞİ — Gölge Muhasebe (MC4)
# ============================================================

def apply_shadow_accounting(
    cash: float,
    expected_income: float,
    card_debt: float,
    loan_payments_this_month: float = 0.0,  # BUG #030 fix
) -> float:
    """
    Reel Bütçe = Nakit + Düzenli Gelir - Kart Borcu - Ay Sonu Kredi Taksitleri

    MC4 (Gölge Muhasebe): Kart harcaması cebimde duran nakti AZALTIR.
    Kart borcu = harcanmış para.
    BUG #030 fix: Kredi taksitleri zorunlu çıkış — reel bütçeden düşülür.
    Not: alacaklar (receivable PersonalDebt) dahil edilmez; muhatabın kontrolünde.
    """
    return round(cash + expected_income - card_debt - loan_payments_this_month, 2)


def calculate_daily_limit(reel_butce: float, days_remaining: int) -> float:
    """Reel bütçenin gün başına düşen kullanılabilir miktarı."""
    if days_remaining <= 0:
        return 0.0
    return round(reel_butce / days_remaining, 2)


# ============================================================
# 3. ZİKZAK — Devreden Bakiye
# ============================================================

def calculate_carried_forward(
    daily_limit_yesterday: float,
    actual_spent_yesterday: float,
) -> float:
    """
    DEPRECATED (ADR-026): Bu additive devreden bakiye modeli KULLANILMAMALI.
    Dinamik daily_limit (reel_butce/days_remaining) zaten önceki tasarrufu içerir;
    üstüne bunu eklemek ÇİFT-SAYIM üretir ("Sanal Zenginlik" tuzağı, kök vizyonda yasak).
    Ayrıca negatif (aşım) devretmek YNAB'ın kanıta dayalı kuralına aykırı.
    Korunuyor sadece geriye-dönük referans için; generate_cockpit çağırmaz.
    """
    return round(daily_limit_yesterday - actual_spent_yesterday, 2)


def calculate_today_target(daily_limit: float, carried_forward: float) -> float:
    """DEPRECATED (ADR-026): additive today_target = daily_limit + carry çift-sayımdır.
    today_target doğrudan dinamik daily_limit'e eşittir. Bu fonksiyonu kullanma."""
    return round(daily_limit + carried_forward, 2)


# ============================================================
# 4. KART STRATEJİSİ (MC3) — Kesim/Ödeme Döngüsü
# ============================================================

def evaluate_credit_card_strategy(
    today: date,
    statement_day: int,
    payment_day: int,
    current_debt: float,
    credit_limit: float,
) -> Dict:
    """
    Ziraat kart döngüsü analizi (MC3).

    Üç durum:
    - 'vade_avantaji': Kesim sonrası — yeni harcama 35-40 gün vadeye gider (stratejik kullanım dönemi)
    - 'odeme_dikkat':  Son ödeme yaklaştı — borç hazırlığı yapılmalı
    - 'kesim_dikkat':  Kesim yaklaştı — bu dönem harcama bir sonraki ekstreye yansıyacak

    Dönen anahtarlar:
        durum, gunlere_gore, kullanim_oranı, kalan_limit, mesaj
    """
    last_day = monthrange(today.year, today.month)[1]
    statement_day_eff = min(statement_day, last_day)
    payment_day_eff = min(payment_day, last_day)

    days_to_statement = (statement_day_eff - today.day) % last_day
    days_to_payment = (payment_day_eff - today.day) % last_day

    kullanim_orani = round((current_debt / credit_limit) * 100, 1) if credit_limit > 0 else 0.0
    kalan_limit = round(credit_limit - current_debt, 2)

    # Bugün kesim sonrası mı? (kesim günü geçmiş, ödeme günü gelmemiş aralık dışı = vade avantajı)
    if today.day > statement_day:
        durum = "vade_avantaji"
        mesaj = (
            f"Kesim {statement_day_eff}'inde geçti. Bugünden itibaren yapılan "
            f"harcamalar bir sonraki ekstreye gidecek — yaklaşık 35-40 gün vade. "
            f"Kart stratejik silah, nakit korumalı."
        )
    elif today.day <= payment_day and today.day > 1:
        durum = "odeme_dikkat"
        gun_kaldi = payment_day_eff - today.day
        mesaj = (
            f"Son ödeme tarihine {gun_kaldi} gün kaldı ({payment_day_eff}'i). "
            f"{current_debt:.2f} TL borç hazırlığı yapılmalı."
        )
    else:
        durum = "kesim_dikkat"
        gun_kaldi = statement_day_eff - today.day
        mesaj = (
            f"Kesim tarihine {gun_kaldi} gün kaldı ({statement_day_eff}'i). "
            f"Bu dönem harcamalar gelecek ekstreye yansıyacak."
        )

    return {
        "durum": durum,
        "kesim_gunu": statement_day_eff,
        "odeme_gunu": payment_day_eff,
        "gun_to_kesim": days_to_statement,
        "gun_to_odeme": days_to_payment,
        "kullanim_orani": kullanim_orani,
        "kalan_limit": kalan_limit,
        "mevcut_borc": round(current_debt, 2),
        "mesaj": mesaj,
    }


# ============================================================
# 5. YATIRIM K/Z (MC2) — TLY Kaldıraç Stratejisi
# ============================================================

def calculate_investment_pnl(
    lot_count: float,
    cost_per_lot: float,
    current_price: float,
) -> Dict:
    """
    Yatırım K/Z hesabı (stopajsız, brüt).

    Returns:
        toplam_maliyet, guncel_deger, brut_kar, getiri_yuzde
    """
    toplam_maliyet = round(lot_count * cost_per_lot, 2)
    guncel_deger = round(lot_count * current_price, 2)
    brut_kar = round(guncel_deger - toplam_maliyet, 2)
    getiri_yuzde = round((brut_kar / toplam_maliyet) * 100, 2) if toplam_maliyet > 0 else 0.0

    return {
        "lot_count": lot_count,
        "cost_per_lot": cost_per_lot,
        "current_price": current_price,
        "toplam_maliyet": toplam_maliyet,
        "guncel_deger": guncel_deger,
        "brut_kar": brut_kar,
        "getiri_yuzde": getiri_yuzde,
    }


def simulate_partial_sale(
    lot_count: float,
    cost_per_lot: float,
    current_price: float,
    lots_to_sell: float,
    stopaj_orani: float = 0.175,  # %17.5 stopaj — TEFAS yatırım fonu standart oranı
) -> Dict:
    """
    Kısmi satış simülasyonu — Gürcistan senaryosu için kritik.

    Örnek: 4 lot × 4.929,56 TL = 19.718,24 TL satış tutarı (Murat'ın gerçek verisi).

    Returns:
        satis_tutari, kalan_lot, kalan_deger, satis_maliyeti, brut_kar, stopaj, net_kar
    """
    if lots_to_sell > lot_count:
        raise ValueError(f"Satılacak lot ({lots_to_sell}) mevcut lottan ({lot_count}) fazla.")

    satis_tutari = round(lots_to_sell * current_price, 2)
    satis_maliyeti = round(lots_to_sell * cost_per_lot, 2)
    brut_kar = round(satis_tutari - satis_maliyeti, 2)

    # Stopaj sadece kar üzerinden alınır, zarar varsa stopaj yok
    stopaj = round(brut_kar * stopaj_orani, 2) if brut_kar > 0 else 0.0
    net_kar = round(brut_kar - stopaj, 2)
    net_eline_gecen = round(satis_tutari - stopaj, 2)

    kalan_lot = round(lot_count - lots_to_sell, 4)
    kalan_deger = round(kalan_lot * current_price, 2)

    return {
        "satilan_lot": lots_to_sell,
        "satis_tutari": satis_tutari,
        "satis_maliyeti": satis_maliyeti,
        "brut_kar": brut_kar,
        "stopaj_orani": stopaj_orani,
        "stopaj": stopaj,
        "net_kar": net_kar,
        "net_eline_gecen": net_eline_gecen,
        "kalan_lot": kalan_lot,
        "kalan_deger": kalan_deger,
    }


# ============================================================
# 6. COCKPIT — Tüm Verileri Tek Snapshot'a Topla
# ============================================================

def _calculate_expected_income_until_eom(
    user_id: int,
    today: date,
    db: Session,
) -> Tuple[float, List[Dict]]:
    """
    Ay sonuna kadar beklenen düzenli gelirler (sadece is_active=True olanlar).
    MC6 (Varsayım Yasağı) gereği: pasif gelirler dahil edilmez.
    """
    last_day = monthrange(today.year, today.month)[1]
    incomes = (
        db.query(RecurringIncome)
        .filter(RecurringIncome.user_id == user_id, RecurringIncome.is_active == True)
        .all()
    )

    # BUG #086 fix: Bu ay zaten tetiklenmiş (nakde geçmiş) gelir "beklenen"e SAYILMAZ.
    # reel_butce = nakit + recurring_income - ... olduğundan, maaş gününde tetiklenip
    # nakde eklenen gelir hem nakit'te hem recurring_income'da görünüp reel_butce'yi
    # bir maaş kadar şişiriyordu (çift-sayım — kurucu "çift sayma yasak" ihlali).
    # _collect_upcoming_reminders (rules_engine:508) zaten bu guard'ı kullanıyor; tutarlılaştırıldı.
    year_month = today.strftime("%Y-%m")

    total = 0.0
    upcoming = []
    for inc in incomes:
        if inc.last_triggered_year_month == year_month:  # BUG #086: bu ay nakde geçti, çift sayma
            continue
        target_day = min(inc.day_of_month, last_day)
        if target_day >= today.day:  # Bu ay henüz gelmedi
            total += inc.amount
            upcoming.append({
                "ad": inc.name,
                "tutar": inc.amount,
                "tarih": date(today.year, today.month, target_day).isoformat(),
                "tip": "gelir",
            })
    return round(total, 2), upcoming


def _calculate_receivables_until_eom(
    user_id: int,
    today: date,
    db: Session,
) -> float:
    """
    BUG #029 fix: Ay sonuna kadar tahsil edilecek alacakların toplamı.
    beklened_gelir'e eklenir (display); reel_butce hesabında kullanılmaz.
    """
    last_day = monthrange(today.year, today.month)[1]
    eom = date(today.year, today.month, last_day)
    debts = (
        db.query(PersonalDebt)
        .filter(
            PersonalDebt.user_id == user_id,
            PersonalDebt.direction == DebtDirection.receivable,
            PersonalDebt.is_paid == False,
        )
        .all()
    )
    total = sum(d.amount or 0.0 for d in debts if d.due_date and today <= d.due_date <= eom)
    return round(total, 2)


def _calculate_loan_payments_until_eom(
    user_id: int,
    today: date,
    db: Session,
) -> float:
    """
    BUG #030 fix: Ay sonuna kadar ödenecek kredi taksitlerinin toplamı.
    reel_butce'den düşülür — zorunlu çıkışlar planlanabilir bütçenin dışındadır.
    """
    last_day = monthrange(today.year, today.month)[1]
    eom = date(today.year, today.month, last_day)
    loans = (
        db.query(Account)
        .filter(
            Account.user_id == user_id,
            Account.account_type == AccountType.loan,
        )
        .all()
    )
    total = sum(
        (loan.monthly_payment or 0.0)
        for loan in loans
        if loan.next_payment_date and today <= loan.next_payment_date <= eom
    )
    return round(total, 2)


def _collect_upcoming_loan_payments(
    user_id: int,
    today: date,
    db: Session,
    horizon_days: int = 60,
) -> List[Dict]:
    """Önümüzdeki N gün içinde gelecek kredi taksitleri."""
    horizon = today + timedelta(days=horizon_days)
    loans = (
        db.query(Account)
        .filter(
            Account.user_id == user_id,
            Account.account_type == AccountType.loan,
        )
        .all()
    )

    upcoming = []
    for loan in loans:
        if loan.next_payment_date and today <= loan.next_payment_date <= horizon:
            upcoming.append({
                "ad": loan.name,
                "tutar": loan.monthly_payment or 0.0,
                "tarih": loan.next_payment_date.isoformat(),
                "tip": "kredi_taksit",
            })
    return upcoming


def _collect_upcoming_receivables(
    user_id: int,
    today: date,
    db: Session,
    horizon_days: int = 90,
) -> List[Dict]:
    """Beklenen alacaklar — Efe ödemeleri vb. (MC7)"""
    horizon = today + timedelta(days=horizon_days)
    debts = (
        db.query(PersonalDebt)
        .filter(
            PersonalDebt.user_id == user_id,
            PersonalDebt.direction == DebtDirection.receivable,
            PersonalDebt.is_paid == False,
        )
        .all()
    )

    upcoming = []
    for d in debts:
        if d.due_date and today <= d.due_date <= horizon:
            upcoming.append({
                "kim": d.counterparty,
                "tutar": d.amount,
                "tarih": d.due_date.isoformat(),
                "aciklama": d.description or "",
            })
    return sorted(upcoming, key=lambda x: x["tarih"])


def _calculate_total_receivables(user_id: int, db: Session) -> float:
    """
    Tüm ödenmemiş alacakların toplamı (zaman ufku YOK — sözleşmeli takvim baz alınır).

    BUG #006 fix (2 May 2026): Tam Net Değer hesabında kullanılır.
    Sebebi: 5 May Efe ödemesi ile 5 Ocak Efe ödemesi aynı belirsizlikte değil — ikisi de
    sözleşmeli, ikisi de varlık sayılır. Sadece is_paid=False ve direction=receivable
    olanlar dahil edilir.

    Not: PersonalDebt.amount zaten ödenmemiş kalan kısmı temsil eder. Kısmi ödemeler
    in-place güncelleme ile (amount düşürerek) yansıtılır.
    """
    debts = (
        db.query(PersonalDebt)
        .filter(
            PersonalDebt.user_id == user_id,
            PersonalDebt.direction == DebtDirection.receivable,
            PersonalDebt.is_paid == False,
        )
        .all()
    )
    total = sum(d.amount or 0.0 for d in debts)
    return round(total, 2)


def _get_next_due_date(today: date, day_of_month: int) -> date:
    """Bu ay day_of_month geçtiyse gelecek ayın tarihini döndür."""
    last_day = monthrange(today.year, today.month)[1]
    candidate = date(today.year, today.month, min(day_of_month, last_day))
    if candidate < today:
        next_month = today.month % 12 + 1
        next_year = today.year + (1 if today.month == 12 else 0)
        last_day_next = monthrange(next_year, next_month)[1]
        candidate = date(next_year, next_month, min(day_of_month, last_day_next))
    return candidate


def _collect_upcoming_reminders(
    user_id: int, today: date, db: Session,
    accounts: List, kart_borcu: float,
) -> List[Dict]:
    """
    A1: 0-7 gün içinde vadesi gelen olaylar.
    - RecurringIncome/Expense: last_triggered_year_month != bu_ay AND day_of_month 0-7 gün
    - PersonalDebt payable: due_date 0-7 gün, is_paid=False
    Sıralama: card_risk önce, sonra days_until.
    """
    REMINDER_DAYS = 7
    year_month = f"{today.year}-{today.month:02d}"
    acc_map = {a.id: a for a in accounts}

    reminders: List[Dict] = []

    # RecurringIncome
    for inc in db.query(RecurringIncome).filter(
        RecurringIncome.user_id == user_id,
        RecurringIncome.is_active == True,
    ).all():
        if inc.last_triggered_year_month == year_month:
            continue
        target = _get_next_due_date(today, inc.day_of_month)
        days_until = (target - today).days
        if 0 <= days_until <= REMINDER_DAYS:
            reminders.append({
                "type": "income",
                "name": inc.name,
                "amount": inc.amount,
                "days_until": days_until,
                "due_date": target.isoformat(),
                "account_name": "Nakit hesap",
                "card_risk": False,
            })

    # RecurringExpense
    for exp in db.query(RecurringExpense).filter(
        RecurringExpense.user_id == user_id,
        RecurringExpense.is_active == True,
    ).all():
        if exp.last_triggered_year_month == year_month:
            continue
        target = _get_next_due_date(today, exp.day_of_month)
        days_until = (target - today).days
        if 0 <= days_until <= REMINDER_DAYS:
            acc = acc_map.get(exp.account_id)
            card_risk = False
            if acc and acc.account_type == AccountType.credit_card and acc.credit_limit:
                card_risk = (acc.balance + exp.amount) > acc.credit_limit
            reminders.append({
                "type": "expense",
                "name": exp.name,
                "amount": exp.amount,
                "days_until": days_until,
                "due_date": target.isoformat(),
                "account_name": acc.name if acc else "Bilinmeyen",
                "card_risk": card_risk,
            })

    # PersonalDebt (payable, unpaid, due soon)
    for debt in db.query(PersonalDebt).filter(
        PersonalDebt.user_id == user_id,
        PersonalDebt.is_paid == False,
        PersonalDebt.direction == DebtDirection.payable,
        PersonalDebt.due_date != None,
    ).all():
        days_until = (debt.due_date - today).days
        if 0 <= days_until <= REMINDER_DAYS:
            reminders.append({
                "type": "debt",
                "name": f"{debt.counterparty} borcu",
                "amount": debt.amount,
                "days_until": days_until,
                "due_date": debt.due_date.isoformat(),
                "account_name": "",
                "card_risk": False,
            })

    # Kredi kartı SON ÖDEME (A1 tamamlama): kurucu vizyonun EN kritik proaktif hatırlatması.
    # Ziraat döngüsü — son ödeme günü (payment_day) yaklaşıp kart borcu varken koç proaktif
    # uyarmalı ("borç hazırlığı yap"). Kart %99.8 doluyken bu hayati; RecurringExpense/Debt
    # kapsamı bunu içermiyordu → eksikti.
    for acc in accounts:
        if acc.account_type != AccountType.credit_card:
            continue
        if not acc.payment_day or (acc.balance or 0.0) <= 0.01:  # borç yoksa hatırlatma yok
            continue
        target = _get_next_due_date(today, acc.payment_day)
        days_until = (target - today).days
        if 0 <= days_until <= REMINDER_DAYS:
            reminders.append({
                "type": "card_payment",
                "name": f"{acc.name} son ödeme",
                "amount": acc.balance,           # güncel kart borcu (yaklaşık ödenecek)
                "days_until": days_until,
                "due_date": target.isoformat(),
                "account_name": acc.name,
                "card_risk": True,               # yüksek öncelik + vurgu (sıralama başa alır)
            })

    reminders.sort(key=lambda x: (not x["card_risk"], x["days_until"]))
    return reminders


def _calculate_category_patterns(user_id: int, today: date, db: Session) -> List[Dict]:
    """
    Son 30 gün vs önceki 30 günlük gider kalıplarını hesaplar.
    Tek GROUP BY sorgusu — N+1 yok. index: ix_transactions_user_date.
    curr_count >= PATTERN_MIN_TRANSACTIONS olanlar döner (gürültü filtresi).
    """
    curr_start = today - timedelta(days=30)
    prev_start = today - timedelta(days=60)

    rows = db.execute(text(f"""
        SELECT
            category,
            SUM(CASE WHEN transaction_date >= :prev_start
                          AND transaction_date < :curr_start
                     THEN amount ELSE 0 END) AS prev_30d,
            SUM(CASE WHEN transaction_date >= :curr_start
                     THEN amount ELSE 0 END)          AS curr_30d,
            COUNT(CASE WHEN transaction_date >= :curr_start
                       THEN 1 END)                    AS curr_count
        FROM transactions
        WHERE user_id       = :user_id
          AND transaction_type = 'expense'
          AND transaction_date >= :prev_start
          AND (category NOT IN ({_EXCLUDED_SQL}) OR category IS NULL)
        GROUP BY category
        HAVING COUNT(CASE WHEN transaction_date >= :curr_start THEN 1 END) >= :min_count
        ORDER BY curr_30d DESC
    """), {
        "user_id": user_id,
        "prev_start": str(prev_start),
        "curr_start": str(curr_start),
        "min_count": PATTERN_MIN_TRANSACTIONS,
    }).fetchall()

    patterns = []
    for row in rows:
        category, prev_30d, curr_30d, _ = row
        prev_30d = float(prev_30d or 0)
        curr_30d = float(curr_30d or 0)
        # division-by-zero koruması: prev=0 → yeni kategori, change_pct=None
        change_pct: Optional[float] = (
            round((curr_30d - prev_30d) / prev_30d * 100, 1)
            if prev_30d > 0 else None
        )
        anomaly_flag: bool = (
            curr_30d > prev_30d * ANOMALY_THRESHOLD
            if prev_30d > 0
            else curr_30d > 0  # yeni kategori → anomali say
        )
        patterns.append({
            "category": category or "diger",
            "prev_30d": round(prev_30d, 2),
            "curr_30d": round(curr_30d, 2),
            "change_pct": change_pct,
            "anomaly_flag": anomaly_flag,
        })
    return patterns


# ============================================================
# AYLIK ÖZET (A3) — takvim-ayı gelir/gider/net + kategori + önceki-ay trend
# (Mimari kural: matematik rules_engine'de; reports router yalnız bunu çağırır.)
# ============================================================

_TR_AYLAR = [
    "", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran",
    "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık",
]


def _month_bounds(year: int, month: int) -> Tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _month_aggregates(db: Session, user_id: int, start: date, end: date) -> Dict:
    """Bir takvim ayının gelir/gider/net + gider kategori dağılımı (saf okuma)."""
    rows = db.query(
        Transaction.transaction_type.label("ttype"),
        func.coalesce(Transaction.category, "(kategorisiz)").label("category"),
        func.sum(Transaction.amount).label("total"),
        func.count(Transaction.id).label("cnt"),
    ).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
        Transaction.transaction_type.in_([TransactionType.income, TransactionType.expense]),
    ).group_by(
        Transaction.transaction_type,
        func.coalesce(Transaction.category, "(kategorisiz)"),
    ).all()

    total_income = 0.0
    total_expense = 0.0
    tx_count = 0
    expense_by_cat: Dict[str, Dict] = {}
    for r in rows:
        tx_count += r.cnt
        if r.ttype == TransactionType.income:
            total_income += float(r.total)
        else:
            total_expense += float(r.total)
            expense_by_cat[r.category] = {
                "category": r.category,
                "total": round(float(r.total), 2),
                "count": r.cnt,
            }

    cats = sorted(expense_by_cat.values(), key=lambda c: -c["total"])
    for c in cats:
        c["percentage"] = round(c["total"] / total_expense * 100, 1) if total_expense > 0 else 0.0

    net_change = total_income - total_expense
    return {
        "total_income": round(total_income, 2),
        "total_expense": round(total_expense, 2),
        "net_change": round(net_change, 2),
        "transaction_count": tx_count,
        "savings_rate": round(net_change / total_income * 100, 1) if total_income > 0 else None,
        "expense_categories": cats,
    }


def generate_monthly_summary(user_id: int, year: int, month: int, db: Session) -> Dict:
    """A3: takvim-ayı özeti (current + previous_period + trend). Saf okuma."""
    cur_start, cur_end = _month_bounds(year, month)
    pm_y, pm_m = (year - 1, 12) if month == 1 else (year, month - 1)
    prev_start, prev_end = _month_bounds(pm_y, pm_m)

    cur = _month_aggregates(db, user_id, cur_start, cur_end)
    prev = _month_aggregates(db, user_id, prev_start, prev_end)

    def _pct_delta(c: float, p: float) -> Optional[float]:
        return round((c - p) / p * 100, 1) if p > 0 else None

    return {
        "period": {
            "year": year, "month": month,
            "label": f"{_TR_AYLAR[month]} {year}",
            "start": cur_start.isoformat(), "end": cur_end.isoformat(),
        },
        "current": cur,
        "previous_period": {"year": pm_y, "month": pm_m, "label": f"{_TR_AYLAR[pm_m]} {pm_y}"},
        "trend": {
            "income_delta_pct": _pct_delta(cur["total_income"], prev["total_income"]),
            "expense_delta_pct": _pct_delta(cur["total_expense"], prev["total_expense"]),
            "net_change_delta": round(cur["net_change"] - prev["net_change"], 2),
            "prev_total_income": prev["total_income"],
            "prev_total_expense": prev["total_expense"],
            "prev_net_change": prev["net_change"],
        },
    }


def generate_cockpit(user_id: int, today: date, db: Session) -> Dict:
    """
    Tüm cockpit verisini üretir — frontend ve LLM bu çıktıdan beslenir.

    İlke: LLM bu fonksiyonun çıktısını okur, hesap yapmaz.

    BUG #006 fix (2 May 2026): İki net değer metriği döner.
    - net_deger      = Görülen Net Değer (operasyonel; nakit + yatırım - kart - kredi)
    - net_deger_tam  = Tam Net Değer (stratejik; net_deger + alacaklar)
    """
    # Hesapları çek
    accounts = db.query(Account).filter(Account.user_id == user_id).all()

    nakit = 0.0
    kart_borcu = 0.0
    yatirim_deger = 0.0
    emanet_deger = 0.0
    kredi_borcu = 0.0
    accounts_detail = []

    investment_pnl_list = []

    for acc in accounts:
        # BUG #007 FIX: investment hesaplari icin balance her zaman lot * fiyat.
        # Boylece DB'deki balance (Midas'tan girilen 31.342,82) ile hesaplanan
        # deger (6 * 5223.81 = 31.342,86) arasindaki 4 kurus tutarsizligi
        # frontend'den gozukmez.
        if acc.account_type == AccountType.investment and acc.lot_count and acc.current_price:
            display_balance = round(acc.lot_count * acc.current_price, 2)
        else:
            display_balance = acc.balance

        detail = {
            "id": acc.id,
            "ad": acc.name,
            "tip": acc.account_type.value,
            "bakiye": display_balance,
            "is_emanet": acc.is_emanet,
        }

        if acc.account_type == AccountType.cash:
            nakit += acc.balance
        elif acc.account_type == AccountType.credit_card:
            kart_borcu += acc.balance
            detail["limit"] = acc.credit_limit
            detail["kullanim_orani"] = (
                round((acc.balance / acc.credit_limit) * 100, 1)
                if acc.credit_limit else 0.0
            )
        elif acc.account_type == AccountType.loan:
            kredi_borcu += acc.balance
            detail["aylik_taksit"] = acc.monthly_payment
            detail["kalan_taksit"] = acc.remaining_installments
            detail["sonraki_taksit"] = acc.next_payment_date.isoformat() if acc.next_payment_date else None
        elif acc.account_type == AccountType.investment:
            value = (acc.lot_count or 0) * (acc.current_price or 0)
            if acc.is_emanet:
                emanet_deger += value
            else:
                yatirim_deger += value
                # MC2: Kişisel TLY için K/Z hesabı
                if acc.lot_count and acc.cost_per_lot and acc.current_price:
                    pnl = calculate_investment_pnl(
                        acc.lot_count, acc.cost_per_lot, acc.current_price,
                    )
                    pnl["account_id"] = acc.id
                    pnl["account_name"] = acc.name
                    pnl["fund_code"] = acc.fund_code
                    investment_pnl_list.append(pnl)
            detail["lot"] = acc.lot_count
            detail["fiyat"] = acc.current_price
            detail["maliyet_per_lot"] = acc.cost_per_lot
            detail["fund_code"] = acc.fund_code
            detail["guncel_deger"] = round(value, 2)

        accounts_detail.append(detail)

    # Beklenen gelir (ay sonuna kadar) — sadece düzenli gelirler (maaş vb.)
    recurring_income, upcoming_incomes = _calculate_expected_income_until_eom(user_id, today, db)

    # BUG #029 fix: Ay sonu alacakları beklened_gelir'e eklenir (display only)
    receivables_eom = _calculate_receivables_until_eom(user_id, today, db)
    expected_income = round(recurring_income + receivables_eom, 2)  # BUG #029 fix

    # BUG #030 fix: Ay sonu kredi taksitlerini topla
    loan_payments_eom = _calculate_loan_payments_until_eom(user_id, today, db)  # BUG #030 fix

    # Reel bütçe (MC4 — Gölge Muhasebe)
    # Alacaklar dahil değil (muhatap kontrolünde); sadece düzenli gelir + nakit - kart - taksitler
    reel_butce = apply_shadow_accounting(nakit, recurring_income, kart_borcu, loan_payments_eom)  # BUG #030 fix

    # Görülen Net Değer (operasyonel, MC1 — emanet hariç, alacaklar hariç)
    # MC8 ruhuna uygun: cüzdanı açtığında ne görüyorsun
    net_deger = round(nakit + yatirim_deger - kart_borcu - kredi_borcu, 2)

    # BUG #006 fix: Tam Net Değer (stratejik, sözleşmeli alacaklar dahil)
    # Efe takvimi gibi sözleşmeli alacaklar varlık olarak sayılır.
    alacaklar_toplami = _calculate_total_receivables(user_id, db)
    net_deger_tam = round(net_deger + alacaklar_toplami, 2)

    # Günlük limit
    days_remaining = get_month_remaining_days(today)
    daily_limit = calculate_daily_limit(reel_butce, days_remaining)

    # ZikZak — ADR-026: additive carried_forward KULLANILMAZ (çift-sayım / "Sanal Zenginlik" tuzağı).
    # daily_limit = reel_butce / days_remaining ZATEN dinamik; bugün az harcanınca yarınki limit
    # otomatik yükselir (zikzak etkisi burada, çift-saymadan). calculate_carried_forward/
    # calculate_today_target (additive) DEPRECATED — kullanma. Kök vizyondaki "harcama günü lump"
    # hissi ayrı, tek-havuzlu bir "harcama günü tavanı" ile verilecek (bkz. ADR-026 Sonraki adım).
    carried_forward = 0.0  # ADR-026: additive carry reddedildi (bilinçli 0, "eksik" değil)
    today_target = daily_limit  # sürdürülebilir dinamik ortalama = bugünkü hedef

    # Yaklaşan ödemeler ve tahsilatlar
    upcoming_payments = _collect_upcoming_loan_payments(user_id, today, db)
    upcoming_payments.extend(upcoming_incomes)
    upcoming_payments = sorted(upcoming_payments, key=lambda x: x["tarih"])

    upcoming_receivables = _collect_upcoming_receivables(user_id, today, db)

    # Statü cümlesi
    if reel_butce < 0:
        statu = "Reel bütçe negatif — kart borcu nakdi aşıyor. Hayatta kalma modu."
    elif kart_borcu / max(nakit, 1) > 2:
        statu = "Kart borcu nakdin iki katından fazla. Likidite baskısı yüksek."
    elif daily_limit < 100:
        statu = f"Ay sonuna {days_remaining} gün, günlük limit {daily_limit:.0f} TL. Sıkı dönem."
    else:
        statu = f"Ay sonuna {days_remaining} gün, günlük limit {daily_limit:.0f} TL."

    # Uyarılar
    alerts = detect_alerts(
        nakit=nakit,
        kart_borcu=kart_borcu,
        kart_limit=sum((a.credit_limit or 0) for a in accounts if a.account_type == AccountType.credit_card),
        reel_butce=reel_butce,
        upcoming_payments=upcoming_payments,
        today=today,
    )

    return {
        "date": today.isoformat(),
        "tarih_turkce": turkish_date(today),
        "statu": statu,
        "nakit_kasa": round(nakit, 2),
        "kart_borcu": round(kart_borcu, 2),
        "kredi_borcu": round(kredi_borcu, 2),
        "yatirim_deger": round(yatirim_deger, 2),
        "emanet_kasa": round(emanet_deger, 2),
        "beklenen_gelir": expected_income,
        "reel_butce": reel_butce,
        # BUG #006 fix: iki net değer metriği
        "net_deger": net_deger,                        # Görülen (operasyonel)
        "net_deger_tam": net_deger_tam,                # Tam (stratejik)
        "alacaklar_toplami": alacaklar_toplami,        # Transparency
        "daily_limit": daily_limit,
        "days_remaining": days_remaining,
        "carried_forward": carried_forward,
        "today_target": today_target,
        "accounts": accounts_detail,
        "upcoming_payments": upcoming_payments,
        "upcoming_receivables": upcoming_receivables,
        "alerts": alerts,
        "investment_pnl": investment_pnl_list,
        "category_patterns": _calculate_category_patterns(user_id, today, db),
        "upcoming_reminders": _collect_upcoming_reminders(
            user_id, today, db, accounts, kart_borcu
        ),
    }


# ============================================================
# 7. UYARI MOTORU
# ============================================================

def detect_alerts(
    nakit: float,
    kart_borcu: float,
    kart_limit: float,
    reel_butce: float,
    upcoming_payments: List[Dict],
    today: date,
) -> List[Dict]:
    """Otomatik uyarı tespiti."""
    alerts = []

    # 1. Kart kullanımı kritik
    if kart_limit > 0:
        kullanim = (kart_borcu / kart_limit) * 100
        if kullanim >= 95:
            alerts.append({
                "seviye": "kritik",
                "baslik": "Kart kullanım oranı %95 üzeri",
                "mesaj": f"Kart {kullanim:.1f}% dolu. Yeni harcama riskli, kalan limit {kart_limit - kart_borcu:.2f} TL.",
            })
        elif kullanim >= 80:
            alerts.append({
                "seviye": "uyari",
                "baslik": "Kart kullanım oranı yüksek",
                "mesaj": f"Kart {kullanim:.1f}% dolu.",
            })

    # 2. Reel bütçe negatif
    if reel_butce < 0:
        alerts.append({
            "seviye": "kritik",
            "baslik": "Reel bütçe negatif",
            "mesaj": f"Beklenen gelirle birlikte bile bütçe {reel_butce:.2f} TL. Kart borcu nakdi aşıyor.",
        })

    # 3. Nakit çok düşük
    if nakit < 1000:
        alerts.append({
            "seviye": "uyari",
            "baslik": "Nakit çok düşük",
            "mesaj": f"Kasada {nakit:.2f} TL. Acil durum tamponu yok.",
        })

    # 4. 7 gün içinde büyük ödeme var mı?
    week_horizon = today + timedelta(days=7)
    big_payments = [
        p for p in upcoming_payments
        if p.get("tip") == "kredi_taksit"
        and date.fromisoformat(p["tarih"]) <= week_horizon
        and p.get("tutar", 0) > nakit * 0.5
    ]
    for p in big_payments:
        alerts.append({
            "seviye": "uyari",
            "baslik": f"7 gün içinde büyük ödeme: {p['ad']}",
            "mesaj": f"{p['tarih']} tarihinde {p['tutar']:.2f} TL — nakitin %{(p['tutar'] / max(nakit, 1)) * 100:.0f}'i.",
        })

    return alerts


# ============================================================
# 8. KOMUT ÇÖZÜMLEME — gg parser (Quick Expense)
# ============================================================

# Üç format desteklenir:
# 1. "gg 50 yemek"          → 50 TL yemek harcaması (kart varsayılan)
# 2. "gg nakit 50 ulaşım"   → 50 TL ulaşım, nakit
# 3. "gg kart 50 alışveriş" → 50 TL alışveriş, kart

GG_PATTERN = re.compile(
    r"^gg\s+"                                # gg başlangıç
    r"(?:(?P<source>nakit|kart)\s+)?"        # opsiyonel: nakit|kart
    r"(?P<amount>\d+(?:[.,]\d+)?)\s+"        # miktar (50 ya da 50.5 ya da 50,5)
    r"(?P<category>.+)$",                    # kategori (kalan her şey)
    re.IGNORECASE,
)


def parse_gg_command(text: str) -> Optional[Dict]:
    """
    'gg' formatlı hızlı harcama komutunu çözümler.

    Returns:
        {"amount": float, "category": str, "source": "kart"|"nakit", "is_card": bool}
        ya da None (eşleşmezse)
    """
    text = text.strip()
    match = GG_PATTERN.match(text)
    if not match:
        return None

    source = (match.group("source") or "kart").lower()
    amount_str = match.group("amount").replace(",", ".")
    amount = float(amount_str)
    category = match.group("category").strip().lower()

    return {
        "amount": amount,
        "category": category,
        "source": source,
        "is_card": source == "kart",
    }