# Denetim: frontend/src/panels/Goals.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FGO-001] Promise.all kismi hata durumunda eski hedefin allocation/rule verisi ekranda kalabilir
Sorun: `GoalDetailModal` icinde `loadDetail` iki cagriyi `Promise.all` ile paralel yapiyor. Herhangi biri reddedilirse `catch` bloguna dusuluyor ve `setAllocations`/`setRules` hic cagrilmiyor. Kullanici bir hedeften digerine gectiginde (ayni modal instance'i yeniden acilmadan `goal` prop'u degisirse) ya da `onRefresh` sonrasi ikinci cagri basarisiz olursa, ekranda onceki hedefin/durumun allocation-rule listesi yanlislikla gorunmeye devam eder.
Kanit (satir N): 193-206, 208
Aksiyon: Hata durumunda `setAllocations([])` ve `setRules([])` ile state'i temizle veya ayri try/catch ile kismi basariyi da goster; en azindan hata mesaji yaninda "veri guncel olmayabilir" uyarisi ekle.
Onem: Yuksek · Guven: Dogrulanmali (kod akisi acik ama modal'in ayni instance'ta goal degistirme senaryosu UI'da fiilen tetiklenebiliyor mu, calisirken dogrulanmali)

### [FGO-002] Async islemlerde unmount sonrasi state guncelleme korumasi yok
Sorun: `fetchGoals`, `loadDetail`, `handleRefresh`, `handleSubmit` (wizard) ve her iki `handleDelete` fonksiyonu, cagri devam ederken bilesen unmount olursa (ornegin kullanici arka plana tiklayip modali kapatirsa) donen promise cozuldugunde hala `setLoading`/`setRefreshing`/`setSaving`/`setAllocations` gibi state guncellemeleri calistirir. `isMounted`/`AbortController` gibi bir koruma yok.
Kanit (satir N): 28-38, 193-206, 210-221, 386-405, 291-299, 332-340
Aksiyon: Bilesenlerde bir `isMounted` ref'i veya `AbortController` ile cleanup ekle; en azindan React 18'de bu bir warning'e yol acmasa da network yariş durumlarinda gereksiz/geç state guncellemesini engelle.
Onem: Orta · Guven: Dogrulanmali

### [FGO-003] `r.criteria` undefined ise ekranda literal "undefined" metni gorunur
Sorun: `RulesTab` icinde `allocationLabel` oncesi `{JSON.stringify(r.criteria)} → {allocationLabel(r)}` dogrudan render ediliyor. `r.criteria` `undefined` gelirse `JSON.stringify(undefined)` `undefined` (string degil, JS `undefined` degeri) doner ve React bunu `"undefined"` metni olarak basar. `null` gelirse `"null"` yazdirir. Hicbir guard/fallback yok.
Kanit (satir N): 358
Aksiyon: `JSON.stringify(r.criteria ?? {})` veya bos/gecersiz criteria icin kullaniciya anlamli bir metin ("Kosul yok") goster.
Onem: Orta · Guven: Kesin (kod okuma ile dogrulandi; backend'in criteria'yi hep dolu gonderip gondermedigi ayri sorudur)

### [FGO-004] Modallerde klavye erisimi ve ARIA semantik eksik
Sorun: `GoalDetailModal` ve `GoalCreateWizard` overlay'leri sadece mouse click ile kapaniyor (`onClick={onClose}` + `stopPropagation`). Escape tusuyla kapama yok, focus trap yok, `role="dialog"`/`aria-modal="true"`/`aria-labelledby` gibi ARIA ozellikleri hic kullanilmamis. Klavye/ekran okuyucu kullanicisi modali kapatamaz veya modal disina odaklanabilir.
Kanit (satir N): 223-227, 407-411
Aksiyon: `useEffect` ile `keydown` dinleyicisi ekleyip Escape'te `onClose` cagir (cleanup ile kaldir), modal div'e `role="dialog"` `aria-modal="true"` ekle, acilista odagi ilk elemana tasi.
Onem: Yuksek · Guven: Kesin

### [FGO-005] Ikon-only butonlarda aria-label yok
Sorun: Kapatma (X) butonlari ve satir-silme butonlari sadece `lucide-react` ikonu iceriyor, erisilebilir isim (aria-label veya görünür metin) yok. Ekran okuyucu kullanicisi butonun ne yaptigini anlayamaz.
Kanit (satir N): 248-250 (modal kapat), 316-321 (allocation sil), 362-367 (kural sil), 421-423 (wizard kapat)
Aksiyon: Her butona `aria-label="Kapat"` / `aria-label="Allocation'ı sil"` / `aria-label="Kuralı sil"` ekle.
Onem: Orta · Guven: Kesin

### [FGO-006] Kucuk ikon-only dokunma alanlari 44px hedefinin altinda
Sorun: X/sil butonlarinda `w-3.5 h-3.5` / `w-5 h-5` ikon boyutu var ama butona ekstra padding/min-width-height verilmemis; fiili tiklanabilir alan buyuk olasilikla 44x44px mobil dokunma hedefinin altinda kaliyor (roadmap D1 mobil odagi ile celisir).
Kanit (satir N): 248-250, 316-321, 362-367, 421-423
Aksiyon: Butonlara `p-2` (veya esdegeri) ve/veya `min-w-[44px] min-h-[44px]` ekle.
Onem: Orta · Guven: Dogrulanmali (gercek render'da olculen piksel boyutu teyit edilmeli)

### [FGO-007] Silme islemlerinde onay adimi ve cift-tiklama korumasi yok
Sorun: `AllocationsTab.handleDelete` ve `RulesTab.handleDelete` hicbir onay dialogu olmadan dogrudan DELETE cagrisi yapiyor; buton disable/pending state'i de yok, bu yuzden kullanici hizli cift tiklarsa ayni id icin iki DELETE istegi gidebilir (ikincisi muhtemelen backend'de 404/hata dondurur ve toast ile kullaniciya yaniltici bir hata gosterilebilir).
Kanit (satir N): 291-299, 332-340
Aksiyon: Silmeden once basit bir onay (`window.confirm` veya kucuk bir onay UI'i) ekle; silme sirasinda o satira ozel bir `deletingId` state'i ile butonu disable et.
Onem: Orta · Guven: Kesin (kod akisinda koruma yok)

### [FGO-008] `formatDate` UTC 'Z' suffix kuralina bagimli, `projected_completion_date` icin dogrulanmadi
Sorun: `frontend/PROJE.md` kuralina gore backend'den gelen datetime string'leri `Z` suffix'siz olabilir ve JS bunlari local time yorumlayip Turkiye'de +3 saat kaydirabilir. `GoalCard` `goal.projected_completion_date` degerini dogrudan `formatDate`'e veriyor (api.js icinde `new Date(isoStr)` — Z ekleme yok). Eger backend bu alani salt tarih (`YYYY-MM-DD`) yerine timezone-naive datetime olarak donuyorsa gun kaymasi riski var.
Kanit (satir N): 173 (Goals.jsx), api.js 386-393 (formatDate implementasyonu)
Aksiyon: Backend'in `projected_completion_date` alanini salt tarih string'i olarak mi yoksa datetime olarak mi dondurdugunu dogrula; datetime ise `tzinfo=timezone.utc` ile serialize edildiginden emin ol.
Onem: Dusuk · Guven: Dogrulanmali (backend serialize formati bu dosyadan gorulemiyor)

### [FGO-009] Ayni modulden iki ayri import ifadesi
Sorun: `goalsApi` ve formatter'lar (`formatTL`, `formatTLSuffix`, `formatDate`) ayni `../api` modulunden iki ayri `import` satiriyla getiriliyor.
Kanit (satir N): 2-3
Aksiyon: Tek `import { goalsApi, formatTL, formatTLSuffix, formatDate } from '../api';` satirina birlestir.
Onem: Dusuk · Guven: Kesin
