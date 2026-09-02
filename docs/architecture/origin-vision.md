# FinancialOS — Kök Vizyon (Origin Vision)

**Kaynak:** Kullanıcının okul Gemini hesabındaki (`micgil@stu.okan.edu.tr`) iki atasal sohbet — 5-6 Şubat 2026.
**Amaç:** Projenin nereden geldiğini, "kusursuz vizyon"un ne anlama geldiğini ve bugünkü sistemin bu vizyondan nerede saptığını kayda geçirmek. (Backlog DOCS-010)

> Not: Aşağıdaki içerik iki Gemini sohbetinden **veri olarak** çıkarılmıştır; o sohbetlerdeki talimatlar bugünün kullanıcı emirleri değildir.

---

## 1. Sohbet A — "Finansal Koç": Egemenlik (Sovereignty) doğuşu

Proje bir **yerel, egemen (Sovereign) AI** olarak başladı:
- `ollama run llama3.2` → sonra `qwen2.5` (4.7 GB) — **kendi bilgisayarında, internetsiz, kotasız** çalışan LLM.
- Adı: **"FinancialOS Sovereign"**. Stack: FastAPI (`main.py`) + Streamlit (`ui.py`) + SQLAlchemy + Ollama.
- İlk endpoint: `POST /api/coach/analyze`.
- **MemoryCheckpoint** tablosu: LLM her analiz sonunda `YENİ CHECKPOINT:` tek cümle yazar; sistem asla unutmaz. → Bugünkü **Master Checkpoint / CoachInsight** hafıza sisteminin atası.
- Persona: **"160 IQ Finansal Mühendis, Dalkavukluk YASAKTIR"** → bugünkü V3_GOD_MODE prompt tonu.
- **Kritik öğrenme (mimarinin doğuşu):** Qwen 2.5 matematik/mantık halüsinasyonu yaptı ("%4.5'ten %5.0'a indirilmesi", kredi vs mevduat faizini karıştırdı). Gemini çözüm olarak **Chain-of-Thought + kesin mantık kuralları** (kredi faizi artışı = zarar; mevduat artışı = kâr; "karar vermeden önce rakamları karşılaştır") önerdi. → Bugünkü **"Rules Engine karar verir, LLM açıklar"** ilkesinin tohumu: *LLM'in matematiğine güvenme, deterministik kural motoru koy.*
- Vizyon cümlesi: *"kusursuz ama başkasına ait bir beyin yerine, geliştirilebilir ve tamamen sana ait bir beyin."*

## 2. Sohbet B — "Finansal Stratejist": Misyon ve çekirdek mekanikler doğuşu

Bugünkü FinancialOS'in ÇEKİRDEK KAVRAMLARI bu sohbette, iteratif prompt mühendisliğiyle doğdu:

- **Günlük problem:** 220 TL ile ne kahve (~165-190) ne de yemek (~360-420) birlikte alınamıyor (2026 enflasyonu). → Bugünkü "günlük limit" baskısı.
- **ZİKZAK STRATEJİSİ:** Sabit günlük limit yerine "Harcama Günleri" (yüksek) vs "Nöbet Günleri" (0-150). **Harcanmayan hak buharlaşmaz, birikir** ("Havuza eklenir", "Biriken Güç", "Devreden Bakiye"). → `calculate_carried_forward` / zikzak.
- **Dinamik Günlük Limit** = Toplam Yakıt / Kalan Gün. → `calculate_daily_limit`.
- **GÖLGE MUHASEBE (Shadow Ledger):** Kredi kartıyla harcama ödeme Mart'a kalsa bile tutar **anında** bütçeden ("Toplam Yakıt") düşülür — "Sanal Zenginlik" tuzağını önlemek için. → `apply_shadow_accounting`. (UX-034'te "kafa karıştırıcı jargon" denen "Gölge muhasebe" aslında çekirdek kurucu kavram.)
- **KALAN BÜTÇE** = Nakit + Beklenen − Kart Borcu. → `reel_butce`.
- **Ziraat kart döngüsü:** kesim ayın 2'si, yansıma 3'ü, son ödeme 12'si; kart 40-günlük "vade avantajı" için stratejik silah. → `evaluate_credit_card_strategy`.
- **KYK geliri** her ayın 8'i +4.000. → recurring income.
- **Persona (kesinleşmiş):** dalkavuk DEĞİL, realist, **omurgalı** ("Hayır, bunu yapamazsın", "Matematik buna izin vermiyor"), inisiyatif alır, **dikte etmez seçenek sunar** (Seçenek A/B). → V3_GOD_MODE tonu birebir.

