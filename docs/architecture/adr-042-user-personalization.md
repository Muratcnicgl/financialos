# ADR-042 — Kullanıcı kişiselleştirme: saat dilimi şimdi, para birimi aşamalı

**Durum:** Kabul edildi · **Tarih:** 2026-08-05 · **Faz:** P3.5 / H4 · **İlgili:** BUG #197, #169

## Bağlam

Sistem tek kullanıcı (Türkiye) varsayımıyla büyüdü. Kapalı betada "yabancı bir kullanıcı
kendi hayatını kurabilmeli" hedefi üç kişiselleştirme ekseni doğuruyor: **saat dilimi**,
**para birimi**, **dil/locale**. Bunların maliyeti ve riski EŞİT DEĞİL.

- **Saat dilimi:** Uygulama her yerde `date.today()` — yani SUNUCUNUN yerel tarihi —
  kullanıyordu. Sunucu TZ'si doğru ayarlansa bile (BUG #169) başka saat dilimindeki
  kullanıcı için "bugün" yanlış güne düşer: gece yarısı civarı girilen işlem komşu güne
  yazılır, günlük limit yanlış hesaplanır, ay sınırında düzenli gelir/gider tetiklemesi kayar.
  **Bu bir doğruluk hatasıdır ve ucuzdur** (tarih üreten yollar zaten `today` parametresi alıyordu).
- **Para birimi:** Tutarlar `Numeric(19,4)` olarak para-birimsiz saklanıyor; "TL" hem
  backend metinlerinde hem 9 frontend dosyasında biçimlendirmede gömülü. Ayrıca fiyat
  sağlayıcıları (TEFAS/BIST/EVDS) **TRY dünyasına** ait. Gerçek çoklu-para-birimi; kur
  dönüşümü, tarihsel kur, karışık-para-birimi net değer ve raporlama demektir.

## Karar

**Aşamalı kişiselleştirme.**

1. **Şimdi (bu ADR ile uygulandı):** `User.timezone` — tarih üreten tüm kullanıcı-bağlamlı
   yollar `app/user_prefs.user_today(user)` kullanır. TZ boşsa sunucu yereline düşer
   (mevcut kurulumların davranışı **değişmez**). Geçersiz TZ **sessizce kabul edilmez**:
   API 422 döner, çalışma zamanında güvenli varsayılana düşülür + log.

   > ⚠️ **DÜZELTME (6 Ağu 2026, denetim D17 / BUG #237).** Yukarıdaki "TÜM kullanıcı-bağlamlı
   > yollar" iddiası **yazıldığı anda diskte YANLIŞTI**: yalnız 7 router benimsemişti.
   > `action_executor` (koçun yazdığı işlem/ödeme tarihi), `reports` (6 uç), `subscriptions`,
   > cockpit'in snapshot damgası, `coach` bağlamı, `cashflow`/`simulation`/`goal_engine`/
   > `debt_strategy` motorları ve startup catch-up sunucu gününü kullanıyordu. Kök sebep
   > yapısaldı, atlanmış çağrı değil: `execute_pending_action` handler'ları
   > `handler(db, user_id, payload)` ile çağırıyordu — User nesnesi hiç geçmediği için
   > handler `user_today`'e **ulaşamıyordu**. Kapatıldı: `user_prefs.user_today_by_id(db, user_id)`
   > + tüm yolların dönüştürülmesi. İddia artık **teste bağlı** (belge tek başına delil değil):
   > `tests/test_saat_dilimi_kapisi.py` her `date.today()` çağrısını gerekçe zorunluluğuna
   > bağlar, `tests/test_saat_dilimi_kullanici_gunu.py` davranışı UTC+14/UTC-11 uçlarında ölçer.
   > Muafiyet (piyasa takvimi: TEFAS/BIST/EVDS + saf hesap yardımcılarının varsayılanı)
   > `# tz-exempt: <neden>` işaretiyle sayılıdır.
2. **Şimdi (alan olarak):** `User.currency` / `User.locale` saklanır ve API'den okunur/yazılır;
   varsayılanlar `TRY` / `tr-TR`. Böylece kayıt akışı ve dışa aktarım ileriye dönük uyumlu olur.
3. **Sonra (ayrı iş, P8 öncesi):** görüntüleme para birimi → tek bir biçimlendirme helper'ına
   indirgeme + backend metinlerinden "TL" sabitinin kaldırılması. **Çoklu para birimiyle
   hesap tutma** (kur dönüşümü, tarihsel kur) ayrı bir ADR gerektirir; kapalı beta TR
   kullanıcılarıyla başlayacağı için yayın-engeli DEĞİLDİR.

## Alternatifler

- **Her şeyi şimdi yapmak:** çoklu para birimi tüm hesap motorunu (net değer, borç stratejisi,
  bütçe, hedefler) etkiler; kapalı betayı haftalarca geciktirir ve hatalı kur mantığı
  **yanlış finansal karar** üretir. Reddedildi: bar yüksek, kazanç düşük (TR beta).
- **Saat dilimini de ertelemek:** reddedildi — ucuz, sessiz ve **kullanıcının verisini
  yanlış güne yazan** bir doğruluk hatasıdır.
- **TZ'yi tarayıcıdan her istekte göndermek:** istemciye güven + her uçta parametre demek;
  sunucu-tarafı cron/batch yolları yine yanlış kalırdı. Reddedildi.

## Sonuçlar

- (+) Farklı saat dilimindeki kullanıcı doğru "bugün"ü görür; cron/batch yolları kullanıcı
  bazlı doğruya yaklaşır.
- (+) Mevcut kurulum etkilenmez (TZ boş → eski davranış).
- (−) Para birimi hâlâ TRY varsayımlı: bu **açıkça** belgelenmiştir (masterprompt §1.2 H4)
  ve açık betaya (P8) girmeden kapatılacaktır.
- **Kanıt:** `tests/test_user_preferences.py` (7 test) — TZ yoksa geriye uyum, farklı TZ farklı
  gün, geçersiz TZ güvenli varsayılan + API 422, uçtan uca cockpit, varsayılan TRY/tr-TR.
