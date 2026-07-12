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
- BUG #119 (A1 tamamlama): _collect_upcoming_reminders artık vadesi yaklaşan ALACAKLARI
  (receivable, is_paid=False, due_date 0-7 gün) da hatırlatır. Roadmap A1 "alacak (Efe vb.)
  tarihleri yaklaşınca koç proaktif" der; nakit dar (günlük 62 TL) olduğundan Efe'den
  zamanında TAHSİL etmek doğrudan ödeme-gücü meselesi (Garanti kredileri buna bağlı).
- BUG #120: _collect_overdue_debts — vadesi GEÇMİŞ ödenmemiş borç/alacaklar alert olur.
  Hatırlatmalar sadece 0-7 gün ileri baktığından vade geçince kalem sessizce kayboluyordu;
  gecikmiş yükümlülük (kritik) / tahsil edilmemiş alacak (uyarı) artık kokpit alerts'ine düşer.
- BUG #121 (DEVRİMSEL): _detect_cashflow_crunch — generate_forecast (90 gün) ile projekte
  edilen NAKİT KRİZİ (bakiye < 0) kritik alert olur. Sistem artık ANLIK durumu değil, GELECEK
  insolvency'yi kriz OLMADAN önce uyarıyor ("hayatta kalma > yatırım" vizyonu). Forecast kart
  döngüsünü içermez → yanlış-pozitif yok (yalnızca düzenli akış bile negatife düşerse uyarır).
- FEAT-009 (Copilot "Safe to Spend" ilhamı): _calculate_safe_to_spend — cockpit'e `guvenli_harcama`
  metriği = max(0, lowest_balance - kart_borcu - buffer). Forecast'i #121 ile aynı summary'den türetir.
  BUG #123 (kritik): forecast kartı içermediğinden, bir alacak forecast'i pozitife taşıyınca metrik
  TÜM nakdi gösteriyordu (12K kart borcu varken tehlikeli iyimser, reel_butce<0 ile çelişik). Kart
  borcu düşülerek düzeltildi — uçtan-uca gerçekçi senaryo gözlemiyle yakalandı (birim test kaçırmıştı).
- FEAT-006/007 (Rocket Money/Monarch ilhamı): detect_subscriptions — işlem geçmişinde tekrarlayan
  abonelikleri tespit (medyan aralık + farklı-tutar ≤ 2 ayırt edicisi). _subscription_price_alerts
  aboneliğin tutarı arttıysa (sessiz zam) uyarı üretir → cockpit alerts. GET /api/subscriptions.
- FEAT-005 (Copilot/YNAB projected spending): _category_overspend_alerts — ay-içi harcama hızıyla
  her giderin ay-sonu projeksiyonu geçen ayı belirgin aşacaksa erken uyarı (envelope bütçe gerekmez,
  geçen ay yumuşak referans). Ay başında (< 5 gün) gürültü nedeniyle atlanır. Top-2 → cockpit alerts.
- FEAT-010 (startup runway kavramı): _calculate_cash_runway — cockpit'e `nakit_runway_gun`: mevcut
  nakit, gelirsiz kaç gün yeter (nakit / günlük burn). None = belirsiz.
- BUG #124: runway burn'ü artık kredi TAKSİTLERİNİ de içerir (harcama + aylık taksit/30). Aksi halde
  runway sadece harcamaya bakıp "300 gün" derken aynı kredilerin crunch'ı "10 gün sonra kriz" diyordu
  (çelişki). Uçtan-uca gözlemle yakalandı.
- FEAT-001 (YNAB/Actual Budget zarf yöntemi): calculate_envelopes — kategori bazlı aylık bütçe zarfı.
  Yeni Envelope tablosu (create_all-safe); harcanan = bu ayın Transaction toplamı (ayrı allocation
  yok). Cockpit'e `zarflar`. FEAT-005 entegre: zarf varsa aşım öngörüsü GERÇEK bütçeye göre (geçen ay
  yerine). CRUD: /api/envelopes.
- FEAT-002 (YNAB "Ready to Assign"): cockpit'e `atanmamis_nakit = nakit - Σ max(0, zarf_kalan)`.
  Zarflara henüz taahhüt edilmemiş "boşta" nakit; negatif = aşırı-bütçeleme. Zarf yoksa = tüm nakit.
- FEAT-013 (faiz sızıntısı sayacı): calculate_interest_leak — kredi+kart borçlarının AYLIK faiz
  maliyeti (borç × aylık_oran/100). Cockpit'e `faiz_sizintisi` {kalemler, aylik/yillik/gunluk}.
  "Her ay faize kaç TL kaptırıyorsun" — Murat'ın 5-kredi durumunda sarsıcı realist metrik.
- FEAT-012 (borçsuzluk tarihi): generate_cockpit'e `borc_ozgurluk` {kalan_ay, borcsuz_tarih,
  toplam_faiz, asla_bitmez} — avalanche calc'tan (min ödemeyle). Murat'ın borç serüveninin hedefi.
- FEAT-024 (enflasyon-düzeltilmiş net değer): calculate_real_networth — nominal net değer değişimi
  vs enflasyona göre deflate edilmiş REEL değişim (Türkiye'de servet enflasyonla erir; borçlu için
  tersine erime lehte). GET /api/reports/real-net-worth. Enflasyon .env INFLATION_ANNUAL (varsayılan %40).
- FEAT-021 (net değer değişim ayrıştırması): calculate_networth_attribution — bu ayki net değer
  değişimini sürücülerine (nakit, kart/kredi ödeme, yatırım, alacak) ayırır (snapshot'lardan,
  objektif; sürücüler toplamı = değişim). GET /api/reports/net-worth-attribution. Yetersiz geçmiş → None.
- FEAT-022 (finansal sağlık skoru): calculate_health_score — 0-100 ŞEFFAF composite (ödeme gücü,
  faiz yükü, nakit tamponu, kart sağlığı, bütçe uyumu). Bileşenler görünür (kara kutu değil).
  Cockpit'e `saglik_skoru` {skor, seviye, bilesenler}. Tüm solvency sinyallerini tek sayıda özetler.
- FEAT-016 (kart utilization): calculate_card_utilization — toplam kart borcu/limit oranı + kredi-
  sağlık bandı (saglikli<30<orta<70<yuksek<90<kritik) + %30 sağlıklı borç hedefi + iyileşme trendi
  (en eski NetWorthSnapshot kart borcu ÷ güncel limit, ≥7 gün). Cockpit'e `kart_kullanim`.
- BUG #129 fix: recommend_next_action (FEAT-041) "saf/dışa-açık" savunmacı sözleşmesini tamamlar —
  property fuzzing iki gerçek çökmeyi buldu: (a) daily_limit present-but-None → _tl(None) TypeError
  (STABİL dalı), (b) faiz_sizintisi.aylik_toplam None → None>0 TypeError (FIRSAT dalı). Ayrıca
  alacak_yaslanma non-dict / eksik-alanlı en_riskli guard'ı eklendi. Production'da generate_cockpit
  hep geçerli verir (crash yoktu) ama sözleşme artık arbitrer girdide de tutuyor (test_next_action fuzz).
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
import logging
from datetime import date, datetime, timedelta
from calendar import monthrange
from typing import List, Dict, Optional, Tuple
import re

logger = logging.getLogger(__name__)


def _tl(x: float) -> str:
    """
    Türkçe para formatı: 1234.56 -> '1.234,56' (nokta binlik, virgül ondalık).
    BUG #122: alert/mesaj tutarları eskiden '{:,.2f}' ile NOKTA ondalık ("74.99 TL")
    üretiyordu — hem Türkçe UI ile tutarsız hem de grounding bug'ı: koç bunu echo edince
    _TL_NUM_RE noktayı binlik sanıp "74" okuyor, yanlış-pozitif "izlenemeyen tutar" veriyordu.
    """
    return f"{x:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")

from sqlalchemy import text, func
from sqlalchemy.orm import Session
from app.models import (
    Account, AccountType, RecurringIncome, RecurringExpense, Transaction,
    TransactionType, PersonalDebt, DebtDirection, MasterCheckpoint, Envelope,
    NetWorthSnapshot,
)
from app.money import D, ZERO, floatify  # ADR-030: iç aritmetik Decimal, public sınır float(floatify)

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
    loan_payments_this_month=ZERO,  # BUG #030 fix · ADR-030: Decimal default (para)
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
    # NOT: Kesimden sonraki TÜM günler vade_avantaji döner — YENİ harcamanın bir sonraki
    # ekstreye gitmesi (float) her zaman doğru. Kesilen ekstrenin ÖDEME hazırlığı bu fonksiyonun
    # işi DEĞİL; son ödeme yaklaşımı _collect_upcoming_reminders (BUG #096) tarafından ayrıca
    # uyarılır. Bu ikisini birleştirmeye çalışma → çifte uyarı olur.
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
            f"{_tl(current_debt)} TL borç hazırlığı yapılmalı."
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
    toplam_maliyet = round(D(lot_count) * D(cost_per_lot), 2)  # ADR-030: lot(float)+para→Decimal
    guncel_deger = round(D(lot_count) * D(current_price), 2)
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
    # RULE-008: giriş doğrulaması — negatif/sıfır lot, negatif fiyat/maliyet nonsense üretir.
    if lots_to_sell <= 0:
        raise ValueError(f"Satılacak lot pozitif olmalı (verilen: {lots_to_sell}).")
    if current_price < 0 or cost_per_lot < 0:
        raise ValueError(f"Fiyat/maliyet negatif olamaz (fiyat={current_price}, maliyet={cost_per_lot}).")
    if lots_to_sell > lot_count:
        raise ValueError(f"Satılacak lot ({lots_to_sell}) mevcut lottan ({lot_count}) fazla.")

    # ADR-030: para Decimal aritmetiği. lot adedi/oran (float) → D() ile Decimal'e çekilir.
    satis_tutari = round(D(lots_to_sell) * D(current_price), 2)
    satis_maliyeti = round(D(lots_to_sell) * D(cost_per_lot), 2)
    brut_kar = round(satis_tutari - satis_maliyeti, 2)

    # Stopaj sadece kar üzerinden alınır, zarar varsa stopaj yok
    stopaj = round(brut_kar * D(stopaj_orani), 2) if brut_kar > 0 else ZERO
    net_kar = round(brut_kar - stopaj, 2)
    net_eline_gecen = round(satis_tutari - stopaj, 2)

    kalan_lot = round(lot_count - lots_to_sell, 4)          # lot adedi salt miktar → float kalır
    kalan_deger = round(D(kalan_lot) * D(current_price), 2)

    return floatify({  # ADR-030/B1: iç Decimal hesap, public sınır float
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
    })


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

    total = ZERO
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


