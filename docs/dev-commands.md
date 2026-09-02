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

## Koç Kalite Ölçümü (eval)

```powershell
.\venv\Scripts\python.exe -m scripts.eval_runner              # DAVRANIŞ seti (KURAL SIFIR, üslup, format)
.\venv\Scripts\python.exe -m scripts.eval_runner --altin      # ALTIN set G1-G6: koçun MUHAKEMESİ
.\venv\Scripts\python.exe -m scripts.eval_runner --altin --kaydet
.\venv\Scripts\python.exe -m scripts.eval_runner --gecmis     # geçmiş koşumlar (set sütunuyla)
```

**İki set AYNI ŞEYİ ÖLÇMEZ ve oranları kıyaslanmaz.** Davranış seti koçun düzgün KONUŞUP
konuşmadığını, altın set İŞİ yapıp yapmadığını ölçer (1 Eyl 2026'nın gerçek manzarası,
`scripts/coach_altin.py`). Kayıtlar `set` etiketiyle ayrılır; düşüş raporu yalnız aynı seti
karşılaştırır. Ayrıntı: `docs/kalite-seruveni/masterprompt-koc.md` §9.1.

Ücretsiz Gemini katmanı **dakikada 10 istek** verir; altı senaryoluk altın koşum sınıra
değip zincirde bir sonraki sağlayıcıya düşebilir — o koşum sağlayıcı-başına ölçüm SAYILMAZ.

## Stopaj / Getiri Eşiği (Wave-K, G4)

Koç artık vergi aritmetiği YAPMAZ; kural motoru hesaplar, koç okur (`app/vergi.py` +
`rules_engine.calculate_getiri_esigi` → cockpit `getiri_esigi`).

**Eşik oran:** borcun en pahalı kaleminin aylık faizi. Parayı oraya koymak risksiz ve
vergisiz o kadar kazandırır; hiçbir yatırım eşiği geçmiyorsa tartışma biter.
`gereken_brut_yillik` bunun tersidir: bir mevduatın eşiği geçmesi için vermesi gereken
brüt yıllık oran (aylık %4,75 borç → **brüt yıllık %68,49**).

Stopaj oranları mevzuatla değişir. Kod dağıtmadan güncellemek için:

```powershell
$env:STOPAJ_TRY_MEVDUAT_6AY = "20"        # TL vadeli mevduat, <= 6 ay
$env:STOPAJ_TRY_PARA_PIYASASI_FONU = "20"
$env:STOPAJ_TAZELIK_GUN = "180"          # bu gunden eskiyse cikti `bayat=True` gelir
```

**Kaynağı olmayan oran UYDURULMAZ:** bilinmeyen ürün ya da sınır dışı vade `None` döner
(6 aylık dilimin oranı 2 yıllık mevduata uygulanmaz). Bozuk bir override sessizce %0'a
düşmez — düşseydi ürün vergisiz getiri vaat ederdi. Oran `STOPAJ_YURURLUK` tarihinden
`STOPAJ_TAZELIK_GUN` gün sonra **bayat** işaretlenir; hesap durmaz ama koç kullanıcıya
teyit gerektiğini söyler.

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
DATABASE_URL=sqlite:///./data/financialos.db   # opsiyonel

# MODEL SEÇİMİ (BUG #313 — model adı SAĞLAYICIYA aittir, zincire değil)
# Öncelik: <ÖNEK>_MODEL  >  (yalnız LLM_PROVIDER o sağlayıcıyı adlandırdığında) LLM_MODEL
#          >  sağlayıcının kendi DEFAULT_MODEL'i
GEMINI_MODEL=...             # opsiyonel (default: gemini-2.5-flash-lite)
ANTHROPIC_MODEL=...          # opsiyonel (default: claude-opus-4-8)
GROQ_MODEL=...               # opsiyonel (default: openai/gpt-oss-120b)
CEREBRAS_MODEL=...           # opsiyonel (default: gpt-oss-120b)
OPENROUTER_MODEL=...         # opsiyonel (default: meta-llama/llama-3.3-70b-instruct:free)
TOGETHER_MODEL=...           # opsiyonel
DEEPINFRA_MODEL=...          # opsiyonel
LLM_MODEL=...                # opsiyonel — YALNIZ LLM_PROVIDER tek bir sağlayıcıyı
                             # adlandırdığında uygulanır. `LLM_PROVIDER=fallback` iken
                             # HİÇBİR sağlayıcıya uygulanmaz: heterojen bir zincir tek
                             # model adını paylaşamaz (Anthropic'e Gemini model adı
                             # gidiyordu — BUG #313). Zincirde bir halkayı sabitlemek
                             # için o halkanın kendi <ÖNEK>_MODEL'ini yaz.

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
