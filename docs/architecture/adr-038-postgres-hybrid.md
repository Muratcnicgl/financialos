# ADR-038 — PostgreSQL hibrit (dev SQLite / prod Postgres) + RLS + dual-dialect Alembic

**Tarih:** 18 Temmuz 2026 · **Durum:** Kabul edildi (Wave-7, M49-M53+M92) · **İlgili:** ADR-013 (Alembic), ADR-030 (Decimal), ADR-036/037 (workspace)

## Bağlam
Wave-6 sonuna kadar veri katmanı yalnız SQLite'ta test edilmişti; ADR-035 prod-Postgres yolunu öngörüyordu ama
kodda HİÇ Postgres'te koşulmamıştı (rapor B5). Aile/multi-user gerçek kullanımı + veri egemenliği için Postgres
gerekli, ama dev deneyimi (tek-dosya, sıfır-kurulum) SQLite'ta kalmalı → **hibrit.**

## Karar
- **Hibrit dialect:** `DATABASE_URL` dialect'i (`make_url().get_backend_name()`) tespit edilir; app dialect-aware
  engine kurar. **dev = SQLite** (dosya/in-memory), **prod = PostgreSQL** (compose `--profile postgres`).
- **SQLite:** check_same_thread + BUG #060 PRAGMA'ları (foreign_keys/WAL/busy_timeout/synchronous).
- **PostgreSQL:** pool_pre_ping + pool_size/max_overflow (PERF-014). psycopg2 driver.
- **Alembic multi-dialect (M50):** tüm migration'lar İKİ dialect'te koşar. SQLite-özel kalıplar dialect-koşullu:
  enum değeri `ALTER TYPE RENAME VALUE` (Postgres) vs UPDATE (SQLite); `render_as_batch` yalnız SQLite; boolean
  default `sa.false()/true()`; workspace FK'leri Postgres'te fiziksel (ADR-036 "Blok D'de eklenir" sözü), SQLite no-op.
- **Row-Level Security (M51):** Postgres'te 12 scoped tabloda ENABLE+FORCE RLS + `ws_isolation` policy — uygulama
  katmanı `scope_filter` (ADR-036/037) BİRİNCİL, RLS **ikinci/DB-katmanı savunma**. `app.current_workspace_id` GUC
  set edilince DB bağımsız dayatır (app-hook workspace_scope contextvar'ından yazar). SQLite'ta RLS yok.
- **Numeric bütünlük (M52):** Postgres NUMERIC(19,4) exact; SQLite Numeric'i REAL/double saklar. Gerçekçi TL
  büyüklüklerinde (<~1 trilyon) kuruşuna kadar aynı; absürt değerlerde SQLite drift eder (belgelenmiş divergence).

## Alternatifler (reddedildi)
- **Sadece SQLite:** aile/multi-user + eşzamanlı yazım + RLS için yetersiz; veri egemenliği prod'da Postgres ister.
- **Sadece Postgres (dev dahil):** dev'de docker/sunucu kurulumu = friksiyon; testler yavaşlar. Hibrit dev hızını korur.
- **Django-benzeri tek-dialect ORM soyutlaması:** SQLAlchemy zaten dialect-agnostik; sorun migration + RLS + Numeric
  gibi dialect-ÖZEL davranışlar — bunlar dialect-koşullu kodla çözüldü.

## Sonuç / bilinen sapmalar (dev SQLite ↔ prod Postgres)
1. **workspace_id FK:** fiziksel yalnız Postgres (SQLite ALTER ADD FK yapamaz, M11 dersi); SQLite'ta model-FK + app-scope.
2. **RLS:** yalnız Postgres (2. savunma). SQLite'ta app-katmanı scope tek savunma.
3. **Numeric:** absürt değerlerde SQLite drift (gerçekçi domain'de fark yok).
4. **RLS'in etkili olması:** app NON-superuser rolüyle bağlanmalı (compose `financialos`) — superuser RLS'i bypass eder.

## Prod ortam yeteneği notu (M49 keşfi)
Bu geliştirme ortamında docker CLI YOK → Wave-7 gate'leri için **`pgserver`** (bundled postgres binary wheel) ile
docker'sız PostgreSQL 16.2 koşuldu. Türkçe locale (`Turkish_Türkiye.1254`) initdb'yi 0xC0000409 ile çökertiyor →
**`initdb --locale=C`** ile çözülür. `tests/pg_gate.py` dual-dialect test altyapısı (postgres yoksa skip).

## Revize tetikleyicisi
Gerçek prod deploy (Wave-8, VPS) — compose postgres canlı koşulacak, CI'ya postgres service eklenecek (dual-dialect
gate'ler CI'da da). Multi-tenant/ölçek büyürse RLS policy + connection-pool ayarları gözden geçirilir.

## Kaynak
Wave-7 M49-M53 + M92 (milestone-log). Test: `tests/pg_gate.py`, `test_rls_postgres.py`, `test_numeric_dual_dialect.py`,
`test_net_worth_sign_source_m53.py`, `test_null_ordering_dual_dialect_m92.py`.
