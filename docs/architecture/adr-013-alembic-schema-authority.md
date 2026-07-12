# ADR-013 — Alembic şema tek doğruluk kaynağı

**Tarih:** Wave-2 · **Durum:** Kabul edildi (addendum: ADR-013a) · **Kaynak:** `app/main.py:75`, `alembic/env.py`, denetim `dosya-denetimi/database.md` (DB-001)

## Bağlam
Şema iki yerden yönetilebiliyordu: `Base.metadata.create_all` (init_db/setup_data) ve Alembic migration'ları. İkisi senkron değildi → schema drift riski (create_all güncel modeli kurar ama alembic_version bilmez → "table already exists" veya belirsizlik).

## Karar
**Şema yönetiminin tek doğruluk kaynağı Alembic'tir.** Production kodunda (`app/main.py` startup) `Base.metadata.create_all` **YASAK** — schema `alembic upgrade head` ile yönetilir. `create_all` yalnız `scripts/setup_data.py` (test verisi seed) ve `tests/conftest.py` (izole in-memory) içinde kullanılabilir. Yeni tablo eklerken migration yazılmadan commit atılamaz.

## Sonuç
- Temiz DB kurulumu `git clone` + `alembic upgrade head` ile çalışmalı (bkz. **ADR-013a** — bu vaat M1'de non-destructive genesis collapse ile tam gerçekleştirildi; eskiden baseline STAMP olduğu için temiz DB kurulamıyordu).
- `scripts/test_fresh_db_migration.py` bu davranışı kilitler (temiz DB alembic == create_all).
