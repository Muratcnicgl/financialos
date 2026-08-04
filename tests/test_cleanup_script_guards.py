"""
P1 (Wave-9) — BUG #164: yıkıcı temizlik script'inin güvenlik kilitleri.

`scripts/cleanup_orphan_traces.py` eskiden "adı 'test' ile başlamayan = gerçek kullanıcı"
sezgisiyle çalışıp KALAN HERKESİ siliyordu. Kapalı betada adı "Test..." olan gerçek bir
kullanıcının tüm finansal verisi silinirdi. Bu testler, sezginin geri gelmediğini ve
script'in açık onay olmadan HİÇBİR ŞEY silmediğini kilitler.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

import scripts.cleanup_orphan_traces as cleanup
from app.models import Base, User, Account, AccountType


@pytest.fixture
def db_engine(monkeypatch):
    """Gerçek kullanıcılardan biri 'test' ile BAŞLAYAN adda (eski sezginin kurbanı)."""
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    from sqlalchemy.orm import sessionmaker
    s = sessionmaker(bind=eng)()
    u1 = User(name="Murat")
    u2 = User(name="Testere Ahmet")   # gerçek kullanıcı, adı 'test' ile başlıyor
    s.add_all([u1, u2])
    s.commit()
    s.add(Account(user_id=u2.id, name="Ahmet kasa", account_type=AccountType.cash, balance=1234.0))
    s.commit()
    s.close()
    monkeypatch.setattr(cleanup, "engine", eng)
    monkeypatch.setenv("ENVIRONMENT", "development")
    yield eng
    eng.dispose()


def _kullanici_sayisi(eng) -> int:
    with eng.connect() as c:
        return c.execute(text("SELECT COUNT(*) FROM users")).scalar()


def test_id_listesi_verilmeden_hicbir_sey_silmez(db_engine):
    """BUG #164: açık --keep/--delete olmadan script iptal eder (eskiden sezgiyle silerdi)."""
    rc = cleanup.main([])
    assert rc == 2, "Script açık id listesi olmadan çalıştı — yıkıcı sezgi geri gelmiş olabilir"
    assert _kullanici_sayisi(db_engine) == 2, "Kullanıcı silindi!"


def test_adi_test_ile_baslayan_gercek_kullanici_silinmez(db_engine):
    """Adı 'Testere Ahmet' olan GERÇEK kullanıcı, sadece silinecek listesinde ise silinir."""
    rc = cleanup.main(["--keep-user-ids", "1,2", "--delete-user-ids", "99", "--dry-run"])
    assert rc == 0
    assert _kullanici_sayisi(db_engine) == 2

    with db_engine.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
    assert n == 1, "Gerçek kullanıcının hesabı kayboldu"


def test_korunacak_id_dbde_yoksa_iptal(db_engine):
    """Yanlış keep listesi → 'herkesi sil' senaryosu engellenir."""
    rc = cleanup.main(["--keep-user-ids", "42", "--delete-user-ids", "1", "--dry-run"])
    assert rc == 2
    assert _kullanici_sayisi(db_engine) == 2


def test_ayni_id_hem_keep_hem_delete_ise_iptal(db_engine):
    rc = cleanup.main(["--keep-user-ids", "1,2", "--delete-user-ids", "2", "--dry-run"])
    assert rc == 2
    assert _kullanici_sayisi(db_engine) == 2


def test_production_ortaminda_ek_onay_ister(db_engine, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    rc = cleanup.main(["--keep-user-ids", "1", "--delete-user-ids", "2"])
    assert rc == 2, "Production'da onaysız silme yapıldı"
    assert _kullanici_sayisi(db_engine) == 2


def test_acik_onayla_dogru_kullaniciyi_siler(db_engine):
    """Pozitif kontrol: açık liste + onay ile hedeflenen kullanıcı gerçekten silinir."""
    rc = cleanup.main(["--keep-user-ids", "1", "--delete-user-ids", "2"])
    assert rc == 0
    with db_engine.connect() as c:
        kalan = [r[0] for r in c.execute(text("SELECT id FROM users"))]
        hesap = c.execute(text("SELECT COUNT(*) FROM accounts")).scalar()
    assert kalan == [1]
    assert hesap == 0, "Silinen kullanıcının satırları kalmış"
