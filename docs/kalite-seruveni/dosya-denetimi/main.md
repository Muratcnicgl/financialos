# Denetim: app/main.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [MN-001] app/PROJE.md ile kod arasinda create_all celiskisi
- **Sorun:** app/PROJE.md acikca soyle diyor: "main.py kucuk tutulur: app yaratimi, CORS, router kayit, startup `create_all`." Ancak gercek main.py'de create_all cagrisi yok; lifespan sadece log basip catch-up backfill ve scheduler calistiriyor. Kod ADR-013'e atifla "Schema yonetimi alembic ile" diyor (satir 112). Bu, ADR-013'un app/PROJE.md'ye hic yansitilmamis olmasindan kaynaklaniyor — dokumantasyon kod gercekligini yansitmiyor. Yeni bir gelistirici app/PROJE.md'yi okuyup create_all bekleyebilir ya da migration'i unutup DB schema'sinin kendiliginden olusacagini sanabilir.
- **Kanit:** satir 112-113 (kod); app/PROJE.md "Yapi" bolumu (create_all ifadesi)
- **Aksiyon:** app/PROJE.md "Yapi" bolumunu ADR-013'e gore guncelle: "startup create_all" yerine "startup: catch-up backfill + scheduler baslatma; schema alembic upgrade head ile yonetilir" yazilmali.
- **Onem:** Orta · **Guven:** Kesin

### [MN-002] CORS allow_origins listesinde production origin yok
- **Sorun:** docs/architecture.md "prod'da app/main.py'deki listede" diyerek prod origin'lerin buraya eklenecegini varsayiyor, ancak su an listede sadece localhost:5173/3000 ve 127.0.0.1 varyantlari var (satir 154-159). Prod'a deploy edilirse ya CORS tamamen kirilir ya da acele bir hotfix ile origin eklenir; bu satirlar simdiden bir env-degiskenine tasinip gelistirme/prod ayrisimi yapilmamis.
- **Kanit:** satir 152-163
- **Aksiyon:** Prod deploy plani netlesince origin listesini env değişkeninden okuyacak sekilde parametrize et (orn. `ALLOWED_ORIGINS` .env anahtari), boylece main.py'ye her ortam degisikliginde dokunulmaz.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (henuz prod deploy'u olmayan bir MVP oldugu icin aciliyet dusuk)

### [MN-003] _catch_up_snapshots ve run_backfill ayri DB session'lari ile calisiyor
- **Sorun:** `_catch_up_snapshots` (main.py) kendi `db = SessionLocal()` session'inda `last_date` sorgusu yapiyor, sonra `run_backfill(start, today)` (scripts/backfill_net_worth.py) tamamen ayri bir `SessionLocal()` aciyor ve User'i yeniden sorguluyor. Iki ayri session SQLite'ta sorun cikarmaz (WAL/serialize) ama kullanicinin `_catch_up_snapshots` icinde zaten yuklenen `user` objesi hic run_backfill'e pasaslanmiyor — gereksiz ikinci DB round-trip. Fonksiyonel bug degil ama gereksiz coupling/verimlilik kaybı.
- **Kanit:** satir 77-104 (main.py) + run_backfill satir 214-220 (scripts/backfill_net_worth.py)
- **Aksiyon:** Onem dusuk, degistirmeye gerek yok; sadece not dusuldu. Istenirse run_backfill'e opsiyonel `db`/`user` parametresi eklenip tek session paylasilabilir.
- **Onem:** Dusuk · **Guven:** Kesin

### [MN-004] Genis except Exception blocklari sessizce (sadece warning log ile) yutuluyor
- **Sorun:** Lifespan icinde catch-up backfill (satir 114-118), scheduler start (122-125) ve scheduler shutdown (130-133) hatalari `except Exception` ile yakalanip sadece `logger.warning` ile geciliyor; app'in acilmasini engellememe niyeti docstring'de acik (satir 73) oldugu icin bu tasarim kasitli. Ancak scheduler baslatilamazsa (orn. A1/A2 hatirlatma/recurring islem tetikleyicileri) kullanici arayuzde hicbir sinyal gormeden proaktif ozellikler sessizce devre disi kalir — PROJE.md'nin "sessiz except: pass yasak" ilkesine harfiyen uymasa da (log var, pass yok) operasyonel gorunurluk riski tasiyor.
- **Kanit:** satir 114-118, 122-125, 130-133
- **Aksiyon:** Bug degil, bilinen trade-off. Istenirse scheduler basarisiz olursa /api/health cevabina "scheduler_status" alani eklenerek gorunurluk artirilabilir (Wave-3 fikri, simdi kodlanmasin).
- **Onem:** Dusuk · **Guven:** Dogrulanmali

Genel not: Router kayitlari (Grup 1-5), health endpoint'leri ve CORS middleware kurulumu satir satir incelendi; finansal matematik main.py icinde yapilmiyor (Rules Engine ayrimina sadik), DB'ye dogrudan yazim yok, timezone kullanimi (`datetime.now(timezone.utc)`, satir 205) dogru — naive degil aware. Kritik/Yuksek seviyede bulgu yok.
