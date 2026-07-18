# Denetim: app/routers/reports.py

> **M86 güncellik:** 🟡 KISMEN-BAYAT — RRE-001/002 düzeltildi (BUG #073/074); RRE-003 açık


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RRE-001] "both" modunda gelir ve gider ayni kategori satirinda karisiyor
- **Sorun:** category_breakdown endpoint'inde group_by sadece Transaction.category'e gore yapiliyor (satir 74-75), transaction_type'a gore degil. type="both" secildiginde bir kullanicinin ayni kategori adini hem gelir hem gider icin kullanmasi (orn. "diger", "yatirim") o kategoriye ait income amount'lari ile expense amount'lari tek bir "total" alaninda toplaniyor.
- **Kanit:** satir 56-78 (query + group_by), ozellikle satir 65-72 (type filtresi) ve satir 74-78 (group_by/order_by sadece category uzerinden)
- **Kanit-senaryo:** "diger" kategorisinde 1000 TL gelir + 200 TL gider varsa, type="both" cevabinda tek satir donuyor: category="diger", total=1200, count=2 — oysa gercek net etkisi +800, gorunen toplam ise yon bilgisini kaybederek 1200 gosteriyor. percentage de bu hatali toplama gore hesaplaniyor (satir 87).
- **Aksiyon:** group_by'i (transaction_type, category) ikilisine gore yap, ya da "both" modunda gelir/gider satirlarini ayri tutup response'a type alani ekle.
- **Onem:** Kritik · **Guven:** Kesin

### [RRE-002] Kredi hesaplarinda sadece tek bir sonraki taksit gosteriliyor, uzun ufuklu raporda gercek yuku ciddi eksik gosterir
- **Sorun:** upcoming_cashflow, RecurringIncome/RecurringExpense icin _next_occurrences ile ufuk boyunca TUM aylik tekrarlari uretiyor (satir 207, 216), ama Account(loan) icin sadece Account.next_payment_date alanindaki TEK tarihi kullaniyor (satir 193-200). days=180 gibi genis bir ufukta 5 krediden her biri aslinda ~6 taksit odeyecekken rapor sadece 1'er taksit gosteriyor.
- **Kanit:** satir 192-200 (next_payment_date tek deger, tekrar mantigi yok) vs satir 202-218 (RecurringIncome/Expense icin donguyle coklu tarih uretimi)
- **Kanit-senaryo:** days=180, bir kredinin aylik taksiti 5000 TL. Gercekte 6 ay boyunca toplam 30.000 TL odenecek ama total_payable'da sadece 5000 TL gorunuyor. net_flow bu yuzden oldugundan cok daha pozitif/iyimser cikar — kok vizyon prensibi "sanal zenginlik yasak" ile dogrudan celisen bir eksik-gosterim riski.
- **Aksiyon:** Loan hesaplari icin de next_payment_date'ten baslayarak ufuk sonuna kadar aylik tekrar ureten bir _next_occurrences benzeri mantik uygula (monthly_payment doneminin biliniyor olmasi kosuluyla), veya en azindan response'a "bu sadece bir sonraki taksit, toplam kredi yuku degil" uyarisi ekle.
- **Onem:** Yuksek · **Guven:** Kesin (kod okunarak dogrulandi; is mantigi varsayimi acik)

### [RRE-003] due_date / next_payment_date icin alt sinir (bugunden once) filtresi yok — vadesi gecmis kalemler "upcoming" listesine kariyor
- **Sorun:** PersonalDebt sorgularinda (satir 169-190) ve Account(loan) sorgusunda (satir 193-198) sadece `<= horizon` filtreleniyor, `>= today` yok. Vadesi yillar once gecmis, hala is_paid=False olan bir alacak/borc da "upcoming-cashflow" (yaklasan nakit akisi) raporuna dahil oluyor.
- **Kanit:** satir 169-174, 181-186, 193-197
- **Aksiyon:** Ya niyet aciklikla "vadesi gecmis + yaklasan hepsi dahil" ise docstring'e yaz (satir 160-163 guncelle), ya da gecmis vadeli kalemleri ayri bir "overdue" grubuna ayirip "upcoming" listesinden cikar — aksi halde today alaninin (satir 235) altinda tarihli item'lar donerken kullanicinin "yaklasan" beklentisiyle celisir.
- **Onem:** Orta · **Guven:** Kesin

### [RRE-004] app/PROJE.md'nin "session.query() eski pattern" kuralina aykiri
- **Sorun:** Backend kurallari (app/PROJE.md) SQLAlchemy 2.x'te select()/session.execute() tercih edilmesini, session.query()'nin eski pattern oldugunu belirtiyor. Bu dosyadaki tum sorgular db.query(...) kullaniyor.
- **Kanit:** satir 56, 117, 169, 181, 193, 203, 212
- **Aksiyon:** select()/db.execute() pattern'ine tasi (bu dosyaya ozgu, sistemik bir refactor gerekebilir; en azindan yeni kod bu kurala uymali).
- **Onem:** Orta · **Guven:** Kesin (docstring/PROJE.md kurali acik referans)

