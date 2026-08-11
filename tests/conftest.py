"""
Pytest paylaşılan fixture'ları.

BUG #078 fix (TEST-005/006): db_session artık CANLI production engine yerine her test için
izole in-memory SQLite (StaticPool) kullanır. Eskiden conftest production DB'ye create_all +
commit yapıyordu — canlı veri riski + testler arası sızıntı. Artık her test taze DB'de.
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ══════════════════════════════════════════════════════════════════════════
# BUG #286 — SÜİT `.env`'DEN BAĞIMSIZ OLMALI (bu blok app import'undan ÖNCE koşar)
# ══════════════════════════════════════════════════════════════════════════
# Geliştiricinin `.env`'i test SONUCUNU değiştirebiliyordu: `load_dotenv()` ortamda
# olmayan her anahtarı doldurur → aynı commit iki makinede farklı sonuç verir. Bu,
# projenin en temel iddiasını (deterministik süit) sessizce deliyordu.
#
# NEDEN FIXTURE YETMEZ: bu ayarların bir kısmı **import anında** okunur —
# `_compute_cors_origins()` modül seviyesinde koşar, `docs_url` app yaratımında belirlenir,
# SPA mount import sonunda eklenir. Fixture (test başına) o noktada ÇOK GEÇTİR.
# `load_dotenv()` **var olan** değişkeni EZMEZ; bu yüzden burada, app import edilmeden
# önce sabitliyoruz ve `.env` kazanamıyor.
TEST_ENV_SABITLERI = {
    "ENVIRONMENT": "development",        # production → fail-fast + docs kapalı + CORS daralır (BUG #178)
    "REGISTRATION_MODE": "open",         # invite_only → kayıt davet kodu ister (BUG #199)
    "REQUIRE_EMAIL_VERIFICATION": "0",   # kayıt akışını doğrulama adımına sokar (BUG #202)
    "SERVE_SPA": "0",                    # kök yolu arayüze çevirir (BUG #284)
    "FRONTEND_URL": "http://localhost:5173",  # CORS izinli origin listesini belirler
    # `/api/meta` KİMLİKSİZ bir uçtur; künyede yayınlanan adres testin konusudur
    # (BUG #205: kişisel adres yayınlanamaz). `.env`'deki gerçek adres sızarsa
    # `test_kisisel_eposta_sizmaz` geliştiriciye göre kırmızı/yeşil olur.
    "SUPPORT_EMAIL": "destek@ornek-urun.test",
    "AUTH_ENABLED": "false",             # ~900 test kimliksiz fallback yolunda koşar
}
for _anahtar, _deger in TEST_ENV_SABITLERI.items():
    os.environ[_anahtar] = _deger
os.environ.pop("SPA_DIST", None)

DAVRANIS_DEGISTIREN_ENV = tuple(TEST_ENV_SABITLERI) + ("SPA_DIST",)

from app.models import Base, User  # noqa: E402 — env sabitlenmeden app import EDİLMEZ


@pytest.fixture(autouse=True)
def _neutralize_dotenv_auth(monkeypatch):
    """M61: .env'de AUTH_ENABLED=true var (gerçek app login ister). Testler .env'e BAĞLI
    OLMAMALI — auth gerektiren testler kendi fixture'ında `monkeypatch.setenv` ile açar.
    Autouse (auth test fixture'larından ÖNCE koşar) → onların setenv'i kazanır; diğer ~900
    test fallback yolunda koşar. ENVIRONMENT de nötrlenir (settings fail-fast dev).

    BUG #227 (D06): kimlik doğrulama varsayılanı artık AÇIK (fail-closed) — "değişkeni
    silmek" onu kapatmıyor. Fallback yolunu isteyen testler için burada AÇIKÇA kapatılır;
    bu, gerçek bir yerel kurulumun yapması gerekenle aynı hareket (`AUTH_ENABLED=false`).

    BUG #286 (11 Ağu 2026): bu korumanın KAPSAMI tahminle kurulmuştu. `.env`'e kapalı
    beta için `REGISTRATION_MODE=invite_only` yazıldığı gün süit kırmızıya döndü
    (`test_register_basarili_token_doner`) — çünkü liste yalnız `AUTH_ENABLED` ve
    `ENVIRONMENT`'ı sayıyordu. Aynı sınıf: koruma var, kapsamı ölçülmemiş (L11/H25).
    Liste artık `tests/test_env_bagimsizligi_kapisi.py` ile KAYNAKTAN doğrulanıyor:
    davranış değiştiren bir env okuması eklenip buraya yazılmazsa o kapı kırmızıya döner.
    """
    # Modül seviyesinde sabitlenen değerler test başına GERİ YÜKLENİR: bir test onları
    # değiştirirse (monkeypatch olmadan) sonraki testler etkilenmesin.
    for anahtar, deger in TEST_ENV_SABITLERI.items():
        monkeypatch.setenv(anahtar, deger)
    monkeypatch.delenv("SPA_DIST", raising=False)


@pytest.fixture
def db_session():
    """İzole in-memory DB session — her test kendi taze DB'sinde, canlı veriye dokunmadan."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # in-memory DB tek bağlantıda yaşar; StaticPool şart
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    """Test için temiz user (izole in-memory DB'de — cleanup gerekmez)."""
    user = User(name="test_user")
    db_session.add(user)
    db_session.commit()
    yield user
