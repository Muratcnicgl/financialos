# ADR-013a — Migration Genesis Collapse (ADR-013 addendum)

**Tarih:** 12 Temmuz 2026 · **Durum:** Kabul edildi (M1 otonom karar) · **İlgili:** ADR-013 (Alembic tek doğruluk kaynağı)

## Bağlam

ADR-013 "şema yönetimi tek doğruluk kaynağı Alembic; production'da `Base.metadata.create_all` yasak" der. Ancak M1'de (KURAL R3, disk doğrulaması) keşfedildi ki bu vaat **fiilen ihlal ediliyordu**:

- Migration zinciri **sıfırdan-şema DEĞİLdi.** Kök migration `fa46373f4ca8_baseline_existing_schema` bir **STAMP** idi (boş `upgrade()`); taban şema `create_all` (`init_db`/`setup_data`) ile kuruluyordu.
- Sonuç: **bomboş bir DB'de `alembic upgrade head` ÇÖKÜYORDU** — `coach_insights` hiçbir migration tarafından yaratılmadan `0db7cfbb706f` tarafından `batch_alter` ediliyor → `NoSuchTableError: coach_insights` (ve full-şema baseline denemesinde `CircularDependencyError`).
- Yani `git clone` + `alembic upgrade head` ile **temiz kurulum yapılamıyordu.** Bu, Wave-3 (open-source AGPL topluluk, multi-user, mobil yeni ortamlar) için kabul edilemez bir kalite borcu; Firefly III / Beancount / Maybe Finance hepsi temiz-DB upgrade destekler (sektör pratiği). Kalite Serüveni denetimi de bunu `DB-001` olarak işaretlemişti.

Bu OTONOM KARAR PROTOKOLÜ kategori-**(c) ADR İHLALİ / KALİTE BORCU**'dur: "senaryo desteklenmiyor / testi uyarlıyorum" çözümü YASAK.

## Karar

**Non-destructive collapse:** Tek yeni root migration `b70779a2f621_genesis_full_schema`, güncel tam şemayı (21 tablo + 48 index, `create_all` eşdeğeri, autogenerate ile modellerden) yaratır. Mevcut 9 migration'ın **revizyon kimlikleri ve zincir bağları KORUNUR** ama create/alter gövdeleri **no-op (`pass`)** yapılır.

Zincir: `<base> → b70779a2f621 (genesis) → fa46373f4ca8 → … → fec73e5343e5 (head)`.

## Neden non-destructive (silme/re-stamp değil)

- **Canlı DB dokunulmaz:** Canlı DB `fec73e5343e5` (head) durumunda. Genesis onun **atasıdır** → Alembic "uygulanmış" sayar, yeniden ÇALIŞMAZ. No-op'a indirilen migration'lar zaten uygulanmış → yeniden çalışmaz. `alembic current` = fec73e5343e5, `upgrade head` = no-op. **Re-stamp gerekmez, veri riski yok.** (Doğrulandı: canlı 22 tablo, dokunulmadı.)
- **Zincir sürekliliği:** Revizyon kimlikleri silinmediği için canlı DB'nin `alembic_version` kaydı geçerli kalır (silme yaklaşımının aksine).
- Orijinal migration içerikleri **git geçmişinde** korunur.

## Alternatifler (reddedildi)

- **Baseline'ı gerçek create_table yap (incremental):** `coach_insights`'ı extend-öncesi (11 kolon) şemayla yaratmayı + `0db7`'nin batch `CircularDependencyError` latent bug'ını çözmeyi gerektirir → kırılgan, arkeoloji-yoğun.
- **Silme-squash + re-stamp:** 9 migration sil, genesis tek kalsın, canlı DB'yi `alembic stamp` ile yeniden damgala → daha temiz dosya yapısı ama **canlı DB re-stamp riski** + zincir kimliklerini kırar. Non-destructive collapse aynı sonucu risksiz verir.

## Doğrulama

- Temiz DB: `alembic upgrade head` → 21 tablo, şema `create_all` ile **kolon+index düzeyinde TAM ÖZDEŞ** (`scripts/test_fresh_db_migration.py`).
- Canlı DB: dokunulmadı (fec73e5343e5, 22 tablo, upgrade no-op).
- pytest 774 passed (conftest `create_all` kullanır, etkilenmez).
- Yedek: `backups/pre-genesis-collapse-*.db`; rollback tag `pre-kalite-seruveni-merge`.

## Revize tetikleyicisi

İleride şema bir sonraki büyük eşikte tekrar collapse edilebilir (no-op birikirse). Yeni migration'lar genesis üstüne normal yazılır (no-op olanlar değişmez).