### [RRE-005] Matematiksel toplama/yuzde hesabi router icinde yapiliyor, rules_engine.py'de degil
- **Sorun:** app/PROJE.md: "Rules Engine Kurali — matematiksel hesap buraya (rules_engine.py) girer, router'a girmez." Bu dosyada sum/percentage/round hesaplari (satir 80-90, 223-231) dogrudan router icinde yapiliyor.
- **Kanit:** satir 80-90 (grand_total, percentage), satir 223-231 (total_receivable/payable/net_flow)
- **Aksiyon:** Bu raporlama mantigi ayri bir modulde (orn. app/reports_engine.py) toplanip router sadece cagirir hale getirilebilir; en azindan mimari karar olarak dokumante edilmeli (rules_engine.py sadece cockpit karar mantigi icin mi, yoksa tum matematiksel hesap icin mi kapsiyor netlestirilmeli).
- **Onem:** Dusuk · **Guven:** Dogrulanmali (mimari niyet net degil; rules_engine.py'nin kapsami "cockpit karar mantigi" mi yoksa "tum finansal matematik" mi oldugu docs/architecture.md'de acik degil)

### [RRE-006] day_of_month sinir disi deger icin savunmasiz — beklenmeyen ValueError riski
- **Sorun:** _next_occurrences (satir 141-151) day_of_month'u sadece ust sinirdan (ayin son gunu) kirpiyor: `min(day_of_month, last)`. Alt sinir kontrolu yok. day_of_month DB'de sadece Integer, CheckConstraint yok (app/models.py satir 194, 213 sadece yorumda "1-31" yaziyor, kod seviyesinde zorlanmiyor).
- **Kanit:** satir 147 (min(day_of_month, last)); app/models.py satir 194 ve 213 (constraint yok)
- **Kanit-senaryo:** day_of_month=0 veya negatif bir deger DB'ye herhangi bir yoldan (script, manuel veri, gelecekte gevsek bir create endpoint) yazilirsa, `date(cur.year, cur.month, min(0, last))` -> `date(y, m, 0)` ValueError firlatir, endpoint 500 doner, try/except yok.
- **Aksiyon:** _next_occurrences basinda `day_of_month = max(1, min(day_of_month, 31))` gibi bir clamp ekle, ya da create endpoint'lerinde (bu dosyanin disinda) Pydantic Field(ge=1, le=31) ile garanti altina al.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (bu dosyanin disindaki create endpoint'lerinin gercekte 1-31 validasyonu yapip yapmadigi kontrol edilmedi)

### [RRE-007] since = today - timedelta(days) alt siniri dahil (>=) oldugundan pencere aslinda days+1 gun
- **Sorun:** category_breakdown (satir 54) ve net_worth_trend (satir 115) icin `since = date.today() - timedelta(days=days)` sonra `>= since` filtreleniyor. Bu, bugun dahil days+1 gunluk bir pencere anlamina gelir (orn. days=30 icin 31 gun).
- **Kanit:** satir 54/62, satir 115/120
- **Aksiyon:** Niyet "son N gun" ise `since = date.today() - timedelta(days=days-1)` ya da `> since` kullanilmali; niyet zaten "days+1 gun dahil" ise docstring'e (satir 6, 111) acikca yazilmali.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (off-by-one'in kasitli mi tasarim mi hata mi oldugu belirsiz)

### [RRE-008] Kategori bazli yuvarlama ile grand_total yuvarlamasi arasinda kurus tutarsizligi olabilir
- **Sorun:** Her CategoryItem.total ayri ayri round(r.total, 2) ile yuvarlaniyor (satir 85), grand_total ise ham (yuvarlanmamis) r.total degerlerinin toplaminin ayrica round edilmesiyle hesaplaniyor (satir 80, 94). Bagimsiz yuvarlamalar sum(items.total) != grand_total sonucuna yol acabilir (bir-iki kurus fark).
- **Kanit:** satir 80 (grand_total ham toplam), satir 85 (item bazli round), satir 94 (grand_total'in kendi round'u)
- **Aksiyon:** grand_total'i yuvarlanmis item.total degerlerinin toplami olarak hesapla (tutarlilik icin), ya da farkin onemsiz oldugu bilinerek bilincli kabul edildigini not et.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (Float hassasiyeti nedeniyle pratikte fark genellikle 0.01 TL'nin altinda kalir, ama garanti degil)
