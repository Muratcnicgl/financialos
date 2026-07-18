# Denetim: scripts/setup_data.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [SSD-001] drop_all icin hicbir guardrail/onay adimi yok
Sorun: Script calistirildigi an, hangi ortama bagli oldugu (DATABASE_URL) veya kullanicidan onay alinmadan tum veritabanini siliyor. PROJE.md bu scriptin "manuel veri silinir, sadece test oncesi calistir" seklinde davranissal bir kural olarak belgelenmis olmasi, kod seviyesinde bir korumanin yoklugunu telafi etmiyor.
Kanit (satir): 35-38 `Base.metadata.drop_all(bind=engine)` / `Base.metadata.create_all(bind=engine)` — herhangi bir `input()` onayi, `--yes` flag kontrolu veya `DATABASE_URL` icerik kontrolu yok.
Aksiyon: Calistirilmadan once en azindan bir interaktif onay (`input("Emin misin? (evet/hayir): ")`) veya `--force` gibi bir CLI flag'i eklenmeli; ayrica DATABASE_URL'in gelistirme DB'sine isaret ettigi dogrulanmali (ornegin "financialos.db" disinda bir isim iceriyorsa uyar).
Onem: Kritik
Guven: Yuksek

### [SSD-002] Docstring'deki alacak sayisi (13) gercek veriyle (15) celisiyor
Sorun: Modul docstring'i "13 alacak (Efe takvimi, 13 ay yayili)" diyor, ancak `efe_takvim` listesinde fiilen 15 kayit var ve kod ici yorum da (satir 212) "15 odeme" diyerek bunu dogruluyor. Ayrica takvim 2026 Mayis - 2027 Ocak arasi 9 ayi kapsiyor, "13 ay" degil.
Kanit (satir): 16 (`13 alacak (Efe takvimi, 13 ay yayili)`) vs 212 (`15 odeme, toplam 29.635 TL`) vs 214-237 (liste 15 tuple iceriyor, tarihler Mayis 2026 - Ocak 2027 arasinda, 9 ay).
Aksiyon: Docstring 15 alacak / 9 ay olacak sekilde duzeltilmeli; bu tur ozet metinlerin kod ile senkron kalmasi icin mumkunse `len(efe_takvim)` gibi hesaplanan degerden turetilmesi tercih edilmeli.
Onem: Orta
Guven: Yuksek

### [SSD-003] Ozet ciktisindaki hesap/alacak/checkpoint sayilari hardcoded, koddan turetilmiyor
Sorun: OZET blogunda yazdirilan "Hesap : 8", "Alacak : 15 (...)" ve "Checkpoint : 7" satirlari elle yazilmis sabit metinler; SSD-002'de gosterildigi gibi liste ile metin arasinda sessizce sapma olabiliyor ve script bunu hicbir sekilde tespit etmiyor (hata vermiyor, uyarmiyor).
Kanit (satir): 349 (`Hesap        : 8 ...`), 351 (`Alacak       : 15 ...`), 352 (`Checkpoint   : 7 ...`).
Aksiyon: Bu sayilar `len(accounts_listesi)`, `len(efe_takvim)`, `len(checkpoints)` gibi calisma-zamani degerlerinden uretilmeli; boylece liste degisirse ozet otomatik dogru kalir.
Onem: Dusuk
Guven: Yuksek

### [SSD-004] RecurringExpense kayitlarinda account_id hardcoded (magic number)
Sorun: Netflix/Spotify/Internet giderleri `account_id=2` ile Ziraat kartina sabitlenmis. Bu deger, `enpara` ve `ziraat` objelerinin flush sirasinda sirasiyla id=1 ve id=2 alacagi varsayimina dayaniyor; kodda bu iliski aciklanmiyor, degiskenden (`ziraat.id`) degil literal sayidan geliyor.
Kanit (satir): 197-202 (`account_id=2` ucer kez).
Aksiyon: `account_id=2` yerine `account_id=ziraat.id` kullanilmali — bu hem okunurlugu artirir hem de hesap ekleme sirasi degisirse (ornegin yeni bir hesap araya eklenirse) sessizce yanlis hesaba gider baglanmasini engeller.
Onem: Yuksek
Guven: Yuksek

### [SSD-005] Genis except blogu hatayi yutmuyor ama tani bilgisi zayif
Sorun: `except Exception as e` tum hata turlerini yakalayip sadece `str(e)` basiyor; rollback + raise yapildigi icin veri sessizce kaybolmuyor (iyi), fakat hangi asamada (hangi INSERT, hangi obje) hata olustugu konusunda hicbir baglam (traceback, hangi kayit) verilmiyor, bu da 8 hesap + 15 alacak + 7 checkpoint'lik uzun bir insert zincirinde debug'i zorlastirir.
Kanit (satir): 372-375 (`except Exception as e: db.rollback(); print(f"\nHATA: {e}"); raise`).
Aksiyon: En azindan `import traceback; traceback.print_exc()` eklenmeli veya `logging.exception` kullanilmali; boylece hatanin hangi satirdan geldigi ayrica loglanir.
Onem: Dusuk
Guven: Orta

### [SSD-006] TLY hesabinda balance ile lot_count*current_price arasindaki fark aciklanmis ama dogrulanmamis
Sorun: `balance=31342.82` degeri yorumda "6 * 5223.81 = 31342.86 ama Midas 31342.82 gosteriyor" diye aciklaniyor; yani balance alani hesaplanan degerden degil, disaridan (Midas uygulamasindan) elle girilen bir deger. Bu, `balance`in `lot_count * current_price` ile her zaman tutarli olacagi varsayimini kiran bir kenar durum ve rules_engine.py'nin bu iki degeri nasil kullandigi bu dosyadan gorunmuyor.
Kanit (satir): 153 (`balance=31342.82, # 6 * 5223.81 = 31342.86 ama Midas 31342.82 gosteriyor`).
Aksiyon: Dogrulanmali — `app/rules_engine.py` icinde yatirim hesaplari icin `balance` mi yoksa `lot_count * current_price` mi kaynak olarak kullaniliyor incelenmeli; iki alan farkli yerlerde farkli amaçlarla kullaniliyorsa bu bilinen sapma bir yorumla degil kod seviyesinde (ornegin bir "manuel_duzeltme" alani) belgelenmeli.
Onem: Dusuk
Guven: Orta

### [SSD-007] KYK Bursu geliri docstring'de ve OZET'te hic gecmiyor
Sorun: Docstring "1 periyodik gelir (Maas)" diyor (satir 15) ve OZET blogu da sadece "Gelir : 1 (Maas 8300 TL/ay, ayin 1'i)" yazdiriyor (satir 350), ama kodda hem Maas hem de KYK Bursu (4000 TL/ay) olusturuluyor — yani gercekte 2 periyodik gelir var.
Kanit (satir): 15 (docstring, "1 periyodik gelir (Maas)"), 182-190 (KYK Bursu RecurringIncome olusturuluyor), 350 (OZET'te sadece Maas sayiliyor, KYK atlanmis).
Aksiyon: Docstring ve OZET metni 2 gelire (Maas + KYK Bursu) gore guncellenmeli; ayrica net deger hesaplamasinda (355-367) bu aylik gelirlerin dahil edilip edilmedigi (kasten dahil edilmemis olabilir, cunku bu bir "anlik" net deger, gelecekteki gelir degil) yorum ile netlestirilmeli.
Onem: Orta
Guven: Yuksek
