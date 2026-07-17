# ADR-037 — Workspace köprü-deseni, personal-workspace yaşam döngüsü ve fail-fast

**Tarih:** 2026-07-17 · **Durum:** ✅ KARAR VERİLDİ (W4-KURTARMA M62) · **İlgili:** ADR-036 (workspace+izin), BUG #157/#158, tam-proje-durum-raporu §B23a

## Bağlam

M43 (workspace veri-katmanı scoping) `ws_id=None → legacy user_id` **köprü-desenini** getirdi:
`scope_filter(model, user_id, ws_id)` → `ws_id` varsa `workspace_id` filtreler, yoksa eski
`user_id`. Amaç: mevcut 938 testi kırmadan 8 router + rules_engine'i scope'a taşımak. Bu karar
o an alındı ama **ADR yazılmadı** (tam-proje-durum-raporu §B20 itiraf).

tam-proje-durum-raporu §B23a bu köprünün **kalıcı bir fail-open riski** olduğunu gösterdi:
1. Personal workspace YALNIZ elle çalışan `scripts/create_personal_workspaces.py` ile yaratılıyordu
   → **register/oauth akışı personal workspace yaratmıyordu** → 17 Tem'den sonra kaydolan her
   kullanıcı `active_workspace_id → None → legacy user_id` yolundan koşuyordu.
2. `ws_id=None` fallback'inin **son kullanma tarihi, fail-fast'i, deprecation'ı yoktu** →
   BUG #157'nin (SECRET_KEY lazy fail) aynı şekli: sessiz, lazy, fail-open.

## Karar

### 1. Köprü-desen KALICI DEĞİL — geçiş aracı
`ws_id=None → user_id` yalnız (a) test ortamı (workspace yaratmayan ~900 test) ve (b) henüz
backfill edilmemiş kurulum için geçiş yoludur. **Production'da her kullanıcının personal
workspace'i OLMALI** → `ws_id` asla None olmamalı.

### 2. Personal workspace yaratımı KODA bağlandı (tek kanonik nokta)
`app/services/workspace_setup.py:ensure_personal_workspace(db, user)` — idempotent. Çağrılır:
- `auth.py:register` — user ile **aynı transaction'da** (commit=False).
- `auth.py:oauth_callback` — yeni VEYA mevcut user için (idempotent).
- `scripts/create_personal_workspaces.py` — mevcut kullanıcılar için toplu (backfill).

Böylece "personal workspace yaratımı elle script'e bağlı" tuzağı kapandı.

### 3. Production'da fail-fast
`workspace_deps.active_workspace_id`: personal workspace None dönerse →
- **`ENVIRONMENT=production` → HTTP 500** (veri izolasyonu garanti edilemez; sessiz sızma yerine
  görünür hata). BUG #157'nin fail-fast dersinin workspace'e uygulanması.
- **development → warning + None** (legacy yol; testler kırılmaz).

## Alternatifler (reddedildi)
- **`ws_id`'yi zorunlu path/query param yap:** 96 endpoint'i kırar, frontend'i baştan yazdırır. RED.
- **Köprüyü kaldırıp her yeri workspace_id'ye çevir:** ~900 testi kırar, tek adımda riskli. RED
  (M43 zaten köprüyle güvenli geçişi seçti).
- **Fallback'i sessiz bırak:** BUG #157 dersi — sessiz fail-open kabul edilemez. RED.

## Revize Tetiği / Son Kullanma
- **M51 (PostgreSQL RLS, ertelendi):** DB-seviyesi satır güvenliği gelince köprü tamamen kalkar;
  `scope_filter` yerine RLS policy. O noktada bu ADR SUPERSEDED olur.
- Tüm kullanıcıların personal workspace'i doğrulandığında (`SELECT ... WHERE is_personal` = user
  sayısı) `ENVIRONMENT` bağımsız fail-fast'e geçilebilir.

## Kaynak
tam-proje-durum-raporu.md §B23a-b · BUG #157 (fail-fast dersi) · BUG #158 (M61) · ADR-036.
