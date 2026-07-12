# ADR-027 — Koç raporu için "structured output" REDDEDİLDİ (regex-postprocess korunur)

**Tarih:** 11 Temmuz 2026
**Durum:** Kabul edildi (karar: yapma)
**Bağlam:** Kalite serüveni backlog LLM-009/020; dersler-gemini B4 ("kırılgan çıktı formatı").

## Karar

Koçun serbest-metin analiz raporunu **structured output** (LLM'in JSON/şema alanları
döndürüp bizim render etmemiz) ile DEĞİŞTİRMİYORUZ. Mevcut **hedefli regex-postprocess**
(`_postprocess_report`) katmanı korunur.

## Gerekçe (araştırma sonrası)

Dersler B4 "tablo formatı bozuldu / kırılgan çıktı" gözlemi structured output'u akla getiriyor.
Ancak koçun bu özel yapısına bakınca trade-off yanlış:

1. **Postprocess'in kapsamı dar ve davranışsaldır, biçimsel değil.** `_postprocess_report`
   yalnız 3 EDGE davranışı temizler: sahte-tamamlama (KURAL SIFIR ihlali), halüsinasyon YENİ
   CHECKPOINT bölümü, emanet-0 bölümü. Bunlar LLM'in YANLIŞ DAVRANIŞIdır — çıktı FORMATI değil.
   Structured output bunları doğal olarak çözmez (sahte-tamamlama, format değil eylem-iddiası sorunudur).

2. **Koçun ASIL DEĞERİ konuşma-dilidir.** Kurucu vizyon (Gemini B9): "omurgalı, realist,
   'Matematik buna izin vermiyor' diyen" bir SOHBET. Rapor 5-bölümlü ama içi doğal dil +
   Seçenek A/B/C. Şema alanlarına hapsetmek bu tonu ve esnekliği öldürür.

3. **Mevcut yaklaşım artık iyi test edilmiş.** #085 + #085-iter2 + davranış-sözleşmesi harness
   (`test_coach_behavior_contract.py`) postprocess davranışını uçtan-uca kilitliyor. "Kırılgan"
   olan şey artık regresyon-korumalı.

4. **Deterministik veri ZATEN yapısal.** Sayılar cockpit'ten gelir (Rules Engine), grounding
   ile doğrulanır (#083/#110 + invariant). Yani "LLM sayı uydursun ama şema zorlasın" ihtiyacı
   grounding + prompt "sen HESAPLAMA, AKTAR" (#112) ile zaten karşılanıyor.

## Sonuç

Dersler B4'ün doğru çözümü structured output DEĞİL; **contract harness + grounding + hedefli
postprocess** üçlüsüdür (hepsi mevcut). Structured output bu koç için net negatif trade-off.

## Alternatifler / geri dönüş koşulu

Eğer ileride koç ÇOK-TURLU, araç-zincirli (tool-chain) bir ajana dönüşür ve makine-okunur ara
çıktılar gerekirse (örn. UI'nin render edeceği yapılandırılmış karar-masası), o ZAMAN yalnız o
ara adımlar için structured output değerlendirilir — kullanıcıya giden SOHBET metni yine serbest kalır.

İlgili: ADR-026 (zikzak), origin-vision §6, dersler-gemini meta-ders #4.
