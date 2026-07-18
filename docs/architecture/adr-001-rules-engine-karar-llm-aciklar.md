# ADR-001 — Rules Engine karar verir, LLM açıklar

**Tarih:** (kök karar, 2026 başı) · **Durum:** Kabul edildi (temel mimari ilke) · **Kaynak:** `docs/architecture/origin-vision.md` (Gemini kök sohbetleri)

## Bağlam
Ata sürümde (yerel Qwen 2.5) LLM matematik/mantık halüsinasyonu yaptı — kredi vs mevduat faizini karıştırdı, "%4.5→%5.0 indirimi" gibi yanlış çıkarımlar. Finansal bir sistemde LLM'in aritmetiğine güvenmek kabul edilemez.

## Karar
**Tüm sayısal/finansal kararlar deterministik kural motorunda (`app/rules_engine.py` + `debt_strategy.py` + `goal_engine.py` + `cashflow.py`) verilir. LLM (koç) yalnızca kural motorunun ürettiği `cockpit` dict'ini bağlam alır ve AÇIKLAR — hesap yapmaz, karar vermez.** Akış her zaman: kural motoru hesaplar → koç açıklar → aksiyon için `propose_action → onay → execute`.

Enforcement: Master Checkpoint kod seviyesinde (`action_executor.py`), grounding kontrolü (`grounding.py` — koçun her TL'si cockpit'te izlenebilir olmalı), KURAL SIFIR (propose yalnız gerçekleşmiş eylemde).

## Sonuç
- Sağlayıcı-bağımsız güvenilirlik (koç Gemini/Groq/Ollama fark etmez, matematik aynı).
- "LLM'e soralım öğrensin" tembelliği **YASAK**. Yeni özellikte ilk soru: "bu deterministik olabilir mi?"
- **İSİMLENDİRME:** Bu ilkenin gayri-resmi kişi-ismi kullanımı kod/docstring/commit'te **YASAKLANMIŞTIR**; isimsiz form ("ADR-001" / "Rules Engine karar verir, LLM açıklar" / "algoritma karar verir, kullanıcı seçer, AI açıklar") kullanılır.

## İstisna — LLM-çıkarım (dil işleme) katmanı (M75, R3 ile belgelendi)

"LLM hesap yapmaz, karar vermez" ifadesi **finansal/sayısal kararlar** içindir. Sistemde LLM'in
**doğal-dil çıkarımı** yaptığı meşru bir katman vardır ve bu ilkeyi İHLAL ETMEZ:

- **`app/coach_insights.py:extract_explicit_red_line_k2`** — kullanıcının geçmiş mesajlarından ima edilen
  davranışsal "kırmızı çizgileri" (red line) LLM ile çıkarır ve `CoachInsight` olarak yazar. Bu bir **dil
  sınıflandırma/özetleme** işidir (kullanıcının kendi ifadelerini insight'a dönüştürür) — **para hesaplamaz,
  finansal eylem kararı vermez, DB'ye finansal veri yazmaz.** Ürettiği insight yalnız koça bağlam olur;
  yine tüm sayısal kararlar rules_engine'de kalır.

**Sınır kuralı:** LLM yalnız (a) cockpit'i açıklama ve (b) kullanıcı ifadelerinden dil-düzeyi çıkarım
(insight/red-line) yapabilir. **Aritmetik, bakiye, strateji, hedef ilerlemesi = HER ZAMAN kural motoru.**
`app/rules_engine.py`'de LLM çağrısı YOKTUR (R3 grep ile kanıtlı) — çekirdek saf.

## Durum notu (M75)
- **ADR-028** ("koç fiilen tek-sağlayıcı") ADR-034 ile SUPERSEDED (dosyada işaretli).
- `rules_engine.py` LLM-çağrısız (kanıtlı); dil-çıkarım istisnası yukarıda sınırlandı.
