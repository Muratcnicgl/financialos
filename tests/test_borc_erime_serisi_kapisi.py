"""
DVIZ-009 / BUG #459 KAPISI — STRATEJİ ÇIKTISI ERİTME EĞRİSİNİ TAŞIR.

Ölçülen (13 Eyl 2026): `/compare` iki stratejinin özetini veriyordu, ay-ay kalan bakiye
dışarı çıkmıyordu; panelde hiç grafik yoktu. `kalan_seri` = ay sonu TOPLAM kalan bakiye.

Kilitlenen: uzunluk = months_to_freedom (biten senaryo); son eleman 0; azalmayan artış yok
(toplam her ay düşer — faiz asgariyi aşan "asla bitmez" borç hariç); uçta alan var.
"""
from __future__ import annotations

from app.debt_strategy import DebtItem, _result_to_dict, calc_avalanche, calc_snowball


def _d(aid, bal, rate, minp):
    return DebtItem(account_id=aid, name=f"d{aid}", account_type="loan", balance=bal,
                    interest_rate_monthly=rate, min_payment=minp)


def test_kalan_seri_uzunluk_son_sifir_ve_azalan():
    debts = [_d(1, 10000.0, 2.0, 1500.0), _d(2, 3000.0, 4.0, 400.0)]
    for strat in (calc_snowball, calc_avalanche):
        r = _result_to_dict(strat(debts, extra_monthly=500))
        seri = r["kalan_seri"]
        assert len(seri) == r["months_to_freedom"]
        assert seri[-1] == 0.0
        assert all(b >= a for a, b in zip(seri[1:], seri[:-1], strict=True)), "toplam kalan her ay düşmeli"
        assert seri[0] < 13000.0


def test_uc_alani_tasir(db_session, test_user):
    from fastapi.testclient import TestClient
    from app.dependencies import get_current_user, get_db
    from app.main import app
    from app.models import Account, AccountType
    from datetime import date
    db_session.add(Account(user_id=test_user.id, name="Kredi", account_type=AccountType.loan, balance=5000,
                           interest_rate=24.0, monthly_payment=1000, next_payment_date=date(2026, 10, 5),
                           remaining_installments=6))
    db_session.commit()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: test_user
    try:
        r = TestClient(app).get("/api/debt-strategy/compare?extra_monthly=0")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text[:200]
    sb = r.json()["snowball"]
    assert isinstance(sb["kalan_seri"], list) and len(sb["kalan_seri"]) == sb["months_to_freedom"]
