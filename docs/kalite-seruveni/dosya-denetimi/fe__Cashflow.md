# Denetim: frontend/src/panels/Cashflow.jsx

> **M86 güncellik:** 🟢 GÜNCEL — FCF-001/002 açık; FCF-004 bayat


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FCF-001] handleRefresh icin cleanup/iptal mekanizmasi yok
Sorun: Ana veri yukleme useEffect'i (satir 31-48) unmount veya hizli parametre degisiminde `cancelled` bayragiyla korunuyor, ama `handleRefresh` (satir 50-57) ayni korumaya sahip degil. Kullanici Yenile'ye basip component unmount olursa ya da art arda birden fazla kez tiklarsa, gec donen bir `.then` cagrisi unmount sonrasi `setData`/`setRefreshing` calistirir (React "state update on unmounted component" uyarisi) veya daha eski bir istegin cevabi daha yeni istegi ezebilir (race condition).
Kanit (satir 50-57):
```
const handleRefresh = () => {
  setRefreshing(true);
  cashflowApi.getForecast({ days: horizon, include: [...include], crunchThreshold })
    .then(r => setData(r))
    .catch(e => toast.error('Yenileme hatası', { detail: e.message }))
    .finally(() => setRefreshing(false));
};
```
Aksiyon: `handleRefresh`'i de bir `cancelled`/istek-id koruma deseniyle sarmala, veya ana useEffect'i tetikleyecek bir "refreshKey" state'i ekleyip tek bir fetch yolunu tekrar kullan.
Onem: Yuksek · Guven: Dogrulanmali (davranis unmount/tiklama zamanlamasina bagli, ama kod deseni eksik oldugu kesin)

### [FCF-002] Hata durumunda hicbir UI govdesi render edilmiyor
Sorun: `useEffect` hata aldiginda `catch` blogu sadece toast gosterir, `data` `null` kalir; `finally` ile `loading` de `false` olur. Render agacinda `loading` icin (148-153) ve `data` icin (156-170) ayri kosullu bloklar var, ikisi de false/null oldugunda hicbir sey render edilmiyor — kullanici bos bir panelle bas basa kaliyor, toast kaybolduktan sonra hatanin tekrar denenebilecegine dair hicbir gorsel ipucu yok.
Kanit (satir 148 ve 156):
```
{loading && ( ... )}
...
{!loading && data && ( ... )}
```
Aksiyon: `!loading && !data` durumu icin bir hata/bos-durum bileseni (yeniden dene butonu ile) ekle.
Onem: Orta · Guven: Kesin

### [FCF-003] Varsayilan filtre seti FILTER_CHIPS ile senkron degil (magic string tekrari)
Sorun: `include` state'inin baslangic degeri (satir 22) `'incomes', 'expenses', 'receivables', 'payables'` string'lerini elle tekrar yaziyor; bu anahtarlar zaten `FILTER_CHIPS` dizisinde (satir 12-17) tanimli. Biri FILTER_CHIPS'e yeni bir chip ekleyip satir 22'yi guncellemeyi unutursa, yeni filtre varsayilan olarak kapali baslar ve bu sessizce gerceklesir.
Kanit (satir 22): `useState(new Set(['incomes', 'expenses', 'receivables', 'payables']))`
Aksiyon: `new Set(FILTER_CHIPS.map(c => c.key))` kullanarak tek kaynaktan turet.
Onem: Dusuk · Guven: Kesin

### [FCF-004] Esik input'unda virgul degistirme sadece ilk esleseni kapsiyor
Sorun: `applyThreshold` (satir 68-71) `thresholdInput.replace(',', '.')` cagirir; `replace` global bayrak (`/g`) olmadan sadece ilk virgulu degistirir. Kullanici "1,234,56" gibi binlik ayiracli bir deger girerse sonuc "1.234,56" olur ve `parseFloat` bunu `1.234` olarak keser, geri kalan sessizce atilir.
Kanit (satir 69): `const val = parseFloat(thresholdInput.replace(',', '.')) || 0;`
Aksiyon: Tum virgulleri kapsayacak sekilde `replace(/,/g, '.')` kullan veya binlik ayiraci ayri temizle.
Onem: Dusuk · Guven: Kesin

