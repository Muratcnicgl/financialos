"""
BUG #232 — pasifleştirilen kural kullanıcı için "buharlaşıyordu".

Kullanıcı bildirimi: "bir kuralın geçerliliği olmadığını düşünüp pasifleştir butonuna
bastığımda hiçbir yerde görünmüyor; Pasif sekmesinde de Hepsi sekmesinde de yok."

Kök neden frontend'deydi (RedLines paneli listeyi parametresiz çekiyordu, backend
`active_only=True` default'u pasifleri hiç göndermiyordu). Fix `active_only=false`
göndermek. Bu dosya frontend'in dayandığı BACKEND SÖZLEŞMESİNİ kilitler:

  1. `?active_only=false` pasifleri GERÇEKTEN döndürür (query-string'de değer "false"
     metnidir — bool ayrıştırması sessizce True'ya düşerse panel yine boş kalır).
  2. PUT `is_active:false` kaydı silmez, pasifleştirir (geri açılabilir).
  3. Soft-delete edilen kayıt da bu listede görünür (tarihçe iddiası ancak böyle gerçek).

Bu kapı olmadan backend default'u/parse davranışı değişince frontend testleri
(mock'lu oldukları için) yeşil kalır ve bug sessizce geri gelir (L9: kod ile onu
tüketen istemci arasına test).
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


def _kural(db, title="MC7 - Kural", is_active=True):
    cp = MasterCheckpoint(user_id=1, title=title, description="metin",
                          checkpoint_type=CheckpointType.rule, priority=2,
                          is_active=is_active)
    db.add(cp); db.commit(); db.refresh(cp)
    return cp


def test_232_active_only_false_pasifleri_dondurur(client, db_session):
    """Panelin gonderdigi HAM query-string ile: 'false' metni False olarak ayrisir."""
    aktif = _kural(db_session, "Aktif kural", is_active=True)
    pasif = _kural(db_session, "Pasif kural", is_active=False)

    r = client.get("/api/checkpoints?active_only=false")
    assert r.status_code == 200
    idler = {c["id"] for c in r.json()}
    assert aktif.id in idler
    assert pasif.id in idler, "pasif kural donmedi — panel onu hicbir sekmede gosteremez"


def test_232_default_hala_yalniz_aktif(client, db_session):
    """Sozlesme degismedi: parametresiz cagri (koc baglami vb.) yalniz aktifleri alir."""
    _kural(db_session, "Aktif kural", is_active=True)
    pasif = _kural(db_session, "Pasif kural", is_active=False)

    idler = {c["id"] for c in client.get("/api/checkpoints").json()}
    assert pasif.id not in idler


def test_232_pasiflestirme_kaydi_silmez_ve_geri_alinabilir(client, db_session):
    """'Pasiflestir' = devre disi birak, YOK et degil — kullanici geri acabilmeli."""
    cp = _kural(db_session, "Gecerliligi kalmadi", is_active=True)

    r = client.put(f"/api/checkpoints/{cp.id}", json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["is_active"] is False

    liste = client.get("/api/checkpoints?active_only=false").json()
    kayit = next(c for c in liste if c["id"] == cp.id)
    assert kayit["is_active"] is False
    assert kayit["title"] == "Gecerliligi kalmadi"

    # Geri ac
    assert client.put(f"/api/checkpoints/{cp.id}", json={"is_active": True}).json()["is_active"] is True
    assert cp.id in {c["id"] for c in client.get("/api/checkpoints").json()}


def test_232_soft_delete_edilen_kural_tarihcede_gorunur(client, db_session):
    """DELETE soft'tur (router docstring'inin iddiasi) — kayit listede kalmali."""
    cp = _kural(db_session, "Silinen kural", is_active=True)

    assert client.delete(f"/api/checkpoints/{cp.id}").status_code == 204

    idler = {c["id"] for c in client.get("/api/checkpoints?active_only=false").json()}
    assert cp.id in idler, "soft-delete tarihce birakmali; aksi halde 'sildim' geri alinamaz"
