"""
Debt Strategy Engine - Snowball + Avalanche payoff calculator.

Sektor standardi iki strateji:
- Snowball (Dave Ramsey): kucuk bakiyeden buyuge, davranissal motivasyon
- Avalanche (matematik): yuksek faizden dusuge, toplam maliyet minimum

Algoritma 100% deterministik. LLM yok. Pure Python.

ADR-001 uygulamasi: algoritma karar verir (matematik sektor standardi),
kullanici hangi stratejiyle gidecegini secer, AI sadece aciklar.

Mimari notlar:
- Mevcut Account.monthly_payment minimum varsayilir
- 'extra_monthly' kullanici girdisi, ekstra para tum minimumlar uzerine eklenir
- Bir borc bitince freed minimum + extra sonraki borca kayar (rollover)
- Faiz oraninin AYLIK oldugu varsayilir (Account.interest_rate, TR konvansiyonu)
- Kart icin minimum payment %25 bakiye (TR asgari odeme orani)
- Kredi icin minimum = Account.monthly_payment
- Faiz orani yoksa: kart default %4,25/ay, kredi skip (faizsiz simule edilir)
- Max simulasyon: 600 ay (50 yil) - sonsuz dongu koruma
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session
from app.user_prefs import user_today_by_id  # BUG #237 (D17)

from app.models import Account, AccountType
from app.rules_engine import _scope  # M72: aktif workspace kapsamı (köprü; contextvar yoksa user_id)
from app.money_format import format_para as _para  # BUG #256 (H4): para etiketi tek kaynak


# ============================================================
# SABITLER
# ============================================================

DEFAULT_CARD_INTEREST_MONTHLY = 4.25  # TCMB tavan TR (%/ay)
# RULE-038 (M83): iki stratejinin "neredeyse aynı" sayıldığı faiz-tasarrufu eşiği (TL).
# Magic number yerine adlandırıldı; altında davranışsal tercih matematik farktan önemli.
STRATEGY_EQUIVALENCE_THRESHOLD_TL = 50
#: BUG #330: bu YEDEK bir degerdir, sozlesme DEGIL. Gercek oran hesabin ozelligidir
#: (`Account.min_payment_ratio`) — bankaya/limite/kartin yasina gore degisir. Bu sabit
#: yalniz oran BILINMIYORSA kullanilir. Olculen zarar: sabit %25 ile hesaplanan asgari
#: kullaniciya 2.055,28 diye soylendi, bankanin gercegi 1.644,23'tu (411,06 TL fazla).
MIN_CARD_PAYMENT_RATIO = 0.25         # YEDEK kart asgari odeme orani (TR)


def gecerli_asgari_oran(oran) -> float:
    """
    Hesabin asgari oranini dogrular; gecersizse YEDEGE duser.

    Sifir/negatif/1'den buyuk bir oran sessizce kabul edilirse plan bozulur: %0 kart hic
    odenmemis gibi sonsuza kadar surer, %150 bir ayda kapanir. Bilinmeyen, yedektir (L45).
    """
    try:
        o = float(oran)
    except (TypeError, ValueError):
        return MIN_CARD_PAYMENT_RATIO
    return o if 0 < o <= 1 else MIN_CARD_PAYMENT_RATIO
MAX_MONTHS = 600                      # Sonsuz dongu koruma


# ============================================================
# VERI YAPILARI
# ============================================================

@dataclass
class DebtItem:
    """Strateji icin normalize edilmis borc."""
    account_id: int
    name: str
    account_type: str              # 'credit_card' | 'loan'
    balance: float
    interest_rate_monthly: float   # %/ay (0.0 - 100.0 araliginda)
    min_payment: float             # Aylik minimum odeme
    # BUG #330: kart asgari orani HESABIN ozelligi. None = bilinmiyor -> yedek kullanilir.
    # Simulasyonun HER AYINDA gecerlidir (BUG #079: asgari her ay guncel bakiyeden).
    min_payment_ratio: float = MIN_CARD_PAYMENT_RATIO


@dataclass
class MonthSnapshot:
    """Bir ayin simulasyonu."""
    month_index: int
    debt_balances: Dict[int, float]
    paid_this_month: Dict[int, float]
    interest_this_month: Dict[int, float]
    payoff_events: List[int]       # Bu ayda biten borc account_id'leri


@dataclass
class StrategyResult:
    """Tek stratejinin tam sonucu."""
    strategy: str                  # 'snowball' | 'avalanche'
    order: List[int]               # Account ID sirasinda (oncelik)
    months_to_freedom: int
    total_interest_paid: float
    total_paid: float
    payoff_date: Optional[date]
    schedule: List[MonthSnapshot]
    debt_payoff_months: Dict[int, int]  # {account_id: ay_sayisi}


# ============================================================
# YARDIMCI FONKSIYONLAR
# ============================================================

def collect_debts(db: Session, user_id: int) -> List[DebtItem]:
    """DB'den borc hesaplarini cek, DebtItem listesi don."""
    stmt = select(Account).where(
        _scope(Account, user_id),  # M72: workspace_scope set ise o workspace, değilse user_id (legacy)
        Account.account_type.in_([AccountType.credit_card, AccountType.loan]),
        Account.balance > 0,
    )
    accounts = db.execute(stmt).scalars().all()

    items: List[DebtItem] = []
    for a in accounts:
        is_card = a.account_type == AccountType.credit_card

        rate = a.interest_rate
        if rate is None or rate <= 0:
            rate = DEFAULT_CARD_INTEREST_MONTHLY if is_card else 0.0

        asgari_oran = gecerli_asgari_oran(getattr(a, "min_payment_ratio", None))
        if is_card:
            min_pay = max(float(a.balance) * asgari_oran, 50.0)
        else:
            min_pay = float(a.monthly_payment or 0.0)
            if min_pay <= 0:
                if a.remaining_installments and a.remaining_installments > 0:
                    min_pay = float(a.balance) / a.remaining_installments
                else:
                    min_pay = float(a.balance) * 0.05

        items.append(DebtItem(
            account_id=a.id,
            name=a.name,
            account_type=a.account_type.value,
            balance=float(a.balance),
            interest_rate_monthly=float(rate),
            min_payment_ratio=asgari_oran,
            min_payment=float(min_pay),
        ))

    return items


