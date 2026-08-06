# ADR-044 — Para biçimlendirme tek kaynak; TRY kilidi bilinçli ve fail-fast; grounding para birimine bağlı

**Durum:** Kabul edildi · **Tarih:** 2026-08-07 · **Faz:** PUBLISH / H4 (masterprompt §1.2)
**İlgili:** ADR-042 (kişiselleştirme aşamalı), ADR-030 (Decimal para), ADR-001 (Rules Engine karar verir)
**Bug:** #256 · **Öncül bulgu:** `master-durum-raporu-2026-08-06.md` §5.2

## Bağlam

ADR-042 kişiselleştirmeyi üç eksene ayırmıştı: saat dilimi **şimdi**, para birimi/locale
**alan olarak şimdi, görüntüleme sonra**. "Sonra" kısmı (3. madde) açık kalmıştı. 6 Ağustos
2026'da yapılan ölçüm, bunun bir "eksik özellik" değil **yapısal borç** olduğunu gösterdi:

- Para biçimlendirme **yedi ayrı yerde** bağımsız kodlanmıştı: `rules_engine._tl`,
  `action_executor._fmt`, `coach_insights`'ın `{x:,.0f}` kalıbı (İngilizce binlik ayıracı!),
  frontend'de `api.js formatTL`, `DebtStrategy.jsx`'in yerel `TL()`'i (null → "₺0"),
  `HorizonsModal` ve `PremortemModal`'ın kendi `toLocaleString`'ları.
- Etiket ("TL") **167 backend string sabitinde** ve **21 frontend dosyasında 91 satırda** elle yazılıydı.
- `User.currency` alanı vardı ama `user_currency()` **hiçbir üretim kodundan çağrılmıyordu**.
- En kritiği: `app/grounding.py` koçun ürettiği tutarları `(\d…)\s*TL` deseniyle doğruluyordu.
  Etiket değişirse desen hiçbir şey bulamaz, `checked=0` olur ve fonksiyon `{"ok": True}`
  döner — yani **doğrulama katmanı sessizce yeşile düşer**. Dahası: koç bağlamının yatırım
  K/Z satırı ve kart kullanım satırı **etiketsiz** tutar yazıyordu, yani o tutarlar hiç
  denetlenmiyordu (ölçüldü, düzeltildi).

## Karar

**1. Tek kaynak.** Para biçimi ve etiketi iki modülde tanımlıdır ve başka hiçbir yerde
yeniden yazılamaz: `app/money_format.py` (backend) ve `frontend/src/lib/money.js` (frontend).
İkisi aynı sözleşmeyi taşır (kod `TRY`, etiket `TL`, simge `₺`) ve bu hizalanma teste bağlıdır.

**2. TRY kilidi kalır — ama görünür ve dürüst.** Desteklenen küme `{"TRY"}`. Bu bir eksiklik
değil ürün kararıdır: çoklu para birimiyle **hesap tutmak** (kur çevrimi, tarihsel kur,
karışık-para-birimi net değer) ayrı bir ADR gerektirir ve TR beta için yayın-engeli değildir.
BUG #251'in şikâyeti ("ayarlanabilir görünüp gösterilememesi") kilidi kaldırarak değil,
**kilidi ölçülebilir kılarak** kapanır.

**3. İki ayrı hata rejimi.**
- **Kod yolu → fail-fast:** `format_para(..., kod="USD")` `DesteklenmeyenParaBirimi` fırlatır.
  Geliştirici hatası sessizce yanlış etiketli para üretmemelidir.
- **Veri yolu → fail-safe:** `kullanici_para_kodu(user)` DB'de kalmış geçersiz bir kod görürse
  (BUG #246 doğrulaması eklenmeden önce her değer kabul ediliyordu) **çökmez**; uyarı loglar,
  varsayılana düşer. Kullanıcının kendi verisini açamaz hale gelmesi yanlış etiketten ağırdır (L6).

**4. Grounding para birimine bağlıdır ve sıfır-eşleşme artık başarı değildir.**
- Desen etiketleri `money_format.taninan_etiketler()`'ten alır (L21: sinyali, ona göre karar
  verilen sözleşmeye koy).
