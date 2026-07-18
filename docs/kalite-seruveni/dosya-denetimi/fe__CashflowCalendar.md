# Denetim: frontend/src/components/CashflowCalendar.jsx

> **M86 güncellik:** 🟡 KISMEN-BAYAT — FCC-001 düzeltildi; FCC-002/003/005 açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FCC-001] "Bugün" isaretlemesi UTC/local karisimi yuzunden yanlis gun gosterebilir
Sorun: `isToday` hesabi, takvim hucrelerinin ISO tarihini local wall-clock (`viewYear`/`viewMonth`/`day`) ile uretirken (`isoStr`), karsilastirdigi degeri `today.toISOString().slice(0,10)` ile yani UTC gune gore aliyor. Turkiye UTC+3 oldugu icin, yerel saat 00:00-03:00 arasinda `today.toISOString()` bir onceki UTC gunu doner; boylece "bugun" halkasi (ring-1 ring-brand-500) yanlis hucrede gorunur. Bu proje PROJE.md'de tanimli bilinen tarih/timezone tuzagiyla ayni sinif hata.
Kanit (satir 86): `const isToday = iso === today.toISOString().slice(0, 10);` — `iso` local `isoStr(viewYear, viewMonth, day)` (satir 84), `today` ise `new Date()` (satir 27).
Aksiyon: Local gune gore karsilastir, orn. `isoStr(today.getFullYear(), today.getMonth(), today.getDate())` ile bir `todayIso` degiskeni turetip onunla kiyasla; `toISOString()` kullanma.
Onem: Orta · Guven: Kesin

### [FCC-002] closing_balance null/undefined oldugunda NaN/hatali isaret gosterimi
Sorun: `hasForecast` sadece `forecastDay` var mi diye bakiyor; `forecastDay.closing_balance` alani `null`/`undefined` olabilir. Bu durumda `balance >= 0` `false` doner, hucre kirmizi ("−" onekli) gorunur ve `formatTL(Math.abs(balance))` -> `Math.abs(undefined)` = `NaN` -> ekranda "NaN" ya da bozuk deger basilir.
Kanit (satir 89, 111-113): `const balance = forecastDay?.closing_balance;` ... `{balance >= 0 ? '' : '−'}{formatTL(Math.abs(balance), { compact: true })}`
Aksiyon: `hasForecast`'i `forecastDay && forecastDay.closing_balance != null` olarak daralt, ya da render'da `typeof balance === 'number'` kontrolu ekleyip yoksa rakam basmadan sadece gunu goster.
Onem: Orta · Guven: Dogrulanmali (backend'in `closing_balance`'i her zaman sayi mi dondurdugu netlesmeli)

### [FCC-003] selected.day.events alani yoksa TypeError ile cokme riski
Sorun: Secili gun detay panelinde `selected.day.events.length === 0` ve `selected.day.events.map(...)` dogrudan cagriliyor; `events` alaninin backend'den her zaman dizi olarak gelecegi varsayiliyor, opsiyonel zincirleme veya varsayilan deger yok. Backend kontratinda bir degisiklik/eksik veri durumunda component tamamen coker (unhandled exception, tum panel beyaz ekran olur).
Kanit (satir 134, 138): `selected.day.events.length === 0 ? (...) : (... selected.day.events.map((ev, i) => ...))`
Aksiyon: `(selected.day.events ?? [])` ile guvenli varsayilan kullan.
Onem: Dusuk · Guven: Dogrulanmali (mevcut backend semasi muhtemelen garanti ediyor, ama savunmasiz kod)

### [FCC-004] days prop icin varsayilan/guard yok
Sorun: `export default function CashflowCalendar({ days })` icin varsayilan deger tanimlanmamis; fonksiyon govdesinde hemen `for (const d of days) { dayMap[d.date] = d; }` calisiyor (satir 34-36). Tek cagiran yer (`frontend/src/panels/Cashflow.jsx:166`) component'i `!loading && data` blogu icinde render ediyor ve `data.days` API sonucundan geliyor, bu yuzden pratikte bugun icin tetiklenmiyor gibi gorunuyor; ancak API cevabinda `days` alani eksik/null donerse (orn. backend hata payload'i degisirse) component crash eder, ust seviye error boundary yoksa tum sekme beyaz ekrana duser.
Kanit (satir 26, 34-36): `export default function CashflowCalendar({ days }) { ... for (const d of days) {`
Aksiyon: `({ days = [] })` varsayilanini ekle veya `for (const d of days ?? [])` kullan.
Onem: Dusuk · Guven: Dogrulanmali

