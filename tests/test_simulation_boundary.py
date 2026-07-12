"""
Simulasyon projeksiyon SINIR-GUNU cift-sayim testi (P0-7 / BUG #084).

Kok problem: simulate_action ufuklari ZINCIRLEME projekte eder
(_project_forward(world, 30) sonra _project_forward(world, 60)). Her cagri
world.as_of'u pencerenin SONUNA tasir. Pencere kapsami her iki uctan da dahil
(start <= olay <= end) oldugundan, tam sinir gunune (orn. T+30) dusen bir
maas/kredi taksiti hem 1. pencerenin SONU hem 2. pencerenin BASI olarak SAYILIR
-> cift sayim. Tek-cagrili baseline ayni olayi bir kez sayar -> hayalet delta.

Dogru davranis: zincirleme N-pencere birlesimi, tek-cagrili tek-pencere ile
AYNI sonucu vermeli. Pencere yari-acik olmali: (start, end].
"""
from __future__ import annotations

from datetime import date

from app.simulation_engine import (
    _project_forward,
    AccountSnap,
    IncomeSnap,
    DebtSnap,
    WorldSnap,
)

# as_of = 1 Mayis 2026. Sinir gunu T+30 = 31 Mayis 2026.
AS_OF = date(2026, 5, 1)


def _cash_only_world(incomes=None, accounts_extra=None, debts=None) -> WorldSnap:
    cash = AccountSnap(id=1, name="Enpara", account_type="cash", balance=0.0)
    accounts = [cash] + (accounts_extra or [])
    return WorldSnap(
        as_of=AS_OF,
        accounts=accounts,
        incomes=incomes or [],
        debts=debts or [],
    )


def test_maas_sinir_gununde_cift_sayilmaz():
    """Maas gunu = 31 (T+30 sinir gunu). Zincir(30+60) == tek(90) olmali."""
    # Zincirleme: engine'in yaptigi gibi 30 sonra 60
    chained = _cash_only_world(incomes=[IncomeSnap(id=1, name="Maas", amount=10000.0, day_of_month=31)])
    _project_forward(chained, 30)
    _project_forward(chained, 60)

    # Tek cagri baseline
    single = _cash_only_world(incomes=[IncomeSnap(id=1, name="Maas", amount=10000.0, day_of_month=31)])
    _project_forward(single, 90)

    # 90 gun icinde maas: 31 May + 30 Haz = 2 kez (31 Tem, ufuk 30 Tem'i astigi icin yok)
    assert single.cash_total() == 20000.0
    assert chained.cash_total() == single.cash_total(), (
        f"Sinir gunu cift sayildi: zincir={chained.cash_total()} tek={single.cash_total()}"
    )


def test_kredi_taksiti_sinir_gununde_cift_sayilmaz():
    """Kredi taksit gunu = 31 May (T+30 sinir). Zincir(30+60) == tek(90)."""
    def _loan_world():
        loan = AccountSnap(
            id=2, name="Kredi", account_type="loan", balance=100000.0,
            monthly_payment=5000.0, remaining_installments=24,
            next_payment_date=date(2026, 5, 31),
        )
        return _cash_only_world(accounts_extra=[loan])

    chained = _loan_world()
    _project_forward(chained, 30)
    _project_forward(chained, 60)

    single = _loan_world()
    _project_forward(single, 90)

    # Kredi bakiyesi ve nakit her iki yolda ayni olmali
    assert chained.loan_debt_total() == single.loan_debt_total(), (
        f"Kredi taksiti sinir gunu cift dusuldu: zincir={chained.loan_debt_total()} "
        f"tek={single.loan_debt_total()}"
    )
    assert chained.cash_total() == single.cash_total()


def test_alacak_sinir_gununde_cift_sayilmaz():
    """Alacak (paid_date guard'i olsa da) sinir gununde tutarli olmali."""
    def _debt_world():
        return _cash_only_world(
            debts=[DebtSnap(id=1, counterparty="Efe", direction="receivable",
                            amount=8000.0, due_date=date(2026, 5, 31), paid_date=None)]
        )

    chained = _debt_world()
    _project_forward(chained, 30)
    _project_forward(chained, 60)

    single = _debt_world()
    _project_forward(single, 90)

    assert chained.cash_total() == single.cash_total() == 8000.0


def test_rule018_kredi_taksiti_faiz_tahakkuk_eder():
    """RULE-018: sim kredi taksiti faizi karşılar, kalanı anaparayı düşürür (100% anapara DEĞİL).
    10000 borç, %5/ay faiz, 1000 taksit → faiz 500, bakiye 10000+500-1000=9500 (eskiden 9000)."""
    loan = AccountSnap(id=2, name="Kredi", account_type="loan", balance=10000.0,
                       monthly_payment=1000.0, interest_rate=5.0, remaining_installments=20,
                       next_payment_date=date(2026, 5, 10))
    w = _cash_only_world(accounts_extra=[loan])
    _project_forward(w, 30)
    assert abs(loan.balance - 9500.0) < 0.01     # faiz tahakkuk etti (iyimser 9000 DEĞİL)


