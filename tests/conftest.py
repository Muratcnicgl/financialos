import pytest
from app.database import SessionLocal, engine
from app.models import Base, User


@pytest.fixture
def db_session():
    """Test icin DB session - tablolari olustur, session ver, sonunda rollback+close."""
    Base.metadata.create_all(engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def test_user(db_session):
    """Test icin temiz user olustur, sonunda ilgili kayitlari sil."""
    from sqlalchemy import text
    # User modeli: id, name, created_at (email alani yok)
    user = User(name="test_user_decision_rhythm")
    db_session.add(user)
    db_session.commit()
    yield user
    # Cleanup: bu user'a bagli action_history ve coach_insights sil
    db_session.execute(text(f"DELETE FROM action_history WHERE user_id = {user.id}"))
    db_session.execute(text(f"DELETE FROM coach_insights WHERE user_id = {user.id}"))
    db_session.delete(user)
    db_session.commit()