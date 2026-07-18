# Denetim: frontend/src/components/PendingActions.jsx

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [FPA-001] Klavye kisayollari acik modal ustunde de tetikleniyor
Sorun: Y/N/E klavye kisayol handler'i (satir 184-210) sadece odakli elemanin tag'ini (INPUT/TEXTAREA/SELECT) ve busyIdRef'i kontrol ediyor; premortemActionId veya horizonsActionId dolu oldugunda (PremortemModal/HorizonsModal acik) bu durumu hic kontrol etmiyor. Kullanici modal icinde detay incelerken 'y' veya 'n' tusuna basarsa, arka plandaki ilk bekleyen aksiyon sessizce onaylanir/reddedilir — kullanici modal'da baska bir aksiyonu inceliyor olabilir.
Kanit (satir N): 184-210 (handler tanimi, modal state kontrolu yok), 369-388 (modal render kosullari premortemActionId/horizonsActionId'e bagli ama handler bunlari okumuyor).
Aksiyon: Handler icine `if (premortemActionId !== null || horizonsActionId !== null) return;` kontrolu eklenmeli (ya da bu state'leri de ref'e alip kontrol etmeli).
Onem: Kritik · Guven: Kesin

### [FPA-002] Duzenleme modundayken klavye kisayollari onayi/reddi engellemiyor
Sorun: Mouse ile Onayla/Reddet butonlari `disabled={busy || isEditing}` ile korunuyor (satir 325, 334, 343, 355), fakat klavye kisayol handler'i (satir 196-205) `editingById[firstId]` durumunu hic kontrol etmiyor. Kullanici TransactionTable'i duzenleme modunda actiginda (satir 259 isEditing), 'y' veya 'n' tusuna basarsa kaydedilmemis/duzenlenmekte olan aksiyon dogrudan onaylanir veya reddedilir; buton disabled olsa da klavye yolu bunu bypass ediyor.
Kanit (satir N): 196-205 (kosulda editingById kontrolu yok), 259 (isEditing hesaplaniyor ama handler'a aktarilmiyor), 325/334/343/355 (sadece mouse yolu korunuyor).
Aksiyon: Klavye handler'ina editingById map'ini ref uzerinden erisip `if (editingByIdRef.current[firstId]) return;` kontrolu eklenmeli.
Onem: Yuksek · Guven: Kesin

### [FPA-003] JSON.parse hatasi yakalanmiyor — tum liste cokebilir
Sorun: TransactionTable icinde `payload` string ise `JSON.parse(payload)` try/catch olmadan cagriliyor (satir 23). Backend'den bozuk/eksik JSON string gelirse (orn. kismi yazilmis payload, encoding hatasi) bu satir exception firlatir; component agacinda bir Error Boundary gorulmedigi icin bu, sadece o karti degil tum PendingActions listesini (ve muhtemelen ust panel'i) coker.
Kanit (satir N): 23.
Aksiyon: try/catch ile sarmala, parse hatasinda kullaniciya "Payload okunamadi" hata karti goster, digerlerinin render'ini engelleme.
Onem: Yuksek · Guven: Kesin

### [FPA-004] Klavye kisayolu useEffect'i bos bagimlilik dizisiyle onResolved/handleApprove/handleReject'i mount anindan donduruyor (stale closure)
Sorun: Satir 184-210'daki useEffect `[]` bos bagimlilikla calisiyor (eslint-disable ile bastirilmis, satir 209). Bu efekt icindeki handler, disaridaki `handleApprove`/`handleReject` fonksiyonlarini (ve dolayisiyla bunlarin icindeki `onResolved` prop'unu) closure ile yakaliyor. actions/busyId degerleri ref uzerinden guncel okunuyor (dogru pattern) ama `onResolved` prop referansi parent'ta memoize edilmemisse, klavye yoluyla tetiklenen approve/reject cagrisi mount anindaki eski `onResolved`'i kullanir; mouse tiklama yolu ise her render'da taze `onResolved` kullanir. Iki yol arasinda farkli davranis riski var.
Kanit (satir N): 184-210 (bos deps), 217-241 (handleApprove/handleReject icinde onResolved kullanimi, satir 222/235).
Aksiyon: onResolved icin de bir ref (onResolvedRef) tutup handler icinde ref uzerinden cagirmak, ya da handleApprove/handleReject'i useCallback ile stabilize edip bunlari da ref'e alip kullanmak.
Onem: Orta · Guven: Dogrulanmali (parent'in onResolved'i memoize edip etmedigine bagli — bu dosyada gorulemez)