### [FCC-005] Ay navigasyon ve kapatma butonlarinda aria-label yok
Sorun: Onceki/sonraki ay butonlari (ChevronLeft/ChevronRight) ve secili-gun-kapat butonu (X) sadece ikon iceriyor, erisilebilir isim (aria-label veya gorunmez metin) yok. Ekran okuyucu kullanicilari bu butonlarin islevini anlayamaz.
Kanit (satir 57, 63, 130): `<button onClick={prevMonth} className="btn btn-ghost btn-icon !p-1">` / `<button onClick={nextMonth} ...>` / `<button onClick={() => setSelected(null)} ...>`
Aksiyon: Her butona `aria-label="Onceki ay"`, `aria-label="Sonraki ay"`, `aria-label="Kapat"` ekle.
Onem: Orta · Guven: Kesin

### [FCC-006] Takvim hucreleri dokunma hedefi 44px altinda kalabilir
Sorun: Hucreler `aspect-square` ve `grid-cols-7 gap-0.5` ile 7 esit sutuna bolunuyor; kart genisligi mobilde (`grid-cols-1 lg:grid-cols-2` -- Cashflow.jsx satir 165) tam genislik olsa da 7'ye bolununce ozellikle dar telefon ekranlarinda (~360px) hucre kenari ~48-50px civarinda olabilir ama `p-0.5` padding ve icindeki iki satir metin (gun no + bakiye) dokunma alanini gorsel olarak daraltiyor; kesin piksel olcumu render'a bakmadan dogrulanamaz.
Kanit (satir 79, 93-105): `<div className="grid grid-cols-7 gap-0.5">` ... `<button ... className="relative aspect-square rounded-lg ...">`
Aksiyon: Gercek cihazda/DevTools mobil emulasyonda hucre boyutunu olc; 44px altindaysa `min-h-[44px]` gibi bir alt sinir ekle veya padding'i azalt.
Onem: Dusuk · Guven: Dogrulanmali

### [FCC-007] Index key kullanimi (takvim hucreleri ve olay listesi)
Sorun: Hem takvim hucreleri (`cells.map((day, i) => ... key={i}`) hem de secili gunun olay listesi (`selected.day.events.map((ev, i) => ... key={i}`) index'i key olarak kullaniyor. Takvim hucrelerinde grid duzeni ay degistiginde tamamen yeniden olusturuldugu ve stabil oldugu icin risk dusuk; ancak events listesinde ayni gun icinde birden fazla ayni tutarli/etiketli olay varsa veya siralama backend'de degisirse React'in yanlis DOM node'u yeniden kullanmasi (stale text/format) mumkun.
Kanit (satir 82, 94, 138): `key={i}`
Aksiyon: Events icin backend'den stabil bir id/label+amount birlesimi turetip key olarak kullan (orn. `${ev.label}-${ev.amount}-${i}` gecici cozum, kalici cozum backend id'si).
Onem: Dusuk · Guven: Kesin

### [FCC-008] Ay/gun hesaplari memoize edilmiyor
Sorun: `buildCalendarGrid`, `dayMap` olusturma dongusu ve `today` her render'da yeniden hesaplaniyor (useMemo yok). `days` prop'u genelde 30-90 elemanli oldugu icin performans etkisi ihmal edilebilir duzeyde, ama component her ust state degisikliginde (orn. filtre chip'leri) yeniden calisir; buyuk `days` dizilerinde (>90 gun) gereksiz is olur.
Kanit (satir 33-38): `const dayMap = {}; for (const d of days) { dayMap[d.date] = d; } const cells = buildCalendarGrid(viewYear, viewMonth);`
Aksiyon: `useMemo(() => ..., [days])` ve `useMemo(() => buildCalendarGrid(viewYear, viewMonth), [viewYear, viewMonth])` ile sarmalamayi dusun.
Onem: Dusuk · Guven: Kesin
