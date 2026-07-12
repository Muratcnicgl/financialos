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
