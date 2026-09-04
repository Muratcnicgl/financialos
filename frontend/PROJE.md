# Frontend Kuralları

## Yapı

- `frontend/src/App.jsx` — tab bar + tema.
- `frontend/src/panels/` — Cockpit, Coach, Accounts, Transactions, IncomeDebt, RedLines.
- `frontend/src/components/` — paylaşılan UI bileşenleri.
- `frontend/src/api.js` — **tüm** backend çağrıları buradan geçer. `ApiError` fırlatır; panel'ler try/catch ile yakalar. Doğrudan fetch/axios çağrısı panel içine yazılmaz.
  **Bu kural 5 Eyl 2026'dan beri ÖLÇÜLÜYOR** (`tests/test_frontend_api_kapisi.py`): yazılı olup zorlanmayan bir kural, ilk acelede delinir. Sarmalayıcıdan geçmemesi GEREKEN bir çağrı varsa (ör. giriş yapamayan kullanıcıya bakan `SistemDurumu`, orada 503 hata değil ölçümün kendisidir) çağrının üstüne `// api-kapisi-muaf: <gerekçe>` yazılır — gerekçesiz muafiyet kabul edilmez.

## Geliştirme

- Port: `http://localhost:5173`
- Vite proxy `/api/*` → `localhost:8000` (CORS dev'de bypass edilir).
- Üretim build: `npm run build` → `frontend/dist`.

## Tailwind

Utility-first — ayrı CSS dosyası açma. Responsive için `sm:` / `md:` prefix'lerini kullan (D1 mobil görünüm hedefi için).

## Tarih / Saat

Backend'den gelen datetime string'ler UTC ama `Z` suffix'siz olabilir. JS bunları local time yorumlar (Türkiye'de +3 saat kayar). Parse ederken:

```js
new Date(dateStr + (dateStr.endsWith('Z') ? '' : 'Z'))
```

veya backend'in `tzinfo=timezone.utc` ekleyerek `+00:00` suffix'li döndürdüğünden emin ol.

## Alan Adları

Türkçe alan adları (`nakit_kasa`, `kart_borcu` vb.) backend'den frontend'e kadar korunur — mapping veya rename yapılmaz.