### [FPA-005] handleSave tutar (amount) alanini dogrulamadan gonderiyor
Sorun: `handleSave` icinde `parseFloat(form.amount)` dogrudan payload'a yaziliyor (satir 58), bos string veya gecersiz sayisal girdi icin herhangi bir client-side kontrol yok. `form.amount` bos birakilirsa `parseFloat('')` -> `NaN` uretir ve bu deger `newPayload.amount` olarak `actionsApi.edit`'e gonderilir (satir 67); kullanici hicbir client-side uyari almadan istegi yollar.
Kanit (satir N): 58, 90-93 (input alaninda required/min yok).
Aksiyon: Kaydetmeden once `Number.isFinite(parseFloat(form.amount))` kontrolu ekleyip gecersizse `setEditErr` ile engelle.
Onem: Orta · Guven: Kesin

### [FPA-006] getActionId undefined donebilir, key ve state map'lerinde carpisma riski
Sorun: `getActionId` (satir 215) hem `a.id` hem `a.action_id` yoksa `undefined` doner; bu deger dogrudan React `key` (satir 266) ve `errorById`/`editingById`/`payloadById`/`editRequestTimes` map anahtarlari olarak kullaniliyor (satir 257-261, 291, 295, 304). Birden fazla aksiyon ayni sekilde id'siz gelirse hepsi `undefined` key'ini paylasir — React key warning'i yaninda, bir aksiyonun hata/edit durumu digerininkiyle karisir.
Kanit (satir N): 215, 257, 266.
Aksiyon: id yoksa ic gelistirme ortaminda uyari logla ve o karti "gecersiz aksiyon" olarak isaretleyip normal akistan cikar.
Onem: Dusuk · Guven: Dogrulanmali (backend sozlesmesi id/action_id alanlarindan birini her zaman garanti ediyorsa risk yok)

### [FPA-007] parseInt radix belirtilmemis
Sorun: `parseInt(form.account_id)` (satir 61) ikinci radix argumani olmadan cagriliyor. Modern motorlarda ondalik olmayan on-ek (orn. "0x") yoksa pratikte sorun cikarmaz, fakat proje lint kurallari/best-practice acisindan eksik.
Kanit (satir N): 61.
Aksiyon: `parseInt(form.account_id, 10)` yap.
Onem: Dusuk · Guven: Kesin

### [FPA-008] Y/N/E klavye kisayollari kesfedilebilir degil (a11y)
Sorun: Global 'y'/'n'/'e' klavye kisayollari (satir 196-205) hicbir gorsel ipucu, `aria-keyshortcuts` ozniteligi veya ekran okuyucu duyurusu icermiyor. Onayla/Reddet butonlarinda (satir 341-360) bu kisayollara dair bilgi yok; klavye/ekran okuyucu kullanicilari bu ozelligin varligini anlayamaz.
Kanit (satir N): 196-205, 341-360 (buton uzerinde ipucu yok; sadece Premortem/3 Ufuk butonlarinda `title` var, satir 327/336, Onayla/Reddet'te yok).
Aksiyon: Onayla/Reddet butonlarina `aria-keyshortcuts="y"` / `aria-keyshortcuts="n"` ve/veya `title` ekle.
Onem: Dusuk · Guven: Kesin
