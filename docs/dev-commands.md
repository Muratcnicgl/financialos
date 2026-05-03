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

pytest **kullanılmıyor**. Repo kökündeki `test_*.py` dosyaları bağımsız scriptlerdir — DB'yi sıfırlayıp gerçek senaryolarla çalışırlar:

```powershell
python test_coach.py                   # gerçek LLM çağrısı, .env'deki API key gerekli
python test_rules.py
python test_simulation.py
python test_action_executor.py
python test_fund_tracker.py
```

Tek bir test fonksiyonu çalıştırma kavramı yok — her dosya `__main__` gibi başından sonuna akar. Bir senaryoyu izole etmek için ilgili dosyayı düzenleyip alt bölümleri yorumlamak gerekir.

## .env Şeması

Repo kökünde, `.gitignore`'da:

```
LLM_PROVIDER=gemini          # gemini | anthropic | groq | fallback
GEMINI_API_KEY=...
GROQ_API_KEY=...             # fallback için opsiyonel
ANTHROPIC_API_KEY=...        # opsiyonel
LLM_MODEL=...                # opsiyonel, provider'ın default'unu ezer
DATABASE_URL=sqlite:///./data/financialos.db   # opsiyonel
```
