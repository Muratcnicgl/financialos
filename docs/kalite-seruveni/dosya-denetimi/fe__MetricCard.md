# Denetim: frontend/src/components/MetricCard.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FMC-001] variants nesnesi her render'da yeniden olusturuluyor
Sorun: `variants` objesi (5 varyant, her biri 3 Tailwind sinif stringi) component fonksiyonu icinde tanimli, bu yuzden her render'da sifirdan yeniden allocate ediliyor. Statik veri oldugu icin modul seviyesine (component disina) tasinabilir.
Kanit (satir 28): `const variants = {` ... (satir 54): `};` — fonksiyon govdesinde, render'a bagli hicbir degere referans vermiyor.
Aksiyon: `variants` sabitini dosyanin en ustune, component tanimindan disariya tasi (module-level const). Boylece her render'da yeniden allocate edilmez, referans esitligi de korunur.
Onem: Dusuk · Guven: Kesin

### [FMC-002] truncate edilen title/subtitle icin tam metni gosterecek title attribute yok
Sorun: Hem baslik (`h3`, satir 67-69) hem de `subtitle` (satir 96-99) `truncate` sinifi ile kesiliyor ama native `title` attribute veya baska bir tooltip mekanizmasi eklenmemis. Uzun bir metrik basligi/alt yazi (ornegin uzun bir hesap adi) sessizce kirpiliyor, kullanicinin tam metni gormesi icin hicbir yol yok.
Kanit (satir 67-69): `<h3 className="... truncate">{title}</h3>`; (satir 97-99): `<p className="... truncate">{subtitle}</p>`
Aksiyon: `title={title}` / `title={subtitle}` native attribute'unu ilgili elemanlara ekle (hover'da tam metni gosterir, ek bagimlilik gerektirmez).
Onem: Orta · Guven: Kesin

### [FMC-003] Emanet kilit rozeti ve trend ikonlari icin erisilebilirlik etiketi yok
Sorun: `🔒 EMANET` rozeti (satir 71-75) sadece emoji + metin; ekran okuyucu emojiyi "kilit" olarak farkli sekilde okuyabilir veya atlayabilir, semantik bir `aria-label` yok. Ayrica `TrendingUp`/`TrendingDown` ikonlari (satir 86-91) salt gorsel/dekoratif oldugu halde `aria-hidden="true"` isaretlenmemis — lucide-react varsayilan olarak SVG'ye aria-hidden eklemiyor, bu yuzden ekran okuyucu bos/anlamsiz bir grafik elemani duyurabilir.
Kanit (satir 71-75, 86-91)
Aksiyon: Rozete `aria-label="Emanet - dokunulmaz hesap"` ekle; trend ikonlarina `aria-hidden="true"` ekle (baglamsal anlam zaten metin/renk ile veriliyor).
Onem: Orta · Guven: Dogrulanmali (lucide-react'in bu surumde SVG'ye otomatik aria-hidden ekleyip eklemedigi node_modules icinde dogrulanamadi)

### [FMC-004] Yukleniyor durumunda ekran okuyucuya bildirim yok
Sorun: `loading` true iken deger yerine bir pulse-animasyonlu iskelet (`div`, satir 79-81) gosteriliyor ama `aria-busy` veya `role="status"` gibi bir isaretleme yok. Ekran okuyucu kullanicisi kartin yuklenmekte oldugunu fark etmez, degerin neden gorunmedigini anlayamaz.
Kanit (satir 78-93): `<div className="flex items-end gap-2">{loading ? (<div ... animate-pulse />) : (...)}</div>`
Aksiyon: Disaridaki `div`'e `aria-busy={loading}` ekle veya iskelet elemanina `role="status" aria-label="Yukleniyor"` ekle.
Onem: Dusuk · Guven: Dogrulanmali

### [FMC-005] formatTL null/undefined durumunda suffix ile birlikte tuhaf gorunum uretebilir
Sorun: `value` prop'u `null`/`undefined`/`NaN` oldugunda `formatTL` `'—'` doner (api.js satir 364), ancak `MetricCard` bunu `prefix` ve `suffix` ile birlikte diziyor (satir 84): sonuc `"— TL"` gibi anlamsiz bir birlesim olusuyor (ozellikle `prefix` de doluysa, ornek: `"₺— TL"`).
Kanit (satir 84): `{prefix}{formatTL(value)}{suffix}`
Aksiyon: `value == null` durumunda suffix/prefix'i de gizleyecek bir kosul ekle (ornegin: `formatTL(value) === '—' ? '—' : \`${prefix}${formatTL(value)}${suffix}\``).
Onem: Dusuk · Guven: Kesin (formatTL davranisi api.js'de dogrulandi; birlesim mantigi satir 84'te goruldugu gibi kosulsuz)
