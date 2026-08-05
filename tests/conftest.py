"""
Pytest paylaşılan fixture'ları.

BUG #078 fix (TEST-005/006): db_session artık CANLI production engine yerine her test için
izole in-memory SQLite (StaticPool) kullanır. Eskiden conftest production DB'ye create_all +
commit yapıyordu — canlı veri riski + testler arası sızıntı. Artık her test taze DB'de.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User


@pytest.fixture(autouse=True)
def _neutralize_dotenv_auth(monkeypatch):
    """M61: .env'de AUTH_ENABLED=true var (gerçek app login ister). Testler .env'e BAĞLI
    OLMAMALI — auth gerektiren testler kendi fixture'ında `monkeypatch.setenv` ile açar.
    Autouse (auth test fixture'larından ÖNCE koşar) → onların setenv'i kazanır; diğer ~900
    test fallback yolunda koşar. ENVIRONMENT de nötrlenir (settings fail-fast dev).

    BUG #227 (D06): kimlik doğrulama varsayılanı artık AÇIK (fail-closed) — "değişkeni
    silmek" onu kapatmıyor. Fallback yolunu isteyen testler için burada AÇIKÇA kapatılır;
    bu, gerçek bir yerel kurulumun yapması gerekenle aynı hareket (`AUTH_ENABLED=false`)."""
    monkeypatch.setenv("AUTH_ENABLED", "false")
    monkeypatch.delenv("ENVIRONMENT", raising=False)


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
