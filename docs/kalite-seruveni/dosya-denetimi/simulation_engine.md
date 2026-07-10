# Denetim: app/simulation_engine.py

### [SE-001] Zincirlenmis ufuk projeksiyonu sinir tarihinde geliri/kredi taksitini iki kez sayiyor
- **Sorun:** `simulate_action` "aksiyonlu" dunyayi (`world`) T+0 -> T+30 -> T+60 -> T+90 diye ZINCIRLEME `_project_forward` cagrilariyla ilerletiyor (satir 526-529). Her cagridan sonra `world.as_of = end` oluyor (satir 410) ve bir sonraki cagrinin `start`'i bu deger. Hem gelir dongusundeki `if start <= pay_date <= end` (satir 351) hem de kredi taksiti dongusundeki `_next_payment_in_window`'in `cursor >= start` / `cursor <= end` filtreleri (satir 320-323) HER IKI UCU DA kapsayici (`<=`/`>=`). Odeme tarihi tam olarak bir onceki segmentin bitis tarihine (`world.as_of`) denk geldiginde, o odeme hem onceki segmentte (bitis siniri olarak) hem de sonraki segmentte (baslangic siniri olarak) tekrar tetikleniyor. Borc/alacak dongusu `d.paid_date` bayragiyla kendini korudugu icin (satir 385: `if d.paid_date: continue`) bu hataya baglisik degil — ama gelir ve kredi donguleri boyle bir "islendi" bayragi tutmuyor.
- **Kanit:** Ampirik olarak dogrulandi. `day_of_month=31` olan bir gelir icin, `_project_forward(world,30)` sonra tekrar `_project_forward(world,30)` (T+0->T+30->T+60 zinciri, satir 526-529'daki gercek akisin birebir aynisi) cagrildiginda 31 Ocak maasi IKI KEZ islendi: nakit 3000 TL oldu (1000+1000+1000), oysa tek seferde 60 gun projekte edilince (baseline'in kullandigi yontem, satir 533-536) dogru sonuc 2000 TL (1000+1000) cikiyor. Fark tamamen zincirleme artefaktindan kaynaklaniyor, gercek gelir/borc olayindan degil.
- **Neden kritik:** `comparison` (T+30 karar tablosu, satir 540-552) ve T+60/T+90 snapshot'lari `world` (zincirlenmis, hatali) ile `base_world_h` (satir 533-536, HER ZAMAN taze `_load_world` + TEK cagrilik `_project_forward(base_world_h, h)` — zincirlenmemis, dogru) arasindaki farka dayaniyor. Yani `delta_vs_baseline` degerleri, aksiyonun gercek etkisini degil, kismen bu implementasyon hatasini yansitiyor. Kok-vizyon ilkesi "cift-sayma yasak" burada dogrudan ihlal ediliyor.
- **Aksiyon:** Sinir kosulunu yari-acik araliga cevir (orn. devam eden segmentlerde `start < pay_date <= end`, ya da `world.as_of`'u bir sonraki cagriya `end + timedelta(days=1)` olarak devret) VE gelir/kredi donguleri icin de borc dongusundeki gibi "bu ay zaten islendi" izini tutan bir mekanizma ekle (orn. `a.next_payment_date`'i gercekten ilerlet, `inc` icin son islenen ay/tarihi sakla).
- **Onem:** Kritik · **Guven:** Kesin (calistirilarak dogrulandi)

