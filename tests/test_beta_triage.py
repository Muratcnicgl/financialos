"""
P7 / H15 (Wave-9) — BUG #209: geri bildirim GELİŞTİRİCİYE ULAŞMIYORDU.

FEAT-033 widget'ı geri bildirimi topluyordu ama `GET /api/feedback` yalnız kullanıcının
KENDİ kayıtlarını döndürüyor; operatörün göreceği bir yol YOKTU. Beta kullanıcısı
"koç çöktü" diye yazar, kayıt DB'de kalır, geliştirici sunucuya elle SQL atmadıkça
haberdar olmaz → P7 çıkış kapısındaki "geri bildirimler triyajlı" ölçütü ölçülemezdi.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import scripts.beta_triage as triage
from app.models import Base, User, Feedback, ErrorLog
from datetime import datetime


@pytest.fixture
def db(monkeypatch):
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    Session = sessionmaker(bind=eng)
    s = Session()
    u = User(name="Beta", email="beta.kullanici@example.com")
    s.add(u)
    s.commit()
    s.add_all([
        Feedback(user_id=u.id, kind="sikayet", message="Koç cevap vermiyor", status="new",
                 created_at=datetime.utcnow()),
        Feedback(user_id=u.id, kind="oneri", message="Grafik ekleyin", status="closed",
                 created_at=datetime.utcnow()),
        ErrorLog(fingerprint="abc", error_type="RuntimeError", message="patladi",
                 path="/api/coach/chat", method="POST", occurrence_count=5,
                 first_seen_at=datetime.utcnow(), last_seen_at=datetime.utcnow()),
    ])
    s.commit()
    monkeypatch.setattr(triage, "SessionLocal", Session)
    yield s
    s.close()


def test_acik_geri_bildirimler_gorunur(db, capsys):
    assert triage.main([]) == 0
    cikti = capsys.readouterr().out
    assert "Koç cevap vermiyor" in cikti, "Operatör geri bildirimi göremiyor"
    assert "Grafik ekleyin" not in cikti, "Kapatılmış kayıt varsayılan listede"


def test_tumu_bayragi_kapatilanlari_da_gosterir(db, capsys):
    triage.main(["--tumu"])
    assert "Grafik ekleyin" in capsys.readouterr().out


def test_sistem_hatalari_yan_yana_gosterilir(db, capsys):
    """Kullanıcının bildirdiği sorun ile sistemin gördüğü hata birlikte okunmalı."""
    triage.main([])
    cikti = capsys.readouterr().out
    assert "RuntimeError" in cikti and "/api/coach/chat" in cikti
    assert "5x" in cikti, "Tekrar sayısı görünmüyor (önceliklendirme yapılamaz)"


def test_kullanici_epostasi_maskelenir(db, capsys):
    """Rutin triyajda tam adres gerekmez (gizlilik)."""
    triage.main([])
    cikti = capsys.readouterr().out
    assert "beta.kullanici@example.com" not in cikti
    assert "***" in cikti


def test_kayit_kapatilabilir(db, capsys):
    fb = db.query(Feedback).filter(Feedback.status == "new").first()
    assert triage.main(["--kapat", str(fb.id), "--not", "duzeltildi"]) == 0
    db.refresh(fb)
    assert fb.status == "closed"
    assert "operatör notu" in fb.message


def test_olmayan_kayit_kapatma_hata_doner(db):
    assert triage.main(["--kapat", "9999"]) == 1
