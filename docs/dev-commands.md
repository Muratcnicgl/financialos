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
LLM_PROVIDER=gemini          # gemini | anthropic | groq | fallback
GEMINI_API_KEY=...
GROQ_API_KEY=...             # fallback için opsiyonel
ANTHROPIC_API_KEY=...        # opsiyonel
LLM_MODEL=...                # opsiyonel, provider'ın default'unu ezer
DATABASE_URL=sqlite:///./data/financialos.db   # opsiyonel
```
