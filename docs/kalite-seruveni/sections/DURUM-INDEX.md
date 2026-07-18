# Backlog Durum İndeksi (M76, Wave-5 — 18 Tem 2026)

Rapor §B (tam-proje-durum-raporu) tespiti: `sections/` 521 maddenin **DURUM alanı yoktu** →
neyin açık neyin sessizce kapandığı bilinmiyordu ("gerçek stale oranı KANIT YOK"). M76 bunu kapattı.

## Ne yapıldı
1. **521 maddenin HEPSİNE açık `- **Durum:**` alanı eklendi** (greplenebilir). Kaynak: inline `✅` işareti.
   - Başlangıç: 50 madde inline `✅ KAPANDI`, 471 madde işaretsiz (`🔲 AÇIK — kod-doğrulaması bekliyor`).
2. **En kritik boyut RULE (40 madde) tam kod-doğrulaması** yapıldı (bağımsız subagent, her madde güncel
   koda karşı R3 ile kontrol edildi — kanıt satırı + fonksiyon adı takip edildi).

## RULE boyutu — GERÇEK STALE ORANI ÖLÇÜLDÜ
26 işaretsiz RULE maddesinin doğrulaması:

| Sonuç | Adet | Anlam |
|---|---|---|
| ✅ KAPANDI | **11** | Sessizce düzeltilmiş, backlog güncellenmemiş (gerçek stale) |
| 🟡 KISMEN | 3 | Kısmen düzeltildi / bağlam değişti |
| 🔲 AÇIK | 12 | Sorun hâlâ kodda mevcut |

**Gerçek stale oranı (RULE): 11/26 = %42** — işaretsiz maddelerin neredeyse yarısı zaten düzeltilmişti.
Bu, raporun "backlog bayat, güvenilmez" şüphesini SOMUT doğruladı. RULE toplamı: 40 madde → 24 kapalı
(13 inline + 11 doğrulanmış), 3 kısmen, 12 açık.

### RULE'da sessizce kapanmış (11) — çoğu ADR-030 Decimal göçü + BUG fix'leri
RULE-003/004 (BUG #147/#148/#150 kart tarih mantığı), RULE-005 (R3 doğru davranış), RULE-006/035/039/040
(ADR-030 Decimal), RULE-021/024 (test eklendi), RULE-026 (belgelenmiş MC ayrımı), RULE-034 (BUG #132).

### RULE'da HÂLÂ AÇIK (12) — Wave-6 adayları
RULE-007 (FIFO lot yok), RULE-012 (korunum eşiği), RULE-013 (yeni-borç maskeleme), RULE-022 (detect_alerts
testsiz), RULE-025 (tie-break yok), RULE-027 (shadow guard yok), RULE-028 (negatif limit guard yok),
RULE-031 (invariant testi yok), RULE-032 (extra_monthly=0 kötümser), RULE-036 (gün-numarası karşılaştırma),
RULE-037 (sıfır-tutar yutma), RULE-038 (magic number + işaret maskesi).
### RULE'da KISMEN (3)
RULE-029 (datetime karışımı default yolda), RULE-030 (kredi kartı döngüsü kapsam dışı), RULE-033 (banker's rounding).

## Diğer 17 boyut (445 madde) — M85'te TAM DOĞRULANDI (Wave-6)
Wave-5 M76 yalnız alan ekledi; **Wave-6 M85** kalan 17 boyutun 445 `🔲 AÇIK` maddesini 7 paralel subagent ile
madde-madde güncel koda karşı R3 doğruladı. Artık her DURUM alanı `M85 R3 doğrulama:` + kod-kanıtı taşıyor.

### GERÇEK STALE ORANI ÖLÇÜLDÜ (445 madde)
| Sonuç | Adet | Oran |
|---|---|---|
| ✅ KAPANDI (sessizce düzeltilmiş) | **78** | %18 — gerçek stale |
| 🟡 KISMEN (kısmi ilerleme) | 76 | %17 |
| ⏸️ KAPSAM DIŞI (kripto/deploy/PostgreSQL/mobil/PWA) | 17 | %4 |
| ⚪ DEFEKT-DEĞİL | 1 | — |
| 🔲 hâlâ AÇIK | 273 | %61 |

**Yorum:** Non-RULE backlog'ta **%18 sessizce düzeltilmiş + %17 kısmi = %35'i yanlış "açık" etiketliydi** (RULE %42
ile aynı örüntü — backlog bayatlığı iki bağımsız ölçümle doğrulandı). Ama çoğunluk (%61) GERÇEKTEN açık:
büyük oranda **mimari refactor** (god-module bölme BE-001/003/004/LLM-015, service/repository katmanı, config
merkezileştirme), **altyapı** (OTel/Prometheus/Sentry OBS-003/004/012, lint/mypy/gitleaks DEVOPS-002/007/012,
CHECK-constraint DATA-009), ve **yapılmamış özellikler** (FEAT-* çoğu). Bunlar iç-sağlamlaştırmanın gerçek borcu.

### Boyut-bazlı öne çıkanlar
- **En olgun (çok KAPANDI):** TEST (23/35 kapandı — Wave-5/6 test işi gerçek), RESIL (9/20).
- **En ham (çoğu açık):** OBS (19 açık — observability altyapısı yok), PERF (14), UX (35 açık — UX katmanı büyük borç), FEAT (yapılmamış özellikler).
- **En stale (yanlış-açık):** DOCS (5 kapandı — ADR seti/README güncellenmişti), RESIL (BE-010 logging işi backlog'a yansımamıştı).

## Metodoloji notu (gelecek için)
Bir madde düzeltildiğinde: inline başlığa `✅ UYGULANDI (BUG #NNN)` + `- **Durum:**` satırını güncelle.
Böylece backlog bir daha sessizce bayatlamaz (bu boşluğun kök nedeni buydu).
