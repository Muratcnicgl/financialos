# ADR-026 — ZikZak (devreden bakiye) kararı: additive carry REDDEDİLDİ

**Tarih:** 6 Temmuz 2026
**Durum:** Kabul edildi
**Bağlam:** Kalite serüveni RULE-023 + kök vizyon (Sohbet B "Finansal Stratejist", 5-6 Şubat 2026). `rules_engine.py:731` `carried_forward = 0.0` hardcode; "geliştirilecek" notu naif additive açılışı ima ediyordu.

## Karar

**ZikZak'ı `today_target = daily_limit + carried_forward` şeklinde additive olarak AÇMIYORUZ.** Bu, çift-sayım (double counting) üretir ve kurucu vizyonun açıkça yasakladığı "Sanal Zenginlik" tuzağına yol açar.

Bunun yerine:
1. **Zikzak *etkisi* zaten mevcut ve doğru:** `daily_limit = reel_butce / days_remaining` **dinamik**. Bugün az harcanınca `reel_butce` korunur, `days_remaining` düşer → yarınki limit otomatik yükselir. Bütçe korunur, mid-month gelir/gider değişimine dayanıklı.
2. **`calculate_carried_forward` / `calculate_today_target` (additive) fonksiyonları güvensiz** — kullanılmamalı; deprecate edilecek (RULE-023).
3. **Kök vizyonun "harcama günü lump" hissi** (tek seferde splurge) ayrı ve doğru bir modelle karşılanacak: tek bütçe havuzundan türetilen **"harcama günü tavanı"** (`reel_butce − guard_floor × (kalan_gün−1)`) veya haftalık zikzak havuzu — additive carry ile DEĞİL. Bu ayrı bir tasarım adımıdır (bkz. "Sonraki adım").

## Gerekçe (teyitli)

### Matematiksel teyit (simülasyon)
Bütçe 8.276,14 TL / 24 gün. 3 nöbet günü (0 harcama) sonrası:
- **Dinamik ortalama (mevcut):** limit 344.84 → 359.83 → 376.19 → 394.10. Doğru, bütçe korunuyor.
- **Additive carry (naif):** Gün 8 `today_target = 394.10 + kümülatif_carry(1080.86) = 1474.96` — oysa sürdürülebilir günlük 394. **Çift-sayım.** Kullanıcı 1475/gün harcanabilir sanır → bütçe patlar (Sanal Zenginlik).

Çünkü her günün dinamik limiti önceki günlerin tasarrufunu ZATEN içeriyor; üstüne carry eklemek aynı parayı iki kez sayar.

### Davranışsal teyit (araştırma)
- **Mental accounting (Thaler):** açık "nöbet/harcama günü" çerçevelemesi öz-kontrolü artırır → zikzak *kavramı* değerli. [Thaler 1999]
- **YNAB (%75 retention):** pozitif bakiye devreder, **negatif (aşım) devretmez.** Mevcut `calculate_carried_forward` negatifi de devrediyor — kanıta aykırı. [YNAB rollovers]
- Dinamik ortalama slaka'yı tüm günlere ince yayar; kök vizyonun "tek seferde 705 splurge" lump'ını vermez → gerçek UX boşluğu, ayrı çözülecek.

## Sonuçlar

- `generate_cockpit`: `today_target = daily_limit` olarak kalır (additive carry yok); yanıltıcı "geliştirilecek" yorumu düzeltilir (ADR-026 atfı).
- RULE-023 yeniden sınıflandırıldı: "P0 zikzak öldü, aç" → "additive carry güvensiz; dinamik ortalama zaten zikzak; harcama-günü tavanı ayrı tasarlanacak."
- Kök vizyona sadakat KORUNUR: zikzak etkisi + gölge muhasebe + "sanal zenginlik yasağı" hepsi çalışıyor.

## Sonraki adım (ayrı, tasarım gerektiren)
"Harcama günü tavanı" (guard_floor tabanlı, tek-havuz, çift-saymayan) veya haftalık zikzak havuzu — kök vizyonun spending-day lump hissini güvenle verecek. Horizon (günlük rollover vs haftalık spending-day) kök vizyonda haftalığa yakın; implementasyonda numeric test + frontend/coach entegrasyonu ile yapılacak.

## Kaynaklar
- Thaler, R. (1999) "Mental Accounting Matters" — people.bath.ac.uk
- YNAB "Master Your Monthly Rollovers" — ynab.com/blog/master-your-monthly-rollovers
- Simülasyon: bu repoda doğrulandı (dinamik vs additive; çift-sayım gösterildi).
