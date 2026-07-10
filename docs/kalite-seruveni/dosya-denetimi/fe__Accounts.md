# Denetim: frontend/src/panels/Accounts.jsx

### [FAC-001] Dinamik Tailwind sinifi (purge riski)
Sorun: Grup basligindaki ikon rengi `text-${color}-600 dark:text-${color}-400` seklinde calisma-zamaninda birlestirilen bir string ile veriliyor. Tailwind JIT derleyicisi kaynak dosyalarda tam class string'i statik olarak taramadigi icin bu class'lar production build'de purge edilip hic uretilmeyebilir (safelist'e eklenmedigi surece).
Kanit (satir 141): `<Icon className={`w-5 h-5 text-${color}-600 dark:text-${color}-400`} />`
Aksiyon: Renk anahtarlarini tam class stringlerine map eden bir sabit obje kullan (or. `{ positive: 'text-positive-600 dark:text-positive-400', ... }`) ve `color` degeri yerine bu map'ten okunan tam string'i kullan.
Onem: Yuksek · Guven: Kesin

### [FAC-002] Modal bilesninde erisilebilirlik ve klavye destegi eksik
Sorun: `Modal` bileseni (AccountFormModal, PriceUpdateModal, ConfirmDeleteModal'in ortak sarmalayicisi) `role="dialog"`/`aria-modal="true"` tasimiyor, Escape tusuyla kapanmiyor, ve odak (focus) modal acildiginda ilk elemana tasinmiyor / kapaninca tetikleyici butona geri donmuyor (yalnizca AccountFormModal'daki isim input'unda `autoFocus` var, diger iki modalda bile yok — PriceUpdateModal'da var, ConfirmDeleteModal'da hic yok). Ekran okuyucu kullanicilari icin modal'in bir dialog oldugu ve arka plani nasil kapatacaklari belirsiz kalir.
Kanit (satir 628-648): `<div className="fixed inset-0 z-50 bg-black/60 ..." onClick={onClose}> ... <div className="card p-6 ..." onClick={(e) => e.stopPropagation()}>` — role/aria-modal/onKeyDown yok.
Aksiyon: Disaridaki div'e `role="dialog"` `aria-modal="true"` `aria-labelledby` ekle; `useEffect` ile Escape tusunu dinleyip `onClose` cagir; acilista ilk odaklanabilir elemana focus ver, kapaninca tetikleyici butona focus don.
Onem: Yuksek · Guven: Kesin

### [FAC-003] Ikon-only butonlar 44px dokunma hedefinin altinda ve aria-label yok
Sorun: Duzenle/Sil/Kapat/Fiyat guncelle gibi yalnizca ikon iceren butonlarda erisilebilir isim icin sadece `title` attribute'u kullaniliyor (screen reader destegi tutarsiz, klavye/touch kullanicilar icin `aria-label` daha guvenilir). Ayrica `!p-1.5` (6px padding) + `w-3.5 h-3.5` (14px ikon) toplam dokunma alani ~26px civarinda, WCAG 2.5.5 / mobil 44px hedefinin altinda kaliyor.
Kanit (satir 226-231): `<button onClick={onEdit} className="btn btn-ghost btn-icon !p-1.5" title="Düzenle">` / benzer sekilde satir 229, 321, 640.
Aksiyon: `title` yaninda `aria-label` ekle; mobilde dokunma alanini `min-w-[44px] min-h-[44px]` ile buyut veya gorsel boyutu koruyup tikanabilir alani padding/hit-area ile genislet.
Onem: Orta · Guven: Kesin

### [FAC-004] credit_limit=0 durumunda kredi karti detaylari tamamen gizleniyor
Sorun: `a.credit_limit` falsy kontrolu yapiliyor; limit gercekten `0` olarak kaydedilmis bir kredi kartinda (or. kapatilmis/limitsiz kart) hem `AccountRow` icindeki limit/kullanim blogu hem de `utilizationPct` hesaplamasi tamamen atlanir — kullanici karti gorur ama hicbir detay gostermez, sessizce.
Kanit (satir 210-212): `const utilizationPct = a.account_type === 'credit_card' && a.credit_limit ? (a.balance / a.credit_limit) * 100 : null;` ve satir 240: `{a.account_type === 'credit_card' && a.credit_limit && (`
Aksiyon: `a.credit_limit` yerine `a.credit_limit != null` kontrolu kullan; `credit_limit === 0` ise kullanim yuzdesini 0 veya "-" olarak goster, blogu gizleme.
Onem: Orta · Guven: Dogrulanmali (backend'de credit_limit=0 gecerli bir deger mi, dogrulanmadi)

### [FAC-005] Fon kodu bos oldugunda "Fiyat guncelle" TEFAS linki bozuk URL uretebilir
Sorun: `AccountRow` icinde "Fiyat guncelle" butonu sadece `!a.is_emanet` kosuluna bagli (satir 320), `a.fund_code` varligini kontrol etmiyor. `PriceUpdateModal` acildiginda `fund_code` bos/undefined ise TEFAS linki `FonKod=undefined` seklinde gecersiz bir URL'e gider.
Kanit (satir 320-324, 556): `{!a.is_emanet && (<button onClick={onPriceUpdate} ...>Fiyat güncelle</button>)}` ve `const tefasUrl = `https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod=${account.fund_code}`;`
Aksiyon: Buton kosuluna `&& a.fund_code` ekle veya `PriceUpdateModal` icinde `fund_code` yoksa TEFAS linkini gizle.
Onem: Dusuk · Guven: Dogrulanmali (yatirim hesabinda fund_code'un opsiyonel olup olmadigi backend semasindan teyit edilmeli)

### [FAC-006] Kesim/odeme gunu ve taksit sayisi icin ust/alt sinir dogrulamasi yok
Sorun: `parseInt2` yalnizca `NaN` kontrolu yapiyor; kullanici "Kesim gunu" alanina 0, negatif veya 32+ gibi gecersiz bir gun girse form sessizce kabul edip backend'e gonderiyor. Ayni sekilde `remainingInstallments` icin negatif deger engellenmiyor.
Kanit (satir 360-364): `const parseInt2 = (v) => { if (!v || v === '') return null; const n = parseInt(v, 10); return isNaN(n) ? null : n; };` — cagrildigi yerler satir 384-385, 388.
Aksiyon: Kesim/odeme gunu icin `1-31` araligini, taksit sayisi icin `>= 0` kontrolu ekleyip gecersizse `setError` ile kullaniciya bildir.
Onem: Orta · Guven: Kesin

### [FAC-007] Hizli ardisik "Yenile" tiklamalarinda yarisan istek / eski veri geri yazma riski
Sorun: `handleRefresh` `load()`'u await etmeden cagiriyor; kullanici birden fazla kez hizlica tiklarsa (veya `create`/`update` sonrasi `handleSave` da ayni `handleRefresh`'i tetikliyorken) birden fazla `accountsApi.list()` cagrisi es zamanli ucabilir ve gec donen-ama-once baslatilan istek son gelen guncel veriyi ezebilir. Istek iptali (AbortController) veya siralama korumasi yok.
Kanit (satir 49): `const handleRefresh = () => { setRefreshing(true); load(); };` ve satir 34-45'teki `load` icin herhangi bir race-guard yok.
Aksiyon: `AbortController` ile onceki istegi iptal et veya bir `requestId`/ref karsilastirmasi ile yalnizca en son baslatilan istegin sonucunu uygula.
Onem: Dusuk · Guven: Dogrulanmali (tek kullanicili MVP'de pratikte dusuk olasilikli, ama TOCTOU deseni mevcut)

### [FAC-008] `grouped` nesnesi her render'da yeniden hesaplaniyor (memoization eksigi)
Sorun: `grouped` objesi ve icindeki 4 `filter()` cagrisi, bilesen her render edildiginde (or. modal state degisiminde) yeniden hesaplaniyor. Hesap sayisi kucuk oldugu icin performans etkisi ihmal edilebilir, ancak `useMemo` ile onlenebilecek gereksiz bir isleme.
Kanit (satir 99-104): `const grouped = { cash: accounts.filter(...), credit_card: accounts.filter(...), loan: accounts.filter(...), investment: accounts.filter(...) };`
Aksiyon: `useMemo(() => ({...}), [accounts])` ile sar (yalnizca kod kalitesi icin, mevcut olcekte gerekli degil).
Onem: Dusuk · Guven: Kesin