def test_rule018_faizsiz_kredi_tam_anapara():
    """interest_rate None/0 → eski davranış (taksit tümü anapara)."""
    loan = AccountSnap(id=2, name="Kredi", account_type="loan", balance=10000.0,
                       monthly_payment=1000.0, interest_rate=None, remaining_installments=20,
                       next_payment_date=date(2026, 5, 10))
    w = _cash_only_world(accounts_extra=[loan])
    _project_forward(w, 30)
    assert abs(loan.balance - 9000.0) < 0.01


def test_rule019_kart_asgari_odemesi_projeksiyonda():
    """RULE-019: sim kartı asgari ödemeyle eritir (donuk DEĞİL). 12000 kart, %4.25 faiz,
    ödeme günü 12 → 90 günde 3 asgari ödeme (faiz+%25) ile borç ~yarıya iner, cash düşer."""
    card = AccountSnap(id=2, name="Kart", account_type="credit_card", balance=12000.0,
                       credit_limit=12000.0, payment_day=12, interest_rate=4.25)
    w = _cash_only_world(accounts_extra=[card])
    w.accounts[0].balance = 20000.0                 # nakit (asgari ödemeler buradan)
    _project_forward(w, 90)
    assert card.balance < 12000.0                    # eskiden donuk 12000 idi
    assert card.balance < 7000.0                     # ~5736 (asgari %25 × 3 ay)
    assert w.accounts[0].balance < 20000.0           # cash asgari ödemelerle azaldı


def test_rule019_odeme_gunu_yoksa_kart_donuk():
    """payment_day None → kart döngüsü modellenmez (veri eksik, dokunma)."""
    card = AccountSnap(id=2, name="Kart", account_type="credit_card", balance=12000.0,
                       credit_limit=12000.0, payment_day=None, interest_rate=4.25)
    w = _cash_only_world(accounts_extra=[card])
    _project_forward(w, 90)
    assert card.balance == 12000.0


# ============================================================
# PROPERTY / INVARIANT — _project_forward rastgele dünyada sınırları korur
# ============================================================

import math  # noqa: E402
from hypothesis import given, strategies as st, settings  # noqa: E402

_amt = st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False)
_rate = st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
_day = st.integers(min_value=1, max_value=28)


@st.composite
def _random_world(draw):
    accounts = [AccountSnap(id=1, name="cash", account_type="cash",
                            balance=draw(st.floats(-1e5, 1e6, allow_nan=False, allow_infinity=False)))]
    n_loan = draw(st.integers(0, 3))
    for i in range(n_loan):
        accounts.append(AccountSnap(
            id=10 + i, name=f"loan{i}", account_type="loan", balance=draw(_amt),
            monthly_payment=draw(_amt), interest_rate=draw(_rate),
            remaining_installments=draw(st.integers(0, 60)),
            next_payment_date=AS_OF + __import__("datetime").timedelta(days=draw(st.integers(-10, 40))),
        ))
    if draw(st.booleans()):
        accounts.append(AccountSnap(
            id=2, name="card", account_type="credit_card", balance=draw(_amt),
            credit_limit=draw(st.floats(1.0, 1e6, allow_nan=False, allow_infinity=False)),
            payment_day=draw(st.one_of(st.none(), _day)), interest_rate=draw(_rate)))
    incomes = [IncomeSnap(id=100 + i, name=f"inc{i}", amount=draw(_amt), day_of_month=draw(_day))
               for i in range(draw(st.integers(0, 2)))]
    return WorldSnap(as_of=AS_OF, accounts=accounts, incomes=incomes, debts=[])


@given(world=_random_world(), days=st.integers(min_value=1, max_value=400))
@settings(max_examples=250, deadline=None)
def test_projeksiyon_invariantlari(world, days):
    _project_forward(world, days)   # ASLA exception / sonsuz döngü
    for a in world.accounts:
        assert math.isfinite(a.balance), f"{a.name} bakiye finite değil"
        # borç hesaplarının bakiyesi ASLA negatif olamaz (max(0,...) tabanı)
        if a.account_type in ("loan", "credit_card"):
            assert a.balance >= -1e-6, f"{a.name} borç negatife düştü: {a.balance}"
        # taksit sayacı negatif olamaz
        if a.remaining_installments is not None:
            assert a.remaining_installments >= 0
    # event_log tümü string
    assert all(isinstance(e, str) for e in world.event_log)
