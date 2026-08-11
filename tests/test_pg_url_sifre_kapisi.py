"""
POSTGRES URL ŞİFRE KAPISI — BUG #300.

ÖLÇÜLEN DEFEKT: `tests/pg_gate.fresh_pg_database` yeni test veritabanının URL'ini
`str(make_url(base).set(database=ad))` ile üretiyordu. SQLAlchemy'nin `URL.__str__()`
şifreyi **maskeler**:

    str(...)                          -> postgresql://postgres:***@host:5432/db
    render_as_string(hide_password=False) -> postgresql://postgres:gercek@host:5432/db

Yani dönen URL ile kurulan her bağlantı `password authentication failed` alıyordu.
CI'daki dual-dialect kapıları (RLS/Numeric/NULL-ordering/restore provası) bu yüzden
**hiç koşamadı** — 4 hata + 4 setup-error olarak günlerce kırmızıydı.

NEDEN YERELDE GÖRÜNMEDİ: yerel gate `pgserver` ile açılır ve `initdb` onu **trust**
kimlik doğrulamasıyla kurar — şifre hiç sorulmaz. Maskelenmiş şifre orada zararsızdır.
Şifre isteyen her gerçek Postgres'te (CI servisi, prod, Docker compose) sessizce çöker.

DERS (L60): bir sırrı taşıyan nesnenin `str()` biçimi, o sırrı KORUMAK için maskelenir —
yani `str()` bir gösterim biçimidir, bir serileştirme biçimi değil. Bağlantı dizesi
üretirken açıkça `render_as_string(hide_password=False)` istenmelidir; aksi hâlde
"güvenlik için maskeleme" sessiz bir işlevsellik hatasına dönüşür.

Bu kapı postgres GEREKTİRMEZ: saf URL üretimini ölçer, bu yüzden her makinede koşar —
defektin yerelde görünmemesinin sebebi de zaten postgres'in kendisiydi.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from sqlalchemy.engine import make_url

import tests.pg_gate as pg_gate

KOK = Path(__file__).resolve().parent.parent
SIFRE = "cok-gizli-parola"
TEMEL = f"postgresql://postgres:{SIFRE}@127.0.0.1:55432/postgres"


def test_str_maskeler_render_maskelemez():
    """Defektin dayandığı SQLAlchemy davranışı — kapının varsayımı doğrulanır."""
    u = make_url(TEMEL).set(database="yeni")
    assert SIFRE not in str(u), "SQLAlchemy artık maskelemiyorsa bu kapının gerekçesi değişti"
    assert SIFRE in u.render_as_string(hide_password=False)


def test_fresh_pg_database_urlinde_sifre_korunur():
    """KÖK DEFEKT: üretilen URL şifreyi taşımalı, yoksa bağlantı kimlik doğrulayamaz.

    `fresh_pg_database` gerçek bir sunucuya bağlanır; burada yalnız URL üretim satırı
    ölçülüyor — kaynaktan okunarak, sunucu olmadan.
    """
    kaynak = inspect.getsource(pg_gate.fresh_pg_database)
    assert "render_as_string(hide_password=False)" in kaynak, (
        "BUG #300: fresh_pg_database URL'i `str()` ile üretiyor → şifre maskeleniyor "
        "→ şifre isteyen her Postgres'te 'password authentication failed'."
    )
    assert "return str(make_url" not in kaynak.replace(" ", ""), "maskeleyen biçim geri gelmiş"


def test_rls_testleri_rol_sifresini_kaybetmiyor():
    """RLS gate'i uygulama rolüne ayrı bir şifre verir; o da aynı tuzağa düşmüştü."""
    kaynak = (KOK / "tests" / "test_rls_postgres.py").read_text(encoding="utf-8")
    assert "str(make_url(" not in kaynak.replace(" ", ""), (
        "BUG #300: RLS testi rol şifresini `str(url)` ile taşıyor → şifre maskeleniyor."
    )
    assert kaynak.count("render_as_string(hide_password=False)") >= 2


def test_projede_baska_maskeleyen_url_uretimi_yok():
    """Aynı sınıf tekrar etmesin: bağlantı dizesi üretiminde `str(make_url(...))` yasak."""
    ihlaller = []
    for dizin in ("app", "tests", "scripts", "alembic"):
        for py in (KOK / dizin).rglob("*.py"):
            if py.name == Path(__file__).name:
                continue
            for i, satir in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
                sikistirilmis = satir.replace(" ", "")
                if "str(make_url(" in sikistirilmis or "str(_make_url(" in sikistirilmis:
                    ihlaller.append(f"{py.relative_to(KOK).as_posix()}:{i}: {satir.strip()[:90]}")
    assert not ihlaller, (
        "Bağlantı dizesi `str(make_url(...))` ile üretiliyor — şifre maskelenir "
        "(BUG #300). `render_as_string(hide_password=False)` kullanın:\n  "
        + "\n  ".join(ihlaller)
    )
