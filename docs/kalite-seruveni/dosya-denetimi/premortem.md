# Denetim: app/premortem.py

> **M86 güncellik:** 🔴 BAYAT — PM-001/002/003 düzeltildi (BUG #138)


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [PM-001] net_worth_delta parametresi kabul edilir ama hicbir yere yazilmaz
- **Sorun:** `link_premortem_outcome` fonksiyonu `net_worth_delta: Optional[float] = None` parametresini alir ve docstring'de "Karar oncesi/sonrasi net deger farki (opsiyonel)" olarak tanimlar. Ancak fonksiyon govdesinde (348-352. satirlar) sadece `related_action_id`, `actual_outcome`, `outcome_evaluated_at`, `outcome_score` alanlarina yazar — `net_worth_delta` degeri hicbir DecisionJournal kolonuna aktarilmaz, sessizce dusurulur. `DecisionJournal` modelinde (app/models.py) bu degeri tutacak bir kolon da yok. Caller (`app/routers/actions.py:292`) bu farki gercek cockpit before/after degerlerinden ozenle hesaplayip gonderiyor (`float(net_worth_after or 0.0) - float(net_worth_before or 0.0)`) ama bu deger bosa gidiyor. Sonuc: `outcome_score` sadece kaba +1/-1 basari bayragi tasiyor, DecisionJournal'in "Pain + Reflection = Progress" (models.py:600) ay-sonu retro amacinin gerektirdigi sayisal etki hic kaydedilmiyor.
- **Kanit:** satir 317-356 (ozellikle parametre tanimi 323, kullanilmadigi govde 348-352); caller app/routers/actions.py:286-293
- **Aksiyon:** DecisionJournal'a bir `outcome_net_worth_delta` (Float, nullable) kolonu eklenip `link_premortem_outcome` icinde `dj.outcome_net_worth_delta = net_worth_delta` ile yazilmali; ya da parametre gercekten kullanilmiyorsa caller'dan kaldirilip yanlis beklenti verilmemeli.
- **Onem:** Yuksek · **Guven:** Kesin

### [PM-002] PremortemScenario.id icin format/tekillik dogrulamasi yok — frontend React key olarak kullaniyor
- **Sorun:** `id: str = Field(description="Stabil ID: S1..S5")` (satir 47) hicbir `pattern` veya tekillik kontrolu yapmiyor. Sistem prompt'u (satir 104) "ID'ler: S1, S2, S3, S4, S5" diyor ama bu kural sadece prompt seviyesinde — Pydantic modelde zorlanmiyor. `_parse_and_validate` da (167-189) id tekilligini kontrol etmiyor. LLM ayni id'yi iki kez donduse (orn. "S1","S1","S3") ya da bos/duzensiz bir string donduse validation gecer. `frontend/src/components/PremortemModal.jsx:144` bu `id` alanini dogrudan React `key={s.id}` olarak kullaniyor — duplicate id durumunda React render'i sessizce bozulur (yanlis/atlanan senaryo gosterimi).
- **Kanit:** satir 47 (validator yok), satir 104 (prompt kurali), _parse_and_validate 167-189; frontend/src/components/PremortemModal.jsx:144
- **Aksiyon:** `PremortemScenario.id` icin `field_validator` ile `^S[1-5]$` pattern kontrolu ekle; `PremortemResult` seviyesinde bir `model_validator` ile scenario id'lerinin birbirinden farkli oldugunu dogrula (aksi halde retry tetikle).
- **Onem:** Yuksek · **Guven:** Kesin (validasyon eksikligi icin), Dogrulanmali (LLM'in gercekte duplicate id uretme sikligi icin)

### [PM-003] Docstring'de yasakli ozel isim kullanimi (ADR-001 ihlali)
- **Sorun:** Dosyanin en ustundeki modul docstring'i, satir 8'de "[yasakli kisi ismi] felsefesi: Premortem KARAR VERMEZ, sadece korluk noktalarini acar." seklinde ADR-001 tarafindan kod/docstring/commit'te kullanimi yasaklanmis ozel bir kisi ismini iceriyor. Repo'daki diger dosyalar ayni ilkeyi isimsiz sekilde ifade ediyor — orn. `app/debt_strategy.py:10-11`: "ADR-001 uygulamasi: algoritma karar verir (matematik sektor standardi), kullanici hangi stratejiyle gidecegini secer, AI sadece aciklar."
- **Kanit:** satir 8
- **Aksiyon:** Satir 8'i `app/debt_strategy.py:10-11` deki gibi "ADR-001 uygulamasi: Premortem karar vermez, sadece korluk noktalarini acar. Son karar her zaman kullanicinin." seklinde isimsiz ifadeye cevir.
- **Onem:** Yuksek · **Guven:** Kesin

### [PM-004] impact_tl icin isaret/aralik dogrulamasi yok
- **Sorun:** `impact_tl: float = Field(description="Tahmini TL etki (negatif = zarar, 0.0 = belirsiz)")` (satir 50-52) hicbir `le=0` veya makul aralik siniri tasimiyor. LLM matematige guvenilmez ilkesine ragmen (kok vizyon dersi #1), burada uretilen sayisal deger hic bir Rules-Engine tarzi mantik kontrolunden gecmeden dogrudan DecisionJournal'a ve UI'a akiyor. LLM pozitif bir deger (orn. +50000) ya da anlamsiz buyuklukte bir sayi (orn. -1e12) donduse, sema bunu sessizce kabul eder; kullaniciya "basarisizlik senaryosu" olarak yanlis yonlu/olcusuz bir TL etki gosterilebilir.
- **Kanit:** satir 50-52 (alan tanimi), field_validator sadece narrative icin var (satir 59-63), impact_tl icin yok
- **Aksiyon:** `field_validator("impact_tl")` ekleyip `v <= 0` (veya makul bir alt sinir, orn. `v >= -1_000_000_000`) kontrolu yap; ihlalde retry tetiklenecek sekilde `PremortemValidationError` firlat.
- **Onem:** Orta · **Guven:** Dogrulanmali (LLM'in bu degeri hatali uretme sikligi test edilmedi, ama enforcement eksikligi kesin)

### [PM-005] Modul docstring'i "5 senaryo" diyor, dogrulama 3-5 kabul ediyor
- **Sorun:** Dosya basindaki docstring (satir 5): "Murat'in onaylamak uzere oldugu bir aksiyon icin 5 basarisizlik senaryosu uretir." — kesin "5" diyor. Ancak `PremortemResult.scenarios` (satir 71) `min_length=3, max_length=5` ile tanimli ve `_parse_and_validate` (satir 185-188) de `3 <= len(scenarios) <= 5` kabul ediyor. Router docstring'i de (app/routers/premortem.py:48) "3-5 basarisizlik senaryosu" diyor — modul docstring'i ile celisiyor.
- **Kanit:** satir 5 vs satir 71, 185-188; app/routers/premortem.py:48
- **Aksiyon:** Modul docstring'ini "3-5 basarisizlik senaryosu uretir" olarak guncelle (gercek davranisla eslesecek sekilde).
- **Onem:** Dusuk · **Guven:** Kesin

### [PM-006] Tek satirlik fence'li JSON cevaplarda fence-strip mantigi icerigi siler
- **Sorun:** `_parse_and_validate` (satir 170-175) `text.split("\n")` ile satirlara boluyor, sonra `lines[1:]` ile ilk satiri (acilis fence) atiyor. Eger LLM tum JSON'u tek satirda "```json{...}```" seklinde donduruyorsa (satirsonu yok), `text.split("\n")` tek elemanli bir liste doner; `lines[0].startswith("```")` True oldugu icin `lines[1:]` bu tek elemani da siler ve `lines` bos kalir. Sonuc bos string uzerinde `json.loads("")` cagirilir ve JSONDecodeError firlatilir — asil JSON icerik hala mevcutken bosa retry harcanir.
- **Kanit:** satir 170-175
- **Aksiyon:** Fence temizligini regex ile yap (orn. `re.sub(r"^```(?:json)?\s*|\s*```$", "", text)`) — satir bazli degil, string bazli calissin.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (LLM'lerin bu formatta tek-satir donme sikligi bilinmiyor)

### [PM-007] link_premortem_outcome sorgusunda user_id filtresi yok — persist_premortem ile tutarsiz
- **Sorun:** `persist_premortem` (satir 283-288) `DecisionJournal` sorgusunu hem `user_id` hem `decision_text` ile filtreliyor. Ancak `link_premortem_outcome` (satir 341-343) sadece `decision_text == sentinel` ile sorguluyor, `user_id` filtresi yok. Su an `PendingAction.id` global autoincrement oldugu icin (app/models.py:314) sentinel string zaten global tekil, pratik bir veri sizintisi olusmuyor — ama tek-kullanici MVP'den multi-user'a gecis planlandigi icin (PROJE.md, get_current_user notu) bu iki fonksiyonun farkli filtreleme davranisi tasarim tutarsizligi ve ileride izlenmesi zor bir bug kaynagi.
- **Kanit:** satir 283-288 (user_id filtreli) vs satir 341-343 (user_id filtresiz)
- **Aksiyon:** `link_premortem_outcome` imzasina `user_id` ekleyip sorguya dahil et; caller'i (app/routers/actions.py:286-293) guncelle.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
