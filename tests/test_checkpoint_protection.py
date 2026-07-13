"""
Master Checkpoint enforcement (router seviyesi) — BUG #067.
Korunan checkpoint (priority=1 + red_line, örn. MC1 emanet dokunulmazlığı) iki adımda
delinemez: priority/checkpoint_type değiştirilemez + hard-delete edilemez. Founding-kritik.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, MasterCheckpoint, CheckpointType


@pytest.fixture
def db_session():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="murat"))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: db_session.get(User, 1)
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _cp(db, priority=1, ctype=CheckpointType.red_line, title="Emanet dokunulmaz",
        is_system=False):
    cp = MasterCheckpoint(user_id=1, title=title, description="MC1", checkpoint_type=ctype,
                          priority=priority, is_active=True, is_system=is_system)
    db.add(cp); db.commit(); db.refresh(cp)
    return cp


def test_067_korunan_priority_degistirilemez(client, db_session):
    cp = _cp(db_session)
    r = client.put(f"/api/checkpoints/{cp.id}", json={"priority": 3})
    assert r.status_code == 403
    db_session.refresh(cp)
    assert cp.priority == 1


def test_067_korunan_checkpoint_type_degistirilemez(client, db_session):
    cp = _cp(db_session)
    r = client.put(f"/api/checkpoints/{cp.id}", json={"checkpoint_type": "strategy"})
    assert r.status_code == 403


def test_067_korunan_baslik_degistirilebilir(client, db_session):
    """Koruma sadece priority/checkpoint_type'ı kilitler; başlık güncellenebilir."""
    cp = _cp(db_session)
    r = client.put(f"/api/checkpoints/{cp.id}", json={"title": "Emanet altın dokunulmaz"})
    assert r.status_code == 200


def test_067_korunan_hard_delete_edilemez(client, db_session):
    cp = _cp(db_session)
    r = client.delete(f"/api/checkpoints/{cp.id}?hard=true")
    assert r.status_code == 403
    assert db_session.get(MasterCheckpoint, cp.id) is not None   # hâlâ var


def test_067_korunan_soft_delete_edilebilir(client, db_session):
    cp = _cp(db_session)
    r = client.delete(f"/api/checkpoints/{cp.id}?hard=false")
    assert r.status_code == 204
    db_session.refresh(cp)
    assert cp.is_active is False                                 # pasifleşti, silinmedi


def test_067_korunmayan_hard_delete_edilebilir(client, db_session):
    cp = _cp(db_session, priority=2, ctype=CheckpointType.strategy, title="Sıradan")
    r = client.delete(f"/api/checkpoints/{cp.id}?hard=true")
    assert r.status_code == 204
    assert db_session.get(MasterCheckpoint, cp.id) is None       # gerçekten silindi


# --- W3-039 (RCH-002): is_system Master Checkpoint koruması (MC4/5/6/8 gibi rule tipi) ---

def test_w3_039_system_rule_checkpoint_hard_delete_edilemez(db_session, client):
    # MC5 gibi: type=rule, priority=2 → eski guard'da KORUNMUYORDU (red_line değil)
    cp = _cp(db_session, priority=2, ctype=CheckpointType.rule,
             title="MC5 - Dalkavukluk Yasak", is_system=True)
    r = client.delete(f"/api/checkpoints/{cp.id}?hard=true")
    assert r.status_code == 403
    assert db_session.get(MasterCheckpoint, cp.id) is not None   # korundu


def test_w3_039_system_checkpoint_soft_delete_edilebilir(db_session, client):
    cp = _cp(db_session, priority=2, ctype=CheckpointType.rule,
             title="MC8 - Hayatta Kalma", is_system=True)
    r = client.delete(f"/api/checkpoints/{cp.id}?hard=false")
    assert r.status_code == 204
    db_session.refresh(cp)
    assert cp.is_active is False


def test_w3_039_is_system_api_ile_degistirilemez(db_session, client):
    # CheckpointUpdate şemasında is_system yok → PUT ile unprotect edilemez
    cp = _cp(db_session, priority=2, ctype=CheckpointType.rule,
             title="MC6 - Varsayim Yasagi", is_system=True)
    r = client.put(f"/api/checkpoints/{cp.id}", json={"is_system": False})
    # Alan yok sayılır (200) ama koruma korunur
    assert db_session.get(MasterCheckpoint, cp.id).is_system is True
    r2 = client.delete(f"/api/checkpoints/{cp.id}?hard=true")
    assert r2.status_code == 403
