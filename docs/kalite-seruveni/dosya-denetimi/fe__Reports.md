# Denetim: frontend/src/panels/Reports.jsx

### [FRE-001] Gunluk cashflow listesinde index-key kullanimi
Sorun: Ayni tarih grubu icindeki islemler React key olarak dizi index'i ile render ediliyor. Backend'den gelen liste guncellenir/filtrelenirse (or. yeni bir odeme araya girerse) React yanlis DOM node'unu yeniden kullanabilir, ikon/tutar gecici olarak yanlis satirda gorunebilir.
Kanit (satir N): satir 449 `{dayItems.map((item, i) => ( <div key={i} ...`
Aksiyon: Item'a stabil bir id varsa (`item.id` veya `source+date+label` birlesimi) onu key yap.
Onem: Orta · Guven: Kesin

### [FRE-002] Pie/Bar Cell listelerinde index-key
Sorun: Donut ve yatay cubuk grafiklerindeki `Cell` bileşenleri de dizi index'i ile key'leniyor. Kategori sirasi API'den her seferinde ayni gelmezse (or. siralama degisirse) renk-kategori eslesmesi render'lar arasi tutarsiz kayabilir.
Kanit (satir N): satir 215-217 ve 245-247 `items.map((_, i) => <Cell key={i} .../>)`
Aksiyon: `item.category` gibi stabil bir alanı key olarak kullan.
Onem: Dusuk · Guven: Kesin

### [FRE-003] CashflowTimeline `today` prop'u dogrulanmadan Date'e ceviriliyor
Sorun: `CashflowTimeline`, `cashflowData.today` degerini dogrudan `new Date(todayStr + 'T00:00:00')` ile parse ediyor. `today` alani API yanitindan herhangi bir sebeple eksik/undefined gelirse `todayMs` NaN olur, tum nokta pozisyonlari (`pct`) NaN% olarak hesaplanir ve zaman cizelgesi sessizce bozulur (hata firlatilmaz, sadece gorsel olarak kirilir).
Kanit (satir N): satir 433 (`today={cashflowData.today}`) ve satir 560 (`new Date(todayStr + 'T00:00:00')`)
Aksiyon: `todayStr` icin guard ekle (`if (!todayStr) return null;` veya fallback olarak `new Date()` kullan).
Onem: Orta · Guven: Dogrulanmali

### [FRE-004] Ozet kartlarinda tutarli olmayan optional chaining
Sorun: Dosyanin geri kalaninda `data?.grand_total`, `trendData?.items`, `cashflowData?.items` gibi guvenli erisimler kullanilirken, ozet bant blogunda `cashflowData.summary.total_receivable/total_payable/net_flow` dogrudan (optional chaining olmadan) okunuyor. `cashflowItems.length > 0` kontrolu `summary` alaninin var oldugunu garanti etmez; API `items` dolu ama `summary` eksik/malformed donerse TypeError ile panel cokebilir.
Kanit (satir N): satir 409, 415, 421, 425 (`cashflowData.summary.*`)
Aksiyon: `cashflowData.summary?.total_receivable ?? 0` seklinde guvenli erisime cevir.
Onem: Orta · Guven: Dogrulanmali

### [FRE-005] Fetch istekleri AbortController ile iptal edilmiyor
Sorun: Uc useEffect'te de (kategori, trend, cashflow) sadece bir `active` bayragi ile state guncellemesi engelleniyor; agdaki istegin kendisi iptal edilmiyor. Kullanici filtreleri hizli degistirdiginde (or. 30->90 gun art arda tiklama) her tiklama yeni bir HTTP istegi baslatir ve hepsi tamamlanana kadar arka planda calismaya devam eder — bos yere bant genisligi tuketimi ve React StrictMode'da cift-fetch senaryolarinda gecikmis yanit sirasi riski.
Kanit (satir N): satir 84-92, 110-118, 128-136
Aksiyon: `AbortController` ekleyip `fetch`/axios cagrisina `signal` gecir, cleanup'ta `controller.abort()` cagir (api.js bunu destekliyorsa).
Onem: Dusuk · Guven: Dogrulanmali

