# Backlog Durum İndeksi (M76, Wave-5 — 18 Tem 2026)

> ## ⚠️ BU İNDEKS 48 GÜN BAYATLADI — 5 Eylül 2026'da DENETLENDİ
>
> **Bulgu: indeks, kendi AYRINTI dosyasından geride.** `sections/RULE.md` içinde **13 yerde
> `M83` notu** var; bu indekste `M83` kelimesi **hiç geçmiyor**. Sonuç: aşağıdaki
> *"RULE'da HÂLÂ AÇIK (12)"* listesi bugün **yanlıştır** ve ona güvenen biri **zaten
> kapanmış maddeler üzerinde çalışırdı**.
>
> **Bugün ölçülen (kaynak: `sections/RULE.md`'nin `- **Durum:**` satırları):**
>
> | | M76'da (bu belge) | 5 Eyl 2026 |
> |---|---|---|
> | RULE ✅ kapandı | 24 | **30** |
> | RULE 🟡 kısmen | 3 | 4 |
> | RULE ⚪ defekt-değil | — | 6 |
> | **RULE 🔲 açık** | **12** | **0** |
>
> **M83 (Wave-6) beşini kapattı ve TEST'le kilitledi** — `tests/test_rule_acik_maddeler_m83.py`,
> 12 test, bugün koşuldu ve **12/12 geçiyor**: RULE-022 (`detect_alerts` kapsaması) ·
> RULE-025 (deterministik tie-break) · RULE-031 (para-korunum invariantı) · RULE-038
> (adlandırılmış eşik) · RULE-033 (`ROUND_HALF_UP`). Bunların **dördü** bu belgenin
> "HÂLÂ AÇIK" listesinde duruyor.
>
> **Kalan 🟡 (4):** RULE-007 · RULE-012 · RULE-029 · RULE-030.
>
> **İRONİ KAYDA GEÇSİN:** bu belgenin son bölümü *"bir madde düzeltildiğinde Durum satırını
> güncelle, böylece backlog bir daha sessizce bayatlamaz"* diye bitiyor. Önlem **tuttu** —
> ama yalnız ayrıntı dosyasında. **Kimse indeksi güncellemedi.** Bir özet, özetlediği şeyden
> bağımsız bayatlayabilir; ve özet daha çok okunduğu için zararı daha büyüktür.
> **Ders: türetilmiş bir belge elle güncelleniyorsa, türetildiği şeyden bağımsız bir yalan
> kaynağıdır.** Doğru çözüm bu sayıları elle yazmak değil, `sections/*.md`'den ÜRETMEK
> (`scripts/vitrin_uret.py`'nin ölçümden üretme ilkesi — henüz uygulanmadı, açık iş).
>
> Aşağıdaki gövde **18 Temmuz 2026'nın tarihsel kaydıdır**; sayıları o günü anlatır.

Rapor §B (tam-proje-durum-raporu) tespiti: `sections/` 521 maddenin **DURUM alanı yoktu** →
neyin açık neyin sessizce kapandığı bilinmiyordu ("gerçek stale oranı KANIT YOK"). M76 bunu kapattı.

## Bugünkü sayılar — ÜRETİLİYOR, elle yazılmıyor (BUG #348)

Aşağıdaki blok `sections/*.md`'nin **kendisinden** üretilir; elle düzenlenmez.
Güncellemek için: `python scripts/backlog_ozeti.py --yaz`.
Güncelliğini `tests/test_backlog_tutarliligi_kapisi.py` doğrular — yani bu tablo
bir daha sessizce bayatlayamaz (L74'ün mekanizma karşılığı).

<!-- OTOMATIK-BACKLOG-OZETI:BASLA — elle düzenleme; `python scripts/backlog_ozeti.py --yaz` -->

**Üretildi:** `scripts/backlog_ozeti.py` · **Toplam madde:** 521

| Boyut | ⏸ kapsam dışı | ⚪ defekt değil | ⛔ yapılmayacak | ✅ kapandı | 🔲 açık | 🟡 kısmen | toplam |
|---|---|---|---|---|---|---|---|
| A11Y | 2 | 0 | 0 | 2 | 8 | 8 | 20 |
| API | 1 | 0 | 0 | 3 | 11 | 5 | 20 |
| BE | 0 | 0 | 0 | 10 | 23 | 7 | 40 |
| DATA | 0 | 0 | 0 | 8 | 18 | 9 | 35 |
| DEVOPS | 0 | 0 | 0 | 10 | 7 | 3 | 20 |
| DOCS | 0 | 0 | 0 | 8 | 4 | 3 | 15 |
| DVIZ | 0 | 0 | 0 | 1 | 12 | 2 | 15 |
| FE | 0 | 0 | 0 | 8 | 25 | 2 | 35 |
| FEAT | 0 | 0 | 0 | 22 | 17 | 2 | 41 |
| LLM | 0 | 0 | 0 | 16 | 20 | 4 | 40 |
| MOB | 6 | 0 | 2 | 5 | 12 | 0 | 25 |
| OBS | 0 | 0 | 0 | 7 | 12 | 6 | 25 |
| PERF | 0 | 0 | 0 | 5 | 13 | 2 | 20 |
| RESIL | 1 | 0 | 0 | 12 | 2 | 5 | 20 |
| RULE | 0 | 6 | 0 | 30 | 0 | 4 | 40 |
| SEC | 1 | 1 | 0 | 15 | 6 | 12 | 35 |
| TEST | 0 | 0 | 0 | 28 | 2 | 5 | 35 |
| UX | 0 | 0 | 0 | 2 | 31 | 7 | 40 |
| **TOPLAM** | **11** | **7** | **2** | **192** | **223** | **86** | **521** |

<!-- OTOMATIK-BACKLOG-OZETI:BITTI -->

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
*(⚠️ 5 Eyl 2026: bu başlık ARTIK DOĞRU DEĞİL — dördü M83'te kapandı, bkz. yukarıdaki denetim notu.
Liste 18 Tem 2026 kaydı olarak duruyor; bugünkü doğru kaynak `sections/RULE.md`.)*
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
