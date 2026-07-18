# Denetim: app/routers/checkpoints.py

> **M86 güncellik:** 🔴 BAYAT — RCH-001/002/003 düzeltildi; RCH-004 kaldı


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RCH-001] created_at timezone-naive donuyor, PROJE.md kuralini ihlal ediyor
- **Sorun:** `app/models.py:281` MasterCheckpoint.created_at `Column(DateTime, default=datetime.utcnow)` ile timezone-naive UTC olarak saklaniyor. `CheckpointOut.created_at: datetime` (satir 56) bu degeri `tzinfo=timezone.utc` eklemeden dogrudan serialize ediyor. `app/PROJE.md` ve `docs/architecture.md` acikca bu adimi zorunlu kilar: "Frontend'e tarih donen her endpoint'te serialize oncesi tzinfo=timezone.utc ekle... eksik birakirsan JS Turkiye saatinde 3 saat geri gosterir."
- **Kanit:** satir 56 (CheckpointOut.created_at), satir 66-81 (list_checkpoints donus degeri), models.py satir 281
- **Aksiyon:** `_memory_to_history_item` (app/routers/coach.py) pattern'ine uyarak response donmeden once `cp.created_at.replace(tzinfo=timezone.utc)` uygula veya CheckpointOut icin bir serializer/validator ekle.
- **Onem:** Yuksek · **Guven:** Kesin

### [RCH-002] Hard-delete korumasi seed'deki gercek kritik checkpoint'leri kapsamiyor
- **Sorun:** `delete_checkpoint` sadece `priority == 1 AND checkpoint_type == CheckpointType.red_line` kombinasyonunu hard-delete'e karsi koruyor (satir 144-149). Ancak `scripts/setup_data.py` icindeki gercek kritik kurallar (MC4 "Golge Muhasebe Kurali", MC5 "Dalkavukluk Yasak", MC6 "Varsayim Yasagi", MC8 "Hayatta Kalma > Yatirim") priority=1 ile fakat `checkpoint_type=CheckpointType.rule` olarak taniml — `red_line` degil. `CheckpointType.red_line` enum'u tanimli olmasina ragmen mevcut hicbir seed kaydinda kullanilmiyor. Sonuc: docstring'in "MC1 gibi kritik kurallari yanlislikla devre disi birakmayi onler" iddiasinin aksine, gercekte sistemdeki en kritik davranissal kurallar (Dalkavukluk Yasak, Varsayim Yasagi vb.) `?hard=true` ile hicbir engelleme olmadan kalici silinebilir.
- **Kanit:** satir 144 (checkpoints.py) vs scripts/setup_data.py satir 282-323 (MC4/MC5/MC6/MC8 checkpoint_type=CheckpointType.rule, priority=1)
- **Aksiyon:** Koruma kriterini genislet — orn. `priority == 1` tek basina yeterli olsun (type'tan bagimsiz), ya da MC4/5/6/8 gibi davranissal kurallari da `red_line` tipine tasi. Mimari niyet netlestirilmeli.
- **Onem:** Kritik · **Guven:** Dogrulanmali (seed verisine dayanir; canli DB'de tip farkli olabilir ama kod + seed script tutarli sekilde bu acigi gosteriyor)

### [RCH-003] update_checkpoint hard-delete korumasini bypass etmeye izin veriyor
- **Sorun:** `update_checkpoint` (satir 98-118) hicbir kisitlama uygulamadan `priority` ve `checkpoint_type` alanlarini degistirebiliyor. Bu, RCH-002'deki koruma kriteri (priority=1 + red_line) dogru calissa bile trivial sekilde atlatilabilir demektir: bir istemci once `PUT /api/checkpoints/{id}` ile korunan checkpoint'in priority'sini 2'ye veya type'ini red_line disina cekip, ardindan `DELETE ?hard=true` ile kalici silebilir. Delete endpoint'indeki kod-seviyesi enforcement (PROJE.md'nin "Master Checkpoint enforcement kod seviyesinde uygulanir" ilkesi) boylece anlamsizlasiyor, cunku enforcement sadece silme anindaki degerlere bakiyor, degistirilebilirligi kontrol etmiyor.
- **Kanit:** satir 112-114 (update_data serbestce priority/checkpoint_type set ediyor), satir 144 (delete korumasi sadece anlik degerlere bakiyor)
- **Aksiyon:** update_checkpoint icinde de ayni koruma kontrolunu uygula: priority=1 + checkpoint_type=red_line (veya RCH-002 duzeltmesi sonrasi genislemis kriter) olan kayitlarin bu iki alaninin degistirilmesini engelle/ayri onay iste.
- **Onem:** Yuksek · **Guven:** Kesin

### [RCH-004] session.query() kullanimi — PROJE.md SQLAlchemy 2.x kuraliyla celisiyor
- **Sorun:** `app/PROJE.md` acikca belirtiyor: "SQLAlchemy 2.x: select() / session.execute() tercih edilir; session.query() eski pattern." Dosyadaki her sorgu (`list_checkpoints`, `update_checkpoint`, `delete_checkpoint`) eski `db.query(...)` pattern'ini kullaniyor.
- **Kanit:** satir 76, 106-108, 138-140
- **Aksiyon:** `select(MasterCheckpoint).where(...)` + `db.execute(...).scalars()` pattern'ine gecir (tutarlilik icin, acil degil).
- **Onem:** Dusuk · **Guven:** Kesin

### [RCH-005] Hata mesajindaki "MC{cp_id}" etiketi yanlis/yanitici olabilir
- **Sorun:** `delete_checkpoint`'in 403 hata mesaji `f"...(MC{cp_id} '{cp.title}')..."` seklinde DB primary key'ini "MC" onekiyle birlestiriyor (satir 147-148). Ancak gercek MC numaralandirmasi (MC1, MC2, ... MC8) `scripts/setup_data.py`'de checkpoint'in `title` alaninin icine gomulmus, DB id ile hicbir iliskisi yok (orn. MC1 silindiginden dolayi id sirasi kaymis olabilir; "MC2" basligi olan kaydin id'si 1 olabilir). Bu durumda hata mesaji "MC1 'MC2 - TLY Kaldirac Stratejisi'" gibi celiskili/yanlis bir cikti uretebilir.
- **Kanit:** satir 147-148; scripts/setup_data.py satir 256-335 (MC numaralari title string'lerinde, id'den bagimsiz)
- **Aksiyon:** Mesajdan `MC{cp_id}` onekini kaldir, sadece `cp.title` ve `cp.id` (acik sekilde "id=" etiketiyle) kullan.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RCH-006] Liste endpoint'inde sayfalama/limit yok
- **Sorun:** `list_checkpoints` tum aktif (veya tum) checkpoint'leri limitsiz donuyor. Tek-kullanici MVP'de checkpoint sayisi az oldugu icin pratikte risk dusuk, ancak `?active_only=false` ile tarihce sorgulaninca soft-delete edilmis tum kayitlar da limitsiz donecek.
- **Kanit:** satir 66-81
- **Aksiyon:** Su an icin gerekli degil; ileride tarihce buyurse `limit`/`offset` eklenebilir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
