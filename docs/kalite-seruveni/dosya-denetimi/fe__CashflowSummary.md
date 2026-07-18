# Denetim: frontend/src/components/CashflowSummary.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FCSU-001] summary undefined/null ise crash
Sorun: Bilesen `summary` prop'unu default deger olmadan doğrudan destructure ediyor. `summary` undefined veya null gelirse (ornegin cagiran tarafta `data.summary` alani backend cevabinda eksikse) `Cannot destructure property 'lowest_balance' of 'undefined'` hatasi ile tum bilesen crash olur, error boundary yoksa beyaz ekran.
Kanit (satir 5): `const { lowest_balance, lowest_date, total_receivable, total_payable, net_flow, crunch_count, opening_balance } = summary;`
Aksiyon: `export default function CashflowSummary({ summary = {} })` gibi bir default deger ekle veya destructure oncesi `if (!summary) return null;` erken donusu koy.
Onem: Orta · Guven: Kesin (kod olarak dogru okundu; tetiklenme kosulu cagiran tarafin veri sozlesmesine bagli, bu yuzden crash riskinin gercek olasiligi Dogrulanmali ama kodun kirilganligi Kesin).

### [FCSU-002] Alan degerleri null/undefined oldugunda karsilastirma ve renk mantigi bozuluyor
Sorun: `lowest_balance`, `net_flow`, `crunch_count` gibi alanlar `undefined` veya `null` gelirse `<` `>=` `>` karsilastirmalari JavaScript'te `false` donebilir veya `NaN` uretebilir (ornegin `undefined < 0` => false, `undefined >= 0` => false). Bu durumda satir 21, 23, 26, 37, 43, 54, 56, 59, 63 hicbir kosulu dogru tetiklemez; renkler ve ikonlar yanlis/varsayilan gorunur, kullaniciya yanlis finansal sinyal verir (orn. gercekte negatif bakiye pozitif/notr renkte gosterilebilir). `formatTL` bu durumlarda '—' basar ama renk/ikon secimi zaten yanlis karar verilmis olur — sayi ile gorsel sinyal tutarsizlasir.
Kanit (satir 21, 26, 37-40, 43, 54, 56, 59): `lowest_balance < 0`, `lowest_balance >= 0 ? ... : ...`, `net_flow >= 0 ? <TrendingUp/> : <TrendingDown/>`, `crunch_count > 0 ? ... : ...`
Aksiyon: Backend'in bu alanlari her zaman sayi olarak garanti ettigi dogrulanmali; degilse bilesen icinde `?? 0` fallback'i ile normalize et (`const safeLowest = lowest_balance ?? 0;` gibi) boylece sayi ile renk/ikon senkron kalir.
Onem: Dusuk · Guven: Dogrulanmali (cockpit/cashflow endpoint'inin bu alanlari her zaman number olarak dondurdugu varsayimina bagli, backend kodu bu denetimin kapsami disinda).

### [FCSU-003] formatDate cagrisi Z-suffix normalizasyonu yapmiyor (frontend/PROJE.md ihlali riski)
Sorun: `lowest_date` `formatDate` ile bicimlendiriliyor; `api.js` icindeki `formatDate` `new Date(isoStr)` cagirirken proje kurallarinda belirtilen `dateStr + (dateStr.endsWith('Z') ? '' : 'Z')` normalizasyonunu uygulamiyor. Eger backend `lowest_date`'i saat bileseni olan (`YYYY-MM-DDTHH:mm:ss`, Z'siz) bir string olarak donuyorsa, JS bunu yerel saat (TR +3) olarak yorumlar ve gun kayabilir. Saf `YYYY-MM-DD` (tarih-only) stringlerinde bu risk yoktur (ISO date-only UTC kabul edilir), ancak alanin gercek formati bu dosyadan dogrulanamiyor.
Kanit (satir 30): `{formatDate(lowest_date, { withYear: true })}` — cagirdigi `formatDate` (`frontend/src/api.js:386-393`) `new Date(isoStr)` kullaniyor, Z-suffix ekleme yok.
Aksiyon: `lowest_date` alaninin backend'de sadece tarih (saatsiz) oldugu dogrulanmali; oyleyse risk yok. Saat iceren bir alan ise `api.js`'deki `formatDate` fonksiyonuna proje standardindaki Z-suffix normalizasyonu eklenmeli (bu dosyanin degil `api.js`'in sorumlulugu, burada cagri noktasi olarak isaretleniyor).
Onem: Dusuk · Guven: Dogrulanmali.

### [FCSU-004] Memoization yok ama gereksiz de degil
Sorun: Bilesen `React.memo` ile sarilmamis; ust bilesen (`Cashflow.jsx`) her render'da yeni `summary` referansi geciriyorsa gereksiz yeniden render olusabilir. Ancak bilesen kucuk ve pahali hesap icermiyor (sadece format cagrilari), bu yuzden performans etkisi ihmal edilebilir duzeyde.
Kanit (satir 4): `export default function CashflowSummary({ summary }) {` — memo sarmalayici yok.
Aksiyon: Aksiyon gerekmez; bilesen hafif oldugu icin memoization onceligi dusuk. Sadece not olarak birakildi.
Onem: Dusuk · Guven: Kesin.

### [FCSU-005] Net akis kartinda toplam gelir/gider isaretleri sabit kodlanmis, gercek deger negatifse yanilyici olabilir
Sorun: `total_receivable` her zaman `+` on-eki ile, `total_payable` on-eksiz gosteriliyor (satir 47, 49). `total_payable` zaten negatif bir sayi olarak geliyorsa dogru gorunur, ancak pozitif bir sayi (mutlak deger, gider tutari) olarak geliyorsa isaretsiz gosterim kullaniciyi yanlis yonlendirebilir (gider pozitif sayi gibi görünür, negatif renkte ama artı degil eksi isareti olmadan).
Kanit (satir 47, 49): `<span className="text-positive-500">+{formatTL(total_receivable)}</span>` ... `<span className="text-negative-500">{formatTL(total_payable)}</span>`
Aksiyon: `total_payable` alaninin backend'de negatif isaretli mi yoksa mutlak deger mi oldugu dogrulanmali; mutlak deger ise `-{formatTL(Math.abs(total_payable))}` seklinde acik isaret eklenmeli.
Onem: Dusuk · Guven: Dogrulanmali.

## Genel Notlar
- Statik JSX yapisi (4 sabit kart) kullaniyor, `.map()` yok — index-key riski bu dosyada gecerli degil.
- Tum backend veri erisimi prop uzerinden geliyor, dogrudan fetch/axios cagrisi yok — kural ihlali yok.
- useEffect kullanimi yok, bu yuzden bagimlilik/temizlik riski bu dosyada gecerli degil.
- Kontrollu/kontrolsuz input yok (salt-okunur gosterim bileseni).
- Erisilebilirlik: bilesen tamamen statik metin/ikon iceriyor, etkilesimli eleman (buton/link) yok; klavye/44px hedef boyutu kurallari bu dosya icin uygulanabilir degil. Renk kontrasti `text-zinc-400` gibi acik tonlarda dogrulanmali ama bu genel tema denetiminin kapsaminda (dimension audit'te ele alinmis olmali).
- Turkce alan adlari (`opening_balance`, `lowest_balance` vb. haric — bunlar backend'den gelen ingilizce cashflow alanlari, projenin `nakit_kasa` tarzi Turkce alanlarindan farkli bir modul) oldugu gibi korunmus, mapping yapilmamis.
