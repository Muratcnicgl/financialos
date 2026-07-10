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

1. **LLM'in matematiğine ASLA güvenme** → deterministik motor. (Bugün Rules Engine var; grounding kontrolü ekle → LLM-003.)
2. **Varsayım = hata.** Anlık veri, teyit önce. (KURAL SIFIR var; kod-seviyesi enforce + grounding eksik.)
3. **Çift sayma yasak.** (ADR-026 uyguladı; float çift-yuvarlama kaldı.)
4. **Kırılgan çıktı formatı** tekrar eden bela → structured output'a geç (regex postprocess'i emekliye ayır).
5. **Sanal zenginlik yasak** → gölge muhasebe (var; sağlamlaştır).
6. **Omurgalı/realist ton** koru; dalkavukluğa kayma.
7. **Egemenlik** kök ideal → yerel LLM seçeneği stratejik değerlendir (V2).

> Bu dersler, per-file kod denetiminin ve devrimsel geliştirme adımlarının **filtresi**: her değişiklik bu 7 meta-derse hizmet etmeli.
