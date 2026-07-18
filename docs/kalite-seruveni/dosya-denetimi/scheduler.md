# Denetim: app/scheduler.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [SC-001] run_extractor hatada db.rollback() yapmiyor - paylasilan session zehirleniyor, hata izolasyonu vaadi bozuluyor
- **Sorun:** `run_extractor` (satir 88-120) her extractor cagrisini `try/except Exception` ile sarar ama except blogunda (satir 118-120) `db.rollback()` cagrilmaz, sadece log'lanip `{"error": ...}` donulur. Extractor'lardan biri `db.commit()` sirasinda hata atarsa (orn. IntegrityError, OperationalError, StaleDataError) SQLAlchemy session'i "pending rollback" durumuna gecer. Bu `db` nesnesi cagiran yerden geliyor ve fonksiyon donduktan sonra da AYNI session kullanilmaya devam ediyor:
  - `app/coach.py:1813-1832` — `self._save_message(db, user_id, "user", ...)` sonrasi satir 1816'da `trigger_after_user_message(db, user_id)` cagrilir, hemen ardindan satir 1827-1832'de AYNI `db` ile `self._save_message(db, user_id, "assistant", ...)` calisir. Extractor sirasinda session zehirlenirse bu ikinci yazim `PendingRollbackError` ile patlar ve Coach yaniti kullaniciya hic donmez.
  - `run_periodic_batch_for_user` (satir 123-129) gece batch'inde 5 extractor'i AYNI `db` ile sirayla calistirir (satir 127-128). Ilk extractor session'i zehirlerse kalan 4'u de (hepsi ayni poisoned session'i kullandigi icin) hemen hata verir — ama bu hata da run_extractor icinde sessizce yutulur, sonuc: o gece o kullanici icin 5 extractor'in TAMAMI etkin sekilde calismamis olur.
- **Kanit:** satir 88-120 (ozellikle 118-120, rollback eksik); cagrim zinciri icin app/coach.py:1813-1832 ve app/action_executor.py:322-323, 359-360.
- **Celiski:** Bu davranis hem modul docstring'inin acik vaadiyle hem de fonksiyon docstring'leriyle dogrudan celisir:
  - Modul docstring satir 22: "Bir extractor cokerse digerleri etkilenmez."
  - `run_periodic_batch_for_user` docstring satir 124-125: "Bir extractor coker diger 4'u devam eder."
  - `trigger_after_user_message` docstring satir 258: "Hata izolasyonu: cokerse Coach response'u etkilemez."
  Gercekte, rollback eksikligi yuzunden bir extractor'in commit hatasi hem digerlerini hem de (event-triggered yolda) Coach'in kendi yanit kaydini etkileyebilir.
- **Aksiyon:** `run_extractor`'in except blogunda `db.rollback()` cagir (ya da mumkunse repo'da zaten kullanilan savepoint pattern'i uygula: her extractor'i `db.begin_nested()` ile sarip hata durumunda sadece o savepoint'i geri al, disaridaki session'i saglam tut).
- **Onem:** Kritik · **Guven:** Kesin

### [SC-002] _get_active_user_ids SQLAlchemy 1.x query() API kullaniyor - app/PROJE.md konvansiyonuna aykiri
- **Sorun:** `db.query(User).all()` (satir 140) kullaniliyor. `app/PROJE.md`: "SQLAlchemy 2.x: select() / session.execute() tercih edilir; session.query() eski pattern." kuralini ihlal ediyor.
- **Kanit:** satir 140
- **Aksiyon:** `db.execute(select(User)).scalars().all()` seklinde 2.x stiline cevir.
- **Onem:** Orta · **Guven:** Kesin

### [SC-003] nightly_trace_cleanup_job kardes job'lardan farkli hata davranisi - exception'i yeniden firlatiyor
- **Sorun:** `nightly_batch_job` (144-155) ve `k2_batch_job` (158-169) tum hatalari yutup sadece loglar, hicbir zaman raise etmez. `nightly_trace_cleanup_job` (172-203) ise `db.rollback()` + log sonrasi satir 201'de `raise` ile hatayi tekrar firlatiyor. APScheduler bu exception'i kendi executor'unda ayrica yakalayip loglayacagindan hata iki kez loglanir ve ayni scheduler icindeki uc job arasinda tutarsiz bir hata-yonetim politikasi var. Ayrica bu fonksiyon `_db_session()` context manager'ini kullanmiyor, ayni SessionLocal/try/finally mantigini elle tekrar yaziyor (kod tekrari).
- **Kanit:** satir 172-203 (ozellikle 198-201), karsilastirma icin 144-155 ve 158-169.
- **Aksiyon:** Tutarlilik icin ya raise'i kaldirip diger iki job gibi sadece logla, ya da bilincli bir tasarim kararsi bunu docstring'e not dus. `_db_session()` context manager'ini burada da kullanarak kod tekrarini kaldir.
- **Onem:** Dusuk · **Guven:** Kesin

