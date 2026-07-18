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

## M86 (Wave-6) — 74 RAPOR TAM GÜNCELLİK DEĞERLENDİRMESİ
M77 yalnız banner + 2 bulgu örnekledi; **Wave-6 M86** 74 raporu 6 paralel subagent ile değerlendirdi
(her rapor için 2-3 kritik bulgu güncel koda karşı R3). Her rapora `M86 güncellik:` verdict damgası eklendi.

### Güncellik dağılımı (74 rapor)
| Verdict | Adet | Oran | Anlam |
|---|---|---|---|
| 🔴 BAYAT | 14 | %19 | Kontrol edilen bulguların çoğu düzeltilmiş |
| 🟡 KISMEN-BAYAT | 31 | %42 | Kritik bulgular kapatılmış, ikincil/UX açık |
| 🟢 GÜNCEL | 29 | %39 | Bulgular hâlâ büyük oranda geçerli |

**Örüntü:** 45/74 (%61) raporda en az bir bulgu düzeltilmiş — backlog stale-örüntüsüyle tutarlı. **Backend
engine/router raporları** çoğunlukla BAYAT/KISMEN-BAYAT (kritik bulgular bir BUG # ile kapatılmış: #062-#155 serisi;
W3-serisi parseTRNumber/todayLocalISO frontend doğruluk düzeltmeleri). **Frontend UX/a11y raporları** çoğunlukla
GÜNCEL (aria-label, modal Escape/focus-trap, 44px, index-key hâlâ açık — M85 ölçümüyle örtüşüyor).

### ⚠️ M86'da yakalanan CANLI bug (Wave-7 adayı)
- **SBN-001** (`sc__backfill_net_worth.md`): `_balance_at` hesap-tipsiz undo yapıyor → kredi/kart hesapları için
  geçmiş net-değer YANLIŞ hesaplanıyor. Script (runtime değil) ama net-worth trendi tarihsel veriyi bozar.
  Backfill script'i M73'te bir kez koşuldu (snapshot backfill) → geçmiş snapshot'larda latent hata olabilir.

## Tarihsel not (M77 dürüst sınırı — M86'da kapandı)
M77 "75 rapor madde-madde doğrulanmadı" diyordu; **M86 bu sınırı kapattı** — her rapor kritik-bulgu düzeyinde
R3 değerlendirildi + verdict damgalandı. Tam her-bulgu doğrulaması (yüzlerce bulgu) hâlâ yapılmadı ama rapor
düzeyinde güncellik artık ölçülü + işaretli (silent-stale tuzağı kapandı).
