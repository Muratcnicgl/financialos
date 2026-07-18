# Denetim: frontend/src/components/AccountCard.jsx

> **M86 güncellik:** 🟢 GÜNCEL — 8 bulgu hepsi açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FACC-001] account prop icin null/undefined guard yok
Sorun: Bilesen `account` prop'unun her zaman dolu bir nesne oldugunu varsayiyor. `a = account` sonrasi hemen `a.tip`, `a.ad`, `a.bakiye` gibi alanlara erisiliyor.
Kanit (satir 18, 28, 40, 52): `const a = account;` ... `const meta = typeMeta[a.tip] || typeMeta.cash;` ... `{a.ad}` ... `{formatTL(a.bakiye)}`
Aksiyon: Fonksiyon basina `if (!account) return null;` (veya benzeri erken cikis) eklenmeli; ya da cagiran taraf (Accounts panel) hesap listesini filtrelemeden once garanti etmeli.
Onem: Orta · Guven: Dogrulanmali (cagiran panelin her zaman dolu account gonderip gondermedigi bu dosyadan gorulmuyor)

### [FACC-002] maliyet_per_lot=0 oldugunda satir sessizce gizleniyor
Sorun: `a.maliyet_per_lot &&` falsy kontrolu, deger `0` oldugunda da (gecerli bir maliyet olabilir, ornegin bedelsiz/hediye lot) satirin tamamen render edilmemesine yol aciyor. Kullanici "Maliyet/lot" bilgisinin hic olmadigini dusunebilir.
Kanit (satir 111): `{a.maliyet_per_lot && (`
Aksiyon: `a.maliyet_per_lot != null` (veya `!== undefined && !== null`) kontrolune cevrilmeli.
Onem: Dusuk · Guven: Dogrulanmali (0 maliyetin gercek veride olusup olusmayacagi backend semasina bagli)

### [FACC-003] kullanim_orani undefined oldugunda etiket bos kaliyor
Sorun: `a.kullanim_orani?.toFixed(1)` optional chaining sayesinde hata firlatmiyor ama deger undefined ise ifade `undefined` donuyor ve JSX bunu render etmiyor; sonuc olarak kullanicinin gordugu metin sadece "%" oluyor, hicbir sayisal bilgi yok, hata da yok — sessiz bosluk.
Kanit (satir 67): `%{a.kullanim_orani?.toFixed(1)}`
Aksiyon: `a.kullanim_orani != null ? `${a.kullanim_orani.toFixed(1)}` : '—'` gibi acik bir fallback ekle; formatTL/formatPercent'teki '—' konvansiyonuyla tutarli olur.
Onem: Dusuk · Guven: Kesin

### [FACC-004] Bilinmeyen hesap tipi sessizce "Nakit" olarak etiketleniyor
Sorun: `typeMeta[a.tip] || typeMeta.cash` fallback'i, backend'den `tip` alani beklenmeyen/yeni bir deger (ornegin ileride eklenecek "savings") ile geldiginde kullaniciya yanlislikla "Nakit" ikonu ve etiketi gosteriyor; hicbir uyari/log yok.
Kanit (satir 28): `const meta = typeMeta[a.tip] || typeMeta.cash;`
Aksiyon: Bilinmeyen tip icin norotr bir "Bilinmeyen" etiketi/ikonu kullanilmasi veya console.warn ile isaretlenmesi daha guvenli olur.
Onem: Dusuk · Guven: Dogrulanmali (su an sadece 4 tip destekleniyor, yakin vadede yeni tip eklenip eklenmeyecegi belirsiz)

### [FACC-005] Kullanim orani progress bar'inda erisilebilirlik semantigi eksik
Sorun: Kullanim yuzdesini gorsel olarak temsil eden div (renk + genislik) `role="progressbar"`, `aria-valuenow`, `aria-valuemin/max` gibi ARIA ozellikleri tasimiyor; ekran okuyucu kullanicilari bu bilgiyi sadece yukaridaki metinden (ayni componentte var) alabiliyor, bar'in kendisi anlamsiz bos bir div olarak gorunuyor.
Kanit (satir 70-75): `<div className="h-2 bg-zinc-200 ..."><div className="h-full ..." style={{ width: ... }} /></div>`
Aksiyon: Disaridaki div'e `role="progressbar" aria-valuenow={a.kullanim_orani} aria-valuemin={0} aria-valuemax={100}` eklenebilir. Metin yaninda oldugu icin Kritik degil.
Onem: Dusuk · Guven: Kesin

### [FACC-006] "Fiyat guncelle" butonunun dokunma hedefi 44px altinda olabilir
Sorun: Buton `!py-1.5 !text-xs` ile kucultulmus (padding-y 0.375rem + text-xs satir yuksekligi), toplam yukseklik tipik olarak ~28-30px civarinda kalir; mobilde (D1 hedefi PROJE.md'de belirtilmis) 44px onerilen minimum dokunma alaninin altinda kalma riski var.
Kanit (satir 118-125): `className="mt-2 w-full btn btn-secondary !py-1.5 !text-xs"`
Aksiyon: Mobil breakpoint'te `sm:!py-1.5` gibi ayirip kucuk ekranda daha buyuk padding kullanmak, veya butonu cevreleyen tiklanabilir alani (ornegin dis padding) genisletmek.
Onem: Dusuk · Guven: Dogrulanmali (`.btn`/`.btn-secondary` sinifinin taban padding'i bu dosyada tanimli degil, gercek yukseklik icin CSS dosyasi kontrol edilmeli)

### [FACC-007] sonraki_taksit tarihi Z-suffix kontrolu olmadan formatDate'e geciyor
Sorun: `formatDate(a.sonraki_taksit)` cagrisi, frontend/PROJE.md'de belirtilen "Z suffix yoksa ekle" pattern'ini uygulamiyor; `api.js` icindeki `formatDate` de dogrudan `new Date(isoStr)` yapiyor. Eger `sonraki_taksit` saat bileseni olan bir datetime string ise (sadece tarih degil) ve suffix'siz geliyorsa, JS bunu yerel saat olarak yorumlayip gun kaymasi riski tasir.
Kanit (satir 92-96): `{a.sonraki_taksit && (... {formatDate(a.sonraki_taksit)} ...)}`
Aksiyon: Backend'in bu alani sadece tarih (`YYYY-MM-DD`, saatsiz) olarak dondurdugu dogrulanmali; oyle degilse `formatDate` icinde Z-suffix normalizasyonu eklenmeli.
Onem: Orta · Guven: Dogrulanmali (alanin backend semasinda sadece tarih mi datetime mi oldugu bu dosyadan gorulmuyor)

### [FACC-008] Bilesen React.memo ile sarilmamis
Sorun: `AccountCard` bir liste icinde (muhtemelen Accounts panelinde `.map` ile) render ediliyor olabilir; parent state degistiginde (ornegin baska bir karta tiklama, tema degisimi disi) tum kartlar gereksiz yere yeniden render olabilir. `onPriceUpdateClick` prop'u da parent'ta inline fonksiyon olarak geciliyorsa referans her render'da degisir ve memoizasyon zaten ise yaramaz.
Kanit (satir 17): `export default function AccountCard({ account, onPriceUpdateClick }) {`
Aksiyon: Performans sorunu somut olarak gozlemlenmedigi surece dusuk oncelikli; gozlemlenirse `React.memo` + parent'ta `useCallback` ile `onPriceUpdateClick` sarmalanmali.
Onem: Dusuk · Guven: Dogrulanmali (parent'in render sikligi ve liste boyutu bu dosyadan bilinmiyor)
