# Ürün & UX (kod: UX)

> Kullanıcının gerçek baskısı: kart ~%99.8, 5 kredi, 13 dağınık alacak, günlük limit ~62 TL. Kişisel yatırım tavsiyesi yok; yatırımla ilgili maddeler yalnız görünürlük/giriş kolaylığı.

### [UX-001] İlk açılış onboarding'i yok — sistem kendini tanıtmıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: onboarding/coach-mark turu yok
- **Kanıt:** `App.jsx:98-110`; Cockpit stratejik kartları `Cockpit.jsx:164-204`
- **Aksiyon:** localStorage `onboarded` flag ile 3-4 adımlık coach-mark turu (bugünkü hedef, kart doluluk, koça harcama yaz).
- **Etki:** Yüksek · **Efor:** M

### [UX-002] Geri-al (undo) hiçbir yerde yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: undo yok, Toast action prop yok
- **Kanıt:** `Transactions.jsx:668`, `Accounts.jsx:585`, `IncomeDebt.jsx:979`, `Toast.jsx`
- **Aksiyon:** Toast'a `action:{label,onClick}`; düşük-riskli silmelerde modal yerine optimistic remove + "Geri Al" toast'ı.
- **Etki:** Yüksek · **Efor:** M · **Not:** Backend soft-delete veya gecikmeli commit gerekebilir.

### [UX-003] Kart doluluğu (%99.8) Cockpit'te sadece düz sayı
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: kart kullanım barı var ama MetricCard düz sayı
- **Kanıt:** `Cockpit.jsx:149`; doluluk barı yalnız `Accounts.jsx:250-265`
- **Aksiyon:** Cockpit kart kartına utilization bar + "%99.8 · limite 120 TL kaldı"; %95 üstünde kırmızı.
- **Etki:** Yüksek · **Efor:** S

### [UX-004] Günlük limit pasif — "bugün ne kadar kaldı" canlı değil
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: günlük hedef pasif, canlı halka yok
- **Kanıt:** `Cockpit.jsx:207-225`
- **Aksiyon:** Bugünkü işlemleri çıkarıp "Bugün kalan: X/62 TL" halka; aşımda "Yarının limitinden N TL borçlandın" (zikzak bağı).
- **Etki:** Yüksek · **Efor:** M · **Not:** Bugünkü harcama toplamı backend'den gerekebilir.

### [UX-005] Limit yaklaşınca "dur" nudge'ı yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: QuickEntry limit-aşımı nudge yok
- **Kanıt:** `Transactions.jsx:372-388`
- **Aksiyon:** Kayıttan önce tutar bugünkü kalanı aşıyorsa 1 adımlık inline onay ("Bu, limitini 258 TL aşıyor. Yine de ekle?"). Sadece aşımda.
- **Etki:** Yüksek · **Efor:** S · **Not:** Bildirim yorgunluğu için günde bir/2x üstünde tetikle.

### [UX-006] Coach'ta cevap sonrası hızlı-yanıt chip'leri yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: hızlı-yanıt chip yalnız boş state
- **Kanıt:** Chip'ler yalnız empty state `Coach.jsx:429-444`
- **Aksiyon:** Cevap altına bağlam duyarlı 2-3 chip ("Neden bu sıra?", "Kart için plan çıkar").
- **Etki:** Orta · **Efor:** M · **Not:** Chip'ler soru olmalı, KURAL SIFIR'ı bozmamalı.

### [UX-007] 13 alacak için yaşlandırma (aging) görünümü yok
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: yaşlandırma bandı var ama IncomeDebt toplam-bekleyen bandı yok
- **Kanıt:** `IncomeDebt.jsx:75-93,581-592`
- **Aksiyon:** "Toplam bekleyen: X · en eskisi N gün" bandı; varsayılan "en eski/gecikmiş önce"; gecikmiş kırmızı şerit.
- **Etki:** Yüksek · **Efor:** S

