# Denetim: app/routers/goals.py

> **M86 güncellik:** 🔴 BAYAT — RGO-001/002/003/007 düzeltildi (BUG#072/136)


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RGO-001] Manuel allocation tutari gercek transaction tutariyla dogrulanmiyor -> sanal zenginlik riski
- **Sorun:** create_allocation (POST /{goal_id}/allocations) payload.amount degerini dogrudan link_transaction'a geciriyor. Transaction bulunup sahiplik kontrolu yapiliyor (200-205) ama tx.amount ile payload.amount arasinda hicbir iliski/sinir kontrolu yok. schemas.GoalAllocationCreate.amount da herhangi bir gt/le kisiti tasimiyor (app/schemas.py:290-292). Kullanici 10 TL'lik bir transaction'i goal'e "1.000.000 TL katki" olarak baglayabilir; current_amount/progress_percent bu uydurma degerden hesaplanir (goal_engine._compute_cash_target, current = sum(GoalAllocation.amount)).
- **Kanit:** satir 186-222 (ozellikle 200-214); schemas.py satir 290-292 destekleyici kanit.
- **Aksiyon:** create_allocation icinde abs(payload.amount) <= abs(tx.amount) (veya esitlik) dogrulamasi ekle; ya da amount parametresini kaldirip tx.amount'u otomatik kullan.
- **Onem:** Kritik · **Guven:** Kesin

### [RGO-002] Ayni transaction birden fazla goal'e tam tutarla baglanabiliyor -> cift sayim
- **Sorun:** GoalAllocation.uq_goal_tx unique constraint'i sadece (goal_id, transaction_id) ciftini korur (models.py 801-802). create_allocation bu transaction'in baska bir goal'e zaten baglanip baglanmadigini kontrol etmiyor. Ayni 5.000 TL'lik gercek para hem "Acil Durum Fonu" hem "Tatil Fonu" goal'ine tam tutarla baglanabilir; iki goal'in current_amount toplami gercekte var olmayan 10.000 TL "ilerleme" gosterir. Kok vizyon ilkesi #3 (cift-sayma yasak) ile dogrudan celisiyor.
- **Kanit:** satir 186-222 (link_transaction cagrisi oncesi capraz-goal kontrolu yok).
- **Aksiyon:** Ayni transaction_id icin diger goal'lerdeki mevcut allocation toplamini sorgula, yeni allocation'in transaction'in gercek tutarini asmasini engelle (tum goal'ler uzerinde toplam <= tx.amount).
- **Onem:** Kritik · **Guven:** Kesin

### [RGO-003] GoalRead datetime alanlari tzinfo=utc olmadan donduruluyor -> frontend'de 3 saat kayma
- **Sorun:** docs/architecture.md ve app/PROJE.md acikca sart kosuyor: "Frontend'e tarih donen her endpoint'te serialize oncesi tzinfo=timezone.utc ekle" (referans pattern: coach.py _memory_to_history_item). goals.py'deki hicbir endpoint (create_goal, list_goals, get_goal, update_goal, refresh_goal_endpoint) bu donusumu yapmiyor; ORM nesnesi dogrudan response_model=schemas.GoalRead ile donuluyor. GoalRead.created_at/updated_at/last_refreshed_at/achieved_at (schemas.py 284-287) naive UTC datetime olarak serialize edilir, JS bunlari yerel saat sanip Turkiye'de 3 saat geri gosterir (orn. goal olusturma zamani, son refresh zamani, achieved_at).
- **Kanit:** satir 49-83 (create_goal donusu), 86-99 (list_goals), 102-114 (get_goal), 117-140 (update_goal), 160-176 (refresh_goal_endpoint); karsilastirma icin app/routers/coach.py'deki tzinfo=timezone.utc pattern'i.
- **Aksiyon:** Goal ORM -> GoalRead donusumunde created_at/updated_at/last_refreshed_at/achieved_at alanlarina .replace(tzinfo=timezone.utc) uygulayan bir serialize helper ekle (coach.py'deki pattern ile tutarli).
- **Onem:** Yuksek · **Guven:** Kesin

### [RGO-004] create_allocation goal.status kontrolu yapmiyor
- **Sorun:** Goal "paused" veya "abandoned" durumundayken bile create_allocation cagirilip yeni allocation eklenebiliyor; ardindan link_transaction icinde refresh_goal cagrilir (goal_engine.py 223) ve progress_percent guncellenir. Kullanici duraklattigi/vazgectigi bir hedefin ilerleme yuzdesi arka planda degismeye devam eder, UI'da tutarsiz gorunur.
- **Kanit:** satir 186-222 (goal.status hic okunmuyor).
- **Aksiyon:** create_allocation basinda goal.status == "active" degilse 409/400 dondur (veya en azindan uyar).
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RGO-005] create_allocation goal_type'i "cash_target" ile sinirlamiyor -> debt_freedom'da etkisiz veri
- **Sorun:** debt_freedom goal'lerin ilerlemesi sadece Account bakiyelerinden hesaplanir (goal_engine._compute_debt_freedom), GoalAllocation hic okunmaz. Router bu ayrimi zorlamiyor; bir debt_freedom goal'ine manuel allocation eklenebilir, kayit DB'de durur, list_allocations'ta gorunur ama progress_percent'e hicbir etkisi olmaz. Kullaniciyi yaniltan olu/etkisiz veri.
- **Kanit:** satir 186-222; goal_engine.py 62-96 (baseline/current_debt hesaplamasinda GoalAllocation kullanilmiyor).
- **Aksiyon:** create_allocation'da goal.goal_type != "cash_target" ise 400 dondur, veya UI/API dokumantasyonunda acikca belirt.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [RGO-006] delete_allocation / update_rule / delete_rule: sahiplik kontrolunden once ID'ye gore var-yok sorgulanmasi (dusuk seviye IDOR/enumeration izi)
- **Sorun:** delete_allocation (253-257), update_rule (335-339) ve delete_rule (363-367) once ID'ye gore (kullanici filtresi olmadan) kaydi bulup 404/403 farkli koduyla donuyor. Bu, saldirganin "bu ID var ama baska kullaniciya ait" ile "bu ID hic yok" durumlarini status kodundan ayirt etmesine izin verir (404 vs 403). Tek-kullanicili MVP'de risk dusuk ama multi-user gecise (dependencies.py get_current_user JWT plani) hazir degil.
- **Kanit:** satir 253-265, 335-347, 363-374.
- **Aksiyon:** Sorguyu bastan user_id join'i ile yap (orn. GoalAllocation.join(Goal).filter(Goal.user_id==current_user.id)), her iki durumda da 404 dondur.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RGO-007] GoalAllocationCreate.amount icin sifir/negatif sinir yok
- **Sorun:** schemas.GoalAllocationCreate.amount (schemas.py 290-292) hicbir kisit tasimiyor (gt/lt/ne yok). amount=0 gonderilerek anlamsiz bir allocation satiri yaratilabilir (hicbir mali etkisi olmayan cop kayit, unique constraint'i de bosa harcar - o transaction bir daha gercek bir tutarla baglanamaz cunku (goal_id, transaction_id) zaten dolu).
- **Kanit:** satir 183-222; schemas.py 290-292.
- **Aksiyon:** schemas.py'de `amount: Decimal = Field(..., ne=0)` benzeri bir kisit ekle; router seviyesinde de payload.amount == 0 icin erken red.
- **Onem:** Dusuk · **Guven:** Kesin
