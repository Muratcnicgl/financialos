# API Referansı

FastAPI otomatik dökümanı (development):
- **Swagger UI:** `http://localhost:8000/docs` (production'da kapalı — SEC-015/M34)
- **OpenAPI şeması:** `http://localhost:8000/openapi.json` (dev) veya repo kökü `openapi.json`

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
| `/api/prices/currency|gold` | TCMB EVDS döviz/altın (M19) | public |
| `/api/health` | sağlık + auth_enabled | public |

Şema tek doğruluk kaynağı: `app/routers/*.py` + `openapi.json`.
