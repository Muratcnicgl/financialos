# Denetim: app/routers/actions.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RAT-001] link_premortem_outcome cagrisi try/except ile korunmuyor - basarili aksiyon 500 gibi gorunebilir
- **Sorun:** approve_action icinde execute_pending_action basarili olup ActionHistory zaten commit edildikten (satir 269-283) SONRA link_premortem_outcome cagriliyor (satir 286-293), ama bu cagri herhangi bir try/except ile sarilmadi. Ayni fonksiyonun hemen altindaki reflection cagrisi (satir 296-307) tam olarak bu risk icin acikca try/except ile korunmus ("rollback guvenligi: ... hatasi aksiyonu etkilemez" yorumu, satir 234-235 ve 70-71). link_premortem_outcome ise session.commit()/session.refresh() icerir (app/premortem.py satir 354-355) ve herhangi bir DB hatasi (constraint, lock, vb.) burada firlatilirsa FastAPI bunu yakalanmamis exception olarak 500'e cevirir. Kullaniciya "islem basarisiz" gibi gorunur ama pending.status zaten 'executed' olarak commit edilmis, para/hesap degisikligi zaten uygulanmis durumda — response ile gercek durum arasinda celiski olusur.
- **Kanit:** satir 286-293 (unguarded call), karsilastirma icin satir 296-307 (guarded reflection cagrisi), app/premortem.py satir 340-356 (icinde try/except yok)
- **Aksiyon:** link_premortem_outcome cagrisini reflection cagrisindaki gibi try/except ile sar; hata olursa sadece logger.warning yaz, response'u etkileme.
- **Onem:** Yuksek · **Guven:** Kesin

### [RAT-002] net_worth_delta hesaplaniyor ama hicbir yerde kullanilmiyor (dead parameter)
- **Sorun:** approve_action satir 292'de `net_worth_delta=float(net_worth_after or 0.0) - float(net_worth_before or 0.0)` hesaplanip link_premortem_outcome'a parametre olarak geciriliyor. Ancak app/premortem.py'deki link_premortem_outcome fonksiyonu bu parametreyi imzasinda kabul ediyor (satir 323) ama govdesinde (satir 340-356) hicbir yerde `dj`'ye yazmiyor / kullanmiyor. app/models.py'deki DecisionJournal sinifinda da net_worth_delta adinda bir kolon yok. Yani bu satirda yapilan hesaplama tamamen olu kod — CPU harciyor, hicbir etkisi yok, ve okuyan biri "premortem net deger farkini takip ediyor" zannedip yanilir.
- **Kanit:** satir 292 (hesaplama+cagri), app/premortem.py satir 323 ve 340-356 (parametre kullanilmiyor), app/models.py DecisionJournal tanimi (net_worth_delta kolonu yok)
- **Aksiyon:** Ya link_premortem_outcome/DecisionJournal'a gercek bir net_worth_delta kolonu ekleyip kullan, ya da bu olu hesaplamayi ve parametreyi kaldir.
- **Onem:** Orta · **Guven:** Kesin

