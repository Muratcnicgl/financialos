# Per-Dosya Denetim Güncellik İndeksi (M77, Wave-5 — 18 Tem 2026)

Rapor §B tespiti: `dosya-denetimi/` altındaki 75 per-dosya denetim raporunun **güncelliği bilinmiyordu**
— Wave-2/3'te alınmış bu anlık görüntülerdeki bulguların ne kadarı hâlâ geçerli, ne kadarı sessizce
düzeltilmiş? M77 bu belirsizliği işaretledi + örnekledi.

## Ne yapıldı
1. **75 raporun HEPSİNE güncellik banner'ı eklendi** — her rapor artık açıkça "tarihsel anlık görüntü,
   bulgular güncel koda karşı madde-madde doğrulanmadı, kullanmadan önce `file:line` DOĞRULA" diyor.
2. **Örneklem doğrulaması** (en kritik rapor `rules_engine.md`) güncel koda karşı yapıldı.

## Örneklem ölçümü — derin denetim katmanı da BAYAT
`rules_engine.md` raporunun grep-doğrulanabilir ölü-kod bulguları:

| Bulgu | İddia (Wave-2/3) | M77 güncel kod | Sonuç |
|---|---|---|---|
| RE-001 | `evaluate_credit_card_strategy` çağrılmıyor (ölü kod) | `rules_engine.py:2098` cockpit'e bağlı ("ölü koddu; artık bağlı") | ✅ DÜZELTİLMİŞ |
| RE-002 | quick-entry (`parse_gg_command`) bir endpoint'e bağlı değil | `transactions.py:_parse_quick_text` + `quick_text` alanı router'a bağlı | ✅ DÜZELTİLMİŞ (farklı implementasyon) |

**Örneklem: 2/2 bulgu düzeltilmiş.** M76'daki RULE %42 stale oranıyla birlikte, hem backlog (`sections/`)
hem derin denetim (`dosya-denetimi/`) katmanlarının **önemli oranda bayat** olduğu iki bağımsız örnekle
doğrulandı.

## DÜRÜST SINIR
- 75 raporun tamamı madde-madde YENİDEN doğrulanMADI (yalnız 1 rapordan 2 bulgu örneklendi).
- Banner "bulgu geçersiz" DEMİYOR — "doğrulanmadı, kullanmadan önce kontrol et" diyor. Bazı bulgular
  (özellikle Wave-4 sonrası dosyalar: workspace, auth) hâlâ geçerli olabilir.
- Tam boyut-bazlı yeniden doğrulama Wave-6 işi (her rapor bir subagent turu, ~75 tur).

## Neden tam doğrulama yapılmadı (KURAL 12 dürüstlüğü)
75 raporun her bulgusunu güncel koda karşı doğrulamak ~75 bağımsız denetim turu = devasa. M77'nin
amacı **güncelliği İŞARETLEMEK + ölçmek** (belirsizliği gidermek), her bulguyu kapatmak değil. Silent-stale
tuzağı artık kapalı: her rapor okuyucuyu "önce doğrula" diye uyarıyor + git/ledger'a yönlendiriyor.
