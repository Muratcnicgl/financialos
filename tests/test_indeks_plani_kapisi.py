"""
DATA-023 (BUG #498): `Transaction` kompozit indeksleri sorgu planında GERÇEKTEN kullanılıyor.

Ölçüm (14 Eyl 2026, canlı SQLite, EXPLAIN QUERY PLAN): `ix_transactions_user_category`
"düşük getirili olabilir" deniyordu; kategori yönetiminin iki sorgusu (kullanım sayısı ve
birleştirme UPDATE'i — `routers/categories.py`) onu COVERING indeks olarak kullanıyor.
Tarih aralıklı sorgular doğru biçimde `ix_transactions_user_date`e gidiyor. Kilitlenen:
her indeksin en az bir gerçek sorguda plana girdiği — kullanılmayan indeks bu kapıda görünür.
"""
from __future__ import annotations

from sqlalchemy import create_engine, text

from app.models import Base


def _plan(con, sql: str) -> str:
    return " | ".join(r[3] for r in con.execute(text("EXPLAIN QUERY PLAN " + sql)))


def test_her_kompozit_indeks_bir_sorguda_kullanilir():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    beklenen = {
        # categories._kullanim_sayisi / birleştirme
        "SELECT COUNT(*) FROM transactions WHERE user_id=1 AND category='market'": "ix_transactions_user_category",
        # liste / raporlar (kullanıcı + tarih)
        "SELECT * FROM transactions WHERE user_id=1 AND transaction_date>='2026-09-01' ORDER BY transaction_date DESC": "ix_transactions_user_date",
        # hesap geçmişi
        "SELECT * FROM transactions WHERE account_id=3 AND transaction_date>='2026-09-01'": "ix_transactions_account_date",
    }
    with eng.connect() as con:
        for sql, indeks in beklenen.items():
            plan = _plan(con, sql)
            assert indeks in plan, f"{indeks} plana girmiyor: {plan}"
    # model gerçekten bu üç indeksi tanımlıyor (ad değişirse yukarıdaki iddia boşa düşer)
    adlar = {ix.name for ix in Base.metadata.tables["transactions"].indexes}
    assert set(beklenen.values()) <= adlar
