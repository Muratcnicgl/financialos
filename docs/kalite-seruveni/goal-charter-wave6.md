# Goal Charter — WAVE-6: İÇ SAĞLAMLAŞTIRMA

**Tarih:** 2026-07-18 · **Rollback tag:** `pre-wave-6` (004394f)
**Baseline:** `docs/kalite-seruveni/tam-proje-durum-raporu.md` + `goal-charter-wave6-iskelet.md`
**Giriş durumu:** Wave-5 kapanışı · 1124 backend + 63 vitest + 2 e2e · coverage %90 · `AUTH_ENABLED=true` · tek user (id=1 = muraticgil@gmail.com)

---

## ÜRÜN-DNA (Murat, 18 Tem 2026) — TARTIŞMA YOK
- Wave-6 = **İÇ SAĞLAMLAŞTIRMA.** Yeni kullanıcı-görünür özellik YOK.
- **KAPSAM DIŞI, AÇMA:** kripto · VPS/deploy · PostgreSQL · mobil. Hepsi ayrı karar bekliyor.
- Kaynak: raporun kanıtladığı açık borçlar + Wave-5 iskeletindeki 7 aday.
- Yeni özellik olmadığı için **KULLANIM-GATE devre dışı**; canlı-doğrulama-gate + test geçerli.

## DEĞİŞMEZ KURALLAR
Wave-2/3/4/5 charter'ları tam metin geçerli. KURAL 1/3/12, K10, D1, R3, W1-W8, ADR-001, ADR-013,
OTONOM KARAR + SELF-CORRECTION. Her milestone: **canlı-doğrulama-gate → tag → push → MCP → milestone-log.**
Charter Revize açık (ürün-DNA hariç) = tag `charter-revise-w6-<N>` + MCP. Tıkanıklıkta OTONOM KARAR.
asistan arayuzu'a "ne yapayım" YASAK.

> ⚠️ **ERKEN-TAMAM YASAĞI:** "TAMAM" demeden önce TÜM agent'lar bitmiş + tam süit tek seferde koşulmuş olacak
> (Wave-5'te erken-TAMAM hatası oldu, self-correction ile düzeldi — bu sefer baştan doğru).

---

# BLOK A — RULE MOTORU (M82-M84) [EN ÖNCELİKLİ]

**Blok gerekçesi:** İskelet aday #1 — RULE'da 12 açık madde. rules_engine ADR-001'in kalbi. M83: RULE %42 stale
(M76 ölçümü) — hangi 12 madde gerçekten açık, R3 ile ayıkla.

### M82 — action_type tek-kaynak borcu
- **Gerekçe:** İskelet aday #2. BUG #161 kaçağı `action_type` string'lerinin 3 yere (coach tool enum + propose_action
  valid_types + execute dispatcher) dağılmış olmasından geldi (M68 dersi).
- **Çıktı:** action_type string'leri kaç yere dağılmış (grep), tek enum/sabit kaynağa topla, drift testini kilitle
  (yeni action_type eklenince 3 nokta senkron değilse test kırılsın).
- **D1:** 2-3 referans (event-type registry deseni).
- **Gate:** canlı-doğrulama-gate → tag `milestone-82-action-type-single-source`.

### M83 — 12 açık RULE maddesi
- **Gerekçe:** M76 RULE'da 12 AÇIK + 3 KISMEN madde kod-doğruladı (`sections/DURUM-INDEX.md`).
- **Çıktı:** Önce R3: 12 maddenin kaçının gerçekten açık olduğunu diskten doğrula (bayat olabilir). Gerçekten açık
  olanları kapat: her biri kural + test + rules_engine entegrasyonu.
- **Gate:** canlı-doğrulama-gate → tag `milestone-83-rule-acik-maddeler`.

### M84 — rules_engine kapsama tamamlama
- **Gerekçe:** Wave-5 M71 workspace yolunu test etti; bu iş-mantığı dallarını bitirir.
- **Çıktı:** stopaj / kırmızı-çizgi / util-guard / hayatta-kalma dallarından test edilmeyen kalmasın.
- **Gate:** canlı-doğrulama-gate → tag `milestone-84-rules-engine-kapsama`.

