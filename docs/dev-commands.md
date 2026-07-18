# Geliştirme Komutları

## Backend

Python venv kökte, çalışma dizini repo kökü:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.setup_data           # DB'yi sıfırlar + Murat'ın gerçek Mayıs 2026 verilerini yükler
uvicorn app.main:app --reload --port 8000
```

Health: `http://localhost:8000/` veya `/api/health` · Swagger: `/docs`

## Frontend

Ayrı terminal:

```powershell
cd frontend
npm install
npm run dev                            # http://localhost:5173, /api -> :8000 proxy
npm run build                          # üretim build'i frontend/dist
```

## Test Scriptleri

**GÜNCEL (M87, Wave-6):** Aşağıdaki eski not artık YANLIŞ. `tests/` olgun bir **pytest** süiti (1150+ test,
in-memory SQLite + FakeProvider + hypothesis + Playwright e2e). Ana komut: `.\venv\Scripts\python.exe -m pytest tests/ -q`.
Kök `test_*.py` scriptleri tarihsel/manuel araçlardır (pytest `testpaths=["tests"]` ile toplanmaz). Aşağısı o eski manuel scriptlerin tarihsel notudur:

```powershell
python test_coach.py                   # gerçek LLM çağrısı, .env'deki API key gerekli
python test_rules.py
python test_simulation.py
python test_action_executor.py
python test_fund_tracker.py
```

Tek bir test fonksiyonu çalıştırma kavramı yok — her dosya `__main__` gibi başından sonuna akar. Bir senaryoyu izole etmek için ilgili dosyayı düzenleyip alt bölümleri yorumlamak gerekir.

## Yedekleme

SQLite DB'sini elle yedekle (online backup — aktif bağlantıları kesmez):

```powershell
python -m scripts.backup                  # data/backups/YYYY-MM-DD-HHMM.db
python -m scripts.backup --keep-days 7    # 7 günden eski yedekleri sil
```

Otomatik günlük yedek (Windows Görev Zamanlayıcı — tek seferlik kurulum):

```powershell
schtasks /create /tn "FinancialOS Backup" /tr "powershell -Command 'cd C:\Users\18155\PycharmProjects\financialos; .\venv\Scripts\python.exe -m scripts.backup'" /sc daily /st 03:00
```

Yedekler `data/backups/` altında, 30 günden eskisi otomatik silinir.

## .env Şeması

Repo kökünde, `.gitignore`'da:

```
LLM_PROVIDER=gemini          # gemini | anthropic | groq | ollama | fallback
GEMINI_API_KEY=...
GROQ_API_KEY=...             # fallback için opsiyonel
ANTHROPIC_API_KEY=...        # opsiyonel
LLM_MODEL=...                # opsiyonel, provider'ın default'unu ezer
DATABASE_URL=sqlite:///./data/financialos.db   # opsiyonel

# Ollama (YEREL/EGEMEN — offline, veri makineden çıkmaz; LLM-005)
OLLAMA_ENABLED=1             # fallback zincirine yerel Ollama'yı SON halka ekler
OLLAMA_BASE_URL=http://localhost:11434/v1   # opsiyonel (default budur)
OLLAMA_MODEL=qwen2.5:7b-instruct            # opsiyonel (default budur)
OLLAMA_TIMEOUT=120           # opsiyonel, yerel model yavaşsa artır
```

**Egemen/offline mod:** `LLM_PROVIDER=ollama` → koç tamamen yerel çalışır (internet
gerekmez). Önce `ollama pull qwen2.5:7b-instruct` + `ollama serve`. Bulut sağlayıcı
kullanıp yalnızca hepsi düşünce yerel yedek isteniyorsa `LLM_PROVIDER=fallback` +
`OLLAMA_ENABLED=1` yeterli (Ollama zincirin son halkası olur).

## Commit-Öncesi Test Kapısı (W3-058)

Gizli regresyonları önlemek için (BUG #061 dersi) git pre-commit hook'u:

```bash
bash scripts/install-hooks.sh      # tek sefer: core.hooksPath=.githooks
```

Staged dosyalara göre ilgili süiti koşar: `app/`·`tests/`·`scripts/`·`alembic/` `.py` → pytest
(`-x` ilk hatada durur); `frontend/src/*.jsx` → vitest. Kırmızıysa commit engellenir.
Bilinçli atlama (WIP): `git commit --no-verify`.
