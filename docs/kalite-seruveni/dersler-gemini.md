# Gemini Kök Sohbetlerinden Dersler (tüm hatalar → ders)

**Kaynak:** İki Gemini kök sohbeti tam metin (get_page_text ile satır satır okundu). Amaç: kurucu vizyonun özü olan "tüm hatalardan ders çıkar" — her AI hatasını bugünkü mimariyle eşleştir, çözüldü mü / boşluk mu belirle.

## Sohbet A — "Finansal Koç" (yerel LLM denemeleri)

| # | Tarihsel hata | Ders | Bugünkü durum |
|---|---|---|---|
| A1 | Llama 3.2 bozuk Türkçe ("garantik", "réussen") | Küçük yerel model TR'de yetersiz | Bulut LLM + FallbackProvider ile aşıldı (ama egemenlik vizyonundan sapma — origin-vision V2) |
| A2 | Llama/Qwen: "faiz %4.5'ten %5.0'a **indirilmesi** daha verimli" — hem yön (indirmek≠çıkmak) hem kredi/mevduat karıştırıldı | **LLM matematiğe güvenilmez** | ✅ Kurucu ders: **Rules Engine karar verir, LLM açıklar.** Matematik `rules_engine.py`'de. Ama LLM çıktı grounding kontrolü hâlâ yok (LLM-003 — boşluk) |
| A3 | Qwen 2.5 aynı mantık hatasını tekrarladı | Model büyütmek mantığı düzeltmez; **kural/CoT gerekir** | ✅ V3_GOD_MODE prompt + Rules Engine. Ama prompt-tabanlı guardrail'lar kod seviyesine tam taşınmadı (LLM-023) |
| A4 | Checkpoint sistemi ("YENİ CHECKPOINT:" tek cümle, asla unutma) | **Kalıcı hafıza** çekirdek | ✅ MasterCheckpoint + CoachInsight ile gelişmiş |

## Sohbet B — "Finansal Stratejist" (vizyon/prompt iterasyonu) — EN ÖNEMLİ

| # | Tarihsel hata | Ders (kullanıcının kendi sözleriyle) | Bugünkü durum |
|---|---|---|---|
| B1 | AI "Cuma 2-3 içki içersin" diye **senaryo dikte etti** | "Koç parayı nerede harcayacağına karar vermemeli, **seçenek sunmalı**" | Kısmi — V3 prompt seçenek sunuyor ama enforce edilmiyor (öneri) |
| B2 | AI "Amazon" markasını **varsaydı** (sonra görselden doğru çıktı) | Veri olmadan **varsayma** | ✅ KURAL SIFIR (propose sadece bildirilen eylemde). Ama is_question kenar durumları (LLM-010/BE-027 — boşluk) |
| B3 | AI **gerçekleşmemiş hafta sonu tasarrufuna güvendi** ("bas parayı") | **"Geleceği satın alma, anı yönet. Varsayım yok, veri var."** | ✅ KURAL SIFIR'ın DOĞRUDAN kaynağı. **Ama:** grounding kontrolü olmadığı için LLM hâlâ cockpit-dışı sayı uydurabilir (LLM-003 — kritik boşluk) |
| B4 | **Tablo formatı bozuldu** ("Geçer plam", "SUC aat Kart", "lan Gün") | Çıktı formatı **kırılgan** | ⚠️ Bugün de aynı sınıf: postprocess regex cehennemi (BE-028/LLM-020). Structured output ile kökten çözülmeli (LLM-009/020) |
| B5 | "Sanal Zenginlik" tuzağı: kartla harca ama bütçeden düşme | **Gölge Muhasebe** — kart borcu anında bütçeden düşülür | ✅ `apply_shadow_accounting`. Ama negatif/aşırı değerde korumasız (RULE-027 — boşluk) |
| B6 | "**Çift sayma (double counting) YAPMA**" | Aynı parayı iki kez sayma | ✅ Kurucu kural. **Doğrulandı:** ADR-026 zikzak additive carry'yi tam bu gerekçeyle reddetti. Ama float rounding çift-yuvarlama hâlâ var (RULE-006/035, BUG #007) |
| B7 | Dinamik günlük limit = Toplam Yakıt / Kalan Gün; tasarruf yarına devreder | ZikZak | ✅ Dinamik limit çalışıyor (ADR-026); "harcama günü lump" hissi eksik (tasarım adımı) |
| B8 | Kart döngüsü (kesim 2, ödeme 12) "vade avantajı" silahı | Kart stratejik araç | ✅ `evaluate_credit_card_strategy` — ama RULE-003/004/005 döngü hataları (boşluk) |
| B9 | Persona: dalkavuk DEĞİL, omurgalı, "Matematik buna izin vermiyor", "Hayır yapamazsın" | Realist koç | ✅ V3_GOD_MODE tonu birebir. Llama yumuşak ifadeleri görmezden geliyor → prompt sertliği korunmalı (TEST-025) |
| B10 | Kullanıcı defalarca "**kusursuzluk, sıfır hata, hata lüksü yok**" | Sıfır-hata standardı | Bu, "kurussuz vizyon"un tanımı. RULE-001..040 finansal hatalar bu standardın karşısında açık borç |

