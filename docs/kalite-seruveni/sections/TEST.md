# Test & QA (kod: TEST)

### [TEST-001] Kök `test_*.py` scriptleri gerçek DB'yi `drop_all` ediyor — veri kaybı riski
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: kok test_*.py guard'siz drop_all
- **Sorun:** `test_coach/action_executor/simulation.py` başlangıçta `drop_all(bind=engine)`; engine production `data/financialos.db`'ye bağlı. Elle çalıştırılırsa canlı veri silinir.
- **Kanıt:** `test_coach.py:16-17`, `test_action_executor.py:17-18`, `test_simulation.py:24-26`, `app/database.py:16`
- **Aksiyon:** pytest'e taşırken `sqlite:///:memory:`; geçiş bitene kadar guard `assert "memory" in str(engine.url) or os.getenv("ALLOW_DESTRUCTIVE_TEST")`.
- **Etki:** Yüksek · **Efor:** S

### [TEST-002] Belge çelişkisi: "pytest kullanılmıyor" derken olgun pytest suite var
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: maddenin kendi **Aksiyon**'u uygulanmış. `docs/dev-commands.md:29` artık *"GÜNCEL (M87, Wave-6): Aşağıdaki eski not artık YANLIŞ. `tests/` olgun bir **pytest** süiti"* diyor ve kök `test_*.py` dosyalarını tarihsel/manuel araç olarak ayırıyor. Belge çelişkisi kalmadı.
- **Kanıt:** `docs/dev-commands.md` vs `tests/conftest.py`, `tests/test_cashflow.py`, `.pytest_cache` (pytest-9.0.3)
- **Aksiyon:** dev-commands.md'yi güncelle: (a) `tests/` pytest suite, (b) kök legacy smoke; hedef tam pytest geçişi.
- **Etki:** Orta · **Efor:** S

### [TEST-003] `test_rules.py`/`test_fund_tracker.py` assert içermiyor — print scripti
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: rules matematigi assert'li
- **Sorun:** Çekirdek matematik sadece `print()`; beklenen değerler yorumda. Regresyon otomatik yakalanmaz.
- **Kanıt:** `test_rules.py:22-58`, `test_fund_tracker.py:32-37`
- **Aksiyon:** Yorumdaki değerleri `assert ... == pytest.approx(...)`'a çevir; `tests/test_rules_engine.py`'ye taşı.
- **Etki:** Yüksek · **Efor:** M

### [TEST-004] `rules_engine.py` (çekirdek karar motoru) pytest kapsamında değil
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: rules_engine pytest kapsaminda
- **Kanıt:** `tests/`'te yok; `generate_cockpit`/zikzak/kart stratejisi/uyarı test edilmiyor
- **Aksiyon:** `tests/test_rules_engine.py`: `generate_cockpit` altın-snapshot, `parse_gg_command` format tablosu.
- **Etki:** Yüksek · **Efor:** M

### [TEST-005] İki farklı DB izolasyon deseni çakışıyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: conftest in-memory StaticPool
- **Sorun:** `conftest.py` production engine'e `create_all`+`rollback`; `test_simulation_endpoint.py` doğru `:memory:`+StaticPool. conftest testleri canlı DB'ye yazıyor.
- **Kanıt:** `tests/conftest.py:2-13` vs `tests/test_simulation_endpoint.py:27-45`
- **Aksiyon:** conftest'i StaticPool `:memory:`'ye taşı; tek kanonik `db_session`+`client` fixture; `dependency_overrides` conftest'e.
- **Etki:** Yüksek · **Efor:** M

### [TEST-006] `test_user` fixture `commit()` yapıyor → testler arası sızıntı
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: izole in-memory DB
- **Kanıt:** `tests/conftest.py:22,29`; `tests/test_goal_engine.py:33-46` (sızıntıyı belgeler + manuel DELETE workaround)
- **Aksiyon:** SAVEPOINT deseni (`connection.begin()`→test→`transaction.rollback()`); manuel DELETE'leri sil. (MEMORY savepoint feedback'i ile uyumlu)
- **Etki:** Yüksek · **Efor:** M

