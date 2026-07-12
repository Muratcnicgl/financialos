# Denetim: app/rules_engine.py

> Not: Bu dosya daha once docs/kalite-seruveni/sections/RULE.md altinda dimension-bazli
> taranmis (RULE-001..040, ozellikle RULE-003/004/005/006/007/008/009/020/021/022/024/026/
> 027/028/035/036/039 bu dosyayla ilgili). Asagidaki bulgular o taramanin KACIRDIGI, ozellikle
> "olu kod" ve dogrudan formul disi incelikler — tekrar yok.

### [RE-001] `evaluate_credit_card_strategy` (MC3 kart stratejisi) hicbir yerden cagrilmiyor — tamamen olu kod
- **Sorun:** Fonksiyon modul docstring'inde madde 4 olarak listelenmis ("Kart stratejisi"), `docs/architecture/origin-vision.md` bunu "Ziraat kart dongusu ... kart stratejik silah" olarak kok vizyonun bir parcasi sayiyor. Ama repo genelinde `evaluate_credit_card_strategy(` sadece kendi tanimini eslesiyor — `generate_cockpit` cagirmiyor, hicbir router/coach.py/frontend tuketmiyor. Dondurdugu `vade_avantaji`/`kesim_dikkat`/`odeme_dikkat` durumlari da grep'te sadece bu dosyada ve RULE.md'de geciyor. Yani MC3 kart-dongusu analizi kullaniciya veya LLM'e HICBIR sekilde ulasmiyor.
- **Kanit:** `app/rules_engine.py:166` (tanim) — `generate_cockpit` (satir 629-796) icinde cagri yok; repo-capinda grep `evaluate_credit_card_strategy\(` yalnizca satir 166'yi buluyor.
- **Aksiyon:** Ya `generate_cockpit` cockpit dict'ine `kart_stratejisi: evaluate_credit_card_strategy(...)` olarak bagla (kredi karti hesaplari icin), ya da fonksiyonu ve dogstring maddesini kaldirip vizyon belgesinden cikar — su anki hal "ozellik var" izlenimi verip aslinda hicbir sey yapmiyor (sanal ozellik, kok vizyondaki "sanal zenginlik yasak" ilkesiyle ayni ailede bir yaniltma riski).
- **Onem:** Yuksek · **Guven:** Kesin

### [RE-002] `parse_gg_command` + `GG_PATTERN` ("gg" hizli harcama komutu) production'da hic kullanilmiyor
- **Sorun:** Modul docstring'inde madde 7 "Komut cozumleme" olarak listelenen bu ozellik, sadece bagimsiz test script'i `test_rules.py`'de cagriliyor. `app/routers/` altinda, `app/coach.py`'de veya `frontend/src/` altinda `parse_gg_command`/`GG_PATTERN`/"gg " komutuna dair hicbir referans yok. Yani kullanicinin "gg 50 yemek" yazarak hizli harcama girme ozelligi hicbir endpoint'e baglanmamis.
- **Kanit:** `app/rules_engine.py:873-905`; repo-capinda grep sadece `test_rules.py:7,22-25` ve `docs/kalite-seruveni/sections/TEST.md:22` (gelecekte test eklenmesi onerisi) donuyor.
- **Aksiyon:** Ozellik gercekten istenen bir UX ise bir router endpoint'ine (orn. `POST /api/transactions/quick`) bagla; degilse dosyadan/docstring'den cikar ki "var" sanilan bir ozellik yanlislikla guvenilir gorunmesin.
- **Onem:** Orta · **Guven:** Kesin

### [RE-003] `get_next_occurrence` off-by-one: bugun == gun-of-month ise bir ay atliyor
- **Sorun:** Satir 97'de `if today.day < target_day: return ...` kosulu KATI (strict) `<` kullaniyor. `today.day == target_day` oldugunda (yani olay TAM BUGUN gerceklesecekse) bu dal calismaz, fonksiyon dogrudan "sonraki aya gec" bloguna duser ve bugunku gerceklesmeyi atlayip bir ay sonrasini doner. Karsilastirma: ayni dosyadaki `_get_next_due_date` (satir 475-484) `if candidate < today: sonraki aya gec` kullaniyor — `candidate == today` durumunda dogru sekilde BUGUNU doner. Iki fonksiyon ayni is icin farkli (ve biri hatali) mantik tasiyor.
- **Kanit:** `app/rules_engine.py:97` (hatali) vs `app/rules_engine.py:479` (dogru desen)
- **Aksiyon:** `if today.day <= target_day:` yap (esitlik dahil), ya da fonksiyonu tamamen kaldirip `_get_next_due_date` desenine yonlendir.
- **Not:** Fonksiyon su an RE-002/genel olu-kod durumu nedeniyle cagrilmiyor (bkz. grep: sadece kendi tanimi + RULE.md'de RULE-003'un onerdigi "duzeltme" olarak anilıyor). Ama tam da RULE-003 bu fonksiyonu "dogru cozum" olarak onerdigi icin, biri bu tavsiyeyi kor kor uygularsa bu off-by-one'i da production'a tasir.
- **Onem:** Orta · **Guven:** Kesin