### [UX-008] Alacak tahsilatı için tek-tık "hatırlat"/paylaş yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: hatırlatma kopyala/paylaş yok
- **Kanıt:** `IncomeDebt.jsx:602-617`
- **Aksiyon:** "Hatırlatma metni kopyala" (nötr, counterparty). Otomatik gönderim değil.
- **Etki:** Orta · **Efor:** S

### [UX-009] QuickEntry kategori önermiyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: QuickEntry kategori önermiyor
- **Kanıt:** `Transactions.jsx:155-167,25-28`
- **Aksiyon:** Geçmişe dayalı en olası 2 kategoriyi chip öner (client-side frequency map). LLM gerekmez.
- **Etki:** Orta · **Efor:** M

### [UX-010] Optimistic feedback zayıf — her CRUD sonrası tam refresh
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: her CRUD tam refresh, optimistik yok
- **Kanıt:** `Transactions.jsx:138-152`, `IncomeDebt.jsx:116-165`, `Accounts.jsx:51-65`
- **Aksiyon:** Local state hemen güncelle, arka planda revalidate; hata'da geri al.
- **Etki:** Orta · **Efor:** M

### [UX-011] Mobilde 10 sekme yatay scroll'a sıkışıyor — alt nav yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: md altı bottom-nav yok
- **Kanıt:** `App.jsx:22-33,163-181`
- **Aksiyon:** `md:` altında bottom nav (5 sekme + "Daha"); `pb-[env(safe-area-inset-bottom)]`.
- **Etki:** Yüksek · **Efor:** M

### [UX-012] Streak/süreklilik göstergesi yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: streak göstergesi yok
- **Kanıt:** Hiçbir panelde streak yok
- **Aksiyon:** "🔥 7 gün üst üste" veya "Bu ay 12/30 gün limitin altında". Ceza değil pozitif; kırılınca suçlayıcı olma (fresh-start).
- **Etki:** Orta · **Efor:** M

### [UX-013] Yaklaşan vadeler pasif liste — tek-tık aksiyona dönüşmüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Cockpit vade listeleri pasif, Geldi/Ödedim butonu yok
- **Kanıt:** `Cockpit.jsx:366-406`
- **Aksiyon:** Her vadeye buton (gelir→"Geldi", borç→"Ödedim", kart→"Koça sor"); PendingAction üretebilir.
- **Etki:** Orta · **Efor:** M

### [UX-014] Coach "Yeni sohbet" `window.confirm` ile tüm geçmişi siliyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Yeni sohbet window.confirm, arşivle yok
- **Kanıt:** `Coach.jsx:261-262`
- **Aksiyon:** Uygulama içi modal + "arşivle" (sil yerine gizle).
- **Etki:** Orta · **Efor:** S

### [UX-015] Coach geçmişinde arama yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Coach geçmiş arama yok
- **Kanıt:** `Coach.jsx:158-177`
- **Aksiyon:** İnce arama kutusu (client-side) + "sadece aksiyonlu" filtresi.
- **Etki:** Düşük · **Efor:** S

### [UX-016] Tutar inputları numeric klavye ipucu vermiyor (`type="text"`)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: tutar inputları inputMode yok
- **Kanıt:** `Transactions.jsx:576`, `IncomeDebt.jsx:681`, `Accounts.jsx:443`
- **Aksiyon:** Para→`inputMode="decimal"`, gün→`inputMode="numeric"`; ₺ prefix. Virgül parse korunur.
- **Etki:** Orta · **Efor:** S

### [UX-017] IncomeDebt boş durumları CTA'sız, sıradan metin
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: IncomeDebt boş durum CTA'sız
- **Kanıt:** `IncomeDebt.jsx:288-291,320-323,378-383` vs `Transactions.jsx:310-316`
- **Aksiyon:** Üç sekmede de `EmptyState`+"İlk gelirini ekle" CTA.
- **Etki:** Düşük · **Efor:** S