### [TEST-007] `action_executor` Master Checkpoint enforcement'ı pytest'te değil
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: Master Checkpoint assert'li
- **Sorun:** Sistemin en kritik güvenlik kuralı sadece assert'siz scriptte print ile kontrol ediliyor.
- **Kanıt:** `test_action_executor.py:121-130`
- **Aksiyon:** `tests/test_action_executor.py`: `test_emanet_satis_reddedilir` (assert not success + lot değişmedi), kisisel satis, reject, add_transaction bakiye.
- **Etki:** Yüksek · **Efor:** M

### [TEST-008] `coach.py` FallbackProvider zinciri hiç test edilmiyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: test_fallback_provider FakeProvider
- **Kanıt:** `docs/architecture.md`; `test_coach.py:105-113` (tek gerçek çağrı)
- **Aksiyon:** Sahte provider'larla (biri ProviderEmptyResponseError, biri başarılı) ikinciye geçişi assert et.
- **Etki:** Yüksek · **Efor:** M · **Not:** TEST-012 ile birlikte.

### [TEST-009] Frontend'de hiç test altyapısı yok (Vitest/RTL kurulu değil)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: vitest + testing-library
- **Kanıt:** `frontend/package.json:7-27` (test script yok)
- **Aksiyon:** `vitest+@testing-library/react+jsdom`; `vite.config.js` test bloğu; ilk test: api.js UTC parse + ApiError.
- **Etki:** Orta · **Efor:** M

### [TEST-010] CI yok — testler otomatik çalışmıyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: ci.yml backend+e2e
- **Kanıt:** `.github/` yok
- **Aksiyon:** `.github/workflows/ci.yml`: `pytest tests/ --cov=app --cov-fail-under=60` + frontend `npm test`; push+PR.
- **Etki:** Yüksek · **Efor:** M

### [TEST-011] Test bağımlılıkları requirements'ta beyan edilmemiş
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: requirements-dev.txt
- **Kanıt:** `requirements.txt` pytest/httpx/pytest-cov/hypothesis yok; `test_simulation_endpoint.py:13` TestClient
- **Aksiyon:** `requirements-dev.txt` (pytest, pytest-cov, httpx, hypothesis, coverage[toml]) sabit sürüm.
- **Etki:** Yüksek · **Efor:** S

### [TEST-012] Mock/sahte LLM provider yok — testler gerçek API'ye vuruyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: FakeProvider inject
- **Kanıt:** `test_coach.py:1-5,126`
- **Aksiyon:** `FakeProvider` (sabit tool-call/metin); CoachEngine'i provider-inject edilebilir yap; gerçek API testleri `@pytest.mark.llm` default skip.
- **Etki:** Yüksek · **Efor:** M

### [TEST-013] Rules Engine matematiği için Hypothesis property testleri yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: property_math @given invariant
- **Kanıt:** `test_rules.py:29-58`
- **Aksiyon:** `net_eline_gecen <= satis_tutari`, `stopaj>=0`, `lots_to_sell<=lot_count`, daily_limit round-trip invariant'ları.
- **Etki:** Orta · **Efor:** M

### [TEST-014] debt_strategy snowball/avalanche için Hypothesis invariant
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: debt_metric_properties @given
- **Kanıt:** `tests/test_debt_strategy.py:92-119,191-204`
- **Aksiyon:** Rastgele portföyler; `avalanche.interest <= snowball.interest`, `months <= MAX_MONTHS`, tüm borçlar payoff'ta.
- **Etki:** Orta · **Efor:** M

### [TEST-015] `simulation_engine` gerçek mantığı endpoint testinde mock'lu
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: gercek mantik test e2e
- **Kanıt:** `test_simulation_endpoint.py:138` (`@patch simulate_action`); `test_simulation.py:88-117` (print)
- **Aksiyon:** `tests/test_simulation_engine.py`: kanonik veri, baseline vs aksiyon delta assert, emanet ihlali ok=False.
- **Etki:** Orta · **Efor:** M

### [TEST-016] Coverage ölçümü/raporu yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: pyproject coverage source=app
- **Kanıt:** `.coveragerc`/`pyproject [tool.coverage]` yok
- **Aksiyon:** `[tool.coverage.run] source=["app"]` + `fail_under=60`; `--cov-report=term-missing,html`; baseline al.
- **Etki:** Orta · **Efor:** S