def _add_months(d: date, months: int) -> date:
    """
    RULE-010 fix: d'ye n TAKVİM ayı ekler (gün ay sonuna clamp'lenir). Eskiden payoff_date
    `today + month*30 gün` idi → 12 ay=360≠365, uzun vadede haftalarca kayıyordu.
    """
    from calendar import monthrange
    total = d.month - 1 + months
    year = d.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


def _simulate(
    debts: List[DebtItem],
    priority_order: List[int],
    extra_monthly: float,
    today: Optional[date] = None,
) -> StrategyResult:
    """
    Verilen oncelik sirasi + ekstra para ile ay-ay simulasyon.
    Snowball/Avalanche ortak motoru - sadece priority_order farkli.
    RULE-010: `today` enjekte edilebilir (deterministik payoff_date; default date.today()).
    """
    if not debts:
        return StrategyResult(
            strategy='', order=[], months_to_freedom=0,
            total_interest_paid=0.0, total_paid=0.0,
            payoff_date=None, schedule=[], debt_payoff_months={},
        )

    state: Dict[int, float] = {d.account_id: d.balance for d in debts}
    debt_by_id: Dict[int, DebtItem] = {d.account_id: d for d in debts}

    total_interest = 0.0
    total_paid = 0.0
    schedule: List[MonthSnapshot] = []
    debt_payoff_months: Dict[int, int] = {}
    last_base_min: Dict[int, float] = {}  # BUG #089: her borca fiilen ödenen güncel minimum
    month = 0

    while any(b > 0.01 for b in state.values()) and month < MAX_MONTHS:
        month += 1
        snapshot_interest: Dict[int, float] = {}
        snapshot_paid: Dict[int, float] = {}
        snapshot_events: List[int] = []

        # 1. Faiz tahakkuk
        for aid, bal in list(state.items()):
            if bal <= 0.01:
                continue
            d = debt_by_id[aid]
            interest = bal * (d.interest_rate_monthly / 100.0)
            state[aid] = bal + interest
            total_interest += interest
            snapshot_interest[aid] = interest

        # 2. Minimum odemeleri yap
        available_extra = extra_monthly
        for aid in priority_order:
            if state[aid] <= 0.01:
                continue
            d = debt_by_id[aid]
            # BUG #079 fix (P0-3): kart asgari ödemesi her ay GÜNCEL bakiyeden hesaplanır
            # (azalır). Eskiden collect_debts'te başlangıç bakiyesinden hesaplanan SABİT
            # min_payment kullanılıyordu → kart gerçekte olduğundan hızlı kapanıyor,
            # snowball/avalanche payoff ay sayısı sistemli iyimser çıkıyordu.
            if d.account_type == 'credit_card':
                # BUG #330: oran HESAPTAN gelir. Burada sabite dusmek, ilk ayi dogru
                # sonraki aylari yanlis yapar ve tum odeme planini sessizce kaydirir.
                base_min = max(state[aid] * d.min_payment_ratio, 50.0)
            else:
                base_min = d.min_payment  # kredi: sabit taksit
            # BUG #089 fix: bir borç bittiğinde rollover'a EKLENECEK tutar, o borca fiilen
            # ödenen güncel minimum olmalı — collect_debts'teki SABİT başlangıç min_payment DEĞİL.
            # Kart minimumu her ay azaldığı için (BUG #079), stale büyük başlangıç min'ini
            # rollover'a eklemek "hayalet para" yaratıp kredi-içeren planları sistemli iyimser
            # (months_to_freedom çok erken) gösteriyordu. Fiilen ödenen base_min'i sakla.
            last_base_min[aid] = base_min
            min_pay = min(base_min, state[aid])  # Bakiyeden fazla ödeme yok
            state[aid] -= min_pay
            total_paid += min_pay
            snapshot_paid[aid] = min_pay

            if state[aid] < 0.01:
                refund = abs(state[aid])
                state[aid] = 0.0
                available_extra += refund
                snapshot_events.append(aid)
                if aid not in debt_payoff_months:
                    debt_payoff_months[aid] = month

        # 3. Ekstra parayi oncelik sirasinda kalan ilk borca uygula (rollover)
        for aid in priority_order:
            if available_extra <= 0.01:
                break
            if state[aid] <= 0.01:
                continue
            pay = min(available_extra, state[aid])
            state[aid] -= pay
            available_extra -= pay
            total_paid += pay
            snapshot_paid[aid] = snapshot_paid.get(aid, 0.0) + pay

            if state[aid] < 0.01:
                state[aid] = 0.0
                if aid not in snapshot_events:
                    snapshot_events.append(aid)
                if aid not in debt_payoff_months:
                    debt_payoff_months[aid] = month

        schedule.append(MonthSnapshot(
            month_index=month,
            debt_balances={aid: round(b, 2) for aid, b in state.items()},
            paid_this_month={aid: round(p, 2) for aid, p in snapshot_paid.items()},
            interest_this_month={aid: round(i, 2) for aid, i in snapshot_interest.items()},
            payoff_events=list(snapshot_events),
        ))

        # 4. Snowball/Avalanche rollover: biten borclarin FİİLEN ödenen minimum'u (stale
        # başlangıç değil — BUG #089) sonraki ay extra'ya eklenir. Kredi için last_base_min
        # == sabit taksit; kart için o borcun son ödenen (azalmış) minimumudur.
        for aid in snapshot_events:
            extra_monthly += last_base_min.get(aid, debt_by_id[aid].min_payment)

    # RULE-010: gerçek takvim ay. RULE-011: MAX_MONTHS'a ulaşıldıysa borç min ödemeyle ASLA
    # bitmiyor → sahte "50 yıl sonra" tarihi yerine payoff_date=None (çağıran yanılmasın).
    # tz-exempt: saf hesap yardımcısı — `today` enjekte edilir; kullanıcının gününü
    # kompozisyon sınırı (compare_strategies/simulate_consolidation) geçirir.
    payoff = None if month >= MAX_MONTHS else _add_months(today or date.today(), month)

    return StrategyResult(
        strategy='',
        order=priority_order,
        months_to_freedom=month,
        total_interest_paid=round(total_interest, 2),
        total_paid=round(total_paid, 2),
        payoff_date=payoff,
        schedule=schedule,
        debt_payoff_months=debt_payoff_months,
    )


