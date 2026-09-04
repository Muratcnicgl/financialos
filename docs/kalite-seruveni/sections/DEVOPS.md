# CI/CD, build, tooling (kod: DEVOPS)

> Tek-kullanıcı MVP, Windows geliştirme. Çoğu madde "şimdi ucuz, ileride zorunlu". SEC/TEST bölümleriyle bazı noktalar örtüşür; burada build/otomasyon lensinden.

### [DEVOPS-001] CI yok — hiçbir otomatik kontrol çalışmıyor
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: ci.yml backend+e2e (M69)
- **Sorun/Fırsat:** `.github/` yok; test/lint/build push anında doğrulanmıyor, regresyon sessizce giriyor.
- **Kanıt:** repo kökü (`.github` yok)
- **Aksiyon:** `.github/workflows/ci.yml`: Python 3.11 + Node matrix; `pytest tests/`, frontend `npm run build`, lint. Push+PR tetik.
- **Etki:** Yüksek · **Efor:** M

### [DEVOPS-002] Lint/format aracı yok (ruff/black) — stil tutarsız
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `ruff` var, **tam sürümle sabit** (`requirements-dev.txt`: `ruff==0.16.4`), yapılandırması `ruff.toml`'da ve CI'da bir GERİLEME SAYACI olarak koşuyor (`ci.yml:57` → `scripts/kalite_kapisi.py`). Yani madde "araç yok" diyordu; bugün araç hem var hem tavana bağlı (B 31 · E9 0 · F 202 · S 62).
- **Kanıt:** `pyproject.toml`/`.ruff.toml` yok
- **Aksiyon:** `ruff` (lint+format, black-uyumlu) + `pyproject` config; CI'da `ruff check`.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-003] Frontend lint/format standardı belirsiz (eslint/prettier)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: eslint/prettier yok
- **Kanıt:** `frontend/` (eslint config tutarlılığı doğrulanmalı); package.json'da lint script yok
- **Aksiyon:** eslint (react-hooks plugin — FE-028 exhaustive-deps yakalar) + prettier; `npm run lint`.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-004] pre-commit hook yok — kalite kontrolü commit'e bağlı değil
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `.githooks/pre-commit` var ve staged dosyalara göre pytest/vitest koşuyor; kurulumu `bash scripts/install-hooks.sh` (`core.hooksPath=.githooks`). Bu gecenin her commit'i o kancadan geçti — birkaç kez de gerçekten ENGELLEDİ (kişisel veri tavanı, ölü kod kapısı).
- **Kanıt:** `.pre-commit-config.yaml` yok
- **Aksiyon:** pre-commit: ruff, prettier, gitleaks (secret), büyük-dosya kontrolü.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-005] Bağımlılıklar pin/lock değil — tekrarlanabilir build yok
- **Durum:** 🟡 KISMEN — 5 Eyl 2026 ölçümü: `requirements.txt` **24/27 satır** tam sürümle sabit ve `frontend/package-lock.json` var; yani ürün bağımlılıkları tekrarlanabilir. AÇIK KALAN: `requirements-dev.txt` yalnız **1/5** pinli (`ruff==0.16.4` — o da bilinçli, tavan bir araç sürümüne aittir); `pytest>=8.0`, `pytest-cov>=5.0`, `httpx>=0.27`, `hypothesis>=6.100` alt sınırla duruyor. Yani bir gün süit, kod değişmeden başka bir pytest sürümüyle koşabilir.
- **Kanıt:** `requirements.txt` bazı `>=` (anthropic>=0.79.0 vb.); lock dosyası yok
- **Aksiyon:** `pip-tools`/`uv` ile `requirements.lock` (hash'li); `requirements.in` kaynak. (SEC-021)
- **Etki:** Orta · **Efor:** S

### [DEVOPS-006] Test bağımlılıkları ayrı beyan edilmemiş
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: requirements-dev.txt var, CI kuruyor
- **Kanıt:** `requirements.txt` pytest/httpx/hypothesis yok (TEST-011)
- **Aksiyon:** `requirements-dev.txt`; CI onu kursun.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-007] mypy/tip kontrolü yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: mypy config/gate yok
- **Kanıt:** repo (`mypy.ini`/type check yok); modeller legacy Column (tip'siz)
- **Aksiyon:** `mypy` kademeli (önce yeni modüller, DATA-031 Mapped ile); CI'da opsiyonel gate.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-008] Dockerfile / konteynerleştirme yok
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: Docker+compose+Caddy+HEALTHCHECK (M80)
- **Kanıt:** repo (`Dockerfile`/`compose` yok)
- **Aksiyon:** Multi-stage Dockerfile (backend) + frontend build stage; deploy/tekrarlanabilirlik. Mobile backend deploy için ön koşul.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-009] Deploy stratejisi belgelenmemiş (mobile backend için şart)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: deployment README + ADR-035 (canlı-CD kapsam-dışı)
- **Kanıt:** `docs/architecture/mobile-roadmap.md` (Cloudflare Tunnel/Tailscale/VPS seçenekleri var ama karar/otomasyon yok)
- **Aksiyon:** Bir deploy hedefi seç (VPS+Caddy TLS); deploy script/CD; env yönetimi.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-010] Backup otomasyonu manuel kuruluma bağlı
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: backup scheduler'a bağlı değil, schtasks manuel
- **Kanıt:** `docs/dev-commands.md` (schtasks tek-seferlik kurulum); `scripts/backup.py`
- **Aksiyon:** Backup'ı uygulama scheduler'ına (apscheduler zaten var) bağla — kurulumdan bağımsız; off-site kopya (RESIL-012).
- **Etki:** Orta · **Efor:** S