### [SE-002] `add_transaction` simulasyonu `auto_update_balance` bayragini yok sayiyor
- **Sorun:** Gercek yurutucu `action_executor.py`'deki `_execute_add_transaction` bakiyeyi SADECE `payload.get("auto_update_balance")` True ise gunceller (action_executor.py satir 467: `if payload.get("auto_update_balance") and account_id:`). `simulation_engine.py`'deki `_apply_action`'in `add_transaction` kolu (satir 232-256) bu bayragi HIC okumuyor — `ttype` ne olursa olsun bakiyeyi kosulsuz degistiriyor (satir 240-248). Bu fonksiyonun kendi docstring'i (satir 467: "payload: Action_executor ile ayni format") ayni sozlesmeyi vaat ediyor ama tutmuyor.
- **Kanit:** satir 240-248 (kosulsuz `target.balance += / -=`) vs action_executor.py satir 465-479 (`if payload.get("auto_update_balance") and account_id:` kosulu).
- **Aksiyon:** `_apply_action`'in `add_transaction` kolunda `auto_update_balance` False/eksik ise bakiyeyi degistirme; sadece event_log'a "kayit edildi (bakiye degismedi)" notu dus.
- **Onem:** Kritik · **Guven:** Kesin

### [SE-003] `add_transaction` "transfer" tipinde bakiye degisimi gercek sistemle celisiyor
- **Sorun:** `_apply_action`'in `transfer` kolu (satir 247-248) kosulsuz `target.balance += amount` yapiyor. Gercek `action_executor.py._execute_add_transaction`'daki if/elif zinciri (satir 468-478) SADECE `income` ve `expense` icin bakiye degistiriyor; `transfer` icin hicbir bakiye kolu yok (yani gercek sistemde transfer islemi, `auto_update_balance=True` olsa bile, bakiyeyi ASLA degistirmiyor). Simulasyon boylece "transfer" aksiyonunu gercekte olmayan bir bakiye artisi olarak on izlemede gosterip yanlis karar destegi veriyor.
- **Kanit:** satir 247-248 vs action_executor.py satir 468-478 (transfer icin balance kolu yok).
- **Aksiyon:** `transfer` tipini `income`/`expense` gibi kosulsuz degil, gercek davranisla (bakiyeye dokunmama) hizala; ya da gercek sistemde bilerek eksikse (ayri feature), simulasyonda ayni "no-op" davranisini uygula.
- **Onem:** Yuksek · **Guven:** Kesin

### [SE-004] `mark_debt_paid` zaten odenmis bir borcu tekrar odetebiliyor
- **Sorun:** `_apply_action`'in `mark_debt_paid` kolu (satir 269-284) `d.paid_date` alaninin ONCEDEN dolu olup olmadigini kontrol etmiyor — DB'den yuklenirken (`_load_world`, satir 176) gercekten odenmis bir borc/alacak `paid_date != None` ile geliyorsa bile, bu aksiyon kosulsuz nakit ekleyip/cikarip `d.paid_date = world.as_of` ile UZERINE YAZIYOR (cift odeme). Gercek yurutucu `action_executor.py._execute_mark_debt_paid` bu durumu acikca engelliyor: `if debt.is_paid: return {"success": False, "message": "Bu borc zaten odenmiş olarak isaretli."}` (action_executor.py satir ~510-512).
- **Kanit:** satir 269-284 (guard yok) vs action_executor.py satir 510-512 (guard var).
- **Aksiyon:** Kolun basina `if d.paid_date: return False, "Bu borc/alacak zaten odenmis."` ekle.
- **Onem:** Yuksek · **Guven:** Kesin

