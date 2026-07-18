# Denetim: app/routers/transactions.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RTR-001] created_at serialize edilirken tzinfo=timezone.utc eklenmiyor
- **Sorun:** `_txn_to_dict` icinde `created_at` DateTime alani, PROJE.md / docs/architecture.md kuralina ragmen `tzinfo=timezone.utc` eklenmeden isoformat() ile donduruluyor. Kural acikca: "Frontend'e tarih dönen her endpoint'te serialize öncesi tzinfo=timezone.utc ekle" ve referans pattern `_memory_to_history_item` (app/routers/coach.py) olarak gosteriliyor. Bu dosyada o pattern uygulanmamis.
- **Kanit:** satir 76 (`"created_at": txn.created_at.isoformat() if txn.created_at else None,`) — karsilastir: docs/architecture.md "Datetime / Timezone" bolumu ve app/PROJE.md ayni kural.
- **Aksiyon:** `txn.created_at.replace(tzinfo=timezone.utc).isoformat()` seklinde duzelt (None kontrolu korunarak).
- **Onem:** Kritik · **Guven:** Kesin

### [RTR-002] PUT /transactions/{id} account_id degisimini sahiplik/varlik kontrolu yapmadan kabul ediyor
- **Sorun:** `update_transaction` icinde `update_data` dogrudan `setattr(txn, k, v)` ile uygulaniyor (satir 324-325); eger payload'da `account_id` gonderilirse, bu deger baska bir kullaniciya ait veya var olmayan bir hesabi isaret etse bile hicbir dogrulama yapilmadan txn.account_id'ye yaziliyor. `create_transaction`'da (satir 272-280) ayni durum icin 404 firlatiliyor ama update'te bu kontrol yok. Sonrasinda satir 328-335'teki sorgu account'u bulamazsa (`new_account is None`) sessizce bakiye guncellemesi atlaniyor, fakat txn.account_id DB'de gecersiz/yabanci degerle kaydedilmis oluyor.
- **Kanit:** satir 310, 323-325 (dogrulama yok), 328-335 (sessiz atlama)
- **Aksiyon:** setattr dongusunden once (veya update_data icinde account_id varsa) create_transaction'daki gibi `Account.id == account_id, Account.user_id == user.id` kontrolu yapip bulunamazsa 404 don.
- **Onem:** Yuksek · **Guven:** Kesin

### [RTR-003] PUT /transactions/{id} icin amount>0 dogrulamasi yok
- **Sorun:** `create_transaction` icinde amount icin acik kontrol var (satir 265-266: `if not data.get("amount") or data["amount"] <= 0: raise HTTPException(...)`), fakat `TransactionUpdate` / `update_transaction` icinde amount alanina negatif veya 0 deger PUT edilebilir, hicbir validation yok. Bu, "amount pozitif olmali" is kuralinin update yolunda delinmesine yol aciyor; negatif/sifir tutarli islem kaydi + bozuk bakiye hesaplamasi (`_apply_to_balance`) olusabilir.
- **Kanit:** satir 45-54 (TransactionUpdate şema, validator yok), satir 294-339 (update_transaction, amount kontrolü yok)
- **Aksiyon:** update_data icinde "amount" varsa `<= 0` kontrolu ekle, aksi halde 400 dondur (create_transaction ile simetrik).
- **Onem:** Yuksek · **Guven:** Kesin

### [RTR-004] transaction_type="transfer" hicbir hesap bakiyesini etkilemiyor (sessiz no-op)
- **Sorun:** `TransactionCreate`/`TransactionUpdate` Literal tipi "transfer"i gecerli bir transaction_type olarak kabul ediyor, ancak `_apply_to_balance` sadece "expense" ve "income" dallarini isliyor (satir 110-124); "transfer" icin hicbir kosul yok, dolayisiyla auto_update_balance=True olsa bile transfer islemi kaydedilir ama account.balance HICBIR SEKILDE degismez. Transaction modelinde de tek `account_id` var, hedef hesap (target_account_id) yok — yani "transfer" ozelligi yapisal olarak eksik/olu bir yol. Kullanici "transfer" turunde bir islem girip bakiyenin guncellendigini varsayarsa yanlis sonuc: iki hesap arasi para hareketi kaydedilmis gorunur ama gercek bakiyeler degismez.
- **Kanit:** satir 33, 48 (Literal "transfer" kabul), satir 110-124 (_apply_to_balance icinde transfer dali yok)
- **Aksiyon:** Ya "transfer" turunu API'den tamamen kaldir (Literal'dan cikar) ya da iki hesapli transfer mantigini (kaynak -amount / hedef +amount) implement et; suanki hali kullanicii yaniltir.
- **Onem:** Yuksek · **Guven:** Kesin