### [TEST-017] Coverage eşiği CI gate — önce gerçekçi baseline
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `.github/workflows/ci.yml:97` `--cov-fail-under=93` ile koşuyor (eşik bilinçli olarak `pyproject.toml`'da değil, o satırda; gerekçesi `ci.yml:81`'de yazılı). Maddenin önerdiği 60 değil **93** seçilmiş — ölçülen gerçek %94,02 üzerine kurulu bir ratchet.
- **Kanıt:** pytest-cov #444 (dosya-bazlı eşik yok)
- **Aksiyon:** Global `--cov-fail-under=60` + kritik modüller için ayrı per-modül gate; matrix `coverage combine`.
- **Etki:** Orta · **Efor:** M

### [TEST-018] `pyproject [tool.pytest.ini_options]` yok — test keşfi/marker tanımsız
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: pytest markers tanimli
- **Sorun:** `testpaths`/marker yok; kök `test_*.py` yanlışlıkla toplanıp drop_all çalıştırabilir.
- **Kanıt:** kök config yok; `test_action_executor.py:17` import-time drop_all
- **Aksiyon:** `testpaths=["tests"]`, `markers=["llm","slow"]`, `addopts="--strict-markers"`.
- **Etki:** Yüksek · **Efor:** S · **Not:** TEST-001 riskini de azaltır.

### [TEST-019] `fund_tracker` utcnow'a bağlı testler flaky potansiyeli
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: is_price_stale esik enjekte ama ic utcnow
- **Kanıt:** `test_fund_tracker.py:26-30`
- **Aksiyon:** `is_price_stale`'e enjekte edilebilir `now`; freezegun/monkeypatch; sınır (24h) deterministik.
- **Etki:** Düşük · **Efor:** S

### [TEST-020] Regresyon suite yok — kanonik "Murat 1 Mayıs 2026" altın-snapshot
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: founding_scenario cockpit regresyon
- **Kanıt:** `docs/architecture.md`; kök scriptler veriyi elle kuruyor
- **Aksiyon:** Kanonik veriyi `tests/fixtures/murat_scenario.py`'ye; `generate_cockpit` çıktısını JSON snapshot; diff (syrupy).
- **Etki:** Yüksek · **Efor:** M

### [TEST-021] Kanonik veri kurulumu 3+ dosyada kopya — fixture merkezileştir
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: fixtures/factories merkezi yok
- **Kanıt:** `test_coach.py:25-98` vs `test_simulation.py:31-69` (MC sayısı 8 vs docs 7 tutarsızlık)
- **Aksiyon:** `tests/fixtures.py` `build_murat_scenario(db)`; factory'leri `tests/factories.py`'ye.
- **Etki:** Orta · **Efor:** M

