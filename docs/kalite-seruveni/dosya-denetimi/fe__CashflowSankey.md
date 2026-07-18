# Denetim: frontend/src/components/CashflowSankey.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FCS-001] sankey prop null/undefined ise crash riski
Sorun: Bilesen `sankey` prop'unu dogrudan `sankey.nodes.length` seklinde okuyor, prop'un kendisi hic kontrol edilmiyor.
Kanit (satir 53): `if (!sankey.nodes.length || !sankey.links.length) {`
Aksiyon: Fonksiyon basina `if (!sankey?.nodes?.length || !sankey?.links?.length)` gibi optional chaining ekle, ya da parent'ta garanti varsa PropTypes/defaultProps ile belgele.
Onem: Yuksek · Guven: Dogrulanmali (su an tek cagiran `Cashflow.jsx:167` `data.sankey` gonderiyor; backend yaniti her zaman `sankey` alanini dolduruyor mu dogrulanmadi)

### [FCS-002] CustomNode icinde payload.name kontrolsuz
Sorun: `payload.name` degeri once `.length` sonra `.slice` ile kullaniliyor; `payload` veya `payload.name` eksikse TypeError firlar.
Kanit (satir 31): `{payload.name.length > 14 ? payload.name.slice(0, 13) + '…' : payload.name}`
Aksiyon: `(payload.name ?? '')` ile guvenli varsayilan ekle veya erken don.
Onem: Orta · Guven: Dogrulanmali (recharts Sankey her node icin name garanti ediyor mu netlestirilmeli)

### [FCS-003] data nesnesi her render'da yeniden kuruluyor
Sorun: `data.nodes` / `data.links` map'leri useMemo olmadan her render'da yeniden hesaplaniyor; Sankey/ResponsiveContainer bu referansi prop olarak aliyor, gereksiz yeniden hesaplama/layout tetikleyebilir.
Kanit (satir 64-71): `const data = { nodes: sankey.nodes.map(...), links: sankey.links.map(...) };`
Aksiyon: `useMemo(() => ({...}), [sankey])` ile sar.
Onem: Dusuk · Guven: Kesin

### [FCS-004] Negatif/NaN link degerleri sessizce 0.01'e yuvarlaniyor
Sorun: `Math.max(l.value, 0.01)` negatif bir deger veya `NaN` gelirse hatali/anlamli olmayan bir sonucu (NaN icin `NaN`, negatif icin `0.01`) sessizce UI'ya tasiyor; veri kalitesi sorunu loglanmiyor/uyarilmiyor.
Kanit (satir 69): `value: Math.max(l.value, 0.01),  // recharts sıfır değeri desteklemiyor`
Aksiyon: `Number.isFinite(l.value) && l.value > 0` kontrolu ekleyip gecersiz linkleri filtrele veya console.warn ile isaretle.
Onem: Orta · Guven: Kesin

### [FCS-005] SVG grafik icin erisilebilirlik etiketi yok
Sorun: `ResponsiveContainer`/`Sankey` govdesi herhangi bir `aria-label`, `role="img"` veya metinsel ozet icermiyor; ekran okuyucu kullanicilari diyagramin icerigini alamiyor.
Kanit (satir 78-92): `<div className="w-full" style={{ height: 220 }}> <ResponsiveContainer ...><Sankey ...>`
Aksiyon: Sarmalayici div'e `role="img" aria-label="Nakit akış diyagramı: ..."` ekle veya gorsel olmayan bir ozet (ornegin tablo) sr-only olarak sagla.
Onem: Orta · Guven: Dogrulanmali (proje genelinde grafik bilesenleri icin ortak bir a11y konvansiyonu olup olmadigi bu dosyadan gorulemedi)

### [FCS-006] CustomNode'da index prop'u kullanilmiyor
Sorun: `index` destructure ediliyor ama govdede hic referans edilmiyor.
Kanit (satir 11): `function CustomNode({ x, y, width, height, index, payload }) {`
Aksiyon: Kullanilmiyorsa parametre listesinden cikar (olu kod).
Onem: Dusuk · Guven: Kesin

### [FCS-007] Node tipi icin magic string + sessiz fallback
Sorun: `payload.type` degeri `NODE_COLORS` anahtarlariyla ('income' | 'cash' | 'expense') karsilastiriliyor; bu degerler paylasilan bir sabit/enum olarak tanimli degil. Backend'den beklenmeyen bir `type` gelirse hic uyari vermeden `cash` rengine dusuyor.
Kanit (satir 12): `const color = NODE_COLORS[payload.type] || NODE_COLORS.cash;`
Aksiyon: En azindan dev modda `console.warn` ile beklenmeyen type'i isaretle, veya backend ile paylasilan bir tip listesi/sabit dosyasi kullan.
Onem: Dusuk · Guven: Dogrulanmali (backend'in sankey.nodes[].type alanini nasil urettigi bu dosyadan dogrulanamadi)

### [FCS-008] CustomTooltip node hover durumunda anlamsiz cikti verebilir
Sorun: Tooltip icerigi sadece link (source/target) sekli varsayiyor; kullanici bir node uzerine gelirse recharts payload'i `name`/`value` seklinde olabilir ve `p.source?.name` / `p.target?.name` ikisi de undefined donerek "→" bos gorunumlu bir tooltip render edilebilir.
Kanit (satir 39-44): `const p = payload[0].payload; ... {p.source?.name ?? ''} → {p.target?.name ?? ''}`
Aksiyon: `p.source && p.target` varliğini kontrol edip yoksa node icin ayri bir govde (`{p.name}: {formatTL(p.value)} TL`) render et.
Onem: Orta · Guven: Dogrulanmali (recharts'in node hover'da Tooltip'i tetikleyip tetiklemedigi ve payload sekli bu dosyadan kesin dogrulanamadi)

### [FCS-009] Tooltip'te p.value dogrulanmadan formatTL'ye veriliyor
Sorun: `formatTL(p.value)` cagrisi oncesi `p.value`'nun sayi oldugu kontrol edilmiyor; eksik/NaN deger durumunda kullaniciya anlamsiz bir TL degeri gosterilebilir.
Kanit (satir 46): `{formatTL(p.value)} TL`
Aksiyon: `formatTL` fonksiyonunun (api.js) NaN/undefined durumunu nasil isledigini dogrula; gerekiyorsa burada erken guard ekle.
Onem: Dusuk · Guven: Dogrulanmali (formatTL'nin ic davranisi bu dosyadan gorulemedi)