### [FCF-005] data.days uzunluguna guvensiz erisim
Sorun: Basliktaki ozet metni (satir 79-83) `data.days.length` okur; bu blok `data` truthy oldugunda calisiyor ama `data.days`'in her zaman bir dizi oldugu backend sozlesmesine dayanan bir varsayim — API beklenmedik sekilde `days` alanini eksik/null donerse (or. kismi hata payload'i) burada `TypeError` firlar ve tum panel crash olur.
Kanit (satir 81): `{data.start_date} → {data.end_date} · {data.days.length} gün`
Aksiyon: `data.days?.length ?? 0` gibi guvenli erisim ekle veya API yanitini panel seviyesinde sema dogrulamasindan gecir.
Onem: Orta · Guven: Dogrulanmali (backend'in days alanini her zaman dizi dondurdugu dogrulanamadi)

### [FCF-006] Toggle butonlarinda aria-pressed / erisilebilir durum bilgisi yok
Sorun: Ufuk (horizon) toggle butonlari (satir 89-101) ve filtre chip butonlari (satir 115-127) secili/secili-degil durumunu sadece arka plan rengiyle (bg-brand-500 vs. varsayilan) gosteriyor. Ekran okuyucu kullanicilari icin `aria-pressed` veya benzeri bir durum ozniteligi yok, bu yuzden hangi ufkun/filtrenin aktif oldugu duyurulmuyor.
Kanit (satir 90-98 ve 116-124): butonlarda `aria-pressed` ya da `role="group"` yok, sadece `className` kosullu.
Aksiyon: Her toggle butonuna `aria-pressed={horizon === d}` / `aria-pressed={include.has(key)}` ekle, gruplarina `role="group"` + `aria-label` ver.
Onem: Orta · Guven: Kesin

### [FCF-007] Esik input'u icin gorunur/erisilebilir etiket yok
Sorun: Esik input'u (satir 130-144) sadece bitisik bir `<span>Eşik:</span>` metni ve `title` özniteligiyle aciklaniyor; `<label htmlFor>` iliskisi veya `aria-label` yok. `title` ozniteligi ekran okuyucu ve dokunmatik cihaz destegi acisindan guvenilmez bir erisilebilirlik kaynagi.
Kanit (satir 131-142): `<span>Eşik:</span>` ile `<input ... title="Sıkışma eşiği (TL)" />` arasinda programatik bir iliski yok.
Aksiyon: input'a `aria-label="Sıkışma eşiği (TL)"` ekle veya span'i `<label htmlFor="crunch-threshold">` yapip input'a eslesen `id` ver.
Onem: Dusuk · Guven: Kesin

### [FCF-008] Dokunma hedefi boyutlari 44px altinda kalabilir
Sorun: Ufuk toggle butonlari (`px-3 py-1.5`, satir 93), Yenile butonu (`!text-xs` ile kucultulmus, satir 105) ve filtre chip'leri (`chip` sinifi, satir 119) tipografiye gore ~28-32px yukseklikte olusuyor gibi gorunuyor; bu WCAG 2.5.5 / mobil dokunma hedefi (44x44px) esiginin altinda kalabilir.
Kanit (satir 93, 105, 119): `className="px-3 py-1.5 text-xs ..."`, `className="btn btn-secondary !text-xs"`, `className="chip ..."`
Aksiyon: `.btn`/`.chip` global siniflarinin gercek render yuksekligini olc; 44px altindaysa mobilde `min-h-[44px]` gibi bir alt sinir ekle.
Onem: Dusuk · Guven: Dogrulanmali (gercek yukseklik `.btn`/`.chip` global CSS tanimina bagli, bu dosyada gorunmuyor)

### [FCF-009] toast bagimliligi useEffect disinda birakilmis
Sorun: Ana veri yukleme effect'i (satir 31-48) `toast.error` cagiriyor ama `eslint-disable-line react-hooks/exhaustive-deps` ile `toast` bagimlilik listesinden cikarilmis. `useToast()` her render'da yeni bir referans donuyorsa (Toast.jsx bu denetimin kapsami disinda, dogrulanamadi) bu satirda stale closure riski yoktur cunku sadece cagriliyor, ama `toast` referansinin kendisi degisebilir bir context'ten geliyorsa gelecekte fonksiyon govdesi degisirse sessiz bug'a donusebilir.
Kanit (satir 48): `}, [horizon, includeKey, crunchThreshold]);  // eslint-disable-line react-hooks/exhaustive-deps`
Aksiyon: `useToast()`'un stabil (memoized) bir referans dondurdugunu dogrula; degilse `toast` yerine sadece `toast.error` fonksiyonunu `useRef` ile sabitle veya bagimliliga ekle.
Onem: Dusuk · Guven: Dogrulanmali (Toast.jsx incelenmedi)

### [FCF-010] handleRefresh, useEffect ile ayni fetch mantigini tekrarliyor
Sorun: `handleRefresh` (satir 50-57) ile ana `useEffect` (satir 35-45) icindeki `cashflowApi.getForecast` cagrisi, parametreleri ve hata/finally davranisi neredeyse birebir ayni kodu iki yerde tutuyor. Ileride API imzasi veya hata isleme degisirse iki yeri ayni anda guncellemek gerekecek.
Kanit (satir 35-45 vs 53-56): iki ayri `cashflowApi.getForecast({ days: horizon, include: [...include], crunchThreshold })` zinciri.
Aksiyon: Ortak bir `fetchForecast(isManualRefresh)` yardimci fonksiyonuna ya da ayni effect'i tetikleyen bir "refreshToken" state'ine cikar (bkz. FCF-001 ile birlikte cozulebilir).
Onem: Dusuk · Guven: Kesin