- Yeni alan `etiketsiz`: para biçiminde yazılmış ama etiketi olmayan tutarlar raporlanır ve
  sonucu KIRMIZI yapar. Yanlış-pozitif sınırı bilinçlidir: yüzde, tarih, birim taşıyan sayılar
  ve ayraçsız düz tam sayılar sayılmaz (L22 — gürültü üreten kapı ciddiye alınmaz).

**5. Geri sızma statik kapıyla engellenir.** `tests/test_para_birimi_kapisi.py`:
üretim kodunda yeni `Intl.NumberFormat`/`toLocaleString`/ham `" TL"` reddedilir; backend'de
gerekçeli muafiyet envanteri **sayısıyla** tutulur (yalnız azalabilir); kapı kendi kapsamını
(taranan dosya sayısı) assert eder ve kendi mutasyonunu test eder (L11/H25/L27).

## Alternatifler

- **Çok-para-birimi görüntülemeyi şimdi açmak:** reddedildi. Fiyat sağlayıcıları (TEFAS/BIST/EVDS)
  TRY-denominasyonludur; TRY fiyatını USD defterine toplamak **sessizce yanlış net değer** üretir —
  bu projenin en pahalı hata sınıfı (SBN-001 / BUG #161 ailesi).
- **Sadece etiketi sabit bırakıp biçimlendiriciyi birleştirmek:** reddedildi. Asıl sessiz risk
  etiketin grounding'e gömülü olmasıydı; onu çözmeden yapılan birleştirme kozmetik olurdu.
- **Etiketi her çağrıda parametre olarak taşımak (`format_para(x, "TL")`):** reddedildi —
  yasağın gücü kaynağı SEÇEN kod sayısı kadardır (L26); parametre yeniden çoğaltma yaratır.

## Sonuçlar

- (+) Para birimi kararı **tek yerde** değişir; arayüz, koç metni ve doğrulama birlikte hareket eder.
- (+) `coach_insights` artık İngilizce binlik ayıracı üretmiyor ("5,000 TL" → "5.000 TL");
  bu aynı zamanda bir grounding yanlış-pozitif kaynağıydı (BUG #122 sınıfı).
- (+) Premortem prompt'u ham float yerine biçimli tutar veriyor.
- (+) Koç bağlamındaki etiketsiz tutarlar (yatırım K/Z, kart borcu) artık denetleniyor.
- (−) Çoklu para birimi hâlâ kapalı; açılacağı gün gereken iş **kullanıcı bağlamının
  biçimlendiriciye taşınması**dır (`format_para(x, user)` imzası hazır, çağrı yerleri değil).
  Bu, ADR-042/BUG #237'nin "benimseme yarım kaldı" hatasına düşmemek için burada yazılıdır.

## Kanıt

| İddia | Kapı |
|---|---|
| Tek biçimlendirici (backend) | `tests/test_para_birimi_kapisi.py::test_backend_ikinci_bir_bicimlendirici_yok` |
| Tek biçimlendirici (frontend) | `…::test_frontend_ikinci_bicimlendirici_yok`, `…::test_api_js_yalniz_yeniden_disa_aktarir` |
| Ham etiket sızmıyor | `…::test_backend_para_sabiti_yalniz_gerekceli_yerlerde`, `…::test_frontend_ham_para_etiketi_yok` |
| Muafiyet listesi şişmiyor | `…::test_backend_muafiyet_listesi_sismedi` |
| Kapı kendi kapsamını ölçüyor | `…::test_backend_kapsam_tabani`, `…::test_frontend_kapsam_tabani` |
| Kapı gerçekten yakalıyor | `…::test_kapi_ihlali_gercekten_yakalar` (mutasyon) |
| Grounding tek kaynaktan besleniyor | `tests/test_grounding_para_birimi.py::test_desen_etiketleri_tek_kaynaktan_gelir` |
| Etiketsiz tutar kırmızı | `…::test_etiketsiz_tutar_kirmiziya_duser` + `…::test_kapi_mutasyonu_yakalar` |
| Yanlış-pozitif sınırı | `…::test_para_olmayan_sayilar_etiketsiz_sayilmaz` (6 vaka) |
| Frontend sözleşmesi | `frontend/src/money.test.js` (8 test) |
