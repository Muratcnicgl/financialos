# Denetim: frontend/src/panels/IncomeDebt.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FID-001] Toggle/markPaid aksiyonlarinda hata yakalama yok, unhandled rejection riski
Sorun: handleToggleIncome, handleToggleExpense ve handleMarkPaid fonksiyonlari try/catch icermeden dogrudan API cagirir. Bu fonksiyonlar buton onClick'lerinden `() => handleXxx(item)` seklinde cagriliyor; donen Promise hicbir yerde await/catch edilmiyor.
Kanit (satir 123-126, 135-138, 147-153; cagri noktalari 467, 515, 605): `onClick={onToggle}` -> `onToggle={() => handleToggleIncome(inc)}` -> `await incomesApi.update(...)` catch yok.
Aksiyon: Bu uc handler'i try/catch ile sarip hatayi `setError(...)` uzerinden kullaniciya goster (diger CRUD akislarinda oldugu gibi, orn. handleSaveIncome'un cagirildigi modal try/catch pattern'i). API cagrisi basarisiz olursa kullanici sessizce "islem oldu" zanneder, cockpit ile UI arasinda veri tutarsizligi olusabilir.
Onem: Yuksek · Guven: Kesin

### [FID-002] due_date 'YYYY-MM-DD' string'i UTC olarak parse ediliyor, yerel gece yarisiyla karsilastiriliyor
Sorun: `debt.due_date` sadece tarih (input type="date") oldugu icin `new Date(debt.due_date)` bunu UTC gece yarisi olarak yorumlar (`new Date("2026-05-15")` -> `2026-05-15T00:00:00Z`). Ancak `today` degiskeni `today.setHours(0,0,0,0)` ile YEREL saat diliminde gece yarisina ayarlaniyor. Turkiye UTC+3 oldugu icin iki Date nesnesi arasinda 3 saatlik sabit kayma var; bu kayma `Math.round(...)` ile gun sinirina denk gelen durumlarda "kalan gun" sayisini 1 gun yanlis gosterebilir (orn. vade gunu bugun oldugu halde "1 gun kaldi" veya "gecikti" yazabilir).
Kanit (satir 546-552):
```js
const today = new Date();
today.setHours(0,0,0,0);
const due = new Date(debt.due_date);
return Math.round((due - today) / (1000 * 60 * 60 * 24));
```
Aksiyon: `due_date` string'ini yerel bilesenlere parse et (orn. `const [y,m,d] = debt.due_date.split('-').map(Number); const due = new Date(y, m-1, d);`) boylece hem `today` hem `due` ayni (yerel) referans sisteminde olsun.
Onem: Orta · Guven: Kesin

### [FID-003] "Bugunun tarihi" hesaplarinda toISOString() UTC gunu doner, Turkiye yerel gunuyle uyusmayabilir
Sorun: `new Date().toISOString().slice(0,10)` (satir 150, 865, 955) ve `new Date().toISOString().slice(0,7)` (satir 13) UTC'ye gore "bugun/bu ay" hesaplar. Turkiye UTC+3 oldugundan yerel saat 00:00-02:59 arasinda UTC hala bir onceki gun/ayi gosterir; bu araliktaki kullanimda `paid_date` bir gun geriden, `CURRENT_YEAR_MONTH` ise ay sonunda bir onceki ay olarak kaydedilir/karsilastirilir (orn. "Bu ay" rozeti yanlis gosterilir, odenme tarihi bir gun yanlis yazilir).
Kanit (satir 13, 150, 865, 955).
Aksiyon: Yerel tarihten `YYYY-MM-DD`/`YYYY-MM` uretecek kucuk bir yardimci fonksiyon kullan (orn. `getFullYear/getMonth/getDate` ile manuel format), UTC bazli `toISOString` yerine.
Onem: Dusuk · Guven: Dogrulanmali (sadece gece 00:00-03:00 penceresinde tetiklenir)

