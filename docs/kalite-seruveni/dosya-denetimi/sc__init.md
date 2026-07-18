# Denetim: scripts/__init__.py

> **M86 güncellik:** 🟢 GÜNCEL — 0 bayt paket marker, bilgi-bulgu


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


## Dosya Durumu

Dosya 0 byte, 0 satir - tamamen bos. Python'da `scripts/` dizinini paket olarak isaretleyen standart bir `__init__.py` marker dosyasi. Icinde denetlenecek kod, import, fonksiyon ya da yapilandirma yok.

Bu nedenle klasik "bug / kenar durum / hardcoded yol / sessiz except / tekrar / magic number" kategorilerinde bulunacak bir sey yok - satir icerigi olmadigi icin bu risk siniflarinin hicbiri bu dosyada fiziksel olarak var olamaz.

## Bulgular

### [SIN-001] Dosya bos, paketin __init__ davranisi tanimsiz

**Sorun:** `scripts/__init__.py` icerik acisindan tamamen bos (0 byte). Bu, `scripts` dizininin bir Python paketi olarak calismasini saglar ama paket seviyesinde hicbir davranis (ornegin `scripts.setup_data` gibi alt modullerin kontrollu disari acilmasi, `__all__` tanimi, versiyon bilgisi) yok.

**Kanit (satir):** Dosyanin tamami - 0 satir/0 byte icerik (Read tool "file has 1 lines" bos satir uyarisi verdi, `wc -c` 0 dondu).

**Aksiyon:** Aksiyon gerekmez - bos `__init__.py` Python paketlerinde yaygin ve gecerli bir pattern. Sadece paket-genelinde ortak bir yardimci (ornegin ortak DB session helper'i ya da `scripts/setup_data.py`, `scripts/backup.py` arasinda paylasilan sabitler) ihtiyaci dogarsa buraya eklenmesi degerlendirilebilir. Su an icin degisiklik onerilmiyor.

**Onem:** Bilgi (Info) - bug/risk degil, durum tespiti.

**Guven:** Yuksek - dosya boyutu ve satir sayisi dogrudan olculdu (0 byte, 0 satir).

### [SIN-002] setup_data.py drop_all riski bu dosyada degil, komsu dosyada

**Sorun:** Talimatta belirtilen "setup_data.py drop_all yapar, veri kaybi riski" uyarisi bu denetimin kapsami olan `scripts/__init__.py` icin gecerli degil - o risk `scripts/setup_data.py` dosyasinda yasiyor, bu dosyada degil. `__init__.py` icinde drop_all cagrisi, import veya baska bir yan etki yok.

**Kanit (satir):** Dogrulanmali - `scripts/setup_data.py` icerigi bu denetimde okunmadi (kapsam disi), sadece PROJE.md talimatinda "scripts/setup_data.py drop_all yapar" ifadesi referans olarak veriliyor.

**Aksiyon:** `scripts/setup_data.py` ayri bir denetim turunda incelenmeli; drop_all cagrisinin manuel/production DB'ye karsi bir guard (ornegin ortam degiskeni kontrolu veya interaktif onay) icerip icermedigi orada dogrulanmali.

**Onem:** Orta - risk gercek ama bu dosyanin kapsami disinda, yanlis dosyaya atfedilmemeli.

**Guven:** Orta - `scripts/setup_data.py` bu oturumda okunmadi, sadece proje dokumantasyonundaki beyana dayaniliyor.

## Sonuc

`scripts/__init__.py` bos bir paket marker dosyasi oldugu icin klasik statik kod bulgularina (hardcoded id, sessiz except, magic number, tekrar) konu olamaz. Tek gercek bulgu, dosyanin kapsam disi oldugunun netlestirilmesi ve gercek drop_all riskinin `scripts/setup_data.py` dosyasina yonlendirilmesidir.
