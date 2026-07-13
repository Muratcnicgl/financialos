# Frontend Anti-Pattern Denetimi (M28, 14 Tem 2026)

Wave-2 M2'de backend anti-pattern denetimi yapılmıştı; frontend hiç denetlenmemişti.
40 dosya (panels/ + components/ + hooks/) R3 ile tarandı. **OTONOM yorum (KURAL 12):**
20 ayrı per-file rapor yerine konsolide rapor (aynı kapsam, daha kullanışlı).

## Sonuç: TEMİZ (kritik anti-pattern yok)

| Kontrol | Bulgu | Durum |
|---------|-------|-------|
| **Doğrudan fetch/axios** (api.js dışı) | 0 | ✅ api.js disiplini korunmuş (frontend/PROJE.md) |
| **parseFloat kullanıcı-girişi** | 0 gerçek | Budget:124 + Goals:120 backend-değer coercion (progress_percent, monthly_amount) — user-input DEĞİL, W3-001 kapsamı dışı ✅ |
| **Dinamik Tailwind renk** (`text-${color}`) | safelist'li | ✅ W3-003 (tailwind.config safelist, dist doğrulandı) |
| **Async handler error** | çoğu try/catch | W3-005/007/008/009 (M9/M14) kritikleri kapattı ✅ |
| **TR sayı parse** | parseTRNumber | ✅ W3-001 (13 çağrı yeri) |
| **Tarih Z-suffix** | formatDate | ✅ (api.js normalize) |

## Küçük bulgular (düşük öncelik → Wave-4)
- **index-as-key (23):** `key={i}` bazı map'lerde — stale-DOM riski düşük (statik listeler). W3-016 (Wave-4).
- **useEffect eslint-disable (6):** bilinçli mount-only effect'ler (`check()`, `load()`). Yaygın kabul edilen pattern, bug değil.
- **a11y:** modal role/focus-trap (W3-018), dokunma-hedefi (W3-019) — Wave-4 backlog'da.

## Değerlendirme
Frontend mimari-disiplini sağlam: tek api.js katmanı, TR-locale parse (W3-001), safelist'li
renkler, kritik async error-handling (M9/M14). **Kritik/orta anti-pattern: 0** → otonom
milestone gerekmedi. Kalan küçük maddeler (index-key, a11y) Wave-4 düşük-öncelik.
