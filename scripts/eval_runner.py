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
    """
    Kontrollü MİNİMAL manzara — izole, tekrarlanabilir (gerçek DB'ye dokunmaz).

    NEDEN minimal (12 Tem gözlemi): eval DETERMİNİSTİK KOÇ DAVRANIŞ regresyonunu ölçer
    (KURAL SIFIR, action-proposing, sahte-tamamlama, format) — Murat'ın tam verisini
    simüle etmek DEĞİL. DB'yi zenginleştirmek (5 kredi + alacaklar) koç context'ini
    ~8000+ token'a şişirip Groq+Cerebras free-tier TPM'ini AŞTIRIYOR → ikisi de circuit
    breaker'la atlanıp ZAYIF sağlayıcıya düşülüyor → action senaryoları provider-boyut
    gürültüsüyle bozuluyor (6/8 → 4/8). Minimal DB davranışı sağlayıcı-boyutundan İZOLE
    ölçer. Grounding-analiz senaryoları sağlayıcı-halüsinasyonuna duyarlıdır (kaçınılmaz;
    grounding uydurmayı DOĞRU yakalar → confidence düşer). Bkz. memory reference_groq_tpm_limiti.
    """
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
    try:
        provider = build_provider()
    except Exception as e:
        print(f"Sağlayıcı kurulamadı: {e}")
        print("İpucu: .env'de LLM_PROVIDER + ilgili API key ayarla "
              "(ör. LLM_PROVIDER=groq, GROQ_API_KEY=...). Yerel/offline için LLM_PROVIDER=ollama.")
        raise SystemExit(1)
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