### [RAT-003] net_worth_delta round edilmeden hesaplaniyor - cift-hassasiyet float hatasi riski
- **Sorun:** satir 292'deki `float(net_worth_after or 0.0) - float(net_worth_before or 0.0)` islemi, her iki degerin de zaten `round(...,2)` ile yuvarlanmis oldugu (app/rules_engine.py satir 722: `net_deger = round(nakit + yatirim_deger - kart_borcu - kredi_borcu, 2)`) goz onune alinirsa, IEEE754 float cikarma sonucu 300.04999999999995 gibi degerler uretebilir. Su an RAT-002 nedeniyle bu deger hicbir yere yazilmadigi icin etkisiz, ama link_premortem_outcome/DecisionJournal ileride bu parametreyi kullanmaya baslarsa (RAT-002 duzeltilirse) bu round eksikligi dogrudan kullaniciya yanlis/cirkin bir sayi olarak yansir.
- **Kanit:** satir 292; karsilastirma icin app/rules_engine.py satir 722, 727 (kaynak degerler zaten round'lu)
- **Aksiyon:** RAT-002 duzeltilirse `round(float(net_worth_after or 0.0) - float(net_worth_before or 0.0), 2)` kullan.
- **Onem:** Dusuk · **Guven:** Kesin

### [RAT-004] Pending action sorgusu status filtresi icermiyor - edit_action ile tutarsiz
- **Sorun:** approve_action'da pending action satir 244-251'de `PendingAction.id == action_id, PendingAction.user_id == current_user.id` filtreleriyle cekiliyor — `status == ActionStatus.pending` filtresi YOK. Oysa ayni dosyada edit_action (satir 347-355) bu filtreyi ekliyor (`PendingAction.status == ActionStatus.pending`). Sonuc olarak approve_action zaten 'rejected'/'executed'/'failed' durumundaki bir action_id icin de once (bosuna) cockpit_before hesabi (satir 239, tum rules engine yeniden calisir) ve DB sorgusu yapiyor, sonra execute_pending_action kendi ic kontrolunde (app/action_executor.py satir 279) hatayi yakaliyor. Fonksiyonel olarak veri bozulmuyor (executor korumasi sayesinde) ama gereksiz hesaplama + iki dosya arasinda tutarsiz sorgu pattern'i var.
- **Kanit:** satir 244-251 (status filtresi yok) vs satir 352 (edit_action'da var); app/action_executor.py satir 279 (asil koruma burada)
- **Aksiyon:** approve_action'daki sorguya da `PendingAction.status == ActionStatus.pending` filtresi ekle; boylece zaten sonuclanmis bir action icin gereksiz cockpit_before hesaplamasi/DB sorgusu yapilmaz, ve 404 yerine tutarli bir "zaten islenmis" hatasi erken donulur.
- **Onem:** Dusuk · **Guven:** Kesin

### [RAT-005] Reflection amount esigi negatif tutarlarda yanlis calisabilir (abs() eksik)
- **Sorun:** `_should_reflect` (satir 53-62) satir 60'da `float(payload.get("amount", 0)) < _REFLECTION_AMOUNT_THRESHOLD` kontrolu yapiyor, mutlak deger (abs) almadan. Eger add_transaction payload'inda amount negatif bir sayi olarak gelirse (orn. -500 TL gibi bir isaretli tutar konvansiyonu kullanilirsa), `-500 < 100` True doner ve 500 TL'lik buyuk bir harcama "kucuk harcama" sayilip reflection atlanir — oysa niyet acikca "100 TL alti kucuk harcamalari atla" (satir 54 docstring). app/action_executor.py `_execute_add_transaction` (satir 415-457) amount icin isaret zorunlulugu/validasyonu gostermiyor (sadece `float(amount)` cast), yani negatif deger DB katmaninda engellenmiyor.
- **Kanit:** satir 60; karsilastirma icin app/action_executor.py satir 429-457 (amount isareti dogrulanmiyor)
- **Aksiyon:** `abs(float(payload.get("amount", 0))) < _REFLECTION_AMOUNT_THRESHOLD` kullan, ya da yukarida amount'un her zaman pozitif oldugunu garanti eden bir validasyon ekle.
- **Onem:** Orta · **Guven:** Dogrulanmali (amount'un isaretli mi gonderildigi coach.py/propose_action tarafinda dogrulanmadi)

### [RAT-006] get_action_history limit parametresi validasyonsuz
- **Sorun:** satir 376'da `limit: int = 50` hicbir ust/alt sinir kontrolu olmadan dogrudan `.limit(limit)` (satir 389) icin kullaniliyor. SQLite'ta `LIMIT -1` "sinirsiz" anlamina gelir; yani `?limit=-1` gonderen bir istemci kullanicinin TUM ActionHistory kayitlarini (tasarlanan 50 sinirini asarak) cekebilir. Tek-kullanicili MVP'de dogrudan guvenlik riski dusuk (zaten sadece kendi verisi), ama yine de tasarlanan davranistan sapma ve gelecekte cok sayida kayit birikince performans/response-size sorunu yaratabilir.
- **Kanit:** satir 376, 389
- **Aksiyon:** `limit: int = Query(50, ge=1, le=500)` gibi bir sinir ekle.
- **Onem:** Dusuk · **Guven:** Kesin

### [RAT-007] action_type query parametresi tip aciklamasi yanlis (Optional eksik)
- **Sorun:** satir 377'de `action_type: str = None` seklinde tanimlanmis — tip `str` olarak isaretlenmis ama varsayilan `None`. Dosyanin geri kalaninda (orn. RejectRequest.reason, satir 179) ayni durum `Optional[str] = None` seklinde dogru yaziliyor. FastAPI/Pydantic calisma zamaninda bunu tolere ediyor olsa da, statik tip tutarliligi ve OpenAPI semasi acisindan yanlis/eksik.
- **Kanit:** satir 377; karsilastirma icin satir 179
- **Aksiyon:** `action_type: Optional[str] = None` yap.
- **Onem:** Dusuk · **Guven:** Kesin

### [RAT-008] cockpit_before ve cockpit_after farkli date.today() cagrilariyla hesaplaniyor
- **Sorun:** satir 239 ve 264'te iki ayri `date.today()` cagrisi var (araya execute_pending_action'in DB islemleri giriyor). Istek gece yarisini (00:00) tam bu araliktan gecirirse, cockpit_before ve cockpit_after farkli "bugun" degerleriyle hesaplanir; generate_cockpit devreden bakiye/zikzak gibi tarihe bagli hesaplari icerdigi icin (app/rules_engine.py) bu durumda net_worth_before/after karsilastirmasi tutarsiz bir taban uzerinden yapilabilir. Cok dusuk olasilikli bir race/edge-case (milisaniyeler icinde gece yarisini gecmek gerekir) ama teorik olarak var.
- **Kanit:** satir 239, 264
- **Aksiyon:** Tek bir `today = date.today()` degiskeni satir basinda alinip her iki cagriya da gecilebilir (pratik fayda dusuk, ama tutarliligi garanti eder).
- **Onem:** Dusuk · **Guven:** Dogrulanmali (mimari olarak dogru ama gercek etki ihtimali cok dusuk)