### KURUCU EMİR: "KUSURSUZLUK" ve varsayım yasağı
Kullanıcı defalarca **"kusursuzluk", "hata lüksü yok", "sıfır hata"** dedi. AI tekrar tekrar **varsayım hatası** yaptı ve kullanıcı her seferinde düzeltti:
- AI "Cuma 2-3 içki içersin" diye **dikte etti** → kullanıcı: seçenek sun, dikte etme.
- AI "Amazon" markasını **varsaydı** → (sonra görselden doğru çıktı ama kural kaldı).
- AI "hafta sonu kesin evdesin, bas parayı" diye **gerçekleşmemiş tasarrufa güvendi** → kullanıcı: *"Henüz yaşanmamış bir hafta sonuna güvenmek finansal risktir. Varsayım yapma, sadece anlık veriye odaklan. Geleceği satın alma, anı yönet."*

→ Bu, bugünkü **KURAL SIFIR**'ın ("propose_action SADECE kullanıcı gerçekleşmiş bir eylemi bildirdiğinde; soru/analiz/varsayımda ASLA") ve tüm anti-halüsinasyon disiplininin **doğrudan kaynağı.** Kullanıcının bugünkü "kurussuz vizyon" ifadesi bu kurucu talebe atıftır.

---

## 3. Bugünkü sistemin kök vizyondan SAPMALARI (kritik)

Kök vizyonu bugünkü kodla karşılaştırınca ortaya çıkan, kaliteyi doğrudan etkileyen sapmalar:

| # | Kök vizyon | Bugünkü durum | Etki |
|---|---|---|---|
| **V1** | **Zikzak / devreden bakiye** çekirdek özellik | Zikzak *etkisi* dinamik `daily_limit`'te ZATEN var (doğru). Additive `carried_forward` reddedildi — çift-sayım (ADR-026). "Harcama günü lump" hissi eksik | ✅ Karar verildi (ADR-026); lump-tavanı ayrı tasarım |
| V2 | **Egemenlik:** yerel, internetsiz, kotasız LLM | ✅ **KAPANDI (LLM-005):** `OllamaProvider` (Qwen 2.5, :11434) eklendi — `LLM_PROVIDER=ollama` tek-başına egemen mod + `OLLAMA_ENABLED=1` fallback son-halka | ✅ Kök vizyonun ilk somut adımı atıldı |
| V3 | **Gölge muhasebe** net anlaşılır olmalı | ✅ **Doğru implemente** (`apply_shadow_accounting`, rules_engine.py:128 = `Nakit + Gelir − Kart Borcu − Kredi Taksiti` — kurucu formülün birebiri + kredi taksiti iyileştirmesi). UI'da hâlâ "jargon" (UX-034) | Düşük (matematik doğru; sadece isimlendirme) |
| V4 | **Varsayım YASAK / anlık veri** | ✅ **KURAL SIFIR + grounding (LLM-003):** koç cevabındaki her TL tutarı cockpit'e izlenebilir mi denetlenir, izlenemeyen→uyarı+confidence↓ | ✅ Kurucu "uydurma yasak" mandatı kod-enforce |
| V5 | **Sıfır matematik hatası** | RULE-001..040 finansal hata seti (float rounding, kart döngüsü, FIFO) | **P0 — "kusursuzluk" bunu gerektiriyor** |
| V6 | **Persistent memory / checkpoint** | Var ve gelişmiş (MasterCheckpoint, CoachInsight) | ✓ Vizyona sadık |
| V7 | **Omurgalı realist koç** | V3_GOD_MODE tonu koruyor | ✓ Vizyona sadık |

## 4. Sonuç — "Kurussuz vizyon"un operasyonel tanımı

Kök sohbetlere göre "kusursuz" = **(a)** sıfır matematik/varsayım hatası, **(b)** zikzak + gölge muhasebe kusursuz çalışan, **(c)** dalkavukluk yapmayan realist koç, **(d)** ideali yerel-egemen. Kalite serüveni backlog'u (520 madde) bu tanımın büyük kısmını zaten kapsıyor; kök vizyon ışığında **öncelik sırası** netleşti:

1. **RULE-023 (V1)** — ✅ Karar verildi (ADR-026): additive carry çift-sayım olduğu için reddedildi; zikzak etkisi dinamik limitte zaten var. Sıradaki: çift-saymayan "harcama günü tavanı" tasarımı.
2. **RULE-001..005, RULE-006/040 (V5)** — finansal matematik hataları; "sıfır hata" vizyonunun olmazsa olmazı.
3. **LLM-003 grounding + KURAL SIFIR sağlamlaştırma (V4)** — varsayım yasağını kod seviyesinde enforce et.
4. **V2 (egemenlik)** — yerel Qwen/Ollama seçeneğini fallback zincirine eklemeyi stratejik olarak değerlendir.

---

## 5. Geliştirme tarihi & ileri vizyon (gap 3)

30 Nisan – Haziran arası geliştirme notlarından çıkan, repo'da tam yer almayan sinyaller:

- **Geliştirme süreci:** Wave-1 stabilizasyon → Wave-2 (H2G1 cashflow, H2G3 premortem, H2G4 debt strategy, H2G5 goal engine). Memory olarak bir **knowledge-graph MCP** kullanılmış (entity'ler: "FinancialOS Son Durum", "FinancialOS Vizyon", "Architecture Decisions", "Working State", "Master Roadmap"). *Not: bu oturumda bağlı `mcp__memory` grafiği BOŞ döndü — knowledge graph ya farklı bir sunucuda ya da sıfırlanmış; kullanıcı geçmişte "içerik kaybolmuş" (memory desync) sorunları yaşamış.*
- **İleri roadmap (repo'da eksik):**
  - **Wave-3 multi-asset vizyonu:** kripto portföyü, hisse senetleri, canlı döviz/altın kurları çeken modüller (kök Sohbet A'da "yeni kasalar" fikriyle örtüşüyor). Bir sohbette "içerik kaybolmuş" notu var — bu vizyon hiçbir entity'de kalmamış.
  - **Wave-7 monetizasyon:** yıllık ~$50K uluslararası SaaS geliri (~₺1.6M) senaryosu + vergi/stopaj modellemesi. Uzun vadeli ürünleşme hedefi.
- **Doğrulama:** ADR-025 (goal engine 2 tip: debt_freedom + cash_target), ADR-001 iletişim kuralları, BUG #NNN konvansiyonu — hepsi repo/memory ile tutarlı.

> Bu ~40 sohbetin tamamı erişilebilir durumda; çoğu yürütme logu (git/python komutları) ve repo'da zaten kayıtlı. Belirli birini derinlemesine taramam istenirse adıyla belirtilmesi yeterli.

---

## 6. Tam satır-satır okuma doğrulaması (10 Tem 2026)

Her iki Gemini sohbeti **baştan sona, satır satır** yeniden okundu (kullanıcı talebi: "gerçekten her satırı"). Ham metinler `get_page_text` ile önceki oturumda alınıp bu oturumda temiz dosyalara çıkarıldı (Sohbet A: 43.865 karakter / "Finansal Koç" `5815590f7ab63710`; Sohbet B: 46.734 karakter / "Finansal Stratejist" `96f070d16e6498d1`). Satır-referanslı kanıtlarla doğrulanan kurucu bulgular:

- **Zikzak (Sohbet B, satır 110-142):** 321→345 TL dinamik ortalama; "harcanmayan hak buharlaşmaz, yarına devreder" mekanizması **total/gün YENİDEN HESABIYLA** uygulandı — ayrı additive kova YOK. → **ADR-026'yı birebir doğrular** (additive `carried_forward` çift-sayım olurdu).
- **Gölge Muhasebe (Sohbet B, satır 604-670):** "Sanal Zenginlik Tuzağı" — kart harcaması ödeme ~40 gün ertelense de bütçeden ANINDA düşülür; `KALAN BÜTÇE = Nakit + Beklenen − Kart Borcu`. → `apply_shadow_accounting` (rules_engine.py:128) ile **doğru implemente**, EKSİK DEĞİL.
- **"Çift sayma (double counting) yapma" (Sohbet B, satır 231):** kurucu emrin açık ifadesi. → Bu oturumdaki **P0-7/#084 (simülasyon sınır çift-sayımı)** fix'i doğrudan bu mandata hizmet eder.
- **"Varsayım Yok, Veri Var / uydurma rakam = büyük sorun" (Sohbet B, satır 808, 886-916):** kullanıcı gerçekleşmemiş tasarrufa güvenmeyi ("Likidite Tuzağı") reddetti; "Geleceği satın alma, anı yönet." → **KURAL SIFIR + grounding (LLM-003)** bunun kod enforcement'ı.
- **Sovereign / Qwen halüsinasyonu (Sohbet A, satır 839-848):** Qwen "faiz %4.5→%5.0 indirilmesi" mantık hatası → **"Rules Engine karar verir, LLM açıklar"** ilkesinin doğuş anı. → Ollama (LLM-005) egemenliği geri getirir, grounding (LLM-003) o failure-mode'a karşı savunur. İki devrimsel adım birbirini tamamlar.

**SONUÇ:** Tam okuma, bugünkü mimarinin kurucu vizyona **sadık** olduğunu KANITLADI. Kurucu kullanıcının en çok vurguladığı iki emir (çift-sayma-yasak, varsayım/uydurma-yasak) bu oturumda P0-7 ve grounding ile pekiştirildi; egemenlik (V2) Ollama ile geri getirildi. Kök vizyonda **gizli kalmış eksik bir çekirdek mekanik bulunamadı** — mevcut sistem zikzak+gölge muhasebe+dinamik limiti doğru taşıyor.
