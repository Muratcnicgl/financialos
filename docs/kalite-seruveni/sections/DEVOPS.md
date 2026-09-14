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
- **Durum:** ✅ KAPANDI — BUG #474 (14 Eyl 2026). Ölçüldü: `frontend/`de eslint yok, lint betiği yok; koddaki 26 `eslint-disable` direktifi hiçbir yapılandırmanın tanımadığı kurallara işaret ediyordu (susturma bile ölçülmüyordu). Kuruldu: eslint 9.39.5 + @eslint/js + eslint-plugin-react 7.37.5 + eslint-plugin-react-hooks 7.1.1 (tam sürüm sabit; eslint 10 BİLEREK değil — plugin-react peer ^9), tek düz config `frontend/eslint.config.js`, `npm run lint` → `scripts/lint.cjs`. **İlk koşum 112 hata + 11 uyarı; ikisi GERÇEK defekt:** `PendingActions.jsx`de `useEffect`/`useState` erken `return null` satırından SONRA çağrılıyordu (rules-of-hooks — koşul değişince React "fewer hooks" ile çöker; bugün üst bileşen boş listede bileşeni çizmediği için görünmüyordu). Ayrıca 8 diyalogda render sırasında ref yazımı (`onCloseRef.current = onClose`) tek kaynağa (`useDialog(kutuRef, onClose)`) çekildi; `BudgetBreakdown` içinde her render'da yeniden tanımlanan `Row` bileşeni dışarı alındı; 13 `jsx-key`, 32 kullanılmayan değişken/import, 20 boş direktif temizlendi. Hata artık SIFIR ve sıfır kalır; tek warn kuralı `react-hooks/set-state-in-effect` (27) TAVANLI: `kalite-baseline.json › frontend` + `scripts/eslint_kapisi.py` (ruff sayacıyla aynı felsefe, kural başına). Kapı pre-commit'e (frontend src/e2e/scripts değişince, ~17 sn) ve CI'a bağlandı; **CI'da vitest de koşmuyordu** (200+ test yalnız yerel hook'a bağlıydı) → `frontend-kalite` işi ikisini koşar. Windows'ta "İ" içeren yollarda ESLint'in ignore eşleştirmesi bozuluyor (`@eslint/config-array` toLowerCase kaymalı dilimleme; Node'un path.relative'i temiz) → sarmalayıcı 8.3 kısa yola düşer, gerekçe dosyada. prettier ⛔ (ruff format ile aynı gerekçe: 200+ dosyalık anlamsız diff). Kapı testi `tests/test_eslint_kapisi.py` (12 test, mutasyon 5/5).
- **Kanıt:** `frontend/eslint.config.js`, `frontend/scripts/lint.cjs`, `scripts/eslint_kapisi.py`, `.githooks/pre-commit`, `.github/workflows/ci.yml › frontend-kalite`
- **Aksiyon:** eslint (react-hooks plugin — FE-028 exhaustive-deps yakalar) + prettier; `npm run lint`.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-004] pre-commit hook yok — kalite kontrolü commit'e bağlı değil
- **Durum:** ✅ KAPANDI — 5 Eyl 2026 ölçümü: `.githooks/pre-commit` var ve staged dosyalara göre pytest/vitest koşuyor; kurulumu `bash scripts/install-hooks.sh` (`core.hooksPath=.githooks`). Bu gecenin her commit'i o kancadan geçti — birkaç kez de gerçekten ENGELLEDİ (kişisel veri tavanı, ölü kod kapısı).
- **Kanıt:** `.pre-commit-config.yaml` yok
- **Aksiyon:** pre-commit: ruff, prettier, gitleaks (secret), büyük-dosya kontrolü.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-005] Bağımlılıklar pin/lock değil — tekrarlanabilir build yok
- **Durum:** ✅ KAPANDI — **BUG #390 (11 Eyl 2026):** 5 Eyl'deki "24/27" ölçümünden sonra güvenlik tabanı `>=` ile eklenmiş ve gevşek satır **9'a** çıkmıştı — madde ölçen kapı olmadığı için gerilemişti. `requirements.txt` ve `requirements-dev.txt` artık tamamen `==` (kurulu venv sürümleri; pip çözümü doğrulandı). Kapı `tests/test_bagimlilik_sabitleme_kapisi.py` dosyadan türetir. Hash'li lock (`pip-tools`/`uv`) BİLEREK yok: tek makine + CI, `pip-audit` her push'ta; ihtiyaç ölçülmeden ikinci bir araç ve akış eklemek L79 sınıfı. Yükseltme bilinçli: pip-audit kırmızısı ya da ölçülmüş ihtiyaç; satır değişir, `git blame` sebebi gösterir.
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
- **Durum:** ✅ KAPANDI — BUG #494 (14 Eyl 2026). Ölçüldü: SQLite yedeği yalnız Windows Görev Zamanlayıcı'ndan (`gorevleri_kur.ps1`, 03:15) ya da elle koşuyordu — görevi kurmayan makinede hiç yedek alınmıyor, bunu ölçen yoktu. Çekirdek `app/yedek.py`e taşındı (`sqlite_yedekle`: çevrimiçi yedek + integrity_check + saklama; hata YÜKSELİR, yarım kopya kalmaz); `app/scheduler.py` SQLite'ta `sqlite_backup` işini 03:15'te koşturur (fiyat 02:45 ve gece batch 03:00'dan sonra), izleme sarmalayıcısıyla çalışma kaydı bırakır — yedek ölürse `/api/ops/scheduler › sorunlu_isler` ve canlı kapı görür. CLI (`python -m scripts.backup`) aynı çekirdeği çağırır (uygulama `scripts/`e bağımlı değil — BE-033 kapısı). PostgreSQL'de iş listede yok; oradaki yedek `pg_backup` dış işi (BUG #240). Windows görevi yedek olarak kalır (iki bağımsız yol). ⚪ Off-site kopya RESIL-012'nin konusu. Kapı `tests/test_yedek_isi_kapisi.py` (4 test).
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
- **Durum:** ✅ KAPANDI — BUG #475 (14 Eyl 2026). Ölçüldü: Makefile/justfile/tasks yok; aynı komut dört yerde farklı yazılıyordu (dev-commands, contributing, pre-commit, ci.yml — testler üç ayrı biçimde). Karar: Makefile ⛔ tek başına (Windows'ta `make` yok), tasks.ps1 ⛔ (CI Linux), ikisi birden ⛔ (iki kaynak = sürüklenme). Tek kaynak `scripts/gorev.py` — Python zaten şart, her yerde aynı: `python -m scripts.gorev <görev>` (kur, goc, calistir, arayuz, derle, test, test-hizli, test-arayuz, e2e, lint, kapilar, yedek, durum, koc-eval), `--kuru` komutu gösterir. `Makefile` tek satırlık vekil (`.DEFAULT` → gorev.py), komut bilgisi taşımaz. Kapı testi `tests/test_gorev_kapisi.py`: her hedef var, `kapilar` scripts/ altındaki HER `*_kapisi.py`yi kapsar (yeni kapı eklenip unutulursa kırmızı), `test-hizli` pre-commit ile aynı seçim, Makefile'a komut sızmaz, belgeler anar; mutasyon 3/3.
- **Kanıt:** `scripts/gorev.py`, `Makefile`, `docs/dev-commands.md › Görev koşucusu`
- **Aksiyon:** `Makefile`/`justfile` (setup, run, test, lint, backup); Windows için `tasks.ps1` veya `just`.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-015] `.env.example` güncelliği/sürüklenme riski
- **Durum:** ✅ KAPANDI — **BUG #393 (11 Eyl 2026):** `.env.example` ↔ kod iki yönde zaten kapılı (`test_env_adi_kapisi`: her örnek anahtar okunuyor, her okunan anahtar belgeli). Sürüklenen şey anlatımdı: README "four providers", `.env.example` yorumu dört ad; kod 8 önek + 6 halkalı zincir. PROJE.md sağlayıcı listesi taşımıyor (ölçüldü). İki belgenin `LLM_PROVIDER` anlatımı düzeltildi ve `tests/test_saglayici_belgesi_kapisi.py` `SAGLAYICI_ONEKLERI`/`_ZINCIR_SIRASI` ile karşılaştırır (mutasyon: README'de tek harf → kırmızı). `Settings` şemasından türetme yapılmadı: env okumaları `Settings`'te toplanmış değil (BE-012 açık); kapı şemayı değil kaynağı ölçer, sonuç aynı.
- **Kanıt:** `.env.example` vs README (Groq/Cerebras/Gemini/OpenRouter) vs PROJE.md (gemini/anthropic/groq) — provider listesi tutarsız
- **Aksiyon:** `.env.example`'ı `Settings` (BE-012) şemasından türet/senkronla; tek doğruluk kaynağı.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-016] Frontend build çıktısı/deploy pipeline yok
- **Durum:** ✅ KAPANDI — ölçümle (14 Eyl 2026, BUG #494 turu): madde "build+artifact yok" diyordu; kullanılan dağıtım yolu `deploy/windows/guncelle.ps1` (BUG #353: kaynak damgası bayatsa `npm run build`, damga doğrulamalı) ve `frontend/dist`i sunan yol canlıda doğrulanıyor (`/api/meta` build damgası). CI'da build artifact'ı ⚪: statik dosyalar bu kurulumda konteynere değil Windows servisine dağıtılıyor; Docker imajı yalnız backend (Dockerfile). Ayrı statik host gerekirse o zaman açılır.
- **Kanıt:** `frontend/` (`npm run build` var, dağıtım yok)
- **Aksiyon:** CI'da build + artifact; backend `StaticFiles` ile serve veya ayrı statik host.
- **Etki:** Düşük · **Efor:** M

### [DEVOPS-017] Bağımlılık güncelleme otomasyonu yok (Dependabot/Renovate)
- **Durum:** ✅ KAPANDI — BUG #494 turu (14 Eyl 2026): `.github/dependabot.yml` — pip (haftalık, pazartesi), npm (`/frontend`, haftalık, minor+patch gruplu), github-actions (aylık). Güvenlik güncellemeleri Dependabot'un varsayılan güvenlik PR'larıyla; CI (pytest + vitest + kapılar) her PR'da koşar, ratchet'ler sürüm değişikliğini yakalar (ruff/eslint sürüm kilidi bilinçli: o iki paket için PR kapıyı kıracak ve `--yaz` ile yeniden ölçüm isteyecek — sürpriz değil, tasarım).
- **Kanıt:** repo (dependabot config yok)
- **Aksiyon:** Dependabot/Renovate (haftalık PR); güvenlik güncellemeleri otomatik.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-018] Ortam ayrımı yok (dev/prod config)
- **Durum:** ✅ KAPANDI — M85 R3 doğrulama: settings.py environment/is_production, compose ENVIRONMENT
- **Kanıt:** `os.getenv` dağınık (BE-012); DEBUG/prod ayrımı yok
- **Aksiyon:** `Settings.env` (dev/prod); CORS/docs/log-level/rate-limit ortama göre.
- **Etki:** Orta · **Efor:** S