def _calculate_total_payables(user_id: int, db: Session) -> float:
    """
    Tüm ödenmemiş kişisel BORÇLARIN toplamı (direction=payable, is_paid=False).

    BUG #116 fix: Tam Net Değer, alacakları (varlık) sayarken kişisel borçları (yükümlülük)
    saymıyordu → net değeri fazla-iyimser gösteriyordu (realist-koç etiğiyle çelişki). Simetri:
    net_deger_tam = net_deger + alacaklar − borçlar. Banka borçları (kart/kredi) zaten
    net_deger'de düşülüyor; bu yalnız KİŞİSEL payable'ları kapsar (Efe'ye borç gibi).
    """
    debts = (
        db.query(PersonalDebt)
        .filter(
            PersonalDebt.user_id == user_id,
            PersonalDebt.direction == DebtDirection.payable,
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
    - PersonalDebt payable: due_date 0-7 gün, is_paid=False (borç öde)
    - PersonalDebt receivable: due_date 0-7 gün, is_paid=False (BUG #119: Efe'den tahsil et)
    - Kredi kartı SON ÖDEME: payment_day 0-7 gün + kart borcu > 0 (BUG #096)
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

    # PersonalDebt (receivable, unpaid, due soon) — BUG #119: Efe alacakları.
    # Vadesi yaklaşan alacak = Murat'ın TAHSİL etmesi gereken nakit girişi. Nakit dar
    # olduğundan (günlük 62 TL) zamanında tahsilat solvency-kritik; roadmap A1'in açık
    # hedefi. card_risk=False (risk değil, giriş fırsatı → sıralamada risklerden sonra).
    for debt in db.query(PersonalDebt).filter(
        PersonalDebt.user_id == user_id,
        PersonalDebt.is_paid == False,
        PersonalDebt.direction == DebtDirection.receivable,
        PersonalDebt.due_date != None,
    ).all():
        days_until = (debt.due_date - today).days
        if 0 <= days_until <= REMINDER_DAYS:
            reminders.append({
                "type": "receivable",
                "name": f"{debt.counterparty} alacağı",
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


def _collect_overdue_debts(user_id: int, today: date, db: Session) -> List[Dict]:
    """
    BUG #120: Vadesi GEÇMİŞ, ödenmemiş borç/alacaklar → gecikme uyarısı (alert).
    Hatırlatmalar sadece 0-7 gün İLERİ bakar; vade geçince kalem sessizce kaybolurdu.
    Solvency koçu için bu kör nokta:
    - payable geç: Murat bir yükümlülüğü kaçırdı (ceza/temerrüt riski) → seviye 'kritik'
    - receivable geç: Efe geç kaldı, tahsil edilmeli (beklenen nakit girişi) → seviye 'uyari'
    Sıralama: en çok geciken önce (aciliyet).
    """
    debts = db.query(PersonalDebt).filter(
        PersonalDebt.user_id == user_id,
        PersonalDebt.is_paid == False,
        PersonalDebt.due_date != None,
        PersonalDebt.due_date < today,
    ).all()

    alerts: List[Dict] = []
    for d in sorted(debts, key=lambda x: x.due_date):   # en eski (en çok geciken) önce
        gecikme = (today - d.due_date).days
        # "tutar" numerik alanı: grounding (_collect_numeric) bu tutarı DOĞRULANMIŞ saysın —
        # aksi halde tutar yalnızca mesaj string'inde kalır, koç doğru tutarı yazınca grounding
        # "izlenemeyen" sanıp confidence'ı yanlışlıkla düşürür. Frontend bu alanı yok sayar.
        if d.direction == DebtDirection.payable:
            alerts.append({
                "seviye": "kritik",
                "baslik": f"Gecikmiş borç: {d.counterparty}",
                "mesaj": f"{d.counterparty}'a {_tl(d.amount)} TL borç {gecikme} gün gecikti — öde.",
                "tutar": d.amount,
            })
        else:
            alerts.append({
                "seviye": "uyari",
                "baslik": f"Gecikmiş alacak: {d.counterparty}",
                "mesaj": f"{d.counterparty} {_tl(d.amount)} TL {gecikme} gün gecikti — tahsil et.",
                "tutar": d.amount,
            })
    return alerts


def _cashflow_forecast_summary(
    user_id: int, today: date, db: Session, horizon_days: int = 90,
) -> Optional[Dict]:
    """
    generate_forecast summary'sini güvenli döner (hata → None; forecast asla cockpit'i
    düşürmesin). `today` ENJEKTE edilir → generate_cockpit'in bugünü ile TUTARLI
    (backfill/test dahil). Hem nakit krizi (#121) hem güvenli-harcama (FEAT-009) buradan
    türetilir — generate_cockpit forecast'i BİR KEZ hesaplar.
    """
    try:
        from app.cashflow import generate_forecast  # lazy: döngüsel import riskini sıfırla
        fc = generate_forecast(db, user_id, horizon_days=horizon_days, today=today)
    except Exception as e:
        logger.warning("nakit akış öngörüsü hesaplanamadı user_id=%s: %s", user_id, e)
        return None
    return fc.get("summary")


def _crunch_alert_from_summary(
    summary: Optional[Dict], horizon_days: int = 90,
) -> Optional[Dict]:
    """
    BUG #121 (DEVRİMSEL — İLERİYE DÖNÜK ÖDEME-GÜCÜ): forecast summary'sinden projekte
    NAKİT KRİZİ'ni (crunch: bakiye < 0) kritik alert'e çevirir. GELECEK insolvency'yi kriz
    OLMADAN önce uyarır — "hayatta kalma > yatırım" vizyonu.

    Kapsam sınırı (cashflow.py): forecast kredi KARTI döngüsünü İÇERMEZ → yanlış-POZİTİF yok
    (yalnızca düzenli akış bile negatife düşerse uyarır; kart krizleri #096/#027 kapsar).
    """
    if not summary or summary.get("crunch_count", 0) <= 0:
        return None
    first_crunch = summary["crunch_dates"][0]
    lowest = summary.get("lowest_balance", 0.0)
    lowest_date = summary.get("lowest_date", first_crunch)
    return {
        "seviye": "kritik",
        "baslik": "Nakit krizi öngörüsü",
        "mesaj": (
            f"{horizon_days} gün içinde nakit sıfırın altına düşüyor "
            f"(ilk kriz {first_crunch}, en düşük {_tl(lowest)} TL @ {lowest_date}). "
            f"Alacakları öne al veya gideri ertele — kriz henüz ÖNLENEBİLİR."
        ),
        # grounding: projekte edilen tutar cockpit'te numerik olarak izlenebilir olsun (#120 dersi)
        "tutar": abs(lowest),
    }


def _detect_cashflow_crunch(
    user_id: int, today: date, db: Session, horizon_days: int = 90,
) -> Optional[Dict]:
    """Geriye-uyumlu sarıcı (#121 testleri bunu doğrudan çağırır)."""
    summary = _cashflow_forecast_summary(user_id, today, db, horizon_days)
    return _crunch_alert_from_summary(summary, horizon_days)


def _calculate_safe_to_spend(summary: Optional[Dict], kart_borcu=ZERO, buffer=ZERO) -> float:
    """
    FEAT-009 (Copilot "Safe to Spend" ilhamı, kopya değil): BUGÜN, gelecekteki yükümlülükler
    hesaba katılınca güvenle harcanabilecek EN BÜYÜK tutar. Matematik: bugün X harcamak tüm
    gelecek bakiyeleri X düşürür → kısıt lowest_balance - X >= buffer → X <= lowest_balance - buffer.

    BUG #123 (KART-FARKINDALIĞI — kritik güvenlik düzeltmesi): forecast kredi KARTI döngüsünü
    İÇERMEZ (cashflow.py). Kart borcu düşülmezse, bir alacak (ör. Efe) forecast'i pozitife
    taşıdığında güvenli-harcama TÜM nakdi gösteriyordu — oysa 12.000 kart borcu varken bu
    TEHLİKELİ İYİMSER (reel_butce negatif / "hayatta kalma modu" ile çelişir). Bu yüzden kart
    borcu (Gölge Muhasebe ruhu) düşülür → Murat gibi kart-batık durumda 0 döner. Realist koç
    "12.000 borç dururken 4.276'yı güvenle harca" DEMEZ.
    """
    if not summary:
        return 0.0
    lowest = summary.get("lowest_balance", 0.0)
    return round(max(ZERO, D(lowest) - D(kart_borcu) - D(buffer)), 2)  # ADR-030: Decimal


def _calculate_cash_runway(
    user_id: int, today: date, db: Session, nakit: float, window_days: int = 30,
) -> Optional[int]:
    """
    FEAT-010 (startup "runway" kavramı): mevcut likit nakit, son window_days harcama hızıyla
    HİÇ gelir gelmezse kaç GÜN yeter. runway = nakit / (son N gün gider / N). Belirsizlik/
    işsizlik kaygısını somut sayıya indirger. Salt hesap; `nakit` çağırandan gelir (re-query yok).

    Dönüş: gün sayısı (int); nakit ≤ 0 → 0; son dönemde hiç gider yoksa → None (belirsiz/sonsuz).
    """
    if nakit <= 0:
        return 0
    start = today - timedelta(days=window_days)
    spent = D(db.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == TransactionType.expense,
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= today,
    ).scalar() or 0.0)

    # BUG #124 (tutarlılık): gelirsiz senaryoda kredi TAKSİTLERİ de cash'i eritir → günlük
    # burn'e dahil et. Aksi halde runway (sadece harcama) aynı kredilerin ürettiği nakit-krizi
    # öngörüsüyle ÇELİŞİR (uçtan-uca gözlem: runway 300 gün derken crunch "10 gün sonra kriz").
    loan_monthly = D(db.query(func.coalesce(func.sum(Account.monthly_payment), 0)).filter(
        Account.user_id == user_id,
        Account.account_type == AccountType.loan,
        Account.remaining_installments > 0,
    ).scalar() or 0.0)

    daily_burn = spent / window_days + loan_monthly / 30  # ADR-030: para Decimal / int
    if daily_burn <= 0:
        return None  # ne harcama ne taksit → belirsiz/sonsuz
    return int(D(nakit) / daily_burn)  # ADR-030: nakit Decimal / burn Decimal


def _calculate_category_patterns(user_id: int, today: date, db: Session) -> List[Dict]:
    """
    Son 30 gün vs önceki 30 günlük gider kalıplarını hesaplar.
    Tek GROUP BY sorgusu — N+1 yok. index: ix_transactions_user_date.
    curr_count >= PATTERN_MIN_TRANSACTIONS olanlar döner (gürültü filtresi).
    """
    # BUG #108 fix: pencereler EŞİT 30 gün olmalı. Eskiden curr `>= today-30` (üstten sınırsız)
    # = 31 gün, prev `[today-60, today-30)` = 30 gün → sabit harcayan kategori bile fazladan
    # sınır gününden dolayı hafif pozitif change_pct/anomali eğilimi gösteriyordu (off-by-one).
    # curr = [today-29, today] (30 gün), prev = [today-59, today-30] (30 gün).
    curr_start = today - timedelta(days=29)
    prev_start = today - timedelta(days=59)

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
          AND transaction_date <= :today
          AND (category NOT IN ({_EXCLUDED_SQL}) OR category IS NULL)
        GROUP BY category
        HAVING COUNT(CASE WHEN transaction_date >= :curr_start THEN 1 END) >= :min_count
        ORDER BY curr_30d DESC
    """), {
        "user_id": user_id,
        "prev_start": str(prev_start),
        "curr_start": str(curr_start),
        "today": str(today),  # RULE-020: üst sınır — GELECEK tarihli işlemler curr'e sızmasın
        "min_count": PATTERN_MIN_TRANSACTIONS,
    }).fetchall()

    patterns = []
    for row in rows:
        category, prev_30d, curr_30d, _ = row
        prev_30d = D(prev_30d or 0)
        curr_30d = D(curr_30d or 0)
        # division-by-zero koruması: prev=0 → yeni kategori, change_pct=None
        change_pct: Optional[float] = (
            round((curr_30d - prev_30d) / prev_30d * 100, 1)
            if prev_30d > 0 else None
        )
        anomaly_flag: bool = (
            curr_30d > prev_30d * D(ANOMALY_THRESHOLD)  # ADR-030: para Decimal * eşik D()
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


def _collect_recent_transactions(user_id: int, db: Session, limit: int = 8) -> List[Dict]:
    """
    Son N işlem (C2-lite): koçun analizini gerçek harcamalara dayandırması için.
    Cockpit'e girer → tutarlar grounding'e dahil olur (halüsinasyon yüzeyi düşer).
    """
    txns = (
        db.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(limit)
        .all()
    )
    result = []
    for t in txns:
        result.append({
            "tarih": t.transaction_date.isoformat() if t.transaction_date else None,
            "tip": t.transaction_type.value,
            "tutar": round(D(t.amount), 2),
            "kategori": t.category or "(kategorisiz)",
            "aciklama": t.description or "",
        })
    return result


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


def _category_overspend_alerts(
    user_id: int, today: date, db: Session,
    min_days: int = 5, over_ratio: float = 1.15, top_n: int = 2,
) -> List[Dict]:
    """
    FEAT-005 (Copilot/YNAB "projected spending") + FEAT-001 entegrasyonu: ay-içi harcama
    HIZIYLA her giderin ay-sonu projeksiyonunu REFERANSLA kıyaslar; belirgin aşacaklar için
    ERKEN uyarı. Referans: bir kategori için ZARF (envelope) bütçesi varsa GERÇEK bütçe;
    yoksa geçen ayın aynı kategorisi (yumuşak referans). Salt okuma. Ay başında (< min_days)
    projeksiyon gürültülü → atlanır.
    """
    days_in_month = monthrange(today.year, today.month)[1]
    days_elapsed = today.day
    if days_elapsed < min_days:
        return []

    curr = _month_aggregates(db, user_id, date(today.year, today.month, 1), today)
    prev_year, prev_month = (today.year - 1, 12) if today.month == 1 else (today.year, today.month - 1)
    ps, pe = _month_bounds(prev_year, prev_month)
    prev_by_cat = {c["category"]: c["total"] for c in _month_aggregates(db, user_id, ps, pe)["expense_categories"]}
    # FEAT-001: aktif zarf bütçeleri (varsa gerçek referans)
    envelopes = {e.category: D(e.monthly_amount) for e in db.query(Envelope).filter(
        Envelope.user_id == user_id, Envelope.is_active == True).all()}  # noqa: E712

    warnings: List[Dict] = []
    for c in curr["expense_categories"]:
        cat = c["category"]
        mtd = c["total"]
        if mtd <= 0:
            continue
        if cat in envelopes:
            ref, ref_label = envelopes[cat], "bütçe"       # FEAT-001: gerçek zarf bütçesi
        else:
            ref, ref_label = prev_by_cat.get(cat, 0.0), "geçen ay"
        if ref <= 0:
            continue  # referans yok → yeni-kategori gürültüsü elenir
        projected = round(mtd / days_elapsed * days_in_month, 2)
        if projected > D(ref) * D(over_ratio):  # ADR-030: para Decimal, oran D()
            asim_pct = round((projected - ref) / ref * 100, 1)
            warnings.append({
                "seviye": "uyari",
                "baslik": f"Kategori aşım öngörüsü: {cat}",
                "mesaj": (
                    f"{cat} bu gidişle ay sonu ~{_tl(projected)} TL olur "
                    f"({ref_label} {_tl(ref)} TL, %{asim_pct} fazla). Hız kes."
                ),
                "tutar": projected,        # grounding
                "_proj": projected,        # sıralama için (dışa sızmaz sorun değil)
            })
    warnings.sort(key=lambda w: -w["_proj"])
    for w in warnings:
        w.pop("_proj", None)
    return warnings[:top_n]


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

    total_income = ZERO
    total_expense = ZERO
    tx_count = 0
    expense_by_cat: Dict[str, Dict] = {}
    for r in rows:
        tx_count += r.cnt
        if r.ttype == TransactionType.income:
            total_income += D(r.total)
        else:
            total_expense += D(r.total)
            expense_by_cat[r.category] = {
                "category": r.category,
                "total": round(D(r.total), 2),
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


# ============================================================
# FEAT-006 — ABONELİK DENETÇİSİ (subscription detection)
# ============================================================
# İlham: Rocket Money / Monarch / Copilot abonelik tespiti (araştırıldı, kopya değil).
# Standart yaklaşım: 90-180 gün işlem taraması → merchant grubu → düzenli aralık (aylık/yıllık)
# → tutar eşleşmesi (fiyat artışına tolerans). FinancialOS'te "merchant" = description.
# EKLENEN AYIRT EDİCİ: farklı-tutar sayısı ≤ 2 (abonelik sabit ya da tek fiyat-artışıdır;
# market/yemek gibi değişken harcamada çok sayıda farklı tutar olur → yanlış-pozitif elenir).

_SUB_MIN_OCCURRENCES = 3          # abonelik kabulü için min tekrar
_SUB_MONTHLY_GAP = (24, 35)       # ~aylık medyan aralık (gün)
_SUB_ANNUAL_GAP = (350, 381)      # ~yıllık
_SUB_MAX_DISTINCT_AMOUNTS = 2     # sabit veya tek fiyat-artışı


def _normalize_merchant(desc: str) -> str:
    """Açıklamayı grup anahtarına indirger. RecurringExpense tetikleyicisi '{ad} — {ay}'
    eklediğinden ' — ' sonrasını atarız (aynı aboneliğin ayları birleşsin)."""
    d = (desc or "").strip().lower()
    if " — " in d:
        d = d.split(" — ")[0].strip()
    return " ".join(d.split())


def detect_subscriptions(
    user_id: int, today: date, db: Session, lookback_days: int = 180,
) -> Dict:
    """
    FEAT-006: İşlem geçmişinde tekrarlayan abonelik-benzeri ödemeleri tespit eder.
    Salt okuma (rules_engine ilkesi). Dönüş: {abonelikler:[...], aylik_toplam, yillik_toplam, adet}.

    Bir grup abonelik sayılır ⇔ (a) ≥ _SUB_MIN_OCCURRENCES tekrar, (b) farklı tutar ≤ 2
    (fiyat artışına tolerans, değişken harcama elenir), (c) medyan aralık aylık VEYA yıllık bandında.
    """
    from collections import defaultdict
    start = today - timedelta(days=lookback_days)
    txns = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.expense,
            Transaction.transaction_date >= start,
            Transaction.description.isnot(None),
        )
        .order_by(Transaction.transaction_date)
        .all()
    )

    groups: Dict[str, list] = defaultdict(list)
    for t in txns:
        key = _normalize_merchant(t.description)
        if key:
            groups[key].append(t)

    subscriptions: List[Dict] = []
    for key, items in groups.items():
        if len(items) < _SUB_MIN_OCCURRENCES:
            continue
        items.sort(key=lambda t: t.transaction_date)
        gaps = [
            (items[i + 1].transaction_date - items[i].transaction_date).days
            for i in range(len(items) - 1)
        ]
        gaps = [g for g in gaps if g > 0]
        if not gaps:
            continue
        gaps_sorted = sorted(gaps)
        median_gap = gaps_sorted[len(gaps_sorted) // 2]

        amounts = [round(D(t.amount), 2) for t in items]
        distinct = set(amounts)
        if len(distinct) > _SUB_MAX_DISTINCT_AMOUNTS:
            continue  # değişken harcama (market vb.) — abonelik değil

        if _SUB_MONTHLY_GAP[0] <= median_gap <= _SUB_MONTHLY_GAP[1]:
            period, aylik_maliyet = "monthly", amounts[-1]
        elif _SUB_ANNUAL_GAP[0] <= median_gap <= _SUB_ANNUAL_GAP[1]:
            period, aylik_maliyet = "annual", round(amounts[-1] / 12, 2)
        else:
            continue  # düzensiz aralık — abonelik değil

        subscriptions.append({
            "isim": items[-1].description,        # orijinal (en son) açıklama
            "anahtar": key,
            "period": period,
            "guncel_tutar": amounts[-1],
            "aylik_maliyet": aylik_maliyet,
            "tekrar": len(items),
            "son_tarih": items[-1].transaction_date.isoformat(),
            "fiyat_degisti": len(distinct) >= 2,  # FEAT-007 sinyali: fiyat değişmiş
            "eski_tutar": amounts[0],             # FEAT-007: ilk (en eski) tutar
            "yeni_tutar": amounts[-1],            # FEAT-007: son (güncel) tutar
        })

    subscriptions.sort(key=lambda s: -s["aylik_maliyet"])
    aylik_toplam = round(sum((D(s["aylik_maliyet"]) for s in subscriptions), ZERO), 2)
    return floatify({  # ADR-030/B1: iç Decimal, public sınır float
        "abonelikler": subscriptions,
        "aylik_toplam": aylik_toplam,
        "yillik_toplam": round(aylik_toplam * 12, 2),
        "adet": len(subscriptions),
    })


def _subscription_price_alerts_from_result(sub_result: Dict) -> List[Dict]:
    """FEAT-007: detect_subscriptions SONUCUNDAN sessiz zam uyarılarını türetir (saf).
    Yalnızca artış (yeni > eski) uyarılır — düşüş değil."""
    alerts: List[Dict] = []
    for s in sub_result.get("abonelikler", []):
        eski = s.get("eski_tutar", 0.0)
        yeni = s.get("yeni_tutar", 0.0)
        if s.get("fiyat_degisti") and yeni > eski > 0:
            artis_pct = round((yeni - eski) / eski * 100, 1)
            alerts.append({
                "seviye": "uyari",
                "baslik": f"Abonelik zammı: {s['isim']}",
                "mesaj": (
                    f"{s['isim']} {_tl(eski)} → {_tl(yeni)} TL'ye çıkmış "
                    f"(%{artis_pct} artış). Hâlâ kullanıyor musun?"
                ),
                "tutar": yeni,  # grounding: yeni tutar cockpit'te izlenebilir
            })
    return alerts


def _subscription_price_alerts(user_id: int, today: date, db: Session) -> List[Dict]:
    """Geriye-uyumlu sarıcı (mevcut testler bunu doğrudan çağırır)."""
    return _subscription_price_alerts_from_result(detect_subscriptions(user_id, today, db))


# FEAT-041: "boşta nakit → karta öde" fırsatını önermek için asgari eşik (küçük bakiyeyle
# uğraştırma). Altındaki atanmamış nakit için proaktif borç-ödeme önerisi çıkmaz.
_IDLE_CASH_ACTION_MIN = 500.0


def recommend_next_action(cockpit: Dict) -> Optional[Dict]:
    """
    FEAT-041 (DETERMİNİSTİK SONRAKİ EYLEM — "İLK ADIM"): tüm sinyalleri (alerts, alacak
    yaşlandırma, boşta nakit, kart borcu, kriz) TEK bir "şimdi yapılacak en yüksek etkili
    hamle"ye indirir. Kurucu ilke "Rules Engine karar verir, LLM açıklar"ın en kritik çıktısı:
    öncelik LLM yargısına (Kural 17, zayıf sağlayıcıda güvenilmez) DEĞİL, koda bağlanır →
    sağlayıcı kalitesinden BAĞIMSIZ güvenilir #1 eylem. Koç bunu AÇIKLAR, türetmez. Salt okuma.

    Öncelik sırası (hayatta kalma > fırsat): temerrüt riski → nakit krizi → gecikmiş tahsilat
    → boşta nakdi borca (fırsat) → yolunda. Dönüş: {tip, eylem, gerekce, tutar} veya None (borç
    yok + acil yok). `tip`: 'temerrut'|'kriz'|'tahsilat'|'firsat'|'stabil'.
    """
    alerts = cockpit.get("alerts") or []
    if not isinstance(alerts, list):   # savunmacı: generate_cockpit hep liste verir, ama saf/dışa-açık
        alerts = []
    kritikler = [a for a in alerts if isinstance(a, dict) and a.get("seviye") == "kritik"]

    # 1. TEMERRÜT — gecikmiş BORÇ (ceza/temerrüt riski) her şeyin önünde.
    gecikmis_borc = next((a for a in kritikler if "Gecikmiş borç" in a.get("baslik", "")), None)
    if gecikmis_borc:
        return {
            "tip": "temerrut",
            "eylem": gecikmis_borc.get("baslik", "Gecikmiş borcu öde"),
            "gerekce": gecikmis_borc.get("mesaj", ""),
            "tutar": gecikmis_borc.get("tutar"),
        }

    # Savunmacı (alerts guard'ıyla tutarlı): alacak_yaslanma bozuk/eksik gelse de çökmemeli.
    # en_riskli yalnız TAM bir dict ise kullanılır (aşağıdaki 'kim'/'tutar'/'gecikme_gun'
    # erişimleri KeyError üretmesin) — production'da generate_cockpit hep tam verir.
    ay = cockpit.get("alacak_yaslanma")
    if not isinstance(ay, dict):
        ay = {}
    _er_list = ay.get("en_riskli")
    _er = _er_list[0] if isinstance(_er_list, list) and _er_list else None
    en_riskli = _er if (isinstance(_er, dict) and {"kim", "tutar", "gecikme_gun"} <= _er.keys()) else None

    # 2. NAKİT KRİZİ öngörüsü — henüz olmadan müdahale. En riskli alacağı tahsil ETMEK krizi
    # önler (nakit girişi); alacak yoksa gideri ertele.
    crunch = next((a for a in kritikler if "kriz" in a.get("baslik", "").lower()), None)
    if crunch:
        if en_riskli:
            return {
                "tip": "kriz",
                "eylem": f"{en_riskli['kim']}'den {_tl(en_riskli['tutar'])} TL tahsil et",
                "gerekce": (f"Nakit krizi öngörülüyor; {en_riskli['gecikme_gun']} gün geciken bu "
                            f"tahsilat krizi önleyebilir. {crunch.get('mesaj', '')}"),
                "tutar": en_riskli["tutar"],
            }
        return {
            "tip": "kriz",
            "eylem": "Ertelenebilir gideri ertele / harcamayı kes",
            "gerekce": crunch.get("mesaj", "Nakit krizi öngörülüyor."),
            "tutar": crunch.get("tutar"),
        }

    # 3. GECİKMİŞ TAHSİLAT — kriz yoksa da geciken alacak nakit girişidir (solvency-dostu).
    _gecikmis_adet = ay.get("gecikmis_adet", 0)
    if isinstance(_gecikmis_adet, (int, float)) and _gecikmis_adet > 0 and en_riskli:
        return {
            "tip": "tahsilat",
            "eylem": f"{en_riskli['kim']}'den {_tl(en_riskli['tutar'])} TL tahsil et",
            "gerekce": (f"{_gecikmis_adet} gecikmiş alacağın var (toplam "
                        f"{_tl(ay.get('toplam_gecikmis') or 0)} TL); en eskisi {en_riskli['gecikme_gun']} gün. "
                        f"Nakit dar — önce en eskisini tahsil et."),
            "tutar": en_riskli["tutar"],
        }

    # 4. FIRSAT — boşta nakit + kart borcu + kriz YOK → karta öde (faiz sızıntısını durdur).
    # GÜVENLİK: yalnız nakit BOL iken öner (runway None=gidersiz/sonsuz veya ≥30 gün). Nakit
    # dar iken (runway<30) boşta görünen nakdi karta yatırmak yakın likidite ihtiyacını riske
    # atabilir — realist koç dar nakitte cash-tüketen tavsiye vermez (crunch yoksa bile).
    atanmamis = cockpit.get("atanmamis_nakit", 0) or 0
    kart_borcu = cockpit.get("kart_borcu", 0) or 0
    runway = cockpit.get("nakit_runway_gun")
    nakit_bol = runway is None or runway >= 30
    if atanmamis >= _IDLE_CASH_ACTION_MIN and kart_borcu > 0 and nakit_bol:
        odenebilir = round(min(atanmamis, kart_borcu), 2)
        fs = cockpit.get("faiz_sizintisi")
        if not isinstance(fs, dict):
            fs = {}
        _aylik_faiz = fs.get("aylik_toplam") or 0   # present-but-None → 0 (savunmacı; None>0 çökerdi)
        gerekce = f"{_tl(atanmamis)} TL boşta nakdin var, kart borcun {_tl(kart_borcu)} TL."
        if _aylik_faiz > 0:
            gerekce += f" Karta ödemek aylık faiz sızıntısını ({_tl(_aylik_faiz)} TL) azaltır."
        return {
            "tip": "firsat",
            "eylem": f"Boşta {_tl(odenebilir)} TL'yi kart borcuna öde",
            "gerekce": gerekce,
            "tutar": odenebilir,
        }

    # 5. STABİL — acil hamle yok. Borç varsa disipline (borçsuzluk tarihiyle motive et), yoksa None.
    if kart_borcu > 0 or (cockpit.get("kredi_borcu", 0) or 0) > 0:
        gunluk = cockpit.get("daily_limit", 0) or 0   # present-but-None → 0 (savunmacı; _tl(None) çökerdi)
        gerekce = f"Bugünlük kritik sinyal yok. Günlük limit {_tl(gunluk)} TL; her aşmama borcu hızlandırır."
        bo = cockpit.get("borc_ozgurluk") or {}
        if bo.get("borcsuz_tarih") and not bo.get("asla_bitmez"):
            gerekce += f" Bu tempoyla {bo['borcsuz_tarih']} tarihinde borçsuzsun — disiplin bunu öne çeker."
        return {
            "tip": "stabil",
            "eylem": "Acil bir hamle yok — günlük limitine sadık kal, borcu erit",
            "gerekce": gerekce,
            "tutar": None,
        }
    return None


# FEAT-015: kart asgari-ödeme tuzağı uyarı eşiği. 12 ay = min-only'nin "kuyruk" sınırı;
# altında zaten hızlı kapanır, üstünde faiz sızıntısı stratejik uyarıyı hak eder.
_MIN_TRAP_ALERT_MONTHS = 12


def _min_payment_trap_alerts(trap: Optional[Dict]) -> List[Dict]:
    """
    FEAT-015: asgari-ödeme tuzağı uyarısı. Kart SADECE asgari ödemeyle ASLA kapanmıyorsa
    (asgari < aylık faiz → borç sarmalı) KRİTİK; uzun kuyruk (≥12 ay) ise stratejik UYARI.
    Yalnızca EN KÖTÜ kart bildirilir (alert yorgunluğu #126 — gürültü yok). Salt sunum.
    """
    if not trap or not trap.get("kartlar"):
        return []
    worst = trap["en_yuksek_faiz"]
    if worst.get("asla_bitmez"):
        return [{
            "seviye": "kritik",
            "baslik": "Kart asgari ödeme sarmalı",
            "mesaj": (
                f"{worst['ad']} kartı SADECE asgari ödemeyle ASLA kapanmaz — asgari ödeme aylık "
                f"faizin altında, borç büyüyor. Asgarinin belirgin üstüne öde."
            ),
            "tutar": worst["bakiye"],  # grounding: bakiye cockpit'te (asgari_tuzagi) izlenebilir
        }]
    if worst.get("ay", 0) >= _MIN_TRAP_ALERT_MONTHS:
        return [{
            "seviye": "uyari",
            "baslik": "Kart asgari ödeme tuzağı",
            "mesaj": (
                f"{worst['ad']} kartını yalnız asgariyle ödersen {worst['ay']} ay sürünür ve "
                f"{_tl(worst['toplam_faiz'])} TL faiz ödersin (biter {worst['payoff_tarih']}). "
                f"Asgarinin üstüne ekle — süre ve faiz hızla düşer."
            ),
            "tutar": worst["toplam_faiz"],  # grounding: toplam_faiz cockpit'te izlenebilir
        }]
    return []


def calculate_envelopes(user_id: int, today: date, db: Session) -> Dict:
    """
    FEAT-001 (YNAB/Actual Budget zarf yöntemi): aktif bütçe zarflarının BU AY durumu.
    Salt okuma. Harcanan = bu ayın o kategorideki gider toplamı (Transaction — tek doğruluk
    kaynağı, ayrı allocation yok). kalan = bütçe - harcanan; aşıldıysa görünür işaret.

    Dönüş: {zarflar:[{category, butce, harcanan, kalan, yuzde, asildi}], toplam_butce,
             toplam_harcanan, toplam_kalan, asan_adet}. Zarf yoksa boş.
    """
    envs = db.query(Envelope).filter(
        Envelope.user_id == user_id, Envelope.is_active == True,  # noqa: E712
    ).all()
    if not envs:
        return {"zarflar": [], "toplam_butce": 0.0, "toplam_harcanan": 0.0,
                "toplam_kalan": 0.0, "asan_adet": 0}

    curr = _month_aggregates(db, user_id, date(today.year, today.month, 1), today)
    spent_by_cat = {c["category"]: c["total"] for c in curr["expense_categories"]}

    zarflar: List[Dict] = []
    toplam_butce = toplam_harcanan = ZERO
    asan = 0
    for e in envs:
        butce = D(e.monthly_amount)
        harcanan = D(spent_by_cat.get(e.category, 0.0))
        asildi = harcanan > butce
        if asildi:
            asan += 1
        toplam_butce += butce
        toplam_harcanan += harcanan
        zarflar.append({
            "category": e.category,
            "butce": round(butce, 2),
            "harcanan": round(harcanan, 2),
            "kalan": round(butce - harcanan, 2),
            "yuzde": round(harcanan / butce * 100, 1) if butce > 0 else 0.0,
            "asildi": asildi,
        })
    zarflar.sort(key=lambda z: -z["yuzde"])  # en dolu/aşan önce
    return floatify({  # ADR-030/B1: iç Decimal, public sınır float
        "zarflar": zarflar,
        "toplam_butce": round(toplam_butce, 2),
        "toplam_harcanan": round(toplam_harcanan, 2),
        "toplam_kalan": round(toplam_butce - toplam_harcanan, 2),
        "asan_adet": asan,
    })


# FEAT-027: alacak yaşlandırma kova sınırları (gün, gecikme). Muhasebe AR-aging standardı.
_AGING_BUCKETS = (
    (61, "60+ gün gecikmiş"),
    (31, "31-60 gün gecikmiş"),
    (1, "1-30 gün gecikmiş"),
)


def calculate_receivables_aging(user_id: int, today: date, db: Session) -> Optional[Dict]:
    """
    FEAT-027 (alacak yaşlandırma / AR aging): ödenmemiş alacakları (Murat'ın 13 dağınık
    alacağı) vade yaşına göre gruplar — hangi alacağın peşine ÖNCE düşüleceğini netleştirir.
    Nakit dar; zamanında tahsilat solvency-kritik (koç Kural 12). Salt okuma.

    Kovalar (öncelik: en çok geciken önce): 60+ / 31-60 / 1-30 gün gecikmiş · vadesi
    gelmemiş · tarihsiz. Boş kova atlanır. `en_riskli` = en çok geciken 3 kalem. Alacak
    yoksa None. Gecikme = (today - due_date).gün; due_date None → "tarihsiz" (kör nokta).
    """
    debts = db.query(PersonalDebt).filter(
        PersonalDebt.user_id == user_id,
        PersonalDebt.direction == DebtDirection.receivable,
        PersonalDebt.is_paid == False,  # noqa: E712
    ).all()
    if not debts:
        return None

    # etiket → kalem listesi (sıralı kova düzenini korumak için ayrı ordered anahtar listesi)
    _order = [lbl for _, lbl in _AGING_BUCKETS] + ["vadesi gelmemiş", "tarihsiz"]
    kova_map: Dict[str, List[Dict]] = {lbl: [] for lbl in _order}
    gecikmis_kalemler: List[Dict] = []

    for d in debts:
        if d.due_date is None:
            etiket, gecikme = "tarihsiz", 0
        else:
            gecikme = (today - d.due_date).days
            if gecikme >= 1:
                etiket = next(lbl for gun, lbl in _AGING_BUCKETS if gecikme >= gun)
            else:
                etiket = "vadesi gelmemiş"
        kalem = {
            "kim": d.counterparty,
            "tutar": round(D(d.amount), 2),
            "gecikme_gun": gecikme,
            "due_date": d.due_date.isoformat() if d.due_date else None,
            "aciklama": d.description or "",
        }
        kova_map[etiket].append(kalem)
        if gecikme >= 1:
            gecikmis_kalemler.append(kalem)

    kovalar = [
        {
            "etiket": lbl,
            "adet": len(kova_map[lbl]),
            "tutar": round(sum(k["tutar"] for k in kova_map[lbl]), 2),
            "kalemler": sorted(kova_map[lbl], key=lambda k: -k["gecikme_gun"]),
        }
        for lbl in _order if kova_map[lbl]
    ]
    toplam = round(sum(D(d.amount) for d in debts), 2)
    toplam_gecikmis = round(sum(k["tutar"] for k in gecikmis_kalemler), 2)
    return {
        "toplam": toplam,
        "adet": len(debts),
        "toplam_gecikmis": toplam_gecikmis,
        "gecikmis_adet": len(gecikmis_kalemler),
        "kovalar": kovalar,
        "en_riskli": sorted(gecikmis_kalemler, key=lambda k: -k["gecikme_gun"])[:3],
    }


def calculate_interest_leak(user_id: int, db: Session) -> Dict:
    """
    FEAT-013 (faiz sızıntısı sayacı): kredi + kart borçlarının AYLIK faiz maliyeti. Murat'ın
    5 kredi + dolu kartında "her ay faize kaç TL kaptırıyorsun" görünür olur — realist koçun
    en sarsıcı metriklerinden. Salt hesap: aylık_faiz = borç × (aylık_faiz_oranı/100).
    interest_rate yoksa (None) o hesap atlanır. Emanet/yatırım hariç.
    """
    accs = db.query(Account).filter(
        Account.user_id == user_id,
        Account.account_type.in_([AccountType.loan, AccountType.credit_card]),
    ).all()
    kalemler: List[Dict] = []
    aylik_toplam = ZERO
    for a in accs:
        borc = D(a.balance or 0.0)
        oran = float(a.interest_rate or 0.0)
        if borc <= 0 or oran <= 0:
            continue
        aylik = round(borc * D(oran) / 100, 2)  # ADR-030: borc Decimal, oran (%) → D()
        aylik_toplam += aylik
        kalemler.append({
            "ad": a.name,
            "borc": round(borc, 2),
            "aylik_oran": oran,
            "aylik_faiz": aylik,
        })
    kalemler.sort(key=lambda k: -k["aylik_faiz"])  # en çok sızdıran önce
    aylik_toplam = round(aylik_toplam, 2)
    return {
        "kalemler": kalemler,
        "aylik_toplam": aylik_toplam,
        "yillik_toplam": round(aylik_toplam * 12, 2),
        "gunluk": round(aylik_toplam / 30, 2),  # ADR-030: para Decimal / int
    }


# FEAT-024: yıllık enflasyon varsayımı — Türkiye'de dominant servet faktörü. .env ile ayarlanır.
_INFLATION_ANNUAL = float(os.getenv("INFLATION_ANNUAL", "0.40"))


# FEAT-017: borç azaltma kilometre taşları (Ramsey: DİSKRET kutlama sürekli metrikten daha
# motive edicidir). Yüksekten düşüğe kontrol edilir; ulaşılan EN YÜKSEK band döner.
_DEBT_MILESTONES = (75, 50, 25, 10)


def _debt_milestone_band(yuzde: float) -> int:
    """Verilen borç-azaltma %'sinin ulaştığı en yüksek kilometre taşı (0 = <%10)."""
    for m in _DEBT_MILESTONES:
        if yuzde >= m:
            return m
    return 0


def calculate_debt_progress(
    user_id: int, today: date, db: Session, guncel_borc: float,
) -> Optional[Dict]:
    """
    FEAT-017 (borç ödeme ilerlemesi — motivasyon): en eski NetWorthSnapshot'tan bugüne toplam
    borç (kart+kredi) ne kadar AZALDI. Borç-batık için momentum (Ramsey: davranışsal başarı
    faktörü #1). "Başladığından beri X TL / %Y borç ödedin." Salt hesap; yeterli geçmiş yoksa
    veya başlangıç borcu 0 ise None. `guncel_borc` = kart+kredi (çağırandan, re-query yok).

    Not: pozitif = ilerleme (borç azaldı); negatif = borç büyüdü (realist koç bunu da dürüstçe
    yansıtır). Sadece anlamlı geçmişte (≥7 gün) döner — gürültü/aynı-gün sıçraması olmasın.

    KİLOMETRE TAŞI: `milestone` = ulaşılan en yüksek band (%10/25/50/75), `yeni_milestone` =
    en son snapshot'tan BUGÜNE band ARTTIYSA o band (taze geçiş → koç kutlar), yoksa None.
    Diskret kutlama sürekli metrikten daha motive edici (Ramsey), ama sadece GERÇEK geçişte.
    """
    earliest = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == user_id).order_by(NetWorthSnapshot.snapshot_date.asc()).first()
    if not earliest:
        return None
    gun = (today - earliest.snapshot_date).days
    if gun < 7:
        return None  # anlamlı trend için en az bir hafta
    baslangic_borc = D(earliest.card_debt) + D(earliest.loan_debt)
    if baslangic_borc <= 0:
        return None
    odendi = round(baslangic_borc - guncel_borc, 2)   # + = ilerleme, − = borç büyüdü
    yuzde = round(odendi / baslangic_borc * 100, 1)
    milestone = _debt_milestone_band(yuzde)

    # Taze geçiş tespiti: bugünden ÖNCEKİ en son snapshot'ın band'ı ile karşılaştır.
    yeni_milestone = None
    if milestone > 0:
        prev = db.query(NetWorthSnapshot).filter(
            NetWorthSnapshot.user_id == user_id,
            NetWorthSnapshot.snapshot_date < today,
        ).order_by(NetWorthSnapshot.snapshot_date.desc()).first()
        if prev is not None:
            prev_odendi = baslangic_borc - (D(prev.card_debt) + D(prev.loan_debt))
            prev_band = _debt_milestone_band(round(prev_odendi / baslangic_borc * 100, 1))
            if milestone > prev_band:   # band bu snapshot aralığında ARTTI → taze kutlama
                yeni_milestone = milestone

    return floatify({  # ADR-030/B1: public sınır float
        "baslangic_tarih": earliest.snapshot_date.isoformat(),
        "gun": gun,
        "baslangic_borc": round(baslangic_borc, 2),
        "guncel_borc": round(guncel_borc, 2),
        "odendi": odendi,
        "yuzde": yuzde,
        "ilerleme": odendi > 0,
        "milestone": milestone,            # ulaşılan en yüksek band (0/10/25/50/75)
        "yeni_milestone": yeni_milestone,  # taze geçiş → koç kutlar (yoksa None)
    })


# FEAT-016: kredi kartı kullanım oranı bantları (kredi-skoru davranışında genel eşikler).
# %30 altı "sağlıklı" — kredi notunda en ağır tek faktörlerden biri kullanım oranıdır.
_UTIL_HEALTHY: float = 30.0
_UTIL_HIGH: float = 70.0
_UTIL_CRITICAL: float = 90.0


def calculate_card_utilization(
    user_id: int, today: date, db: Session, accounts: Optional[List] = None,
) -> Optional[Dict]:
    """
    FEAT-016: Kredi kartı KULLANIM ORANI (utilization) + iyileşme trendi + kredi-sağlık bandı.

    Oran = toplam kart borcu / toplam kart limiti. Kredi notu davranışında en ağır tek
    faktörlerden biridir; %30 altı sağlıklı sayılır. Murat %99.8'de → notu baskılıyor, her
    ödenen TL oranı düşürür. `saglikli_borc_hedefi` = %30'a inmek için borç seviyesi (somut çapa).

    Trend: en eski NetWorthSnapshot'ın kart borcu, GÜNCEL toplam limitle oranlanır (limit
    stabil varsayımı — kart limiti nadiren değişir) → bugünün oranıyla karşılaştırılır. ≥7 gün
    geçmiş gerekir. Salt hesap; kart yoksa veya toplam limit 0 ise None. `accounts` verilirse
    re-query yapılmaz (generate_cockpit zaten çekmiştir).
    """
    if accounts is None:
        accounts = db.query(Account).filter(Account.user_id == user_id).all()
    cards = [a for a in accounts if a.account_type == AccountType.credit_card]
    toplam_limit = sum(D(c.credit_limit or 0) for c in cards)
    toplam_borc = sum(D(c.balance or 0) for c in cards)
    if not cards or toplam_limit <= 0:
        return None

    oran = round(toplam_borc / toplam_limit * 100, 1)
    if oran >= _UTIL_CRITICAL:
        band = "kritik"
    elif oran >= _UTIL_HIGH:
        band = "yuksek"
    elif oran >= _UTIL_HEALTHY:
        band = "orta"
    else:
        band = "saglikli"

    # İyileşme trendi — limit stabil varsayımıyla geçmiş kart borcunu bugünkü limitle oranla.
    trend = None
    earliest = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == user_id).order_by(NetWorthSnapshot.snapshot_date.asc()).first()
    if earliest:
        gun = (today - earliest.snapshot_date).days
        if gun >= 7:
            oran_onceki = round(D(earliest.card_debt) / toplam_limit * 100, 1)
            trend = {
                "baslangic_tarih": earliest.snapshot_date.isoformat(),
                "gun": gun,
                "baslangic_oran": oran_onceki,
                "degisim": round(oran - oran_onceki, 1),  # negatif = iyileşme (oran düştü)
                "iyilesme": oran < oran_onceki,
            }

    saglikli_borc_hedefi = round(toplam_limit * D(_UTIL_HEALTHY) / 100, 2)  # ADR-030: limit Decimal * oran D()
    kalan_limit = round(toplam_limit - toplam_borc, 2)
    if band == "kritik":
        mesaj = (
            f"Kart kullanımın %{oran} — neredeyse dolu. Kredi notunu baskılar ve acil "
            f"nakit tamponun yok. %30'a inmek için borç {_tl(saglikli_borc_hedefi)} TL "
            f"seviyesine düşmeli; her ödediğin TL oranı doğrudan iyileştirir."
        )
    elif band == "yuksek":
        mesaj = (
            f"Kart kullanımın %{oran} — yüksek. %30 altı sağlıklı sayılır; "
            f"{_tl(saglikli_borc_hedefi)} TL borç seviyesi hedef."
        )
    elif band == "orta":
        mesaj = f"Kart kullanımın %{oran} — sağlıklı eşiğe (%30) yakın, iyi yoldasın."
    else:
        mesaj = f"Kart kullanımın %{oran} — sağlıklı aralıkta (%30 altı). Tamponun korunuyor."

    return floatify({  # ADR-030/B1: public sınır float
        "oran": oran,
        "band": band,
        "toplam_borc": round(toplam_borc, 2),
        "toplam_limit": round(toplam_limit, 2),
        "kalan_limit": kalan_limit,
        "saglikli_esik": _UTIL_HEALTHY,
        "saglikli_borc_hedefi": saglikli_borc_hedefi,
        "kart_adet": len(cards),
        "trend": trend,
        "mesaj": mesaj,
    })


def calculate_real_networth(
    user_id: int, today: date, db: Session, annual_inflation: Optional[float] = None,
) -> Optional[Dict]:
    """
    FEAT-024 (enflasyon-düzeltilmiş / REEL net değer): Türkiye'de enflasyon serveti eritir —
    nominal net değer artsa bile REEL (satın alma gücü) olarak azalabilir. Tersine, BORÇLU için
    enflasyon borcu eritir (reel yük azalır). Bu ayrım realist koçun kritik içgörüsü.

    En eski ↔ en güncel snapshot arası: nominal değişim vs enflasyona göre deflate edilmiş reel
    değişim. Yeterli geçmiş yoksa None. Salt hesap; enflasyon varsayımı parametre (.env INFLATION_ANNUAL).
    """
    if annual_inflation is None:
        annual_inflation = _INFLATION_ANNUAL
    earliest = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == user_id).order_by(NetWorthSnapshot.snapshot_date.asc()).first()
    latest = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == user_id).order_by(NetWorthSnapshot.snapshot_date.desc()).first()
    if not earliest or not latest or earliest.id == latest.id:
        return None
    gun = (latest.snapshot_date - earliest.snapshot_date).days
    if gun < 1:
        return None

    factor = (1 + annual_inflation) ** (gun / 365.0)   # dönem enflasyon faktörü (oran, float)
    reel_guncel = latest.net_worth_full / D(factor)     # ADR-030: net_worth Decimal / faktör D()
    nominal_degisim = latest.net_worth_full - earliest.net_worth_full
    reel_degisim = reel_guncel - earliest.net_worth_full
    return floatify({  # ADR-030/B1: public sınır float
        "baslangic_tarih": earliest.snapshot_date.isoformat(),
        "gun": gun,
        "baslangic_net": round(earliest.net_worth_full, 2),
        "nominal_net": round(latest.net_worth_full, 2),
        "reel_net": round(reel_guncel, 2),               # başlangıç satın alma gücüyle
        "nominal_degisim": round(nominal_degisim, 2),
        "reel_degisim": round(reel_degisim, 2),
        "enflasyon_etkisi": round(reel_degisim - nominal_degisim, 2),  # enflasyonun aşındırdığı/erittiği
        "yillik_enflasyon": annual_inflation,
    })


def calculate_networth_attribution(user_id: int, today: date, db: Session) -> Optional[Dict]:
    """
    FEAT-021 (net değer değişim ayrıştırması): bu ayki net değer değişimini SÜRÜCÜLERİNE ayırır
    (snapshot'lardan, objektif). "Net değerin +X TL: nakit +A, kart borcu ödeme +B, kredi +C,
    yatırım +D, alacak +E." net_deger = nakit + yatırım + alacak - kart - kredi olduğundan
    Δnet = Δnakit + Δyatırım + Δalacak - Δkart - Δkredi (sürücüler toplamı = değişim).

    Referans: bu ayın 1'ine (veya öncesine) en yakın snapshot. Yeterli geçmiş yoksa None.
    """
    latest = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == user_id).order_by(NetWorthSnapshot.snapshot_date.desc()).first()
    if not latest:
        return None
    ref_date = date(today.year, today.month, 1)
    ref = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.user_id == user_id,
        NetWorthSnapshot.snapshot_date <= ref_date,
    ).order_by(NetWorthSnapshot.snapshot_date.desc()).first()
    if not ref or ref.id == latest.id:
        return None  # ay başı referansı yok / tek snapshot → ayrıştırma anlamsız

    surucureler = [
        {"ad": "Nakit", "katki": round(latest.cash - ref.cash, 2)},
        {"ad": "Kart borcu ödeme", "katki": round(ref.card_debt - latest.card_debt, 2)},
        {"ad": "Kredi ödeme", "katki": round(ref.loan_debt - latest.loan_debt, 2)},
        {"ad": "Yatırım", "katki": round(latest.investment_value - ref.investment_value, 2)},
        {"ad": "Alacak", "katki": round(latest.receivables - ref.receivables, 2)},
    ]
    surucureler.sort(key=lambda x: -abs(x["katki"]))  # en etkili sürücü önce
    return {
        "baslangic_tarih": ref.snapshot_date.isoformat(),
        "baslangic_net": round(ref.net_worth_full, 2),
        "guncel_net": round(latest.net_worth_full, 2),
        "degisim": round(latest.net_worth_full - ref.net_worth_full, 2),
        "surucureler": surucureler,
    }