# ============================================================
# STRATEJI ALGORITMALARI
# ============================================================

def calc_snowball(debts: List[DebtItem], extra_monthly: float = 0.0,
                  today: Optional[date] = None) -> StrategyResult:
    """Snowball: bakiye kucukten buyuge."""
    # RULE-025 (M83): ikincil tie-break account_id → eşit bakiyede deterministik sıra
    # (DB sorgu sırasına bağlı keyfi öncelik önlenir; aynı girdi hep aynı çıktı).
    order = sorted(debts, key=lambda d: (d.balance, d.account_id))
    result = _simulate(debts, [d.account_id for d in order], extra_monthly, today=today)
    result.strategy = 'snowball'
    return result


def calc_avalanche(debts: List[DebtItem], extra_monthly: float = 0.0,
                   today: Optional[date] = None) -> StrategyResult:
    """Avalanche: faiz orani yuksekten dusuge."""
    # RULE-025 (M83): ikincil tie-break account_id → eşit faizde deterministik sıra
    order = sorted(debts, key=lambda d: (-d.interest_rate_monthly, d.account_id))
    result = _simulate(debts, [d.account_id for d in order], extra_monthly, today=today)
    result.strategy = 'avalanche'
    return result


def compare_strategies(
    db: Session,
    user_id: int,
    extra_monthly: float = 0.0,
) -> dict:
    """
    Iki stratejiyi yan yana hesapla, karsilastirma sonucu don.

    Returns:
        {debts, snowball, avalanche, comparison: {interest_saved, months_difference, note}}
    """
    debts = collect_debts(db, user_id)

    if not debts:
        return {
            'debts': [],
            'snowball': None,
            'avalanche': None,
            'comparison': {
                'interest_saved_with_avalanche': 0.0,
                'months_difference': 0,
                'recommendation_note': 'Aktif borc yok.',
            }
        }

    # BUG #237 fix (D17): payoff_date kullanıcının gününden türer (sunucununki değil).
    bugun = user_today_by_id(db, user_id)
    snowball = calc_snowball(debts, extra_monthly, today=bugun)
    avalanche = calc_avalanche(debts, extra_monthly, today=bugun)

    saved = snowball.total_interest_paid - avalanche.total_interest_paid
    months_diff = snowball.months_to_freedom - avalanche.months_to_freedom

    if abs(saved) < STRATEGY_EQUIVALENCE_THRESHOLD_TL:  # RULE-038 (M83): adlandırılmış eşik
        note = 'Iki strateji neredeyse ayni sonuc verir. Davranissal tercih daha onemli.'
    elif saved > 0:
        note = (
            f'Avalanche {_para(saved, ondalik=0)} tasarruf eder ve {abs(months_diff)} ay daha '
            f'hizli biter. Snowball motivasyon icin tercih edilir.'
        )
    else:
        note = (
            f'Snowball {_para(abs(saved), ondalik=0)} tasarruf eder — cunku kucuk borc yuksek '
            f'faizli. Iki yontem de iyi secim.'
        )

    # BUG #081 fix (P0-4/DS-003): faizi belirtilmemiş krediler FAİZSİZ (0%) simüle ediliyor →
    # toplam faiz/ay sayısı iyimser çıkar ("sanal zenginlik"). Bunu sessizce yapma; UI/koç
    # uyarabilsin diye açıkça bildir.
    interest_free_loans = [
        d.name for d in debts
        if d.account_type == 'loan' and d.interest_rate_monthly == 0.0
    ]
    warnings = []
    if interest_free_loans:
        warnings.append(
            f"{len(interest_free_loans)} kredinin faizi belirtilmemiş, FAİZSİZ varsayıldı "
            f"({', '.join(interest_free_loans)}) — gerçek maliyet ve süre daha yüksek olabilir."
        )

    return {
        'debts': [
            {
                'account_id': d.account_id,
                'name': d.name,
                'account_type': d.account_type,
                'balance': d.balance,
                'interest_rate_monthly': d.interest_rate_monthly,
                'min_payment': d.min_payment,
            }
            for d in debts
        ],
        'snowball': _result_to_dict(snowball),
        'avalanche': _result_to_dict(avalanche),
        'comparison': {
            'interest_saved_with_avalanche': round(saved, 2),
            'months_difference': months_diff,
            'recommendation_note': note,
        },
        'warnings': warnings,
    }


