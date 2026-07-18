# Denetim: app/action_executor.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [AE-001] Handler commit ile status-commit ayrisik; ikinci commit veya post-commit kod patlarsa gercek mutasyon "failed" olarak raporlaniyor
- **Sorun:** `execute_pending_action` icinde handler (`_execute_*`) kendi `db.commit()`'ini zaten yapip parayi/lotu/borcu kalici olarak DB'ye yaziyor (orn. satir 403, 481, 519, 608, 674). Handler basariyla donduktan SONRA, ayni try blogu icinde ikinci bir `db.commit()` ile `pending.status = executed` yaziliyor (satir 318-320), ardindan `trigger_after_action_resolution` cagriliyor (satir 322-323). Bu ikinci commit veya import/cagri herhangi bir istisna firlatirsa (SQLite kilit hatasi, import hatasi, vb.), kod disaridaki `except Exception` bloguna dusuyor (satir 332-335): `db.rollback()` cagriliyor (ki bu artik hicbir seyi geri almaz, cunku handler'in mutasyonu ONCEKI commit ile zaten kalici hale gelmis) ve `_mark_failed` ile `pending.status = failed` YENI bir transaction'da commit ediliyor. Sonuc: kullaniciya "aksiyon basarisiz" donuyor, PendingAction kaydi `failed` gorunuyor, ama hesap bakiyesi/lot/borc DB'de ZATEN degismis durumda. Kullanici veya koc ayni aksiyonu tekrar onaylarsa/tetiklerse, mutasyon ikinci kez uygulanip cift-sayima yol aciyor.
- **Kanit:** satir 305-335 (ozellikle 306, 318-323, 332-335); handler'lardaki erken commit'ler: satir 403 (`_execute_update_account_balance`), 481 (`_execute_add_transaction`), 519 (`_execute_mark_debt_paid`), 608 (`_execute_sell_investment`), 674 (`_execute_add_master_checkpoint`).
- **Aksiyon:** Handler'in veri mutasyonu ile status='executed' guncellemesini TEK bir commit sinirinda birlestir (handler'lar kendi `db.commit()`'ini yapmasin, ust seviyede tek commit olsun) VEYA ikinci commit/post-commit kodu ayri bir try/except'e al ve bu blok basarisiz olursa `_mark_failed` COGRAMASIN — bunun yerine "executed ama bildirim/log basarisiz" gibi ayri bir durum dondur; asla zaten commit edilmis bir finansal mutasyonu 'failed' olarak isaretleme.
- **Onem:** Kritik · **Guven:** Kesin

### [AE-002] sell_investment: credit_to_account_id gecersiz/emanet ise satis parasi hicbir hesaba yazilmadan sessizce kayboluyor
- **Sorun:** Satir 597-606'da `credit_account_id` verilmisse hesap sorgulanir; ama hesap bulunamazsa (`credit_account` None kalir) veya bulunan hesap `is_emanet=True` ise, `sim["net_eline_gecen"]` tutari HICBIR hesaba eklenmiyor. Buna ragmen satir 592-594'te lot dususu ve `inv.balance` guncellemesi zaten yapilmis, satir 608'de commit ediliyor ve fonksiyon `"success": True` donuyor (satir 610). Kaynak tarafinda emanet korumasi var (satir 558-565, aksiyon tamamen reddediliyor) ama hedef tarafinda esdeger bir koruma yok — para sessizce sistemden siliniyor, ne hata ne uyari donuyor.
- **Kanit:** satir 597-621, karsilastir satir 558-565.
- **Aksiyon:** `credit_account_id` acikca verilmis ama gecersiz/emanet cikarsa, tum handler'i basarisiz dondur (satis lot'u dusurulmesin) ya da en azindan sonuc/mesaja "para hicbir hesaba yatirilmadi" seklinde acik bir uyari ekle.
- **Onem:** Kritik · **Guven:** Kesin