### [FID-004] Tutar alaninda binlik ayirici (nokta) icin Turkce format sessizce yanlis parse edilir
Sorun: `amount.replace(',', '.')` sadece ONDALIK virgulu noktaya cevirmeyi hedefler, ama kullanici Turkce binlik format girerse (orn. "1.234,56") sonuc "1.234.56" olur ve `parseFloat` bunu `1.234` olarak keser — hata mesaji gostermeden tutari ~1000 kat yanlis kaydeder (sessiz veri bozulmasi, `amt > 0` oldugu icin validasyon gecer).
Kanit (satir 641, 750, 851): `const amt = parseFloat(amount.replace(',', '.'));` — hem IncomeFormModal hem ExpenseFormModal hem DebtFormModal'da tekrar eden pattern.
Aksiyon: Binlik ayiricilari once temizleyen (`.replace(/\./g, '')` sonra virgulu noktaya cevir) veya kullanicidan sade ondalik format isteyen bir yardimci parse fonksiyonu ekle; bu ucleme kod da ortak bir util'e cikarilmali.
Onem: Yuksek · Guven: Kesin

### [FID-005] Ikon-only butonlarda aria-label yok, sadece title
Sorun: Power/Pencil/Trash2/CheckCircle butonlarinin tumu sadece `title` ile etiketleniyor, `aria-label` yok. Ekran okuyucu destegi tarayiciya/`title` render'ina birakiliyor ve tutarsiz duyurulabiliyor.
Kanit (satir 467, 470, 473, 515, 518, 521, 604-610, 612, 615, 1037).
Aksiyon: Her ikon butonuna `aria-label={...}` ekle (title ile ayni metin olabilir).
Onem: Dusuk · Guven: Dogrulanmali

### [FID-006] Ikon buton dokunma alani 44px altinda (mobil erisilebilirlik)
Sorun: Satir/aksiyon butonlari `btn-icon !p-1` (4px padding) + `w-3/w-3.5` (12-14px) ikon kullaniyor; toplam dokunma alani ~20-22px, WCAG/mobil onerilen 44x44px'in belirgin altinda. `docs/wave-2-roadmap.md` D1 mobil hedefiyle celisir.
Kanit (satir 467-475, 515-523, 604-617).
Aksiyon: Mobilde `min-w-[44px] min-h-[44px]` veya en azindan `p-2.5` civarina cikaracak responsive padding ekle.
Onem: Orta · Guven: Kesin

### [FID-007] Modal'da Escape tusu ve focus trap yok
Sorun: `Modal` bileşeni sadece backdrop tiklamasinda kapaniyor (satir 1027-1030); klavye ile Escape kapatmiyor, odak modal acildiginda ilk alana tasinmiyor (autoFocus var ama modal disina Tab ile kacilabilir), kapaninca tetikleyici butona odak donmuyor.
Kanit (satir 1025-1044).
Aksiyon: `useEffect` ile `keydown` Escape dinleyicisi ekle, kapanista tetikleyici elemente odak geri ver, basit bir focus-trap uygula.
Onem: Orta · Guven: Kesin

### [FID-008] daysRemaining icin gereksiz useMemo — string/boolean bagimliliklarla ucuz hesap
Sorun: `useMemo(() => {...}, [debt.due_date, debt.is_paid])` (satir 546-552) her render'da yeniden calisacak kadar ucuz bir hesaplamayi memoize ediyor; performans kazanci yok, sadece okunabilirligi dusuruyor. Bug degil ama gereksiz karmasiklik.
Kanit (satir 546-552).
Aksiyon: Duz bir fonksiyon cagrisina indir, useMemo kaldirilabilir.
Onem: Dusuk · Guven: Dogrulanmali

### [FID-009] load() icin unmount sonrasi state guncelleme koruma yok
Sorun: `load()` fetch tamamlanmadan bilesen unmount olursa (orn. sekme hizli degistirilirse — ama bu panel tab-based degil route-based oldugundan risk dusuk), `setIncomes/setExpenses/...` unmount sonrasi cagrilabilir. Cleanup/AbortController yok.
Kanit (satir 49-70).
Aksiyon: Gerekirse `let cancelled = false` + cleanup pattern'i veya AbortController ekle; risk dusuk oldugu icin oncelik dusuk.
Onem: Dusuk · Guven: Dogrulanmali