def _annuity_payment(principal: float, monthly_rate: float, term_months: int) -> float:
    """Sabit taksitli (annüite) kredi aylık ödemesi. r=0 → eşit anapara bölüşümü."""
    if term_months <= 0:
        return principal
    # BUG #128 fix (property test yakaladı): İhmal edilebilir oran (≤1e-6 %/ay) faizsiz
    # sayılır — aksi halde çok küçük r'de factor-1≈r katastrofik hassasiyet kaybı verir
    # (annüite sayısal kararsız), toplam faiz negatife düşerdi. Gerçekçi oran (≥0.001) etkilenmez.
    if monthly_rate <= 1e-6:
        return principal / term_months
    r = monthly_rate / 100.0
    # BUG #128 fix (property test yakaladı): Aşırı oran×vade'de (1+r)^n float sınırını aşar
    # (OverflowError). Bu uçta annüite taksiti asimptotik faiz-only'e (principal×r) yakınsar:
    # factor/(factor-1) → 1. Endpoint zaten oran≤20/vade≤360 sınırlar; guard saf fonksiyonu korur.
    try:
        factor = (1 + r) ** term_months
        return principal * r * factor / (factor - 1)
    except OverflowError:
        return principal * r


def calculate_consolidation_baseline(debts: List[DebtItem]) -> Optional[dict]:
    """
    FEAT-014 (konsolidasyon taban çizgisi — ASSUMPTION-FREE): birden çok borcu tek krediye
    çevirmek YALNIZCA teklif edilen faiz oranı mevcut AĞIRLIKLI ORTALAMA orandan DÜŞÜKSE
    tasarruf ettirir. Bu eşik kullanıcının KENDİ borçlarından türetilir (dış varsayım yok,
    "al/sat" değil nötr matematik — FEAT KISIT). 5 kredi + kart durumunda kritik karar aracı.

    Ağırlıklı ort. aylık oran = Σ(bakiye × oran) / Σ(bakiye). <2 borç → None (konsolidasyon
    en az iki borç ister). Salt hesap.
    """
    active = [d for d in debts if d.balance > 0]
    if len(active) < 2:
        return None
    toplam = sum(d.balance for d in active)
    agirlikli_oran = sum(d.balance * d.interest_rate_monthly for d in active) / toplam
    return {
        "borc_adet": len(active),
        "toplam_bakiye": round(toplam, 2),
        "agirlikli_ort_oran": round(agirlikli_oran, 3),  # %/ay — konsolidasyon eşiği
        "en_yuksek_oran": round(max(d.interest_rate_monthly for d in active), 3),
        "en_dusuk_oran": round(min(d.interest_rate_monthly for d in active), 3),
    }