### [AE-003] _execute_update_fund_price: user_id hic kullanilmiyor, hesap sahiplik kontrolu yok
- **Sorun:** `_execute_update_fund_price(db, user_id, payload)` (satir 625) `user_id` parametresini aliyor ama fonksiyon govdesinde HICBIR yerde kullanmiyor; satir 636'da `update_fund_price_manual(db, account_id, float(new_price))` cagirilirken `user_id` iletilmiyor. `fund_tracker.update_fund_price_manual` da hesabi sadece `Account.id == account_id` ile sorguluyor (user_id filtresi yok — bkz. app/fund_tracker.py satir 110). Dosyadaki DIGER TUM handler'lar (`_execute_update_account_balance` satir 386-389, `_execute_add_transaction` satir 443-446, `_execute_mark_debt_paid` satir 504-507, `_execute_sell_investment` satir 548-551) `Account.user_id == user_id` filtresini zorunlu tutuyor; bu handler tek istisna. Tek-kullanicili MVP'de pratik zarar sinirli olsa da, dosyanin kendi ic tutarliligini ve gelecekteki multi-user JWT gecisini (app/PROJE.md: "multi-user gecisinde JWT get_current_user'a baglanir") kirar.
- **Kanit:** satir 625, 630-636; app/fund_tracker.py satir 110.
- **Aksiyon:** `update_fund_price_manual` cagrisina `user_id` parametresi ekle, fonksiyon icinde `Account.user_id == user_id` filtresi ekle (diger handler'larla ayni pattern).
- **Onem:** Yuksek · **Guven:** Kesin

### [AE-004] sell_investment: actual_price=0 falsy-check nedeniyle current_price'a sessizce dusuluyor
- **Sorun:** Satir 581: `actual_price = float(payload.get("actual_price") or inv.current_price)`. Python'da `0 or X` ifadesi `X`'i dondurur. LLM/kullanici acikca `actual_price: 0` gonderirse (orn. fonun degersiz kaldigi bir tasfiye senaryosu), kod bunu yok sayip `inv.current_price` kullanir — satis simulasyonu ve `net_eline_gecen` yanlis (fazla) hesaplanir. `_execute_update_account_balance`'daki `new_balance is None` kontrolu (satir 383) dogru pattern'i kullanirken burada tutarsizlik var.
- **Kanit:** satir 581, karsilastir satir 382-383.
- **Aksiyon:** `payload.get("actual_price") if payload.get("actual_price") is not None else inv.current_price` seklinde degistir.
- **Onem:** Yuksek · **Guven:** Dogrulanmali (0 degerinin gercek dunyada gelme ihtimali dusuk ama kod deseni kesin hatali)

### [AE-005] add_transaction: income turu kredi karti hesabina uygulanirsa borc azalacagi yerde artiyor
- **Sorun:** Account.balance alaninin anlami modelde acikca tanimli: "Kart/kredi: borc (pozitif)" (app/models.py satir 154). `_execute_add_transaction`'da auto_update_balance blogunda (satir 467-479) `txn_type == "income"` durumunda hesap turune bakilmaksizin `account.balance += float(amount)` yapiliyor (satir 469). Eger bir kredi karti hesabina "income" turunde bir islem (orn. karta yapilan bir odeme/borc kapama) kaydedilirse, bu kod borcu AZALTMAK yerine ARTIRIYOR — cunku kart harcamalarinda ayni satir mantigi "borc buyur" anlaminda kullanilyor (satir 473-475 yorum: "Kart borcu buyur"). Kart borcu odemesi icin ayri bir dal yok.
- **Kanit:** satir 467-479, referans yorum satir 473-475, alan aciklamasi app/models.py satir 154.
- **Aksiyon:** Kredi karti hesabina "income" turu icin ayri bir dal ekle (borc azalt: `account.balance -= amount`) veya coach prompt/validation seviyesinde kart odemesini "income" olarak degil ayri bir aksiyon turu olarak modelle.
- **Onem:** Yuksek · **Guven:** Dogrulanmali (bu path'in LLM tarafindan gercekten tetiklenip tetiklenmedigi bu dosyanin disinda, coach.py prompt'una bagli)

### [AE-006] Parasal alanlarda tutarsiz yuvarlama — float birikim hatasi riski
- **Sorun:** `simulate_partial_sale` (rules_engine.py) tum ciktilarini `round(...,2)` ile donduruyor ve bu dosyada `diff` (satir 411) ve limit asim uyarisi (satir 190) da yuvarlaniyor; ancak dogrudan bakiye atamalari yuvarlama yapmiyor: `account.balance = float(new_balance)` (satir 401), `account.balance += float(amount)` / `-= float(amount)` (satir 469, 474, 477), `credit_account.balance += sim["net_eline_gecen"]` (satir 605). Float ikili temsil hatasi (orn. 0.1+0.2 problemi) tekrarli islemlerde bakiyede kurus seviyesinde sapmaya yol acabilir.
- **Kanit:** satir 401, 469, 474, 477, 605.
- **Aksiyon:** Tum bakiye atama/guncellemelerini `round(x, 2)` ile sarmalayarak dosyanin geri kalaniyla tutarli hale getir (veya Decimal/kurus-tam-sayi'ya gecisi degerlendir — bu daha buyuk bir mimari karar).
- **Onem:** Orta · **Guven:** Dogrulanmali (etkinin gozle gorulur olmasi uzun vadeli birikime bagli)

### [AE-007] Kart limit uyarisi: credit_limit=0 falsy oldugu icin uyari hic tetiklenmiyor
- **Sorun:** Satir 186 `if card and card.credit_limit:` — `credit_limit` degeri `0` ise (orn. kullaniciyi engellemek icin bilincli 0 limit girilmis bir kart), bu kosul `False` olur ve limit asim uyarisi (satir 187-195) hicbir zaman tetiklenmez; oysa boyle bir kartta HER harcama limiti asar ve uyari en cok bu durumda gerekli.
- **Kanit:** satir 186.
- **Aksiyon:** `if card and card.credit_limit is not None:` seklinde degistir.
- **Onem:** Orta · **Guven:** Kesin

### [AE-008] add_transaction: transaction_type="transfer" + auto_update_balance sessizce hicbir bakiye degistirmiyor
- **Sorun:** `txn_type` gecerli degerleri `income/expense/transfer` (satir 431), ancak auto_update_balance blogu (satir 467-479) sadece `income` ve `expense` dallarini isliyor. `transfer` secilip `auto_update_balance=True` gonderilirse, islem kaydi olusturulur (satir 453-463) ama `balance_diff = 0.0` kalir, hicbir hesap bakiyesi degismez — ve payload semasinda zaten hedef/ikinci hesap alani da yok (sadece tek `account_id`). Fonksiyon yine de `"success": True` donuyor; kullanici "transfer basariyla auto-update edildi" izlenimine kapilabilir.
- **Kanit:** satir 429-479 (ozellikle `txn_type not in (...)` kontrolu satir 431 ve auto-update blogu 467-479).
- **Aksiyon:** `transfer` turunu ya tam destekle (iki hesapli payload + iki tarafli bakiye guncellemesi) ya da `auto_update_balance=True` ile `transfer` birlikte istendiginde acikca hata/uyari dondur.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [AE-009] add_master_checkpoint: priority alani docstring'deki 1-3 araligina karsi dogrulanmiyor
- **Sorun:** Docstring "priority: int (1-3)" diyor (satir 646-647) ama `priority = payload.get("priority", 2)` (satir 652) ve `int(priority)` (satir 670) hicbir ust/alt sinir kontrolu yapmiyor. LLM `priority: 99` veya negatif bir deger gonderirse sessizce DB'ye yaziliyor.
- **Kanit:** satir 646-647, 652, 670.
- **Aksiyon:** `priority` degerini 1-3 araligina clamp'le veya araligin disindaysa `{"success": False, ...}` dondur.
- **Onem:** Dusuk · **Guven:** Kesin
