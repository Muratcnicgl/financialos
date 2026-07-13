# TR Number Locale Denetimi (M31, 14 Tem 2026)

Wave-3 M6/W3-001'de "1000× veri bozulması" bug'ı (`parseFloat(x.replace(',','.'))` →
"1.234,56"=1.234). R3 ile tüm frontend TR-locale parse/format tarandı.

## Sonuç: TR locale DOĞRU işleniyor

| Kullanım | Sayı | Durum |
|----------|------|-------|
| **parseTRNumber** (text-input parse) | 20 | ✅ W3-001, "1.234,56"→1234.56 (US "1,234.56" de tolere) |
| **formatTL/Suffix** (display) | 19 dosya | ✅ Intl tr-TR (nokta binlik, virgül ondalık) |
| **Number()** (kullanıcı girişi) | DebtStrategy rate/term/amount/slider | ✅ hepsi `<input type="number/range">` → tarayıcı "." ondalık verir, Number() DOĞRU |
| **parseFloat** (raw) | Budget:124, Goals:120 | ✅ backend-değer coercion (progress_percent/monthly_amount), user-input DEĞİL |

## Edge-case test kapsamı (W3-001, api.test.js)
- `"1.234,56"` (TR) → 1234.56 · `"1,234.56"` (US) → 1234.56 · `"1234.56"` → 1234.56 ·
  `"1.234"` (TR binlik) → 1234 · `"1.5"` (ondalık) → 1.5 · `"₺ 1.234,56"` → 1234.56 · geçersiz→NaN.
- Hepsi geçiyor (6 vitest).

## Küçük (düşük öncelik → Wave-4)
- 3 raw `toLocaleString('tr-TR')`/`Intl.NumberFormat` (HorizonsModal, PremortemModal,
  DebtStrategy) — **doğru TR çıktı** ama merkezi `formatTL` helper'ını bypass eder
  (tutarlılık). Refactor Wave-4 (risk/fayda düşük, çıktı zaten doğru).

## Değerlendirme
**Kritik/orta TR-locale bug: 0.** parseTRNumber (text) + Number (number-input) + formatTL
(display) tutarlı. Edge-case'ler testli. Otonom milestone gerekmedi.