### [RTR-005] loan hesabi + income turu de sessiz no-op
- **Sorun:** `_apply_to_balance` icinde `atype == "loan"` dalinda sadece "expense" (taksit) isleniyor (satir 122-124); "income" turunde loan hesabina hicbir etki yok. Belgelenmis (docstring satir 88-95) davranis bu sekilde ama kredi hesabina yanlislikla "income" turunde bir kayit girilirse (orn. fazla odeme/iade) sessizce yoksayilir, kullaniciya hata da donmez.
- **Kanit:** satir 122-124
- **Aksiyon:** loan+income durumunu ya aciqca reddet (400) ya da anlamli bir islemi tanimla (orn. borc azaltma) — sessiz yoksayma yerine.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RTR-006] Para tutarlari float ile tutuluyor — kumulatif yuvarlama riski
- **Sorun:** `amount: Optional[float]` ve `Account.balance` Float kolonu uzerinde tekrarlanan `+=`/`-=` islemleri (satir 112-124) IEEE-754 float aritmetigi ile yapiliyor. Cok sayida kucuk islem sonucu balance'da kurus bazinda kumulatif sapma olusabilir (klasik 0.1+0.2 problemi). Bu dosyaya ozel bir yuvarlama fonksiyonu veya Decimal kullanimi yok.
- **Kanit:** satir 34, 49 (`amount: Optional[float]`), satir 112-124 (`account.balance -= sign * amount` vb.)
- **Aksiyon:** Kesin cozum bu dosyanin kapsami disinda olabilir (schema-genelinde Decimal'e gecis gerekebilir), ancak en azindan bakiye guncellemesinden sonra `round(account.balance, 2)` gibi bir normalize adimi eklenebilir.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RTR-007] Quick-entry default hesap secimi deterministik degil
- **Sorun:** `data.get("is_card_expense")` true/false'a gore credit_card veya cash hesabi `.first()` ile seciliyor (satir 246-258), ORDER BY yok. Kullanicinin ayni tipte (orn. birden fazla nakit hesabi) birden fazla hesabi olursa, hangi hesabin secilecegi DB'nin donus sirasina bagli, ongorulemez olabilir.
- **Kanit:** satir 246-258
- **Aksiyon:** Deterministik bir sira ekle (orn. `.order_by(Account.id)` veya kullanicinin "varsayilan hesap" alani).
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RTR-008] Hizli giris kategori eslemesi substring bazli — yanlis pozitif riski
- **Sorun:** `_parse_quick_text` icinde `if keyword in rest` substring kontrolu kullaniyor (satir 176), kelime siniri yok. Turkce metinlerde beklenmedik ic-ice gecmeler yanlis kategoriye dusurebilir (orn. ileride eklenecek yeni bir anahtar kelime mevcut kelimelerden birinin alt-string'i olursa sessizce yanlis kategori secilir). Su anki QUICK_KEYWORDS listesinde acik bir çakışma gozlenmedi ama tasarim kirilgan.
- **Kanit:** satir 159-189, ozellikle satir 175-182
- **Aksiyon:** Kelime sinirlarina gore (`re.search(r'\b' + keyword + r'\b', rest)` veya split+set kontrolu) eslestirme yapilmasi daha guvenli olur.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RTR-009] list_transactions limit parametresi ust sinirsiz
- **Sorun:** `limit: int = 200` query parametresi kullaniciyi/istemciyi `?limit=999999999` gibi degerlerle sinirsiz sorgu yapmaya acik birakiyor; ayrica offset/pagination yok, sadece limit var.
- **Kanit:** satir 196-201
- **Aksiyon:** `limit: int = Query(200, le=1000)` gibi bir ust sinir ekle; gerekiyorsa offset parametresi ekle.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