def simulate_consolidation(
    debts: List[DebtItem], new_rate_monthly: float, term_months: int,
) -> Optional[dict]:
    """
    FEAT-014 (konsolidasyon what-if): tüm borçları tek krediye (verilen oran + vade) çevirince
    aylık taksit + toplam faiz. Nötr karşılaştırma — mevcut ağırlıklı ort. orana göre tasarruf
    edip etmediğini gösterir. Tavsiye DEĞİL: kullanıcı teklif edilen oran/vadeyi girer, sistem
    matematiği yapar. <2 borç veya geçersiz vade → None. Salt hesap.
    """
    base = calculate_consolidation_baseline(debts)
    if base is None or term_months <= 0:
        return None
    principal = base["toplam_bakiye"]
    taksit = _annuity_payment(principal, new_rate_monthly, term_months)
    toplam_odeme = taksit * term_months
    toplam_faiz = toplam_odeme - principal
    return {
        **base,
        "yeni_oran": round(new_rate_monthly, 3),
        "vade_ay": term_months,
        "yeni_taksit": round(taksit, 2),
        "yeni_toplam_faiz": round(toplam_faiz, 2),
        "yeni_toplam_odeme": round(toplam_odeme, 2),
        # eşik kıyası: yeni oran ağırlıklı ortalamadan düşükse konsolidasyon FAİZ oranı olarak avantajlı
        "oran_avantajli": new_rate_monthly < base["agirlikli_ort_oran"],
    }