### [SC-004] datetime.utcnow() kullanimi - deprecated ve dosya icinde tutarsiz
- **Sorun:** `nightly_batch_job` (146, 155) ve `k2_batch_job` (160, 169) log mesajlarinda `datetime.utcnow().isoformat()` kullaniyor; ayni dosyada `nightly_trace_cleanup_job` (186) ise `datetime.now(timezone.utc)` kullaniyor. `datetime.utcnow()` Python 3.12+'da deprecated (DeprecationWarning) ve tz-naive dondugu icin PROJE.md'nin genel "aware/naive tutarliligi" ilkesiyle de uyumsuz — su an sadece log string'i oldugundan frontend'e sizan bir bug degil, ama teknik borc ve dosya-ici tutarsizlik.
- **Kanit:** satir 146, 155, 160, 169 (utcnow) vs satir 186 (now(timezone.utc)).
- **Aksiyon:** Tum loglarda `datetime.now(timezone.utc)` kullanarak tek standarda gec.
- **Onem:** Dusuk · **Guven:** Kesin

### [SC-005] Trace cleanup cutoff'u tz-aware, ReasoningTrace.created_at DB'de tz-naive/server-default - karsilastirma DB-backend'ine bagimli kirilgan
- **Sorun:** `nightly_trace_cleanup_job` satir 186'da `cutoff = datetime.now(timezone.utc) - timedelta(days=90)` tz-AWARE bir deger hesaplar ve `ReasoningTrace.created_at < cutoff` (187-189) ile karsilastirir. `app/models.py:698`'de `created_at = Column(DateTime, server_default=func.now(), ...)` — SQLite'ta bu `CURRENT_TIMESTAMP` ile tz-naive UTC string olarak yazilir. SQLite + SQLAlchemy'nin varsayilan DATETIME tip islemcisi tz-aware datetime'lari strftime ile serialize ederken tzinfo'yu sessizce dusurdugu icin bu ozel kombinasyonda pratikte dogru sonuc uretiyor gibi gorunuyor, ancak bu davranis SQLite'a ozgu bir yan etki. Proje Postgres'e gecerse (`TIMESTAMP WITHOUT TIME ZONE` kolonuna tz-aware Python datetime ile karsilastirma) farkli/bozuk sonuc verebilir veya driver hatasi firlatabilir. Ayrica bu, `docs/architecture.md`'deki "DB'deki tum DateTime alanlari timezone-naive UTC" ilkesiyle query tarafinda tutarsiz bir pattern (query'de aware kullanmak).
- **Kanit:** satir 186-189; karsilastirma icin app/models.py:698.
- **Aksiyon:** `cutoff`'u da naive UTC olarak hesapla (`datetime.utcnow() - timedelta(days=90)` veya `datetime.now(timezone.utc).replace(tzinfo=None)`), boylece DB-backend'inden bagimsiz garanti dogru davransin.
- **Onem:** Orta · **Guven:** Dogrulanmali (SQLite'ta pratikte calisiyor olabilir; Postgres gecisi olmadan gozlemlenebilir bir hata uretmiyor)

### [SC-006] start_scheduler - onceki scheduler nesnesi durdurulmadan degistirilebilir (dusuk olasilikli kaynak sizintisi)
- **Sorun:** `start_scheduler()` (206-238) sadece `_scheduler is not None and _scheduler.running` durumunda mevcut scheduler'i geri donuyor (209-210). Eger `_scheduler` mevcut ama `.running == False` ise (orn. `.start()` sonrasi bir hata veya beklenmedik durdurma), kod yeni bir `AsyncIOScheduler` olusturup global `_scheduler`'i degistirir (212); eski nesne acikca `shutdown()` edilmeden referansi kaybedilir.
- **Kanit:** satir 208-213
- **Aksiyon:** Yeni scheduler olusturmadan once eski `_scheduler` non-None ise `.shutdown(wait=False)` cagirarak temizle. Dusuk olasilikli bir edge-case oldugundan opsiyonel iyilestirme.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