### [FRE-006] Zaman cizelgesi noktalari klavye/screen-reader ile erisilemiyor
Sorun: `CashflowTimeline` icindeki her nokta salt `title` attribute'u ile bilgi veriyor (tarayici native tooltip), `hover:scale-125` ile etkilesimli gorunuyor ama `tabIndex`, `role`, `aria-label` yok. Klavye kullanicisi bu noktalara hic erisemez, ekran okuyucu `title` attribute'unu guvenilir/tutarli bir sekilde duyurmaz.
Kanit (satir N): satir 572-584 (`<div title={...} className="... hover:scale-125 ...">`)
Aksiyon: `tabIndex={0}`, `role="img"` veya `button`, `aria-label` ekle; gerekirse gorunur/erisilebilir bir tooltip bileseni kullan.
Onem: Orta · Guven: Kesin

### [FRE-007] Filtre buton gruplarinda secili durum ARIA ile iletilmiyor
Sorun: Gun araligi, tur (Gider/Gelir/Tum), trend araligi ve cashflow gun butonlari secili durumu yalnizca CSS sinifiyla (`btn-primary` vs `btn-secondary`) gosteriyor; `aria-pressed` veya `aria-current` yok. Ekran okuyucu kullanicisi hangi filtrenin aktif oldugunu anlayamaz.
Kanit (satir N): satir 149-160, 272-277, 365-370
Aksiyon: Her toggle butonuna `aria-pressed={days === d}` (veya ilgili kosul) ekle.
Onem: Orta · Guven: Kesin

### [FRE-008] CustomTooltip `percentage` alanini guardsiz kullaniyor
Sorun: `d.percentage.toFixed(1)` cagrisi `percentage` alaninin API'den her zaman sayi olarak geldigini varsayiyor. Alan eksik/undefined gelirse (or. backend'de bos kategori/0 toplam kenar durumu) `toFixed` cagrisi TypeError firlatir ve tum grafik karti coker.
Kanit (satir N): satir 42 (`%{d.percentage.toFixed(1)}`)
Aksiyon: `(d.percentage ?? 0).toFixed(1)` seklinde guvenli hale getir.
Onem: Orta · Guven: Dogrulanmali

### [FRE-009] Tarih regex'i yalnizca saf YYYY-MM-DD formatini kabul ediyor
Sorun: `fmtXDate` ve `formatLongDate`, `^(\d{4})-(\d{2})-(\d{2})$` regex'i ile eslesmezse (or. backend bir gun zaman damgasini `T00:00:00` veya `Z` suffix'i ile donduruyorsa) sessizce orijinal ISO string'i oldugu gibi gosterir; kullanici "10 Tem Cuma" yerine "2026-07-10T00:00:00Z" gibi cig bir string gorebilir, hata firlamaz.
Kanit (satir N): satir 490-492, 534-537
Aksiyon: Regex'i esnetip veya once `dateStr.slice(0,10)` ile tarih kismini izole ederek normalize et.
Onem: Dusuk · Guven: Dogrulanmali

### [FRE-010] Gunluk gruplama backend siralamasina sessizce guveniyor
Sorun: `groupByDate` + `Object.entries(...)` ile olusturulan liste, `cashflowItems` dizisinin zaten kronolojik sirali geldigini varsayiyor; dosyada aciktan bir `sort` yok. Backend siralama garantisini bir gun degistirirse (veya ileride filtre/arama eklenirse) takvim gorunumu sessizce karisik sirada render olur.
Kanit (satir N): satir 438 (`Object.entries(groupByDate(cashflowItems))`)
Aksiyon: Render'dan once `cashflowItems` uzerinde acik bir `.sort((a,b) => a.date.localeCompare(b.date))` uygula, backend garantisine bagimli kalma.
Onem: Dusuk · Guven: Dogrulanmali