### [TEST-022] `models.py` schema/constraint testi yok (dual-index, cascade, unique)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: workspace_model create_all+unique
- **Kanıt:** git log `89d3710`,`91546aa` (index bug'ları); MEMORY dual-index
- **Aksiyon:** `tests/test_schema.py`: `:memory:` create_all smoke; GoalAllocation cascade/unique.
- **Etki:** Orta · **Efor:** S

### [TEST-023] Alembic migration'ları test edilmiyor (upgrade round-trip)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: fresh_db_migration CI'da
- **Kanıt:** `alembic/`+`alembic.ini` var, test yok
- **Aksiyon:** `tests/test_migrations.py`: `alembic upgrade head` temiz DB'de; models vs migration drift.
- **Etki:** Düşük · **Efor:** M

### [TEST-024] `propose_action` KURAL SIFIR için LLM eval harness yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: KURAL SIFIR harness
- **Kanıt:** `docs/architecture.md`; `test_coach.py:145-151`
- **Aksiyon:** girdi→beklenen-davranış (selam→tool YOK, "500 harcadım"→VAR, "emanet satalım"→YOK); 10-15 vaka, her değişimde.
- **Etki:** Yüksek · **Efor:** M · **Not:** LLM-004 ile aynı harness.

### [TEST-025] Prompt regresyon testi (promptfoo/DeepEval) seçilmeli
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: promptfoo yasak-ifade regresyon yok
- **Kanıt:** `docs/architecture.md` (Llama dalkavukluk sorunu)
- **Aksiyon:** promptfoo `assert not-contains ["Harika","Mükemmel"]` + `contains "Matematik buna izin vermiyor"`; Gemini+Groq matrisi.
- **Etki:** Orta · **Efor:** M

### [TEST-026] cashflow forecast için Hypothesis genişletmesi
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: test_cashflow @given
- **Kanıt:** `tests/test_cashflow.py:339-360,366-382`
- **Aksiyon:** `@given` ile `_month_occurrences` clamp invariant (gün>ay_uzunluğu→ay-sonu), determinizm property.
- **Etki:** Düşük · **Efor:** S

### [TEST-027] `get_current_user` çok-kullanıcı izolasyonu testi yaygın değil
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: cross-user izolasyon (scope_enforcement)
- **Kanıt:** `test_simulation_endpoint.py:171-185` (tek router)
- **Aksiyon:** Cross-user 404'ü tüm mutasyon endpoint'lerine parametrize et.
- **Etki:** Düşük · **Efor:** M

### [TEST-028] `fund_tracker` dış fiyat çağrıları için mock yok (ağ bağımlılığı)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: price_providers monkeypatch
- **Kanıt:** `requirements.txt:13-16` (tefas/borsa/yfinance)
- **Aksiyon:** Dış çağrıları adapter arkasına; `responses`/mock ile deterministik.
- **Etki:** Düşük · **Efor:** M

### [TEST-029] `scheduler` proaktif hatırlatma testi zamana bağlı olabilir
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: test_scheduler deterministik
- **Kanıt:** `tests/test_scheduler.py`; wave-2 A1
- **Aksiyon:** `should_remind(today, due_date, ...)` saf fonksiyona ayır, tarih enjekte et; scheduler'ı manuel `func()` ile by-pass.
- **Etki:** Düşük · **Efor:** M

### [TEST-030] `main.py` startup + health smoke testi yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: test_startup+smoke
- **Kanıt:** `app/main.py`
- **Aksiyon:** `tests/test_app_smoke.py`: `TestClient` `/api/health` 200 + router prefix'leri; import-time create_all patlarsa yakalar.
- **Etki:** Orta · **Efor:** S

### [TEST-031] Datetime/timezone serileştirme regresyon testi yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: test_serializers +00:00
- **Kanıt:** `app/PROJE.md`; `_memory_to_history_item`
- **Aksiyon:** `tests/test_datetime_serialization.py`: tarih dönen endpoint yanıtı `+00:00`/`Z` suffix içeriyor mu.
- **Etki:** Orta · **Efor:** S

### [TEST-032] Test isimlendirmesi karışık: kök script vs tests/ pytest aynı ad
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: kok test_*.py tasinmadi
- **Kanıt:** kök `test_simulation.py` vs `tests/test_simulation_endpoint.py`; `test_action_executor.py:17` import-time yan etki
- **Aksiyon:** Kök scriptleri `scripts/smoke/`'a taşı veya sil; kısa vade `testpaths=["tests"]`.
- **Etki:** Orta · **Efor:** S

### [TEST-033] `goal_rules`/`premortem` birim testi zayıf/endpoint-only
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: premortem_coverage birim
- **Kanıt:** `tests/test_premortem_endpoint.py`, `test_premortem_link_outcome.py`
- **Aksiyon:** `tests/test_premortem.py` saf karar fonksiyonları; endpoint=sözleşme, birim=mantık.
- **Etki:** Düşük · **Efor:** M

### [TEST-034] Contract testi yok: backend şema ↔ frontend api.js beklentisi
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: cockpit contract backend ama frontend yok
- **Kanıt:** `frontend/PROJE.md` (mapping yok); `schemas.py`; `api.js`
- **Aksiyon:** Kritik yanıt şemalarını (cockpit anahtarları) JSON snapshot; iki tarafta referans. Alan adı değişimi kırmızı verir.
- **Etki:** Orta · **Efor:** M

### [TEST-035] Flaky-test önleme politikası/marker yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: markerlar var ama CI filtresiz
- **Kanıt:** `test_coach.py` (canlı API), `test_fund_tracker.py:26` (utcnow)
- **Aksiyon:** `@pytest.mark.llm/network/slow`; CI default `-m "not llm and not network"`; sadece dış-bağımlı testlerde `pytest-rerunfailures`; birim testlerde retry YASAK.
- **Etki:** Orta · **Efor:** S

---
**Kaynaklar:** FastAPI+SQLModel testing; Hypothesis (property-based, finansal precision); DeepEval/promptfoo (LLM eval); Vitest+RTL 2026; pytest-cov 2026 + fail_under #444.