def simulate_purchase_opportunity_cost(
    debts: List[DebtItem], amount: float, today: Optional[date] = None,
) -> Optional[dict]:
    """
    FEAT-030 (satın alma fırsat maliyeti): `amount` TL'yi HARCAMAK vs onu EN YÜKSEK FAİZLİ
    borca ödemek — borçsuzluk tarihine ve toplam faize etkisi. İmpuls harcamayı somut maliyetle
    yavaşlatan realist araç (nötr what-if, "alma/harcama" emri değil).

    Yöntem: baseline = avalanche(extra=0). Karşı-senaryo: amount, avalanche'ın hedefleyeceği
    en yüksek faizli borçtan ŞİMDİ düşülür (sanki bugün ödedin) → yeniden avalanche. Fark =
    harcamanın gerçek maliyeti (kaç ay geç + kaç TL fazla faiz). Salt hesap; borç yoksa None.
    """
    active = [d for d in debts if d.balance > 0]
    if not active or amount <= 0:
        return None
    baseline = calc_avalanche(active, extra_monthly=0.0, today=today)
    # amount'ı AVALANCHE SIRASINDA (en yüksek faiz önce) borçlara dağıt — bir borcu bitirince
    # kalanı bir sonrakine taşar (eskiden yalnız en üstteki borca uygulanıp fazlası boşa gidiyordu).
    target = max(active, key=lambda d: d.interest_rate_monthly)  # ilk (en yüksek faiz) — gösterim
    remaining = amount
    reduced = []
    for d in sorted(active, key=lambda x: -x.interest_rate_monthly):
        pay = min(remaining, d.balance)
        reduced.append(replace(d, balance=d.balance - pay))
        remaining -= pay
    applied = round(amount - remaining, 2)   # fiilen borca giden (amount > toplam borç ise fazlası hariç)
    # NOT (modelleme sınırı): ödeme bir borcu TAMAMEN bitirirse, o borcun payoff-EVENT'i (ve
    # min ödemesinin rollover'ı) baseline'da olurdu, ön-ödemede olmaz → çok küçük borçları yok
    # eden uç girdilerde tasarruf hafife/tersine gösterilebilir. Gerçekçi kısmi ödemede (kullanıcı:
    # amount < kart bakiyesi) sorun yok; araç caydırıcı amaçlı, bu yönde tutucu (maliyeti abartmaz).
    with_payment = calc_avalanche([d for d in reduced if d.balance > 0.01],
                                  extra_monthly=0.0, today=today)

    faiz_tasarrufu = round(baseline.total_interest_paid - with_payment.total_interest_paid, 2)
    ay_kazanci = baseline.months_to_freedom - with_payment.months_to_freedom
    return {
        "harcama": round(amount, 2),
        "hedef_borc": target.name,          # amount'ın ödeneceği en yüksek faizli borç
        "uygulanan": round(applied, 2),     # amount > bakiye ise bakiye kadarı
        "baseline_ay": baseline.months_to_freedom,
        "baseline_faiz": baseline.total_interest_paid,
        "odersen_ay": with_payment.months_to_freedom,
        "odersen_faiz": with_payment.total_interest_paid,
        "faiz_tasarrufu": faiz_tasarrufu,   # harcarsan KAYBEDİLEN faiz tasarrufu
        "ay_kazanci": ay_kazanci,           # harcarsan GECİKEN borçsuzluk (ay)
        "baseline_payoff": baseline.payoff_date.isoformat() if baseline.payoff_date else None,
        "odersen_payoff": with_payment.payoff_date.isoformat() if with_payment.payoff_date else None,
    }