### [SE-005] `sell_investment` eksik `cost_per_lot`/`current_price` verisini sessizce 0 kabul ediyor
- **Sorun:** `_apply_action`'in `sell_investment` kolu (satir 198-230), `inv.cost_per_lot` veya `inv.current_price` None ise bunu ACIKCA reddetmiyor. `cost = lots * (inv.cost_per_lot or 0.0)` (satir 210) maliyet verisi eksikse maliyeti 0 TL varsayarak karligi (ve dolayisiyla stopaji) YAPAY OLARAK SISIRIYOR. `price = float(payload.get("actual_price") or inv.current_price or 0.0)` (satir 208) de ayni sekilde fiyat eksikse 0 TL varsayip "bedava satis" hesabi yapiyor. Gercek yurutucu bunu acikca engelliyor: `if inv.cost_per_lot is None or inv.current_price is None: return {"success": False, "message": "cost_per_lot veya current_price eksik — satis simulasyonu yapilamaz."}` (action_executor.py satir 575-579).
- **Kanit:** satir 208, 210 vs action_executor.py satir 575-579. Ayrica `_load_world` (satir 137-143) DB'de gercekten `0` olan `cost_per_lot`/`current_price` degerlerini de `else None` ile None'a cevirdigi icin (bkz. SE-007), bu senaryo dusunulenden daha kolay tetiklenir.
- **Neden onemli:** Kok-vizyon ilkesi "varsayim=hata" burada dogrudan ihlal ediliyor — eksik veri sessizce 0 TL maliyet/fiyat varsayimina donusuyor, kullaniciya yanlis "kar" / "stopaj" rakami sunuluyor.
- **Aksiyon:** `sell_investment` kolunun basina `if inv.cost_per_lot is None or inv.current_price is None: return False, "..."` guard'ini ekle (action_executor.py ile birebir tutarli).
- **Onem:** Yuksek · **Guven:** Kesin

### [SE-006] Kredi taksit gunu, kisa aydan sonra kalici olarak kayiyor (gun-drift)
- **Sorun:** `_next_payment_in_window` (satir 313-332) her iterasyonda bir sonraki odeme gununu, ORIJINAL `next_pay.day` yerine bir onceki iterasyonda KIRPILMIS `cursor.day`'den turetiyor (satir 331: `cursor = date(y, m, min(cursor.day, ldom))`). Gelir dongusu bunu doğru yapiyor (satir 349: her seferinde sabit `inc.day_of_month` kullaniliyor), ama kredi dongusu yapmiyor.
- **Kanit:** Calistirilarak dogrulandi — `next_payment_date=2026-01-31` icin `_next_payment_in_window(..., 2026-01-01, 2026-04-30)` sonucu `[2026-01-31, 2026-02-28, 2026-03-28, 2026-04-28]` donuyor. Mart 31 gun oldugu halde (dogru deger 2026-03-31 olmali) ve Nisan 30 gun oldugu halde (dogru deger 2026-04-30 olmali) kalici olarak 28'e kilitlenmis kaliyor.
- **Aksiyon:** Kirpma icin her zaman `next_pay.day` (orijinal sabit gun) kullan, `cursor.day`'i degil — gelir donguson deki `day = min(inc.day_of_month, ldom)` deseniyle ayni yap.
- **Onem:** Orta · **Guven:** Kesin (calistirilarak dogrulandi)

### [SE-007] `_load_world` gercek sifir degerlerini None'a ceviriyor (falsy-0 tuzagi)
- **Sorun:** `credit_limit`, `monthly_payment`, `lot_count`, `cost_per_lot`, `current_price` alanlari `float(a.X) if a.X else None` deseniyle yukleniyor (satir 134, 137, 141, 142, 143). Python'da `0.0` falsy oldugu icin, DB'de GERCEKTEN `0` olan bir deger (orn. tamamen odenmis kredi icin `monthly_payment=0`, ya da degeri sifirlanmis bir fon icin `current_price=0`) sessizce `None`'a donusuyor — "veri yok" ile "deger sifir" ayrimi kayboluyor.
- **Kanit:** satir 134, 137, 141, 142, 143.
- **Etki:** Su an dosyadaki tuketici kod noktalari genelde `(x or 0)` ile geri toparliyor, bu yuzden cogu yerde sessiz kaliyor; ama `_snapshot_to_dict`'in `"fiyat": a.current_price` alaninda (satir 436) gercek 0 fiyat, frontend/LLM'e `null` olarak gidiyor — "fiyat bilinmiyor" ile "fiyat sifir" farkli anlamlar tasidigi halde ayirt edilemiyor. Ayrica SE-005'teki eksik-veri guard'i eklenirse, gercek-0 degerler de yanlislikla "eksik veri" olarak reddedilir.
- **Aksiyon:** Deseni `float(a.X) if a.X is not None else None` olarak degistir.
- **Onem:** Orta · **Guven:** Kesin