### [UX-018] Swipe/gesture yok — mobilde küçük ikon butonları
- **Durum:** 🟡 KISMEN (BUG #265, 7 Ağu 2026) — maddenin **"ikon 44px altı"** yarısı kapandı ve
  artık ölçülüyor (`frontend/e2e/tema-mobil.spec.js`; 390px'te her kontrol ≥44px). **Swipe/gesture
  hâlâ yok** — ayrı iş.
- **Kanıt:** `Transactions.jsx:481-488`, `IncomeDebt.jsx:602-617`
- **Aksiyon:** Swipe-action (alacak sağa→ödendi, sola→hatırlat/sil); en azından 44px hit-target.
- **Etki:** Orta · **Efor:** L

### [UX-019] Pull-to-refresh yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: pull-to-refresh yok
- **Kanıt:** Her panelde manuel Yenile
- **Aksiyon:** Ana scroll'a pull-to-refresh (mobil); buton masaüstünde kalsın.
- **Etki:** Düşük · **Efor:** M

### [UX-020] Goals/DebtStrategy açık temada bozuk
- **Durum:** ✅ KAPANDI (BUG #265 / ADR-047, 7 Ağu 2026) — madde **eksik tarif ediyordu**: yalnız
  Goals/DebtStrategy değil, `Workspace` ve `Login` de tamamen koyu-varsayan yazılmıştı (toplam 101
  kullanım) ve açık temada başlıklar 1.05 kontrastla GÖRÜNMÜYORDU. 128 sınıf tema-duyarlı çifte
  çevrildi. Kalıcı kapı: `frontend/e2e/tema-mobil.spec.js` (her panel × her tema render edilir,
  kontrast ≥3:1). Mutasyon 3/3.
- **Kanıt:** `Goals.jsx:55,141,229`; `DebtStrategy.jsx:21,55`
- **Aksiyon:** Sabit koyu renkleri tema-duyarlı çiftlere çevir. (FE-008 ile aynı)
- **Etki:** Orta · **Efor:** M

### [UX-021] "Görülen" vs "Tam Net Değer" ayrımı açıklamasız
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: subtitle statik ama ? popover yok
- **Kanıt:** `Cockpit.jsx:186-203`
- **Aksiyon:** Tıklanınca "?" popover: "Görülen = cüzdanında olan. Tam = sözleşmeli alacaklar dahil." (mobilde tap-to-open)
- **Etki:** Orta · **Efor:** S

### [UX-022] Emanet "dokunulmazlığı" görsel olarak zayıf
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: emanet chip var ama commitment metni/link yok
- **Kanıt:** `Cockpit.jsx:164-171`; `Accounts.jsx:219-223`
- **Aksiyon:** "🔒 Kendine söz: bu hesaba dokunma" + bağlı kırmızı çizgiye link (commitment device).
- **Etki:** Düşük · **Efor:** S

### [UX-023] Bildirim yorgunluğu — uyarı seviyeleri/sıklığı yönetilmiyor
- **Durum:** 🟡 KISMEN — M85 R3 doğrulama: alert seviye stili var ama katlanır kritik bandı yok
- **Kanıt:** `Cockpit.jsx:227-265,366-406,480-514`; usage `Coach.jsx:392-411`
- **Aksiyon:** 1 "kritik" bandı üstte, gerisi katlanabilir "N bilgi"; backend `seviye` alanını kullan.
- **Etki:** Orta · **Efor:** M

### [UX-024] Kart borcunu kapatma için yapılandırılmış "plan" akışı yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: DebtStrategy→Goal kurma akışı yok
- **Kanıt:** `DebtStrategy.jsx` (analiz var, taahhüt yok)
- **Aksiyon:** "Bu planı benimse" → seçilen stratejiyi Goal (debt_freedom) olarak kur + aylık allocation kuralı. (allocation altyapısı var)
- **Etki:** Yüksek · **Efor:** M

### [UX-025] Ekstra ödeme slider'ı 0-5000 sabit — reel bütçeyle ilgisiz
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: slider max 5000 sabit, reel_butce ölçek yok
- **Kanıt:** `DebtStrategy.jsx:166-174`
- **Aksiyon:** Üst sınırı reel_butce'ye göre ölçekle; "Ayırabileceğin ~X TL" referans işareti.
- **Etki:** Orta · **Efor:** S

### [UX-026] Bekleyen aksiyonlarda "toplu onayla/reddet" yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: toplu onay yok
- **Kanıt:** `Cockpit.jsx:129-137`+`PendingActions.jsx`
- **Aksiyon:** 2+ pending'de "Hepsini onayla" (düşük riskli tipler); sell_investment hariç.
- **Etki:** Orta · **Efor:** M

### [UX-027] Reddedilen/geçmiş aksiyonların izi görünmüyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: reddedilen aksiyon izi yok
- **Kanıt:** `Coach.jsx:handleActionResolved` filtreliyor
- **Aksiyon:** "Karar Günlüğü" mini görünümü (DecisionJournal endpoint'i gerekir).
- **Etki:** Düşük · **Efor:** M

### [UX-028] "Bu ay" temposu görünmüyor (ay sonu ufku)
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: ay ilerleme/tempo göstergesi yok
- **Kanıt:** `Cockpit.jsx:216-217`
- **Aksiyon:** Ay ilerleme barı + "harcama temposu hedefte/üstünde" (goal-gradient).
- **Etki:** Orta · **Efor:** M

### [UX-029] Cockpit çok uzun tek kolon — mobilde yorucu
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: tek uzun kolon, önemli-3 + katlanır yok
- **Kanıt:** `Cockpit.jsx:111-527` (9+ bölüm)
- **Aksiyon:** Üstte "bugün önemli 3 şey", gerisi katlanabilir (localStorage tercih).
- **Etki:** Orta · **Efor:** M

### [UX-030] Hesap silme uyarısı sayı vermiyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: silme uyarısı bağlı işlem sayısı vermiyor
- **Kanıt:** `Accounts.jsx:608`
- **Aksiyon:** "Bu hesaba bağlı 47 işlem de silinecek" (bilinçli karar).
- **Etki:** Düşük · **Efor:** S

### [UX-031] Recurring takvim görünürlüğü zayıf
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: recurring takvim şeridi yok
- **Kanıt:** `IncomeDebt.jsx:453-455`
- **Aksiyon:** Gelir & Borç üstüne mini aylık şerit (hangi gün maaş/kira/fatura). Cashflow ile çakışmasın.
- **Etki:** Düşük · **Efor:** M

### [UX-032] Fiyat güncelleme çok adımlı — inline giriş yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: fiyat güncelleme modal, inline giriş yok
- **Kanıt:** `Cockpit.jsx:481-514`; `Accounts.jsx:536-578`
- **Aksiyon:** Tazelik satırında modal açmadan inline fiyat girişi.
- **Etki:** Düşük · **Efor:** S

### [UX-033] Coach input tek satır algısı — uzun istekler zor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: textarea auto-grow + / komut menüsü yok
- **Kanıt:** `Coach.jsx:472-481`
- **Aksiyon:** Auto-grow textarea (2→6) + "/" hızlı komut menüsü.
- **Etki:** Düşük · **Efor:** S

### [UX-034] Mikro-kopya tonu tutarsız — teknik/karışık terimler
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: teknik mikro-kopya, sözlük/ton yok
- **Kanıt:** `Cockpit.jsx:184` ("Gölge muhasebe"), `:356` ("Sıkışma Günü")
- **Aksiyon:** Terim sözlüğü + tek ton (net+insani); "Sıkışma günü"→"Kasa dibi günü". Alan adları korunur.
- **Etki:** Orta · **Efor:** M

### [UX-035] Başarı anları kutlanmıyor — borç kapama/hedef sessiz
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: borç/hedef başarısı kutlanmıyor
- **Kanıt:** `IncomeDebt.jsx:147-153`; Goals achieved düz rozet
- **Aksiyon:** Hedef/eşik geçişinde kısa konfeti + "🎉 X TL borç kapandı, kart %92'ye indi". Ölçülü.
- **Etki:** Orta · **Efor:** S

### [UX-036] Cockpit kaleminden ilgili panele deep-link zayıf
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: Cockpit vade satırları tıklanamaz
- **Kanıt:** `Cockpit.jsx:449-477` (tıklanamaz) vs `:332-339` (cashflow linki var)
- **Aksiyon:** Vade/tahsilat satırlarını tıklanabilir yap → ilgili panel (`setActiveTab` prop mevcut), kaydı vurgula.
- **Etki:** Orta · **Efor:** M

### [UX-037] Filtre durumları oturumlar arası hatırlanmıyor
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: filtreler oturumlar arası hatırlanmıyor
- **Kanıt:** `Transactions.jsx:42-47`, `IncomeDebt.jsx:45-47`, `RedLines.jsx:63-64`
- **Aksiyon:** Filtre tercihlerini localStorage'da tut.
- **Etki:** Düşük · **Efor:** S

### [UX-038] Boş sistem için örnek/şablon önerisi yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: örnek/şablon önerisi yok
- **Kanıt:** `Accounts.jsx:159-167`, `RedLines.jsx:245-249`
- **Aksiyon:** "Tipik başlangıç" şablonları (örnek kırmızı çizgiler, kategori seti); kullanıcı düzenler.
- **Etki:** Düşük · **Efor:** M

### [UX-039] Gün sonu özeti / proaktif ritüel yok
- **Durum:** 🔲 AÇIK — M85 R3 doğrulama: proaktif gün-sonu özet kartı yok
- **Kanıt:** `Coach.jsx:198-248` (yalnız kullanıcı yazınca)
- **Aksiyon:** Cockpit'te "Dünün özeti" kartı (harcama, limit, yarının vadeleri). KURAL SIFIR'ı bozmaz (aksiyon önermez).
- **Etki:** Orta · **Efor:** M

### [UX-040] Erişilebilirlik: dokunma hedefi, kontrast, klavye odağı zayıf
- **Durum:** 🟡 KISMEN (BUG #265 / ADR-047, 7 Ağu 2026) — **dokunma hedefi ve kontrast KAPANDI ve
  ölçülüyor**: 390px'te her panel × her tema render edilir, hedef ≥44px (iki yazılı istisna) ve
  metin kontrastı ≥3:1 (`frontend/e2e/tema-mobil.spec.js`, mutasyon 3/3). **Açık kalan iki ayak,
  dürüst kayıt:** (a) eşik 3:1 — WCAG AA'nın *büyük metin* sınırı; gövde metni için 4.5 hedefi
  ayrı iştir (bugünkü tabanda ikincil metinlerin bir kısmı 3–4.5 aralığında), (b) renk-only durum
  göstergeleri ve `focus-visible` halkaları hâlâ ölçülmüyor.
- **Kanıt:** `Transactions.jsx:482-487` (`!p-1`), `Cockpit.jsx:391` (`text-[9px]`), renk-only işaretler
- **Aksiyon:** Min 44px, min 11px metin, durum göstergelerine ikon+renk, `focus-visible` halkaları.
- **Etki:** Orta · **Efor:** M

---
**Kaynaklar:** YNAB method; Copilot intelligence; Rocket Money; Actual Budget; Maybe Finance; davranışsal finans (mental accounting, loss aversion, commitment devices, fresh-start, goal-gradient, Fogg B=MAP, Save More Tomorrow).