def calculate_min_payment_trap(
    debts: List[DebtItem], today: Optional[date] = None,
) -> Optional[dict]:
    """
    FEAT-015 (kart asgari-ödeme tuzağı): her KREDİ KARTI için SADECE asgari ödeme yapılırsa
    kaç ay sürünür + toplam ne kadar FAİZ ödenir. Kart %99.8 doluyken küçük görünen asgari
    ödeme aylarca faiz sızdırır — "görünmez maliyeti görünür yap" (realist koç) metriği.

    Salt hesap: her kart için `_simulate([kart], [id], extra=0)` → azalan %25 asgari (TR)
    trajektorisi (mevcut motor; BUG #079 azalan-min + RULE-011 asla-bitmez korumalı). Kredi
    HARİÇ — asgari tuzağı kart-spesifik kavram (krediler zaten sabit taksitli, seçim yok).

    Dönüş: kart yoksa None. Aksi halde {kartlar: [...], toplam_faiz}. Her kart:
    ay, toplam_faiz, toplam_odeme, payoff_tarih, asla_bitmez. `en_yuksek_faiz` en çok
    sızdıran kart (uyarı için). Kartlar toplam faize göre azalan sıralı.
    """
    cards = [d for d in debts if d.account_type == 'credit_card' and d.balance > 0]
    if not cards:
        return None
    kartlar = []
    for c in cards:
        r = _simulate([c], [c.account_id], 0.0, today=today)
        asla_bitmez = r.months_to_freedom >= MAX_MONTHS
        kartlar.append({
            "account_id": c.account_id,
            "ad": c.name,
            "bakiye": round(c.balance, 2),
            "aylik_oran": round(c.interest_rate_monthly, 2),
            "ay": r.months_to_freedom,
            "toplam_faiz": r.total_interest_paid,
            "toplam_odeme": r.total_paid,
            "payoff_tarih": r.payoff_date.isoformat() if r.payoff_date else None,
            "asla_bitmez": asla_bitmez,
        })
    kartlar.sort(key=lambda k: -k["toplam_faiz"])  # en çok sızdıran önce
    return {
        "kartlar": kartlar,
        "toplam_faiz": round(sum(k["toplam_faiz"] for k in kartlar), 2),
        "en_yuksek_faiz": kartlar[0],
    }


def _result_to_dict(r: StrategyResult) -> dict:
    """StrategyResult -> JSON-serializeable dict (schedule haric)."""
    return {
        'strategy': r.strategy,
        'order': r.order,
        'months_to_freedom': r.months_to_freedom,
        'total_interest_paid': r.total_interest_paid,
        'total_paid': r.total_paid,
        'payoff_date': r.payoff_date.isoformat() if r.payoff_date else None,
        'debt_payoff_months': r.debt_payoff_months,
    }
