# CI/CD, build, tooling (kod: DEVOPS)

> Tek-kullanıcı MVP, Windows geliştirme. Çoğu madde "şimdi ucuz, ileride zorunlu". SEC/TEST bölümleriyle bazı noktalar örtüşür; burada build/otomasyon lensinden.

### [DEVOPS-001] CI yok — hiçbir otomatik kontrol çalışmıyor
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Sorun/Fırsat:** `.github/` yok; test/lint/build push anında doğrulanmıyor, regresyon sessizce giriyor.
- **Kanıt:** repo kökü (`.github` yok)
- **Aksiyon:** `.github/workflows/ci.yml`: Python 3.11 + Node matrix; `pytest tests/`, frontend `npm run build`, lint. Push+PR tetik.
- **Etki:** Yüksek · **Efor:** M

### [DEVOPS-002] Lint/format aracı yok (ruff/black) — stil tutarsız
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `pyproject.toml`/`.ruff.toml` yok
- **Aksiyon:** `ruff` (lint+format, black-uyumlu) + `pyproject` config; CI'da `ruff check`.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-003] Frontend lint/format standardı belirsiz (eslint/prettier)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `frontend/` (eslint config tutarlılığı doğrulanmalı); package.json'da lint script yok
- **Aksiyon:** eslint (react-hooks plugin — FE-028 exhaustive-deps yakalar) + prettier; `npm run lint`.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-004] pre-commit hook yok — kalite kontrolü commit'e bağlı değil
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `.pre-commit-config.yaml` yok
- **Aksiyon:** pre-commit: ruff, prettier, gitleaks (secret), büyük-dosya kontrolü.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-005] Bağımlılıklar pin/lock değil — tekrarlanabilir build yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `requirements.txt` bazı `>=` (anthropic>=0.79.0 vb.); lock dosyası yok
- **Aksiyon:** `pip-tools`/`uv` ile `requirements.lock` (hash'li); `requirements.in` kaynak. (SEC-021)
- **Etki:** Orta · **Efor:** S

### [DEVOPS-006] Test bağımlılıkları ayrı beyan edilmemiş
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `requirements.txt` pytest/httpx/hypothesis yok (TEST-011)
- **Aksiyon:** `requirements-dev.txt`; CI onu kursun.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-007] mypy/tip kontrolü yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** repo (`mypy.ini`/type check yok); modeller legacy Column (tip'siz)
- **Aksiyon:** `mypy` kademeli (önce yeni modüller, DATA-031 Mapped ile); CI'da opsiyonel gate.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-008] Dockerfile / konteynerleştirme yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** repo (`Dockerfile`/`compose` yok)
- **Aksiyon:** Multi-stage Dockerfile (backend) + frontend build stage; deploy/tekrarlanabilirlik. Mobile backend deploy için ön koşul.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-009] Deploy stratejisi belgelenmemiş (mobile backend için şart)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `docs/architecture/mobile-roadmap.md` (Cloudflare Tunnel/Tailscale/VPS seçenekleri var ama karar/otomasyon yok)
- **Aksiyon:** Bir deploy hedefi seç (VPS+Caddy TLS); deploy script/CD; env yönetimi.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-010] Backup otomasyonu manuel kuruluma bağlı
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `docs/dev-commands.md` (schtasks tek-seferlik kurulum); `scripts/backup.py`
- **Aksiyon:** Backup'ı uygulama scheduler'ına (apscheduler zaten var) bağla — kurulumdan bağımsız; off-site kopya (RESIL-012).
- **Etki:** Orta · **Efor:** S

### [DEVOPS-011] Python sürümü pin'lenmemiş
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `.python-version`/`pyproject` `requires-python` yok
- **Aksiyon:** `.python-version` (3.11) + `requires-python`; deprecated `datetime.utcnow` (DATA-008) gibi sürüm-bağımlı sorunları netleştir.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-012] Güvenlik taraması CI'da yok (pip-audit/bandit/gitleaks)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** CI yok (SEC-020/035)
- **Aksiyon:** CI job: `pip-audit`, `bandit`, `gitleaks`; kritik bulguda fail.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-013] Coverage CI gate yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** coverage config yok (TEST-016/017)
- **Aksiyon:** `pytest --cov=app --cov-fail-under=60`; kademeli yükselt.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-014] Task runner / Makefile yok — komutlar dokümanda dağınık
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `docs/dev-commands.md` (elle komutlar)
- **Aksiyon:** `Makefile`/`justfile` (setup, run, test, lint, backup); Windows için `tasks.ps1` veya `just`.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-015] `.env.example` güncelliği/sürüklenme riski
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `.env.example` vs README (Groq/Cerebras/Gemini/OpenRouter) vs PROJE.md (gemini/anthropic/groq) — provider listesi tutarsız
- **Aksiyon:** `.env.example`'ı `Settings` (BE-012) şemasından türet/senkronla; tek doğruluk kaynağı.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-016] Frontend build çıktısı/deploy pipeline yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `frontend/` (`npm run build` var, dağıtım yok)
- **Aksiyon:** CI'da build + artifact; backend `StaticFiles` ile serve veya ayrı statik host.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-017] Bağımlılık güncelleme otomasyonu yok (Dependabot/Renovate)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** repo (dependabot config yok)
- **Aksiyon:** Dependabot/Renovate (haftalık PR); güvenlik güncellemeleri otomatik.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-018] Ortam ayrımı yok (dev/prod config)
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `os.getenv` dağınık (BE-012); DEBUG/prod ayrımı yok
- **Aksiyon:** `Settings.env` (dev/prod); CORS/docs/log-level/rate-limit ortama göre.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-019] Git hijyen: `.env` diskte, runtime `data/` — sızma/temizlik denetimi
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `.gitignore` (data/ hariç tutulmuş — iyi); `.env` geçmiş commit kontrolü (SEC-018)
- **Aksiyon:** `git log --all -- .env` doğrula; gitleaks pre-commit; `.gitignore` düzenli denetim.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-020] Sürümleme/CHANGELOG/release süreci yok
- **Durum:** 🔲 AÇIK — kod-doğrulaması bekliyor (M76)
- **Kanıt:** `app.version` var ama CHANGELOG/tag disiplini yok (DOCS ile)
- **Aksiyon:** SemVer tag + CHANGELOG (BUG #NNN geçmişini toparla); API versiyonuyla (API-001) hizala.
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** GitHub Actions (Python+Node); ruff; pre-commit; pip-tools/uv lock; pip-audit/bandit/gitleaks; Dependabot; Docker multi-stage.
