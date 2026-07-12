# Veri modeli & DB (kod: DATA)

### [DATA-001] Para alanları `Float` — finansal uygulamada kritik hata
- **Sorun:** Çekirdek para kolonları `Float` (IEEE-754). `0.1+0.2 != 0.3`; kart %99.8 doluyken kullanılabilir limitte yuvarlama hatası limit aşımı/eksik gösterir; reel bütçe her toplamada hata biriktirir.
- **Kanıt:** `app/models.py:154` `Account.balance=Column(Float)`; `:193,210,229,256` (amount'lar)
- **Aksiyon:** Para kolonlarını `Numeric(14,2)` (veya kuruş `Integer`); Python'da `Decimal`. Alembic batch migration. Alan adları korunur.
- **Etki:** Yüksek · **Efor:** L · **Not:** rules_engine `Decimal`e taşınmalı; kademeli. [Modern Treasury; cardinalby]

### [DATA-002] `Numeric` kolonlar SQLite'ta gerçekte REAL olarak saklanıyor
- **Sorun:** SQLite'ın DECIMAL tipi yok; NUMERIC affinity REAL'e çevirir. `asdecimal=True` Python'a Decimal döner ama diskte float, precision kaybı olabilir.
- **Kanıt:** `app/models.py:565` `close_price=Numeric(19,4)`; `:735,764,768,774,813`
- **Aksiyon:** Tam kesinlik için kuruş `Integer` veya `TypeDecorator` (Decimal↔String); okuma noktalarında `Decimal(str(...))`.
- **Etki:** Orta · **Efor:** M

### [DATA-003] SQLite `PRAGMA foreign_keys=ON` hiçbir yerde ayarlanmıyor — FK/ON DELETE sessizce kapalı
- **Sorun:** SQLite'ta FK default OFF. `ondelete=CASCADE/SET NULL` tanımları hiç çalışmıyor; yetim kayıt yazılabiliyor.
- **Kanıt:** Grep `PRAGMA foreign_keys`=0; `app/models.py:723,807,811,819,619`
- **Aksiyon:** `database.py`'de engine `connect` listener: `PRAGMA foreign_keys=ON`. İlgili relationship'lere `passive_deletes=True`.
- **Etki:** Yüksek · **Efor:** S · **Not:** Açınca mevcut yetim kayıtlar IntegrityError verebilir; önce temizlik.

### [DATA-004] WAL journal + `busy_timeout` yok — "database is locked"
- **Kanıt:** `app/database.py:25-29`; scheduler+request eşzamanlı yazım `main.py:120`
- **Aksiyon:** connect listener'da `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`. Backup'ta `-wal`/`-shm` dahil et.
- **Etki:** Orta · **Efor:** S

### [DATA-005] `setup_data.py` `drop_all` alembic'i baypas ediyor — schema çelişkisi
- **Sorun:** main.py "alembic upgrade head" der ama setup_data drop/create yapar, `database.py init_db` hâlâ create_all; create_all sonrası `alembic_version` stamp'lenmiyor → sonraki upgrade çakışır.
- **Kanıt:** `scripts/setup_data.py:36-37`; `app/database.py:50-57`; `app/main.py:113`
- **Aksiyon:** setup_data sonunda `alembic stamp head`; init_db'yi test-dışı yollardan kaldır; tek doğruluk kaynağı alembic.
- **Etki:** Yüksek · **Efor:** M · **Not:** İki baseline migration kafa karıştırıcı — dokümante et.

### [DATA-006] PK kolonlarında `index=True` — redundant index (dual-index anti-pattern)
- **Kanıt:** `app/models.py` 18 tabloda `id=Column(Integer, primary_key=True, index=True)`
- **Aksiyon:** PK'lardan `index=True` kaldır (SQLAlchemy zaten indeksler).
- **Etki:** Düşük · **Efor:** S

### [DATA-007] Timezone tutarsızlığı — bazı tablolar aware, çoğu naive
- **Kanıt:** `app/models.py:631,635,642` aware; `:123,177,...` naive; `:566,698` `func.now()`
- **Aksiyon:** Tek konvansiyon (naive-UTC); karışık bırakma; serialize'da `tzinfo=timezone.utc`.
- **Etki:** Orta · **Efor:** M

### [DATA-008] `datetime.utcnow` deprecated (Python 3.12+)
- **Kanıt:** `app/models.py` çok sayıda `default=datetime.utcnow`
- **Aksiyon:** `lambda: datetime.now(timezone.utc).replace(tzinfo=None)` helper.
- **Etki:** Düşük · **Efor:** M

### [DATA-009] CHECK constraint hiç yok — veri bütünlüğü tamamen uygulama katmanında
- **Sorun:** Negatif amount, `day_of_month=45`, `priority=99`, `progress_percent=250` yazılabilir.
- **Kanıt:** `app/models.py:194,213,279,626,775`
- **Aksiyon:** `CheckConstraint` ekle (day_of_month 1-31, amount>=0, priority 1-3, progress 0-100). Batch migration.
- **Etki:** Orta · **Efor:** M

### [DATA-010] `Goal.user_id` nullable=True — multi-tenant izolasyon deliği
- **Kanıt:** `app/models.py:762`
- **Aksiyon:** `nullable=False`, backfill, migration.
- **Etki:** Orta · **Efor:** S

### [DATA-011] `GoalAllocation`/`GoalRule`'da `user_id` yok — izolasyon join'e bağımlı
- **Kanıt:** `app/models.py:717-745`, `:795-831`
- **Aksiyon:** Denormalize `user_id` ekle veya zorunlu Goal join disiplinini testle garanti et.
- **Etki:** Orta · **Efor:** M

### [DATA-012] FK kolonlarında index eksik
- **Kanıt:** `app/models.py:211,367,381,415,817,679`
- **Aksiyon:** Sık join edilen FK'lara index (RecurringExpense.account_id, GoalAllocation.rule_id).
- **Etki:** Düşük · **Efor:** S

### [DATA-013] `Account`/`Transaction` cascade tanımsız (FK pragma açılınca IntegrityError)
- **Kanıt:** `app/models.py:149,180,227`
- **Aksiyon:** `ondelete=CASCADE`+`passive_deletes=True` veya soft-delete; tutarlı ol.
- **Etki:** Orta · **Efor:** M

### [DATA-014] `updated_at`/version kolonu çoğu tabloda yok — concurrency & sync imkânsız
- **Kanıt:** Sadece Account (`:177`) ve Goal (`:780`); Transaction/PersonalDebt/MasterCheckpoint/Recurring* yok
- **Aksiyon:** Yazılabilir tablolara `updated_at onupdate`; kritiklere `version_id_col` (optimistic lock).
- **Etki:** Orta · **Efor:** M

### [DATA-015] Soft-delete yok — silinen işlem/hesap audit'ten kayboluyor
- **Kanıt:** `app/models.py:222,145`; DecisionJournal:657 kısmi index deseni zaten var
- **Aksiyon:** Finansal tablolara `deleted_at`; sorgulara `WHERE deleted_at IS NULL` (kısmi index).
- **Etki:** Orta · **Efor:** M

### [DATA-016] Enum kolonlar tutarsız — bazıları SQLEnum, çoğu serbest String
- **Kanıt:** `app/models.py:759,770,814,733,295,316,432`
- **Aksiyon:** Sabit-kümeli alanları SQLEnum veya CheckConstraint; mevcut enum.Enum sınıflarını kullan.
- **Etki:** Orta · **Efor:** M

### [DATA-017] SQLEnum `values_callable` yalnız PriceHistory'de — tutarsız
- **Kanıt:** `app/models.py:557-564` vs `:151,228,255`
- **Aksiyon:** Tüm SQLEnum'lerde `values_callable` standardize (değer bazlı saklama).
- **Etki:** Düşük · **Efor:** S

### [DATA-018] `Transaction.account_id` nullable — gelir/gider hesapsız yazılabiliyor ✅ UYGULANDI (12 Tem 2026, API katmanı)
- **Kanıt:** `app/models.py:227`; karşı `RecurringExpense.account_id:211` nullable=False
- **Aksiyon:** İş kuralına göre CHECK ("expense ⇒ account_id NOT NULL") veya nullable=False.
- **Etki:** Orta · **Efor:** S
- **Durum:** POST /api/transactions artık HER create'te (yalnız quick-text değil) varsayılan hesaba düşer (kart-gideri→kart, aksi→nakit); yine de account_id çözülemezse **400** ("yetim"/bakiyesiz işlem oluşmaz). Eskiden nakit hesabı olmayan kullanıcının hesapsız işlemi sessizce bakiyeye dokunmadan yazılıyordu. Model nullable korunur (goal-rule eşleşmesi + iç akışlar için) — enforcement API katmanında. 3 test (hesapsız→400, otomatik-atama→201+bakiye düşer, geçersiz→404). Not: model-seviyesi CHECK/Alembic migrasyon gerektirir (proje create_all, ertelendi).

### [DATA-019] `CoachInsight.status` nullable=True ama default var — üç-değerli mantık kirliliği
- **Kanıt:** `app/models.py:432`
- **Aksiyon:** `nullable=False, server_default="active"`, NULL'ları backfill.
- **Etki:** Düşük · **Efor:** S

### [DATA-020] Seed script `account_id=2` hard-code — kırılgan FK varsayımı
- **Kanıt:** `scripts/setup_data.py:197,199,201`
- **Aksiyon:** `db.flush()` sonrası `ziraat.id` değişkenini kullan.
- **Etki:** Düşük · **Efor:** S

### [DATA-021] `setup_data.py` drop_all koruması yok — veri kaybı riski
- **Kanıt:** `scripts/setup_data.py:36`
- **Aksiyon:** `--force` bayrağı + `DATABASE_URL` "prod" değilse guard; drop öncesi otomatik backup.
- **Etki:** Orta · **Efor:** S

### [DATA-022] `NetWorthSnapshot` tüm para alanları Float — trend yuvarlama biriktirir
- **Kanıt:** `app/models.py:504-510`
- **Aksiyon:** DATA-001 kapsamında Numeric(14,2).
- **Etki:** Düşük · **Efor:** S

### [DATA-023] `Transaction` 3 kompozit index — `user_category` düşük getirili olabilir
- **Kanıt:** `app/models.py:239-246`
- **Aksiyon:** `EXPLAIN QUERY PLAN` ile doğrula; kullanılmıyorsa kaldır veya covering yap.
- **Etki:** Düşük · **Efor:** S

### [DATA-024] `ActionHistory.reverted_by_action_id` self-FK indekssiz + döngü riski
- **Kanıt:** `app/models.py:381`
- **Aksiyon:** Index; döngü kontrolü; ondelete SET NULL.
- **Etki:** Düşük · **Efor:** S

### [DATA-025] `PersonalDebt` `is_paid`+`paid_date` senkron guard yok
- **Kanıt:** `app/models.py:259-260`
- **Aksiyon:** CHECK: `(is_paid=0 AND paid_date IS NULL) OR (is_paid=1 AND paid_date IS NOT NULL)`.
- **Etki:** Düşük · **Efor:** S

### [DATA-026] `Account.balance` sign konvansiyonu overload — CHECK/doküman yok
- **Sorun:** Nakit pozitif=bakiye, kart/kredi pozitif=borç; aynı kolonda ters semantik.
- **Kanıt:** `app/models.py:154`
- **Aksiyon:** account_type'a bağlı CHECK + model docstring + test.
- **Etki:** Orta · **Efor:** S

### [DATA-027] `credit_limit`/`statement_day`/`payment_day` koşullu zorunluluk yok
- **Kanıt:** `app/models.py:158-166` hepsi nullable
- **Aksiyon:** Koşullu CHECK (credit_card ⇒ credit_limit NOT NULL, statement_day 1-31).
- **Etki:** Orta · **Efor:** M

### [DATA-028] `GoalAllocation` amount=0 engellenmiyor ✅ UYGULANDI (12 Tem 2026)
- **Kanıt:** `app/models.py:813,828`
- **Aksiyon:** `CheckConstraint("amount <> 0")`.
- **Etki:** Düşük · **Efor:** S
- **Durum:** `POST /api/goals/{id}/allocations` 0 tutarı reddeder (422 — progress'e etkisiz gürültü). Negatif GEÇERLİ (cash_target withdrawal). API-katmanı enforcement (CHECK/migrasyon değil). 2 test (0→422, negatif→201).

### [DATA-029] Recurring dedup `last_triggered_year_month` String(7) format guard yok
- **Sorun:** "2026-5" veya "May-26" yazılırsa dedup kırılır → mükerrer propose_action.
- **Kanıt:** `app/models.py:198,215`
- **Aksiyon:** GLOB CHECK `'[0-9][0-9][0-9][0-9]-[0-9][0-9]'` veya Date sakla.
- **Etki:** Düşük · **Efor:** S

### [DATA-030] `RecurringExpense` dedup taraması için composite index yok
- **Kanıt:** `app/models.py:203-219`
- **Aksiyon:** `Index(user_id, is_active)` (RecurringIncome'a da).
- **Etki:** Düşük · **Efor:** S

### [DATA-031] Legacy `Column()` — SQLAlchemy 2.x `mapped_column`/`Mapped[]` yok
- **Kanıt:** `app/models.py` geneli; app/PROJE.md "2.x tercih"
- **Aksiyon:** Yeni modellerde `Mapped[int]=mapped_column(...)`; kademeli geç.
- **Etki:** Düşük · **Efor:** L

### [DATA-032] `ApiCallLog` sınırsız büyür — retention yok
- **Kanıt:** `app/models.py:450-489`
- **Aksiyon:** N günden eski kayıt retention job veya aggregate. ReasoningTrace/CoachMemory de aynı sınıf.
- **Etki:** Düşük · **Efor:** M

### [DATA-033] `Goal.progress_percent` negatif/aşım senaryosu (withdrawal)
- **Kanıt:** `app/models.py:774-775`; withdrawal `:797`
- **Aksiyon:** refresh_goal sonrası [0,100] clamp + CHECK.
- **Etki:** Düşük · **Efor:** S

### [DATA-034] `MasterCheckpoint` kritik güvenlik verisi — değişiklik audit'i yok
- **Sorun:** Emanet-satılamaz gibi enforcement kurallarını taşır; hard-delete/update edilebilir, updated_at/log yok.
- **Kanıt:** `app/models.py:271-287`
- **Aksiyon:** `updated_at`; değişiklikleri audit'e yaz; hard-delete engelle.
- **Etki:** Orta · **Efor:** S

### [DATA-035] `Account.current_price` vs `PriceHistory` cache tutarlılığı guard'sız
- **Kanıt:** `app/models.py:172-173` cache; `:540-579` kaynak
- **Aksiyon:** Cache'i tek noktadan güncelle; `last_price_update` yaşını Cockpit'te göster, N günden eskiyse uyar.
- **Etki:** Orta · **Efor:** M

---
**Kaynaklar:** Modern Treasury (floats/cents); cardinalby (currency data types); SQLAlchemy #4858 (FK cascade+SQLite); SQLite Forum (PRAGMA foreign_keys).
