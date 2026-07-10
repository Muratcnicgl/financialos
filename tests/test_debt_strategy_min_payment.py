"""
BUG #079 (P0-3): Kart asgari ödemesi her ay güncel bakiyeden hesaplanmalı (azalan),
başlangıç bakiyesinden sabit değil. Sabit-yüksek min ile kart gerçekte olduğundan
hızlı kapanıp payoff ay sayısı iyimser çıkıyordu.

İzole: DB gerektirmez, _simulate saf fonksiyon.
"""
from app.debt_strategy import _simulate, DebtItem, MAX_MONTHS


def test_kart_asgari_odeme_azalir_ve_yakinsar():
    # min_payment=2500 (bayat/başlangıç) — fix sayesinde KART için yok sayılmalı,
    # her ay güncel bakiyenin %'sinden hesaplanmalı.
    card = DebtItem(account_id=1, name="Kart", account_type="credit_card",
                    balance=10000.0, interest_rate_monthly=4.25, min_payment=2500.0)
    res = _simulate([card], priority_order=[1], extra_monthly=0.0)

    # Yakınsar (payoff MAX_MONTHS'tan önce) ve azalan min yüzünden sabit-2500'den UZUN sürer
    # (sabit 2500 olsaydı ~4-5 ayda biterdi; azalan min ile belirgin daha uzun).
    assert 8 < res.months_to_freedom < MAX_MONTHS, res.months_to_freedom
    # Faiz tahakkuk etti — anaparadan fazla ödendi
    assert res.total_paid > 10000.0
    # Korunum invariantı (RULE-012 sınıfı): ödenen ≈ anapara + toplam faiz
    assert abs(res.total_paid - (10000.0 + res.total_interest_paid)) < 0.5


def test_kredi_sabit_taksit_korunur():
    # Kredi (loan) için min_payment SABİT taksit olarak kalmalı (kart mantığı uygulanmaz).
    loan = DebtItem(account_id=2, name="Kredi", account_type="loan",
                    balance=12000.0, interest_rate_monthly=4.0, min_payment=3000.0)
    res = _simulate([loan], priority_order=[2], extra_monthly=0.0)
    assert 0 < res.months_to_freedom < MAX_MONTHS
    assert abs(res.total_paid - (12000.0 + res.total_interest_paid)) < 0.5
