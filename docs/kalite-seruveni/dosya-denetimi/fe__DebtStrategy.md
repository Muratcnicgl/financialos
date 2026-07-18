# Denetim: frontend/src/panels/DebtStrategy.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FDS-001] Klavye kullanıcısı ekstra ödeme değerini asla commit edemiyor
Sorun: Range input değeri onChange ile state'e yazılıyor ama backend'e gönderme (handleExtraCommit) sadece onMouseUp ve onTouchEnd ile tetikleniyor. Klavye ile (Tab + ok tuşları) slider'ı odaklayıp değiştiren bir kullanıcı hiçbir zaman mouseup/touchend eventi üretmez, dolayısıyla değişiklik asla fetchData'yı tetiklemez — kullanıcı arayüzde değeri değişmiş görür ama strateji hesabı hiç güncellenmez.
Kanıt (satır 164-174): `onChange={(e) => setExtraMonthly(Number(e.target.value))}` + `onMouseUp={handleExtraCommit}` + `onTouchEnd={handleExtraCommit}` — onKeyUp veya benzeri bir klavye commit yolu yok.
Aksiyon: `onKeyUp` (veya `onBlur`) handler'ı ekleyip aynı `handleExtraCommit`'i çağır; ya da input'u debounce edilmiş onChange ile commit et.
Önem: Yüksek · Güven: Kesin

### [FDS-002] İlk yükleme hatası "Aktif borç yok" boş durumuyla karıştırılıyor
Sorun: `fetchData` catch bloğunda sadece toast gösteriliyor, `data` state'i null olarak kalıyor. Render mantığı `!data` durumunu "Aktif borç yok / en az bir borç hesabı gerekli" kartıyla karşılıyor. Böylece ağ hatası veya 500 durumunda kullanıcı, borcu olmadığı yanlış mesajını görür — gerçek hata mesajı sadece kaybolan bir toast'ta kalır.
Kanıt (satır 98-99, 123-131): catch bloğu `toast.error(...)` dışında state güncellemiyor; alt render `!data || !data.debts || data.debts.length === 0` kontrolüyle "Aktif borç yok" kartını basıyor.
Aksiyon: Ayrı bir `error` state'i tutup hata durumunda "Aktif borç yok" yerine yeniden deneme butonlu bir hata kartı göster.
Önem: Yüksek · Güven: Kesin

### [FDS-003] Label input ile programatik olarak ilişkilendirilmemiş
Sorun: "Opsiyonel ekstra aylık ödeme" `<label>` etiketi `htmlFor` içermiyor, altındaki `<input type="range">` da `id` taşımıyor. Ekran okuyucu kullanıcıları için etiket-kontrol ilişkisi kurulamıyor; input'un `aria-label`/`aria-valuetext` de yok, sadece sayısal değer görsel olarak yanında gösteriliyor.
Kanıt (satır 159-174): `<label className="...">Opsiyonel ekstra aylık ödeme</label>` ve hemen altında `<input type="range" ... />` — ikisi arasında `htmlFor`/`id` veya `aria-*` bağı yok.
Aksiyon: `<label htmlFor="extra-monthly">` + `<input id="extra-monthly" aria-valuetext={TL(extraMonthly)}>` ekle.
Önem: Orta · Güven: Kesin

### [FDS-004] useEffect'te fetch iptali/temizlik yok — unmount sonrası setState ve yarış durumu riski
Sorun: `fetchData` içinde `AbortController` veya unmounted-kontrolü yok. Kullanıcı panelden hızlıca çıkarsa (tab değiştirme) devam eden `debtStrategyApi.compare` isteği tamamlandığında unmount olmuş bileşende `setData`/`setLoading` çağrılır. Ayrıca "Yenile" butonuna art arda basılırsa veya slider hızlı sürüklenirse önceki isteğin geç gelen yanıtı sonraki isteğin sonucunu ezebilir (request race), çünkü hiçbir istek sıra/iptal kontrolü yok.
Kanıt (satır 92-106): `fetchData` fonksiyonunda abort/iptal mekanizması yok; `useEffect(() => { fetchData(0); }, [])` içinde cleanup return edilmiyor.
Aksiyon: `AbortController` ile isteği iptal et veya bir `requestId`/ref ile sadece en son isteğin sonucunu uygula; useEffect'ten cleanup fonksiyonu döndür.
Önem: Orta · Güven: Kesin