### [DEVOPS-011] Python sürümü pin'lenmemiş
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `.github/workflows/ci.yml` üç işin üçünde de `python-version: '3.11'` sabitliyor (satır 46 · 109 · 163).
- **Kanıt:** `.python-version`/`pyproject` `requires-python` yok
- **Aksiyon:** `.python-version` (3.11) + `requires-python`; deprecated `datetime.utcnow` (DATA-008) gibi sürüm-bağımlı sorunları netleştir.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-012] Güvenlik taraması CI'da yok (pip-audit/bandit/gitleaks)
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: CI'da **dört** ayrı tarama koşuyor — `pip-audit -r requirements.txt --strict` (`ci.yml:115-119`, her push + haftalık cron) · sır taraması (`scripts/sir_taramasi`, geçmiş dahil) · npm denetimi (`scripts/npm_denetim`) · ruff'ın **S** ailesi (bandit kuralları, tavana bağlı). BUG #260'ın kendi yorumu bu maddenin haklı olduğunu ve nasıl kapandığını yazıyor: *"bir kez yeşil, sürekli yeşil demek değildir"* (L28).
- **Kanıt:** CI yok (SEC-020/035)
- **Aksiyon:** CI job: `pip-audit`, `bandit`, `gitleaks`; kritik bulguda fail.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-013] Coverage CI gate yok
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `ci.yml:97` `--cov-fail-under=93` ile koşuyor (eşik bilinçli olarak workflow satırında, `pyproject.toml`'da değil; gerekçesi `ci.yml:81`'de). `TEST-017` ile aynı iş — iki boyutta iki kez kaydedilmiş.
- **Kanıt:** coverage config yok (TEST-016/017)
- **Aksiyon:** `pytest --cov=app --cov-fail-under=60`; kademeli yükselt.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-014] Task runner / Makefile yok — komutlar dokümanda dağınık
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Makefile/justfile yok
- **Kanıt:** `docs/dev-commands.md` (elle komutlar)
- **Aksiyon:** `Makefile`/`justfile` (setup, run, test, lint, backup); Windows için `tasks.ps1` veya `just`.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-015] `.env.example` güncelliği/sürüklenme riski
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: .env.example iç-tutarlı ama PROJE.md sürüklenme
- **Kanıt:** `.env.example` vs README (Groq/Cerebras/Gemini/OpenRouter) vs PROJE.md (gemini/anthropic/groq) — provider listesi tutarsız
- **Aksiyon:** `.env.example`'ı `Settings` (BE-012) şemasından türet/senkronla; tek doğruluk kaynağı.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-016] Frontend build çıktısı/deploy pipeline yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: CI e2e npm run dev, build+artifact yok
- **Kanıt:** `frontend/` (`npm run build` var, dağıtım yok)
- **Aksiyon:** CI'da build + artifact; backend `StaticFiles` ile serve veya ayrı statik host.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-017] Bağımlılık güncelleme otomasyonu yok (Dependabot/Renovate)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Dependabot/Renovate yok
- **Kanıt:** repo (dependabot config yok)
- **Aksiyon:** Dependabot/Renovate (haftalık PR); güvenlik güncellemeleri otomatik.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-018] Ortam ayrımı yok (dev/prod config)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: settings.py environment/is_production, compose ENVIRONMENT
- **Kanıt:** `os.getenv` dağınık (BE-012); DEBUG/prod ayrımı yok
- **Aksiyon:** `Settings.env` (dev/prod); CORS/docs/log-level/rate-limit ortama göre.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-019] Git hijyen: `.env` diskte, runtime `data/` — sızma/temizlik denetimi
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: .env git-history temiz ama otomatik gitleaks yok
- **Kanıt:** `.gitignore` (data/ hariç tutulmuş — iyi); `.env` geçmiş commit kontrolü (SEC-018)
- **Aksiyon:** `git log --all -- .env` doğrula; gitleaks pre-commit; `.gitignore` düzenli denetim.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-020] Sürümleme/CHANGELOG/release süreci yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: CHANGELOG yok, SemVer disiplini yok
- **Kanıt:** `app.version` var ama CHANGELOG/tag disiplini yok (DOCS ile)
- **Aksiyon:** SemVer tag + CHANGELOG (BUG #NNN geçmişini toparla); API versiyonuyla (API-001) hizala.
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** GitHub Actions (Python+Node); ruff; pre-commit; pip-tools/uv lock; pip-audit/bandit/gitleaks; Dependabot; Docker multi-stage.
