# Backend Kuralları

## Yapı

- `app/main.py` küçük tutulur: app yaratımı, CORS, router kayıt, startup lifespan (M87 düzeltme: `create_all` startup'tan KALDIRILDI — şema artık yalnız Alembic, ADR-013; lifespan `validate_security_config` fail-fast + catch-up backfill + scheduler başlatır). İş mantığı buraya girmez.
- Endpoint'ler `app/routers/` altında konuya göre bölünür. Her router `prefix="/api/<konu>"` kullanır.
- `app/dependencies.py` — `get_db` (per-request SQLAlchemy session) + `get_current_user` (MVP: ilk kullanıcı; multi-user geçişinde JWT buraya bağlanır).

## Datetime / Timezone

DB'deki tüm `DateTime` alanları **timezone-naive UTC**. Frontend'e tarih dönen her endpoint'te serialize öncesi `tzinfo=timezone.utc` ekle:

```python
dt.replace(tzinfo=timezone.utc)
```

Eksik bırakırsan Pydantic suffix'siz ISO string yayar, JS Türkiye saatinde 3 saat geri gösterir. Referans: `_memory_to_history_item` (`app/routers/coach.py`).

## Pydantic / SQLAlchemy

- Pydantic V2 kullanılıyor — `model_validator`, `field_validator`, `model_config` kullan; V1 decorator'ları (`@validator`, `@root_validator`) kullanma.
- SQLAlchemy 2.x: `select()` / `session.execute()` tercih edilir; `session.query()` eski pattern.

## Rules Engine Kuralı

`app/rules_engine.py` DB'yi okur ama **asla yazmaz**. Matematiksel hesap buraya girer, router'a girmez.

## Action Executor Kuralı

Master Checkpoint enforcement `app/action_executor.py`'de kod seviyesinde uygulanır. LLM prompt'una güvenme — kural burada bloklanır.