# Kullanıcı Rehberi

FinancialOS panelleri ve temel akışlar.

## Paneller
- **Cockpit:** anlık finansal manzara — net değer (görülen/tam), güvenli-harcama, sağlık skoru,
  uyarılar, "ilk adım" önerisi.
- **Koç:** yapay zekâ finans koçu. Gerçekleşen bir eylem bildirirseniz onay-kartı çıkar
  (propose→onay→execute); soru/analizde sadece açıklar.
- **Hesaplar:** nakit/kart/kredi/yatırım. Yatırım fiyatları otomatik güncellenir.
- **İşlemler:** gelir/gider girişi (TR sayı formatı: 1.234,56).
- **Gelir & Borç:** düzenli gelirler + kişisel borç/alacak (Efe ödemeleri vb.).
- **Kırmızı Çizgiler:** master checkpoint'ler (dokunulmaz kurallar — sistem korur).
- **Borç Stratejisi:** snowball/avalanche karşılaştırma, konsolidasyon simülatörü.
- **Hedefler / Bütçe / Akış / Raporlar.**

## Temel akışlar
1. **Kurulum:** `docs/deployment/README.md` (Docker veya bare-metal).
2. **İlk veri:** hesaplarını + gelir/borçlarını gir (veya demo: `scripts/setup_data`).
3. **Günlük:** işlem gir → cockpit güncellenir → koça danış.

Detay ADR'ler: `docs/architecture/`.