### [DEVOPS-019] Git hijyen: `.env` diskte, runtime `data/` — sızma/temizlik denetimi
- **Durum:** ✅ KAPANDI — **BUG #384 (11 Eyl 2026):** `.env` geçmişte yok (SEC-018 ölçümü duruyor); eksik olan "otomatik" yarısıydı ve gitleaks değil, var olan `scripts/sir_taramasi`nin commit anında koşmasıydı — CI push'tan SONRA konuşur, o anda anahtar zaten uzakta ve geçmiştedir. `--staged` modu yalnız indeksi tarar (`git show :yol`), pre-commit'te gerçek kapı (`exit 1`, `|| true` yok). Hook bizzat sınandı: uydurma anahtarlı dosya stage'lenip commit denendi → engellendi. Kapı testleri geçici depoda dört durumu ölçer. Yan kazanım: dosyadaki beş `git` çağrısı tek yardımcıya indi, ruff S tavanı 62→60.
- **Kanıt:** `.gitignore` (data/ hariç tutulmuş — iyi); `.env` geçmiş commit kontrolü (SEC-018)
- **Aksiyon:** `git log --all -- .env` doğrula; gitleaks pre-commit; `.gitignore` düzenli denetim.
- **Etki:** Düşük · **Efor:** S

### [DEVOPS-020] Sürümleme/CHANGELOG/release süreci yok
- **Durum:** ✅ KAPANDI — BUG #476 (14 Eyl 2026). Ölçüldü: `CHANGELOG.md` VARDI (madde "yok" diyordu — bayat) ama 5 Ağustos'tan (0.2.0) beri dokunulmamıştı: arada 253 düzeltme (#223–#475), 333 commit; `APP_VERSION` 40 gündür 0.2.0, canlı `/api/meta` eski sürümü bildiriyordu; sürüm etiketi hiç yoktu (yalnız `pre-wave-*`). Mevcut kapı (`test_version_release.py`) yalnız "[APP_VERSION] başlığı var mı" diye bakıyordu — bayat günlük onu geçer. Yapılan: **0.3.0 yayın notu** (alanlara göre, her madde BUG numaralı, kırıcı değişiklikler + bilinen sınırlar), `APP_VERSION=0.3.0`, `docs/contributing.md › Sürüm çıkarma` (5 adım: not → sürüm → kapılar/CI → `git tag -a v<x.y.z>` → dağıt + `/api/meta` damgası), etiketler `v0.2.0` (0.2.0'ın ayarlandığı commit) ve `v0.3.0`. Bayatlama kapısı `tests/test_surum_notu_kapisi.py`: en üstteki yayın = APP_VERSION, sürüm/tarih sırası azalan, anılan her `#NNN` belgelerde gerçek, **defterdeki son BUG ya son sürüm notunda ya 'Yayınlanmamış'ta** (günlük defterden geride kalamaz), yayın adımları yazılı. API versiyonu (API-001) ile hizalama ⚪: `/api/v1/` ön eki ayrı karar, sözleşme dondurma (#306) o boşluğu bugün kapatıyor.
- **Kanıt:** `CHANGELOG.md`, `app/version.py`, `docs/contributing.md`, `git tag -l v*`
- **Aksiyon:** SemVer tag + CHANGELOG (BUG #NNN geçmişini toparla); API versiyonuyla (API-001) hizala.
- **Etki:** Düşük · **Efor:** S

---
**Kaynaklar:** GitHub Actions (Python+Node); ruff; pre-commit; pip-tools/uv lock; pip-audit/bandit/gitleaks; Dependabot; Docker multi-stage.