### [FDS-005] fmtDate 'Z' suffix'i kontrol etmeden Date'e veriyor
Sorun: Proje kuralı (frontend/PROJE.md "Tarih / Saat") backend'den gelen suffix'siz UTC datetime string'lerinin `Z` eklenerek parse edilmesini şart koşuyor; aksi halde JS local time (TR +3) olarak yorumlar. `fmtDate` doğrudan `new Date(iso)` çağırıyor, suffix kontrolü yok. `payoff_date` ay/yıl granülaritesinde gösterildiği için görünür etkisi sınırlı olabilir ama backend gün/saat içeren bir ISO string döndürürse ay sınırı civarında yanlış ay gösterebilir (ör. ayın 1. günü 03:00'dan önceki saatler bir önceki aya kayabilir).
Kanıt (satır 9-16): `return new Date(iso).toLocaleDateString(...)` — `iso.endsWith('Z')` kontrolü veya suffix ekleme yok.
Aksiyon: Proje konvansiyonuna uy: `new Date(iso + (iso.endsWith('Z') ? '' : 'Z'))`.
Önem: Orta · Güven: Dogrulanmali (payoff_date backend'de sadece tarih mi yoksa datetime mi döndürüyor doğrulanmalı)

### [FDS-006] interest_rate_monthly üzerinde .toFixed(2) null/undefined koruması yok
Sorun: `debt.interest_rate_monthly.toFixed(2)` çağrısı, `debt` mevcut olsa bile `interest_rate_monthly` alanı null/undefined gelirse (ör. faizsiz bir hesap türü) TypeError ile tüm paneli çökertir; component'te error boundary yok.
Kanıt (satır 58): `%{debt.interest_rate_monthly.toFixed(2)}/ay`
Aksiyon: `(debt.interest_rate_monthly ?? 0).toFixed(2)` şeklinde güvenli hale getir.
Önem: Orta · Güven: Dogrulanmali (backend şemasının bu alanı her zaman sayısal döndürüp döndürmediği doğrulanmalı)

### [FDS-007] months_difference alanı eksikse "NaN ay" gösterilebilir
Sorun: `data.comparison.months_difference !== 0` kontrolü, alan `undefined` olduğunda da `true` döner (undefined !== 0), bu durumda `Math.abs(undefined)` → `NaN` render edilir ve kullanıcıya "NaN ay" gibi anlamsız bir değer gösterilir.
Kanıt (satır 216-221): `{data.comparison.months_difference !== 0 && (...)}` ve `{Math.abs(data.comparison.months_difference)} ay`.
Aksiyon: `typeof data.comparison.months_difference === 'number' && data.comparison.months_difference !== 0` şeklinde tipi de kontrol et.
Önem: Düşük · Güven: Dogrulanmali (backend bu alanı garanti sayısal döndürüyorsa risk teorik kalır)

### [FDS-008] Slider dokunma hedefi ve odak görünürlüğü doğrulanmadı
Sorun: `<input type="range">` için tarayıcı varsayılan thumb boyutu genelde 44px altında kalır (mobil dokunma hedefi kuralı); ayrıca özel bir `focus-visible` stili tanımlanmamış, sadece `accent-brand-500` uygulanmış. Mobilde D1 hedefi (responsive/dokunma) açısından thumb boyutu küçük kalabilir.
Kanıt (satır 173): `className="w-full accent-brand-500"` — thumb boyutu/focus ring için ek stil yok.
Aksiyon: Tailwind ile `[&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6` benzeri thumb boyutlandırma ve `focus-visible:ring` ekle.
Önem: Düşük · Güven: Dogrulanmali (gerçek render'da thumb boyutu ölçülmedi, statik koddan çıkarım)
