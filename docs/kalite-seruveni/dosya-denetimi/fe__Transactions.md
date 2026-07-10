# Denetim: frontend/src/panels/Transactions.jsx

### [FTR-001] Tutar parse tek virgulu degistiriyor, binlik ayiracli girisi sessizce bozuyor
Sorun: Kullanici Turkce binlik/ondalik formatinda ("1.234,56" gibi, uygulamanin formatTL'nin urettigi bicim) bir tutar yapistirir veya yazarsa, `amount.replace(',', '.')` sadece ILK virgulu noktaya cevirir. "1.234,56" -> "1.234.56" olur, `parseFloat` bunu 1.234 olarak okur, ",56" kismi sessizce kaybolur. Kullaniciya hicbir uyari gitmez, yanlis tutar DB'ye yazilir.
Kanit (satir 525): `const amt = parseFloat(amount.replace(',', '.'));`
Aksiyon: Binlik nokta ayiracini once temizleyip (`.replace(/\./g, '')`) sonra virgulu noktaya cevirecek bir parse helper'i api.js'e eklenip kullanilmali; ya da input'a sadece rakam+tek ayiraci kabul eden bir mask uygulanmali.
Onem: Yuksek · Guven: Kesin

### [FTR-002] Yeni islem varsayilan tarihi UTC gece yarisindan once yerel gunden bir gun geri kayabilir
Sorun: Yeni islem formunda varsayilan tarih `new Date().toISOString().slice(0, 10)` ile hesaplaniyor. `toISOString()` UTC gunu doner; Turkiye (UTC+3) saatiyle 00:00-03:00 arasinda islem girilirse UTC'de hala bir onceki gun oldugu icin form varsayilan olarak dunun tarihini gosterir. Kullanici fark etmezse islem yanlis tarihe kaydedilir.
Kanit (satir 507): `useState(txn?.transaction_date || new Date().toISOString().slice(0, 10))`
Aksiyon: Yerel tarihi kullanan bir helper ekle (orn. `date-fns` ya da manuel `getFullYear/getMonth/getDate` ile "YYYY-MM-DD" uret), UTC kaymasini onle.
Onem: Orta · Guven: Kesin

### [FTR-003] QuickEntry basari mesaji icin unmount sonrasi setState — temizlik yok
Sorun: `handleSubmit` basarili oldugunda `setTimeout(() => setFeedback(null), 2500)` planlaniyor ama bu timer hicbir yerde temizlenmiyor. Kullanici QuickEntry basarili oldugu anla 2.5 saniye icinde baska bir sekmeye gecerse (Transactions paneli unmount olur), zamanlayici yine de tetiklenip unmount olmus bilesende `setFeedback` cagirir; React "Cant perform a React state update on an unmounted component" uyarisi ve potansiyel bellek sizintisina yol acar.
Kanit (satir 366-388, ozellikle 382): `setTimeout(() => setFeedback(null), 2500);` — cleanup/useEffect yok, sadece useState + inline handler icinde.
Aksiyon: Timer id'yi bir ref'te tut, bilesen unmount oldugunda `useEffect` cleanup ile `clearTimeout` cagir; ya da bir "mounted" ref kontrolu ekle.
Onem: Orta · Guven: Kesin

### [FTR-004] Modal: Escape ile kapama ve odak yonetimi yok
Sorun: `Modal` bileseni (TransactionFormModal ve ConfirmDeleteModal'in sarmalayicisi) sadece backdrop tiklamasiyla kapaniyor. Klavye kullanicisi icin Escape tusu ile kapatma yok, modal acildiginda odak iceri tasinmiyor (autoFocus sadece tutar input'unda var, ConfirmDeleteModal'da hic yok), kapandiginda odak tetikleyici butona geri donmuyor. Klavye/screen-reader kullanicisi modal disina tab ile kacabilir (focus trap yok).
Kanit (satir 711-731): `Modal({ title, children, onClose })` icinde sadece `onClick={onClose}` var, `onKeyDown`/Escape veya focus trap mantigi yok.
Aksiyon: `useEffect` ile `keydown` dinleyicisi ekleyip Escape'te `onClose` cagir, acilista `role="dialog" aria-modal="true"` ekle, ilk odaklanabilir elemana focus ver, kapanista tetikleyici elemana focus dondur.
Onem: Orta · Guven: Kesin

### [FTR-005] Tutar input'u serbest metin, harf/karakter sessizce kirpiliyor
Sorun: Tutar alani `type="text"` ve hicbir `inputMode`/pattern kisitlamasi yok. Kullanici "12a3" gibi rakam+harf karisik bir deger girerse `parseFloat` sessizce "12"yi alir, geri kalanini yok sayar; kullaniciya "gecersiz karakter" gibi bir geri bildirim verilmez, sadece nihai tutar beklenenden kucuk cikar.
Kanit (satir 574-582): `<input type="text" value={amount} onChange={(e) => setAmount(e.target.value)} ... />`
Aksiyon: `inputMode="decimal"` ekle, onChange'de sadece rakam/virgul/nokta kabul eden bir regex filtre uygula veya submit oncesi input'un tamaminin sayisal oldugunu (kismi parse degil) dogrula.
Onem: Dusuk · Guven: Kesin

### [FTR-006] Duzenle/Sil ikon butonlari sadece `title` ile etiketleniyor, `aria-label` yok
Sorun: TransactionRow'daki Duzenle ve Sil butonlari sadece gorsel ikon + `title` iceriyor, erisilebilir isim icin `aria-label` yok. Screen reader'lar `title` ozniteligini tutarli sekilde duyurmaz; buton `!p-1` ile kucuk padding aldigindan dokunma hedefi de 44px altinda kaliyor.
Kanit (satir 482-487): `<button onClick={onEdit} className="btn btn-ghost btn-icon !p-1" title="Düzenle">` / ayni desen satir 485.
Aksiyon: `aria-label="Islemi duzenle"` / `aria-label="Islemi sil"` ekle; dokunma hedefini en az 44x44px'e cikar (orn. `!p-2.5`).
Onem: Dusuk · Guven: Kesin
