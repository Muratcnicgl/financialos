"""
_execute_add_master_checkpoint — koç üzerinden yeni egemen kural (red_line/rule) ekleme yolu.
Happy-path + iki doğrulama guard'ı (eksik alan, geçersiz tip). Deterministik, LLM'siz.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, MasterCheckpoint, CheckpointType
from app.action_executor import _execute_add_master_checkpoint


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add(User(id=1, name="murat"))
    session.commit()
    yield session
    session.close()


def test_yeni_checkpoint_olusturulur(db):
    res = _execute_add_master_checkpoint(db, 1, {
        "title": "Emanet dokunulmaz",
        "description": "Emanet hesabı hiçbir koşulda satılmaz/harcanmaz.",
        "checkpoint_type": "red_line",
        "priority": 1,
    })
    assert res["success"] is True
    row = db.query(MasterCheckpoint).filter_by(id=res["checkpoint_id"]).first()
    assert row is not None
    assert row.checkpoint_type == CheckpointType.red_line
    assert row.priority == 1
    assert row.is_active is True


def test_eksik_alan_reddedilir(db):
    res = _execute_add_master_checkpoint(db, 1, {"title": "yarım", "checkpoint_type": "rule"})
    assert res["success"] is False
    assert db.query(MasterCheckpoint).count() == 0   # DB'ye yazılmadı


def test_gecersiz_tip_reddedilir(db):
    res = _execute_add_master_checkpoint(db, 1, {
        "title": "x", "description": "y", "checkpoint_type": "kirmizi_cizgi",  # geçersiz
    })
    assert res["success"] is False
    assert "checkpoint_type" in res["message"]
    assert db.query(MasterCheckpoint).count() == 0


def test_priority_varsayilan_2(db):
    """priority verilmezse default 2."""
    res = _execute_add_master_checkpoint(db, 1, {
        "title": "Acil fon 3 maaş", "description": "Acil durum fonu 3 maaşa ulaşana dek koru.",
        "checkpoint_type": "strategy",
    })
    row = db.query(MasterCheckpoint).filter_by(id=res["checkpoint_id"]).first()
    assert row.priority == 2