def calculate_health_score(
    *, reel_butce: float, kart_borcu: float, kart_limit: float, aylik_faiz: float,
    aylik_gelir: float, runway_gun, crunch_var: bool, zarf_asan, zarf_var: bool,
) -> Dict:
    """
    FEAT-022 (finansal sağlık skoru): 0-100 composite. ŞEFFAF — bileşenler görünür (kara kutu
    değil, realist etik). Veri olmayan bileşen atlanır; skor = mevcut bileşenlerin ortalaması.

    Bileşenler (her biri 0-100):
      Ödeme gücü   : crunch→20, reel_butce≥0→100, negatif→40
      Faiz yükü    : 1 - (aylık faiz / aylık gelir); %30 gelir faize giderse 0
      Nakit tamponu: runway/90 (90 gün+ → 100)
      Kart sağlığı : 1 - kullanım oranı (borç/limit)
      Bütçe uyumu  : aşan zarf yoksa 100; her aşan -25
    """
    bilesenler: List[Dict] = []

    if crunch_var:
        s = 20
    elif reel_butce >= 0:
        s = 100
    else:
        s = 40
    bilesenler.append({"ad": "Ödeme gücü", "puan": s})

    if aylik_gelir > 1:  # anlamlı gelir eşiği: denormal/sıfıra-yakın bölen → inf overflow'u ele
        oran = min(aylik_faiz / aylik_gelir, 10.0)  # oran cap: aşırı değerde round(inf) çökmesin
        bilesenler.append({"ad": "Faiz yükü", "puan": max(0, min(100, round(100 - oran * 333)))})

    if runway_gun is not None:
        bilesenler.append({"ad": "Nakit tamponu", "puan": max(0, min(100, round(runway_gun / 90 * 100)))})

    if kart_limit > 0:
        util = min(kart_borcu / kart_limit, 1.0)  # cap: denormal limitte inf→round çökmesin; >limit zaten 0
        bilesenler.append({"ad": "Kart sağlığı", "puan": max(0, min(100, round((1 - util) * 100)))})

    if zarf_var:
        bilesenler.append({"ad": "Bütçe uyumu", "puan": 100 if zarf_asan == 0 else max(0, 100 - zarf_asan * 25)})

    skor = round(sum(b["puan"] for b in bilesenler) / len(bilesenler)) if bilesenler else 50
    seviye = "iyi" if skor >= 70 else "orta" if skor >= 40 else "kritik"
    return {"skor": skor, "seviye": seviye, "bilesenler": bilesenler}


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

    nakit = ZERO
    kart_borcu = ZERO
    yatirim_deger = ZERO
    emanet_deger = ZERO
    kredi_borcu = ZERO
    accounts_detail = []

    investment_pnl_list = []

    for acc in accounts:
        # BUG #007 FIX: investment hesaplari icin balance her zaman lot * fiyat.
        # Boylece DB'deki balance (Midas'tan girilen 31.342,82) ile hesaplanan
        # deger (6 * 5223.81 = 31.342,86) arasindaki 4 kurus tutarsizligi
        # frontend'den gozukmez.
        if acc.account_type == AccountType.investment and acc.lot_count and acc.current_price:
            display_balance = round(D(acc.lot_count) * acc.current_price, 2)  # ADR-030: lot(float)→D
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
            value = D(acc.lot_count or 0) * D(acc.current_price or 0)  # ADR-030: lot(float)+fiyat→D
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
    borclar_toplami = _calculate_total_payables(user_id, db)  # BUG #116: kişisel payable
    # Simetri + finansal doğruluk: alacaklar varlık (+), kişisel borçlar yükümlülük (−).
    net_deger_tam = round(net_deger + alacaklar_toplami - borclar_toplami, 2)

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

    # ZİKZAK PROJEKSİYONU (kurucu "biriken güç" — Gemini sohbetlerinin ekseni):
    # Bugün harcamazsan reel_butce aynı kalır, kalan gün 1 azalır → yarınki dinamik limit
    # yükselir. ADR-026 ile TUTARLI: additive DEĞİL, aynı bütçenin bir gün az güne bölünmesi
    # (çift-sayım yok). Koç bunu "bugün nöbet tutarsan yarın limitin X'e çıkar" diye kullanır.
    yarin_limit_harcamasiz = (
        round(reel_butce / (days_remaining - 1), 2) if days_remaining > 1
        else round(reel_butce, 2)  # son gün: tüm kalan bütçe bugünündür
    )

    # Yaklaşan ödemeler ve tahsilatlar
    upcoming_payments = _collect_upcoming_loan_payments(user_id, today, db)
    upcoming_payments.extend(upcoming_incomes)
    upcoming_payments = sorted(upcoming_payments, key=lambda x: x["tarih"])

    upcoming_receivables = _collect_upcoming_receivables(user_id, today, db)

    # Statü cümlesi
    if reel_butce < 0:
        statu = "Reel bütçe negatif — kart borcu nakdi aşıyor. Hayatta kalma modu."
    elif nakit > 0 and kart_borcu / nakit > 2:  # RULE-009: max(nakit,1) çarpıtması yerine nakit>0 guard
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
    # BUG #120: vadesi geçmiş borç/alacak gecikme uyarıları (detect_alerts scalar-saf
    # kaldığından ayrı DB helper'ı; kritik gecikmeler listenin başına alınır).
    overdue_alerts = _collect_overdue_debts(user_id, today, db)
    kritik_front = [a for a in overdue_alerts if a["seviye"] == "kritik"]
    # BUG #121 + FEAT-009: forecast'i BİR KEZ hesapla; hem nakit krizi alert'i hem
    # güvenli-harcama metriğini aynı summary'den türet (çift hesaplama yok).
    cashflow_summary = _cashflow_forecast_summary(user_id, today, db)
    crunch_alert = _crunch_alert_from_summary(cashflow_summary)  # kritik, gecikmelerden sonra
    if crunch_alert:
        kritik_front.append(crunch_alert)
    # FEAT-006/007: abonelikleri BİR KEZ tespit et → hem zam uyarıları hem toplam yük.
    sub_result = detect_subscriptions(user_id, today, db)
    sub_price_alerts = _subscription_price_alerts_from_result(sub_result)  # FEAT-007
    overspend_alerts = _category_overspend_alerts(user_id, today, db)      # FEAT-005
    # FEAT-012/015: borçları BİR KEZ topla → hem asgari-ödeme tuzağı uyarısı (FEAT-015) hem
    # borçsuzluk tarihi (FEAT-012, aşağıda) aynı listeden türetilir (çift collect_debts yok).
    _dbts = []
    asgari_tuzagi = None
    konsolidasyon = None
    trap_alerts: List[Dict] = []
    try:
        from app.debt_strategy import (collect_debts as _collect_debts,
                                        calculate_min_payment_trap, calculate_consolidation_baseline)
        _dbts = _collect_debts(db, user_id)
        asgari_tuzagi = calculate_min_payment_trap(_dbts, today=today)  # FEAT-015
        konsolidasyon = calculate_consolidation_baseline(_dbts)         # FEAT-014 (proaktif eşik)
        trap_alerts = _min_payment_trap_alerts(asgari_tuzagi)
    except Exception as e:
        logger.warning("borç metrikleri (tuzak/konsolidasyon) hesaplanamadı user_id=%s: %s", user_id, e)
    alerts = kritik_front + alerts + \
             [a for a in overdue_alerts if a["seviye"] != "kritik"] + \
             sub_price_alerts + overspend_alerts + trap_alerts
    # #125: KARARLI önem sıralaması — tüm 'kritik' kalemler tüm 'uyari'lardan önce (iç sıra korunur).
    # detect_alerts kritik/uyari'yi karıştırıyordu; Murat en ciddi sinyali her zaman en başta görsün.
    _SEV = {"kritik": 0, "uyari": 1}
    alerts.sort(key=lambda a: _SEV.get(a.get("seviye"), 2))
    # #126: alert yorgunluğu — TÜM kritikler kalır (solvency emniyeti), uyarılar top-3 ile sınırlı.
    # Maksimal senaryoda 10 alert gözlemlendi; okunmaz. Gizlenen uyarı sayısı ayrı alanda.
    _MAX_UYARI = 3
    _kritikler = [a for a in alerts if a.get("seviye") == "kritik"]
    _uyarilar = [a for a in alerts if a.get("seviye") != "kritik"]
    gizli_uyari_sayisi = max(0, len(_uyarilar) - _MAX_UYARI)
    alerts = _kritikler + _uyarilar[:_MAX_UYARI]
    guvenli_harcama = _calculate_safe_to_spend(cashflow_summary, kart_borcu=kart_borcu)  # FEAT-009 + #123 kart-farkındalığı
    nakit_runway_gun = _calculate_cash_runway(user_id, today, db, nakit)  # FEAT-010
    zarflar_durumu = calculate_envelopes(user_id, today, db)  # FEAT-001
    # FEAT-002 (YNAB "Ready to Assign" / her liraya görev): zarflara henüz taahhüt edilmemiş nakit.
    # Taahhüt = zarfların kalan (harcanmamış) pozitif bütçesi. Negatif atanmamış = aşırı-bütçeleme.
    # ADR-030: zarflar_durumu public-float; iç Decimal math için D() ile geri çek (2dp, kayıpsız)
    _zarf_taahhut = sum((D(max(0.0, z["kalan"])) for z in zarflar_durumu["zarflar"]), ZERO)
    atanmamis_nakit = round(nakit - _zarf_taahhut, 2)
    faiz_sizintisi = calculate_interest_leak(user_id, db)  # FEAT-013
    alacak_yaslanma = calculate_receivables_aging(user_id, today, db)  # FEAT-027
    borc_ilerleme = calculate_debt_progress(user_id, today, db, kart_borcu + kredi_borcu)  # FEAT-017
    kart_kullanim = calculate_card_utilization(user_id, today, db, accounts)  # FEAT-016 (accounts re-query yok)
    # FEAT-022: finansal sağlık skoru (şeffaf composite)
    _aylik_gelir = D(db.query(func.coalesce(func.sum(RecurringIncome.amount), 0)).filter(
        RecurringIncome.user_id == user_id, RecurringIncome.is_active == True).scalar() or 0.0)  # noqa: E712
    saglik_skoru = calculate_health_score(
        reel_butce=reel_butce, kart_borcu=kart_borcu,
        kart_limit=sum((a.credit_limit or 0) for a in accounts if a.account_type == AccountType.credit_card),
        aylik_faiz=faiz_sizintisi["aylik_toplam"], aylik_gelir=_aylik_gelir,
        runway_gun=nakit_runway_gun, crunch_var=crunch_alert is not None,
        zarf_asan=zarflar_durumu["asan_adet"], zarf_var=len(zarflar_durumu["zarflar"]) > 0,
    )
    # FEAT-012: borçsuzluk tarihi — Murat'ın borç serüveninin motive edici hedefi (avalanche calc).
    # _dbts yukarıda FEAT-015 için BİR KEZ toplandı (collect_debts tekrar çağrılmaz).
    borc_ozgurluk = None
    try:
        from app.debt_strategy import calc_avalanche, MAX_MONTHS
        if _dbts:
            _av = calc_avalanche(_dbts, extra_monthly=0.0)
            borc_ozgurluk = {
                "kalan_ay": _av.months_to_freedom,
                "borcsuz_tarih": _av.payoff_date.isoformat() if _av.payoff_date else None,
                "toplam_faiz": _av.total_interest_paid,
                "asla_bitmez": _av.months_to_freedom >= MAX_MONTHS,
            }
    except Exception as e:
        logger.warning("borç özgürlüğü hesaplanamadı user_id=%s: %s", user_id, e)

    result = {
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
        "alacaklar_toplami": alacaklar_toplami,        # Transparency (net_deger_tam'a +)
        "borclar_toplami": borclar_toplami,            # BUG #116: kişisel payable (net_deger_tam'dan −)
        "daily_limit": daily_limit,
        "guvenli_harcama": guvenli_harcama,  # FEAT-009: kart-hariç ileriye-dönük güvenli harcama tabanı
        "nakit_runway_gun": nakit_runway_gun,  # FEAT-010: gelirsiz nakit kaç gün yeter (None=belirsiz)
        "kart_kullanim": kart_kullanim,  # FEAT-016: kart utilization oranı + trend + kredi-sağlık bandı (None=kart yok)
        "abonelik_yuku": {  # FEAT-006: aylık/yıllık toplam abonelik yükü (Rocket Money headline)
            "aylik": sub_result["aylik_toplam"],
            "yillik": sub_result["yillik_toplam"],
            "adet": sub_result["adet"],
        },
        "zarflar": zarflar_durumu,  # FEAT-001: kategori bütçe zarfları durumu
        "atanmamis_nakit": atanmamis_nakit,  # FEAT-002: zarflara taahhüt edilmemiş "boşta" nakit
        "faiz_sizintisi": faiz_sizintisi,  # FEAT-013: aylık/yıllık faiz maliyeti (kredi+kart)
        "alacak_yaslanma": alacak_yaslanma,  # FEAT-027: alacakların vade-yaşı grupları (None=alacak yok)
        "borc_ilerleme": borc_ilerleme,  # FEAT-017: başlangıçtan beri borç ödeme ilerlemesi (None=yetersiz geçmiş)
        "saglik_skoru": saglik_skoru,  # FEAT-022: 0-100 şeffaf finansal sağlık skoru
        "borc_ozgurluk": borc_ozgurluk,  # FEAT-012: borçsuz olma tarihi + kalan faiz (None=borç yok)
        "asgari_tuzagi": asgari_tuzagi,  # FEAT-015: kart asgari-ödemeyle kaç ay + toplam faiz (None=kart yok)
        "konsolidasyon": konsolidasyon,  # FEAT-014: konsolidasyon eşiği (ağırlıklı ort. oran; None=<2 borç)
        "yarin_limit_harcamasiz": yarin_limit_harcamasiz,  # zikzak: bugün 0 harcarsan yarın
        "days_remaining": days_remaining,
        "carried_forward": carried_forward,
        "today_target": today_target,
        "accounts": accounts_detail,
        "upcoming_payments": upcoming_payments,
        "upcoming_receivables": upcoming_receivables,
        "alerts": alerts,
        "gizli_uyari_sayisi": gizli_uyari_sayisi,  # #126: sığmayan uyarı sayısı ("+N daha")
        "investment_pnl": investment_pnl_list,
        "category_patterns": _calculate_category_patterns(user_id, today, db),
        "upcoming_reminders": _collect_upcoming_reminders(
            user_id, today, db, accounts, kart_borcu
        ),
        "son_islemler": _collect_recent_transactions(user_id, db),  # C2-lite: son 8 işlem
    }
    # FEAT-041: deterministik "İLK ADIM" — tüm sinyalleri tek en-yüksek-etkili hamleye indir
    # (tüm dict hazır olduktan SONRA; alerts/aging/nakit hepsini okur). Koç bunu açıklar, türetmez.
    result["sonraki_eylem"] = recommend_next_action(result)
    return floatify(result)  # ADR-030/B1: iç aritmetik Decimal, public cockpit float serialize


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
                "mesaj": f"Kart {kullanim:.1f}% dolu. Yeni harcama riskli, kalan limit {_tl(kart_limit - kart_borcu)} TL.",
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
            "mesaj": f"Beklenen gelirle birlikte bile bütçe {_tl(reel_butce)} TL. Kart borcu nakdi aşıyor.",
        })

    # 3. Nakit çok düşük
    if nakit < 1000:
        alerts.append({
            "seviye": "uyari",
            "baslik": "Nakit çok düşük",
            "mesaj": f"Kasada {_tl(nakit)} TL. Acil durum tamponu yok.",
        })

    # 4. 7 gün içinde büyük ödeme var mı?
    week_horizon = today + timedelta(days=7)
    big_payments = [
        p for p in upcoming_payments
        if p.get("tip") == "kredi_taksit"
        and date.fromisoformat(p["tarih"]) <= week_horizon
        and D(p.get("tutar", 0)) > nakit / 2  # ADR-030: para Decimal karşılaştırma (nakit/2)
    ]
    for p in big_payments:
        alerts.append({
            "seviye": "uyari",
            "baslik": f"7 gün içinde büyük ödeme: {p['ad']}",
            "mesaj": f"{p['tarih']} tarihinde {_tl(p['tutar'])} TL — nakitin %{(p['tutar'] / max(nakit, 1)) * 100:.0f}'i.",
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
    amount = D(amount_str)
    category = match.group("category").strip().lower()

    return {
        "amount": amount,
        "category": category,
        "source": source,
        "is_card": source == "kart",
    }