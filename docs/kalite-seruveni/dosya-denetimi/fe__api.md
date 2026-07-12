# Denetim: frontend/src/api.js

### [FAPI-001] ApiError mesaji parse edilemeyen/null JSON govdesinde "null" string'i oluyor
Sorun: `data?.detail ?? data` sonucu `null` oldugunda (ornegin 500 hatasi JSON govdesi `null` donerse ya da `res.json()` catch'e dusup `data = null` atandiysa) `ApiError` constructor'indaki mesaj hesaplamasi yanlis dala giriyor. `typeof null !== 'string'`, `null?.message` -> `undefined`, ardindan `undefined || JSON.stringify(null)` calisiyor ve `JSON.stringify(null)` **"null" stringini** dondurur — bu deger truthy oldugu icin `|| \`HTTP ${status}\`` fallback'ine hic ulasilmiyor. Kullaniciya "null" diye anlamsiz bir hata mesaji gosterilir.
Kanit (satir N): 18-26 (constructor), 74-77 (JSON parse hatasinda `data = null`), 84 (`const detail = data?.detail ?? data`)
Aksiyon: Mesaj hesaplamasinda `detail == null` durumunu once ele al: `detail == null ? \`HTTP ${status}\` : (typeof detail === 'string' ? detail : (detail?.message || JSON.stringify(detail) || \`HTTP ${status}\`))`.
Onem: Orta · Guven: Kesin

### [FAPI-002] markPaid varsayilan tarihi UTC'den aliniyor, Turkiye saatinde gece yarisi civari yanlis gunu isaretler
Sorun: `date` parametresi verilmezse `new Date().toISOString().slice(0, 10)` kullaniliyor. `toISOString()` UTC'ye gore doner; Turkiye UTC+3 oldugu icin yerel saat 00:00-02:59 arasinda (yani gece yarisindan sonraki ilk ~3 saat) UTC tarihi hala bir onceki gundedir. Kullanici gece yarisindan hemen sonra "odendi" isaretlerse borc bir onceki tarihe kaydedilir.
Kanit (satir N): 174-177
Aksiyon: Yerel tarihi kullan, ornegin `date || new Date().toLocaleDateString('sv-SE')` (YYYY-MM-DD, yerel saat) veya `date-fns`/manuel yil-ay-gun formatlama; UTC slice kullanma.
Onem: Yuksek · Guven: Kesin

### [FAPI-003] actionsApi.reject, reason verilmediginde JSON.stringify(null) = "null" govdesini Content-Type: application/json ile gonderiyor
Sorun: `reason` falsy oldugunda `body: null` geciliyor. `request()` icinde govde kontrolu `if (body !== undefined)` seklinde — `null !== undefined` oldugu icin bu blok calisir, `Content-Type: application/json` header'i eklenir ve `JSON.stringify(null)` yani literal `"null"` metni istek govdesi olarak gonderilir. Backend `{reason?: string}` gibi bir Pydantic modeli bekliyorsa `null` govdesi (JSON `null`, obje degil) 422 dondurebilir; en azindan govdesiz istek niyeti bozulmus oluyor.
Kanit (satir N): 216-219 (cagrı), 53-56 (`body !== undefined` kontrolu)
Aksiyon: `reject`'te govdeyi tamamen atlamak icin `reason ? { reason } : undefined` kullan (null yerine undefined), boylece `request()` Content-Type/JSON.stringify adimini atlar.
Onem: Orta · Guven: Kesin

### [FAPI-004] formatPercent negatif degerlerde Turkce format kurallarina aykiri cikti uretiyor
Sorun: `showSign && value > 0` kontrolu sadece pozitif degerler icin `+` isareti ekliyor; negatif degerlerde `sign = ''` kalıyor ama `toFixed(2)` zaten `-5.30` gibi eksi isaretini sayinin basina koyuyor. Sonuc `${sign}%${formatted}` = `"%-5,30"` oluyor — yuzde isareti eksi isaretinden once geliyor, beklenen Turkce gösterim `"-%5,30"` degil.
Kanit (satir N): 376-381
Aksiyon: Negatif degerde isareti disari al: `const abs = Math.abs(value).toFixed(2).replace('.', ','); return \`${value < 0 ? '-' : sign}%${abs}\`;`
Onem: Orta · Guven: Kesin

### [FAPI-005] formatDate, proje genelinde belgelenen 'Z' suffix normalizasyonunu uygulamiyor
Sorun: `frontend/PROJE.md` acikca "Backend'den gelen datetime string'ler UTC ama Z suffix'siz olabilir... Parse ederken `new Date(dateStr + (dateStr.endsWith('Z') ? '' : 'Z'))`" kuralini tanimliyor, ancak `formatDate` bunu uygulamadan dogrudan `new Date(isoStr)` cagiriyor. Su anki cagiranlarin (transaction_date, due_date, paid_date vb.) hepsi backend'de `Column(Date)` oldugu icin bu spesifik durumda kaymiyor, ama fonksiyon export edilen genel-amacli bir yardimci — ileride bir DateTime alani (saat bilgisi tasiyan) buraya verilirse Turkiye saatinde gun kaymasi riski var; kuralin merkezi noktasi (api.js) tam da bu korumayi uygulamasi gereken yer.
Kanit (satir N): 386-393
Aksiyon: `formatDate` icine de ayni Z-suffix normalizasyonunu ekle (ornegin saat iceren string'ler icin), boylece cagiran taraf DateTime alani gecerse bile guvenli olsun.
Onem: Dusuk · Guven: Dogrulanmali

### [FAPI-006] request() iptal/timeout mekanizmasi sunmuyor — AbortController/signal destegi yok
Sorun: `request(path, options)` hicbir `signal` parametresi kabul etmiyor ve fetch cagrisina `AbortController` baglamiyor. Panel'ler (ornegin hizli yazilan arama/otomatik yenileme senaryolarinda) devam eden bir istegi iptal edemiyor; unmount sonrasi gec donen bir cevap yine de `await` zincirinden gecip cagiran kodda "stale" state guncellemesine yol acabilir. Ayrica backend yanit vermezse fetch sinirsiz surede beklemede kalir (timeout yok).
Kanit (satir N): 33-64
Aksiyon: `request()` imzasina opsiyonel `signal` parametresi ekle ve/veya `AbortController` + `setTimeout` ile varsayilan bir istek timeout'u uygula; cagiran panel'lerin `useEffect` cleanup'inda iptal edebilmesini sagla.
Onem: Orta · Guven: Dogrulanmali

### [FAPI-007] Non-JSON (orn. HTML) hata govdeleri oldugu gibi kullaniciya mesaj olarak tasiniyor
Sorun: `content-type` `application/json` icermeyen bir hata cevabinda (`res.ok === false`, ornegin proxy/gateway 502/504 HTML sayfasi) `data = await res.text()` ile ham metin okunuyor, ardindan `detail = data?.detail ?? data` -> string oldugu icin `.detail` undefined, dolayisiyla `detail = data` (tum HTML govdesi). `ApiError` constructor'i `typeof detail === 'string'` oldugu icin bu ham HTML/metni dogrudan `message` yapiyor; UI bunu kullaniciya gosterirse cirkin/anlasiz (ve olasi sunucu bilgisi sizdiran) bir hata mesaji cikar.
Kanit (satir N): 78-79 (`data = await res.text()`), 82-86 (`ApiError` firlatma)
Aksiyon: JSON olmayan hata govdelerinde govdeyi dogrudan mesaj yapmak yerine kisa, sabit bir mesaj kullan (`\`HTTP ${res.status}\``) ve ham metni sadece `raw`/`detail` alaninda tut, `message` icin kullanma.
Onem: Dusuk · Guven: Dogrulanmali

### [FAPI-008] "FUND PRICE (3)" bolum basligi ile gercek fundPriceApi tanimi arasinda REPORTS bolumu araya girmis
Sorun: 228. satirdaki `// FUND PRICE (3)` yorum basligi hemen ardindan bos, gercek `fundPriceApi` objesi ise 244. satirda REPORTS bolumunden (231-242) sonra tanimlaniyor. Yorum/kod sirasi karismis; okuyan biri icin yaniltici (baslik burada obje bekletirken araya baska bir API grubu girmis).
Kanit (satir N): 227-244
Aksiyon: `// FUND PRICE (3)` basligini doğrudan `fundPriceApi` tanimindan hemen once tasi (REPORTS bolumunden sonra, 244. satirin ustune).
Onem: Dusuk · Guven: Kesin