## Meta-ders (her iki sohbet)

1. **LLM'in matematiğine ASLA güvenme** → deterministik motor. ✅ Rules Engine + **grounding kontrolü eklendi (LLM-003/#083)** + koç context sayıları grounding-tutarlı (#110 + invariant).
2. **Varsayım = hata.** Anlık veri, teyit önce. ✅ KURAL SIFIR + **gelecek/niyet baskılama (#095)** + uçtan-uca contract harness kilidi.
3. **Çift sayma yasak.** ✅ ADR-026 (zikzak) + **sim sınır çift-sayım (#084)** + beklenen-gelir çift-sayım (#086). (float çift-yuvarlama izleme.)
4. **Kırılgan çıktı formatı** → structured output. Yeniden değerlendirildi: NL koç için regex postprocess UYGUN (artık iyi test edilmiş: #085 + contract harness). Structured output muhtemelen gereksiz.
5. **Sanal zenginlik yasak** → gölge muhasebe. ✅ `apply_shadow_accounting` doğrulandı (golden test) + zikzak "yarınki limit" görünür.
6. **Omurgalı/realist ton** koru; dalkavukluğa kayma. ✅ V3 tonu korundu.
7. **Egemenlik** kök ideal → yerel LLM. ✅ **Ollama sovereign provider (LLM-005)** eklendi.

### Bu turda eklenen meta-dersler (yürütme deneyimi)
8. **Kendi kodunu da ADVERSARIAL denetle.** Birim testler entegrasyon regresyonunu kaçırır: bu turda kendi #085 fix'im analiz raporunu bozuyordu (yalnız-birim testler kaçırdı, per-file ajan yakaladı); kendi #110 grounding-yanlış-pozitifimi ise öz-denetim ajanı yakaladı. **Ders: her büyük değişiklikten sonra bağımsız adversarial öz-denetim + entegrasyon/invariant testi.**
9. **Katman-arası değişiklik katman-arası doğrulama ister.** tzinfo sweep (#092) backend datetime'ı `+00:00` yaptı; frontend parse'ı (`new Date`, `+ 'Z'` DEĞİL) bozmadığı TEYİT edildi — değiştiren, tükettiği tarafı da doğrulamalı.
10. **Araştır → önceliklendir → en kaliteli yol.** Yapılabilir ≠ yapılmalı: structured output yapılabilirdi ama NL koç için yanlış; feature-creep yerine kurucu boşlukları (Borç Çığı, zikzak projeksiyon, aylık trend) kapatıldı.
11. **Uzun-ömürlü dış API endpoint'ine kör güvenme — pytest yeşil ≠ canlı çalışıyor.** 14 Tem 2026: TCMB EVDS'yi ~Nisan 2026'da v2'den v3'e taşımış (`evds2.tcmb.gov.tr/service/evds/` → `evds3.tcmb.gov.tr/igmevdsms-dis`), biz M19'da fark etmedik; kod eski v2 URL'ini çağırıyordu, 405/SPA-HTML dönüyordu. Bulgu gecikti çünkü pytest **mock** kullanıyordu (URL fixture'da tanımlıydı, gerçek HTTP call yapılmadı) → süit yeşildi ama endpoint ölüydü. **Ders:** her dış API entegrasyonu için (a) canlı smoke test (gerçek endpoint'e curl, cevap format+status doğrula), (b) `canli-smoke-testleri.md` kaydı, (c) haftalık scheduler job (`weekly_smoke_test_job`) başarısızlıkta MCP'ye `SMOKE_FAIL:<api>` yazar. Aynı ders Wave-4 CANLI-DOGRULAMA-GATE kuralının doğuşu: her milestone bitiminde mock değil gerçek doğrulama.

> Bu dersler, per-file kod denetiminin ve geliştirme adımlarının **filtresi**: her değişiklik bu meta-derslere hizmet etmeli. Kurucu boşlukların büyük kısmı 11 Tem 2026 turunda kapatıldı (süit 162→291).
