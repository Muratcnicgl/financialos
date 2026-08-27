# API Referansı

## Dondurulmuş sözleşme — tek doğruluk kaynağı

**`docs/api-reference/api-sozlesmesi.json`** (BUG #306). Her handler için yol · metot ·
**kimlik doğrulaması** · parametreler · istek gövdesi şeması · yanıt kodları ve şemaları.
Koddan üretilir, git'te izlenir, `tests/test_api_sozlesmesi.py` ile kilitlenir.

```powershell
.\venv\Scripts\python.exe scripts/sozlesme_dondur.py             # yeniden üret
.\venv\Scripts\python.exe scripts/sozlesme_dondur.py --kontrol   # fark var mı (EXIT=1)
.\venv\Scripts\python.exe -m pytest tests/test_api_sozlesmesi.py # kapı
```

Kapı kırmızıya döndüyse API yüzeyini değiştirmişsindir. **Doğru tepki betiği koşturup
dosyayı yeşile boyamak değildir** — önce değişikliğin bilinçli olduğunu doğrula, gerekçesini
`docs/kalite-seruveni/uygulanan-fixler.md`'ye yaz, sonra yeniden dondur.

Ölçüm (27 Ağu 2026): **125 handler · 106 korumalı · 19 kimliksiz** (19'un tamamı meşru ve
`tests/test_api_sozlesmesi.py::KIMLIKSIZ_UCLAR` listesinde gerekçeleriyle sayılı).

## Canlı şema

- **Swagger UI:** `http://localhost:8000/docs` — **yalnız development.** Production'da
  `/docs`, `/redoc` ve `/openapi.json` üçü de KAPALI (SEC-015/M34, `app/main.py:151`).
- **OpenAPI JSON:** `http://localhost:8000/openapi.json` (development).

> **Düzeltme (BUG #306):** bu belge daha önce şema kaynağı olarak "repo kökü `openapi.json`"
> diyordu. O dosya `.gitignore:71` ile yok sayılıyor ve diskte hiç yoktu — yani belge, var
> olmayan bir dosyayı kaynak gösteriyordu (KURAL R3'ün "doküman da yalan söyler" sınıfı).
> Dondurulmuş sözleşme bu boşluğu kapatır: artık git'te izlenen, testle korunan bir dosya var.

## Ham OpenAPI neden tek başına yetmiyor

`app.openapi()` çıktısında **125 handler'ın 125'i kimliksiz görünür.** Auth
`OAuth2PasswordBearer`/`HTTPBearer` ile değil, `get_current_user(request: Request)` içinde
Authorization başlığı elle okunarak yapılıyor (`app/dependencies.py:50`) — FastAPI bunu
şemanın `security` alanına yazamaz. Bu yüzden dondurulmuş sözleşme kimlik bilgisini
rotanın **bağımlılık ağacından** çıkarır; yalnız OpenAPI'ye bakan bir kapı, korumanın
kalkmasını göremezdi.

## Ana Endpoint Grupları

| Prefix | Konu | Kimlik |
|--------|------|--------|
| `/api/auth` | register/login/refresh/logout/me/password-reset/oauth (ADR-033) | public/JWT |
| `/api/users/me` | KVKK sil/export | JWT |
| `/api/cockpit` | anlık finansal manzara | user |
| `/api/coach` | yapay zekâ koç (chat/history) | user |
| `/api/accounts` `/api/transactions` `/api/incomes` `/api/debts` | CRUD | user |
| `/api/checkpoints` | master checkpoint (is_system korumalı) | user |
| `/api/goals` `/api/cashflow` `/api/reports` `/api/debt-strategy` | analiz | user |
| `/api/prices/currency\|gold` | TCMB EVDS döviz/altın (M19) | public |
| `/api/health` | sağlık + auth_enabled | public |

Şema tek doğruluk kaynağı: `app/routers/*.py` → `api-sozlesmesi.json` (üretilmiş, izlenen).
