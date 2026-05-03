# Wave-2 Yol Haritası

MVP tamam (3 May 2026). Wave-2 tek hedef: sistemden **gerçek finansal değer** üretmek — mühendislik egzersizi değil, hayat problemi çözmek (kart %99.8 dolu, 5 kredi, 13 dağınık alacak, günlük limit 62 TL).

## Hafta 1 — 3-9 May: Gerçek Kullanım

- Yeni büyük özellik **yok**. Sistem her gün canlı kullanılır, koça gerçek olaylar yazılır.
- Mikro-düzeltmeler serbest: 5-10 dakikalık form/buton/etiket dokunuşları kullanırken anında halledilir, biriktirilmez.
- Çıkan eksiklikler/sürtünmeler not edilir → Hafta 2 backlog'una akar.

## Hafta 2 — 10-16 May: Tema A (Otomasyon)

- A1 — Akıllı hatırlatma: maaş günü, kart son ödeme, alacak (Efe vb.) tarihleri yaklaştığında koç proaktif olur.
- A2 — Recurring işlemler: maaş, kira, fatura, abonelik için propose_action otomatik tetiklenir, kullanıcı onaylar.
- A3 — Aylık özet rapor: gelir/gider/net değişim + kategori dağılımı + önceki aya trend.

## Hafta 3 — 17-23 May: Tema D (QoL)

- D1 öncelikli — Mobil görünüm (telefondan kullanım için Tailwind responsive ayarı).
- D3 — Yedekleme: SQLite dosyasına günlük otomatik backup script'i.
- (D2 hızlı işlem formu, D4 kategori istatistiği — süre kalırsa)

## Hafta 4 — 24-31 May: Tema B (Görselleştirme)

~3 hafta veri biriktikten sonra anlamlı: gelir/gider grafiği, net değer trendi, alacak takvimi, fon performansı. recharts zaten kurulu.

## Wave-3 Backlog

- C1 — Anthropic Claude'a geçiş: **sadece** günde 50+ koç çağrısı yapıp Gemini/Groq fallback'in kalite farkını gerçek hissedersen mantıklı. Şu an Gemini Flash-Lite + Groq fallback + MALFORMED_FUNCTION_CALL handling yeterli.
- C2 — Genişletilmiş bağlam (son 30 günlük işlem geçmişi koça): 1 ay veri biriktikten sonra anlamlı.
- C3 — Çok turlu konuşma: kafa karıştırırsa öncelik kazanır, aksi halde mevcut yapı yeter.

## Karar Disiplini

- "Daha ne ekleyim" sorusu yasak; "Sistem hangi gerçek hayat sürtünmesini çözüyor" sorusu serbest.
- Tema dışı büyük özellik fikri çıkarsa Wave-3 backlog'una yazılır, anında kodlanmaz.
