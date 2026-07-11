"""
Koç Eval Runner — CANLI LLM koç kalitesini objektif ölçer.

Vizyon: wave3-vision Bölüm 6 "eval-driven development" — koç kalitesini görünür/ölçülebilir
kılar. Bir prompt/model/kod değişikliği kaliteyi düşürürse pass_rate düşer (regresyon ağı).

Kullanım:
    python -m scripts.eval_runner            # .env'deki LLM_PROVIDER ile
    LLM_PROVIDER=groq python -m scripts.eval_runner

İZOLE in-memory kanonik durum kullanır (Murat'ın tipik manzarası) → GERÇEK DB'ye DOKUNMAZ.
Judge LLM gerekmez; kriterler deterministik (grounding, KURAL SIFIR, sahte-tamamlama, format).
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Account, AccountType
from app.coach import CoachEngine, build_provider
from app.coach_eval import DEFAULT_SCENARIOS, run_eval, format_report


def _canonical_db():
    """Murat'ın tipik manzarası — izole, tekrarlanabilir (gerçek DB'ye dokunmaz)."""
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="Murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    s.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                  balance=11976.0, credit_limit=12000.0, statement_day=2, payment_day=12))
    s.commit()
    return s


def main() -> None:
    provider = build_provider()
    print(f"Sağlayıcı: {getattr(provider, 'NAME', type(provider).__name__)}\n")
    engine = CoachEngine(provider=provider)
    db = _canonical_db()
    try:
        report = run_eval(engine, db, 1, DEFAULT_SCENARIOS)
        print(format_report(report))
    finally:
        db.close()


if __name__ == "__main__":
    main()