### [SE-008] `sell_investment` satis gelirini emanet hedef hesaba kontrolsuz aktarabiliyor
- **Sorun:** `_apply_action`'in `sell_investment` kolu, satis kaynagi hesabin emanet olup olmadigini kontrol ediyor (satir 202-203, dogru), ama nakdin YATIRILACAGI hedef hesabin (`credit_to_account_id`) emanet olup olmadigini HIC kontrol etmiyor (satir 220-224). Gercek yurutucu bu durumu farkli ama yine de emanet-bilincli ele aliyor: `if credit_account and not credit_account.is_emanet: credit_account.balance += ...` (action_executor.py satir 604-605) — yani emanet hedefe para EKLEMIYOR (sessizce atlanmis olsa da). Simulasyon ise boyle bir kontrol olmadan direkt `target.balance += net_to_account` yapiyor (satir 224), bu da MC1 (emanet dokunulmazligi) ile kavramsal olarak celisen bir on-izleme uretebilir.
- **Kanit:** satir 220-224 vs action_executor.py satir 597-606.
- **Aksiyon:** `credit_to_account_id` emanet ise ya reddet ya da action_executor ile tutarli sekilde "krediye eklenmedi" olarak isle.
- **Onem:** Orta · **Guven:** Dogrulanmali (gercek sistemin kendisi de bu durumda parayi sessizce "kaybetmis" gorunuyor — asil duzeltme belki action_executor.py'de olmali; burada sadece iki dosya arasi tutarsizlik/on-izleme yanlisligi olarak isaretliyorum)

### [SE-009] `actual_price=0` payload'i sessizce `current_price` ile ezilir
- **Sorun:** `price = float(payload.get("actual_price") or inv.current_price or 0.0)` (satir 208) — `or` zinciri falsy degerleri atlar. Eger cagiran taraf bilinçli olarak `actual_price: 0` gonderirse (orn. gercek satis fiyati 0 TL — teorik/uc durum ama payload'da acikca belirtilmis), bu deger yok sayilip yerine `inv.current_price` kullanilir; kullanicinin actual_price'i gormezden gelinir.
- **Kanit:** satir 208.
- **Aksiyon:** `payload.get("actual_price")` icin `is not None` kontrolu kullan: `payload["actual_price"] if payload.get("actual_price") is not None else (inv.current_price or 0.0)`.
- **Onem:** Dusuk · **Guven:** Kesin (kod okuma ile net, ama pratikte 0 TL satis fiyati son derece nadir bir senaryo)

### [SE-010] `_next_payment_in_window` her zincirlenmis cagrida orijinal tarihten yeniden tarar (verimlilik)
- **Sorun:** `a.next_payment_date` `_project_forward` icinde hic ilerletilmiyor/guncellenmiyor (satir 366-381); bu yuzden `simulate_action`'in zincirlenmis her `_project_forward` cagrisinda (T+30, sonra T+60, sonra T+90) fonksiyon HER SEFERINDE orijinal `next_payment_date`'ten baslayip yeni `end`'e kadar ay ay tarama yapiyor — onceki cagrilarda zaten taranmis aylar tekrar taraniyor (sadece `cursor >= start` filtresiyle eleniyor). `next_payment_date` cok eski bir tarihse (orn. yillar once), bu O(ay sayisi) kadar gereksiz iterasyon anlamina gelir.
- **Kanit:** satir 313-332 (fonksiyon her zaman `next_pay`'den basliyor), satir 369 (her `_project_forward` cagrisinda `a.next_payment_date` degismeden tekrar kullaniliyor).
- **Aksiyon:** Performans kritik degilse dusuk oncelikli; SE-001 duzeltilirken (odeme durumunun "son islenen tarih" ile takip edilmesi) bu da dogal olarak cozulur.
- **Onem:** Dusuk · **Guven:** Kesin