### [RE-004] `parse_gg_command` — nokta binlik ayirac sanilip ondalik olarak yorumlaniyor
- **Sorun:** `amount_str = match.group("amount").replace(",", ".")` (satir 896) sadece virgulu noktaya cevirir; zaten nokta iceren bir girdi ("1.234" — Turkce binlik ayiracla 1234 TL kastedilmis olabilir) degistirilmeden `float()`'a verilir ve `float("1.234")` = 1.234 doner. Yani "gg 1.234 kira" komutu kullanicinin kastettigi 1234 TL yerine 1.234 TL (neredeyse sifir) olarak parse edilir — parasal anlamda sessiz, ciddi bir yanlis-tutar hatasi.
- **Kanit:** `app/rules_engine.py:896-897`
- **Aksiyon:** Regex'te binlik ayiraci ondalikdan ayirt et (orn. sadece son `[.,]` grubunu ondalik say, oncekileri binlik olarak temizle) veya kullanicidan tek bir formati (orn. sadece nokta=ondalik, binlik ayiraci yok) acikca isteyip UI'da belirt.
- **Onem:** Dusuk (fonksiyon su an cagrilmiyor — RE-002) ama devreye alinirsa Yuksek etkili · **Guven:** Kesin

### [RE-005] `parse_gg_command` kategori `.lower()` — Turkce buyuk I/İ sorunu
- **Sorun:** `category = match.group("category").strip().lower()` (satir 898) Python'un varsayilan `str.lower()`'i kullanir; bu Turkce yerel kurallarini bilmez. `"İ".lower()` Python'da `"i̇"` (i + birlesik nokta, U+0307) doner, ASCII `"i"` DEGIL; `"I".lower()` ise `"i"` doner (Turkce'de `"ı"` olmasi beklenir). Sonuc: kullanici "İş" ya da "ISLEM" gibi buyuk-Turkce-harfli kategori yazarsa, elde edilen string diger yerlerde ayni kategori icin kullanilan yazimla BIREBIR eslesmeyebilir (orn. `_calculate_category_patterns` GROUP BY category ile boyle bir tutarsizlik kategori kirilmasina yol acar).
- **Kanit:** `app/rules_engine.py:898`
- **Aksiyon:** `category.strip().casefold()` de Turkce sorunu cozmez — `str.translate` ile Turkce-ozel harf haritasi (`İ`→`i`, `I`→`ı`) uygulayan bir yardimci fonksiyon kullan.
- **Onem:** Dusuk (fonksiyon su an cagrilmiyor — RE-002) · **Guven:** Kesin (Python davranisi dogrulanabilir dil ozelligi)

### [RE-006] `detect_alerts` "buyuk odeme" filtresinde nakit icin sifir/negatif koruma yok (mesaj satirinda var, kosul satirinda yok)
- **Sorun:** Satir 852'deki filtre kosulu `p.get("tutar", 0) > nakit * 0.5` CIPLAK `nakit` kullanir — `max(nakit, 1)` guard'i YOK. Nakit negatif veya sifirsa `nakit * 0.5` de negatif/sifir olur, boylece pozitif tutarli HER taksit kosulu gecer ve "7 gun icinde buyuk odeme" uyarisi tetiklenir — esik anlamsizlasip her taksidi "buyuk" sayar (esik kavraminin cignenmesi). Ayni fonksiyonda hemen alti (satir 858) mesaj metninde `max(nakit, 1)` guard'i VAR — yani ayni degisken icin filtre ve mesaj arasinda tutarsiz koruma var.
- **Kanit:** `app/rules_engine.py:852` (guard yok) vs `app/rules_engine.py:858` (guard var)
- **Aksiyon:** Filtre kosulunu da `p.get("tutar", 0) > max(nakit, 0) * 0.5` (ya da nakit<=0 icin ayri "nakit yok, her odeme kritik" dali) ile hizala.
- **Onem:** Dusuk · **Guven:** Kesin

Temiz: yukaridaki 6 madde disinda, dosyanin geri kalaninda (bkz. RULE-001..040 zaten belgelenmis formul/yuvarlama/tarih bulgulari haric) yeni kritik bulgu yok.