---

# BLOK B — BACKLOG + DENETİM TAM-DOĞRULAMA (M85-M86)

**Blok gerekçesi:** İskelet aday — Wave-5 M76/M77 DURUM alanı ekledi ama tam doğrulama yapmadı.

### M85 — 521 backlog tam R3 doğrulama
- **Gerekçe:** M76 alan ekledi (17 boyut madde-madde doğrulanmadı, `🔲 AÇIK` = belirsiz).
- **Çıktı:** Her maddenin DURUM'unu commit/tag/test ile TEK TEK doğrula. Bu içeriği kanıtlar. Gerçek
  kapalı/açık/geçersiz oranını kesinleştir.
- **Gate:** canlı-doğrulama-gate → tag `milestone-85-backlog-tam-dogrulama`.

### M86 — 75 denetim raporu tam güncellik
- **Gerekçe:** M77 banner ekledi (1 rapordan 2 bulgu örneklendi, tam doğrulanmadı).
- **Çıktı:** `dosya-denetimi/` her raporu mevcut kodla karşılaştır, bayat olanı işaretle/yenile.
- **Gate:** canlı-doğrulama-gate → tag `milestone-86-denetim-tam-guncellik`.

---

# BLOK C — KANIT + KALİTE KAPANIŞI (M87-M89)

### M87 — kalan KANIT YOK + tutarsızlıklar
- **Gerekçe:** Wave-5 M78 25 tanesini kapattı; kalanlar var.
- **Çıktı:** Raporda kalan her "KANIT YOK" / çelişkiyi kapat.
- **Gate:** canlı-doğrulama-gate → tag `milestone-87-kanit-tutarsizlik-kapanis`.

### M88 — coverage %90 → %92 + mutasyon örneği
- **Gerekçe:** Coverage satır sayabilir; testler gerçekten yakalıyor mu?
- **Çıktı:** En kritik 3 modülde (rules_engine, coach, workspace_deps) mutation testing örneği: testler gerçekten
  yakalıyor mu yoksa satır mı sayıyor. Coverage %90 → %92.
- **D1:** 2-3 referans.
- **Gate:** canlı-doğrulama-gate → tag `milestone-88-coverage-92-mutasyon`.

### M89 — ADR tutarlılık turu
- **Gerekçe:** Wave-5'te 21 ADR materyalize edildi.
- **Çıktı:** Hepsi mevcut kodla tutarlı mı (superseded zincirleri, çelişen kararlar). ADR-index güncel mi.
- **Gate:** canlı-doğrulama-gate → tag `milestone-89-adr-tutarlilik-turu`.

---

# BLOK D — KAPANIŞ (M90-M91)

### M90 — tam süit + performans smoke
- **Çıktı:** 1124+ test tek seferde, flaky var mı (3 kez koşur), en yavaş 10 test. API p95 yanıt smoke.
- **Gate:** canlı-doğrulama-gate → tag `milestone-90-suit-performans-smoke`.

### M91 — kapanış + Wave-7 iskeleti
- **Çıktı:** `tam-proje-durum-raporu` güncelle (fark bölümü). PROJE.md güncelle. Wave-7 için Murat'a NET
  ürün-DNA soruları (kripto/VPS/Postgres/mobil — hâlâ bekleyenler). MCP: GOAL TAMAM W6 + W1 rotasyonu
  (Working State observation sayısı kural sınırında mı).
- **Gate:** canlı-doğrulama-gate → tag `milestone-91-wave6-kapanis`.

---

## BİTİRME
M91 sonunda **DUR.** "GOAL TAMAM WAVE-6" + kapanış raporu (kazanç / açık / borç / kendi iddialarınla çelişen
kaç şey). **M92+ AÇMA, kapsam-dışı bloklara geçme.**

## BAŞLA
`pre-wave-6` tag + charter dosyası. Sonra M82.
