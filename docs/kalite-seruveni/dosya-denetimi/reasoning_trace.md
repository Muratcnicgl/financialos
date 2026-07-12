# Denetim: app/reasoning_trace.py

### [RT-001] Docstring "otomatik nesting" vaadi kodda yok
- **Sorun:** Modul docstring'i (satir 12-27 kullanim ornegi) ve `step()` docstring'i (satir 128-129) soyle diyor: "parent_step_id: ... None ise en son yazilan step parent olur (otomatik nesting)." Ancak `step()` govdesinde (satir 134-143) `parent_step_id` degeri hicbir fallback/otomatik-atama olmadan dogrudan `ReasoningTrace(...)` constructor'ina geciriliyor. `self._step_ids` listesi son yazilan step id'lerini tutuyor ama bu liste `parent_step_id=None` durumunda hic okunmuyor. Sonuc: caller `parent_step_id` gecmedigi surece HER step kok seviyede (`parent_step_id=None`) yaziliyor, "otomatik nesting" gerceklesmiyor.
- **Kanit:** satir 128-129 (docstring vaadi) vs satir 134-143 (gercek implementasyon, fallback yok)
- **Aksiyon:** Ya docstring'i gercek davranisi yansitacak sekilde duzelt ("None ise step root/top-level kalir, nesting icin parent_step_id acikca gecilmeli"), ya da vaat edilen otomatik-nesting mantigini ekle (orn. `parent_step_id = parent_step_id or (self._step_ids[-1] if self._step_ids else None)`). Su an app/coach.py kullanimlari zaten explicit parent_step_id geciyor (retry step'lerinde), yani mevcut davranis production'i bozmuyor ama dokumantasyon yanlis bilgi veriyor ve gelecekteki bir gelistiriciyi/LLM-destekli refactor'u yanlis yonlendirebilir.
- **Onem:** Orta · **Guven:** Kesin

### [RT-002] `step()` finally bloğunda korumasiz commit — DB kaynakli exception orijinal hatayi maskeleyebilir
- **Sorun:** `step()` context manager'i paylasilan (caller ile ortak) `self.db` session'i uzerinde calisir (module docstring satir 10, "recorder = TraceRecorder(db, ...)" — ayni session `chat()` icinde tüm DB yazimlarinda da kullaniliyor). `except Exception as exc: record.error = ...; raise` (satir 149-151) sonrasi `finally` bloğu kosulsuz `self.db.add(record); self.db.commit(); self.db.refresh(record)` calistiriyor (satir 168-170). Eger `with recorder.step(...)` bloğu icinde raise eden exception SQLAlchemy tarafinda session'i "pending rollback" durumuna sokan bir hata ise (orn. IntegrityError/FlushError; su an coach.py'deki cagri noktalarinda boyle bir hata her zaman ic try/except ile yutuluyor ama bu, dosyanin kendi tasarim garantisi degil, cagiran tarafin disiplinine bagli), `finally` icindeki `db.commit()` ikinci bir exception firlatir (orn. `InvalidRequestError: This Session's transaction has been rolled back...`). Bu ikinci exception orijinalin yerine gecer (Python finally-exception-replaces-original davranisi), hem gercek hatanin izini kaybettirir hem de trace kaydinin kendisi hic yazilamaz — sistemin en cok ihtiyac duyacagi an (hata anini izleme) basarisiz olur. Dosyada hicbir yerde `db.rollback()` veya savepoint (`db.begin_nested()`) korumasi yok.
- **Kanit:** satir 147-172 (try/except/finally + kosulsuz commit), ozellikle satir 168-170
- **Aksiyon:** finally bloğunda commit'i `try/except` ile sar; commit basarisiz olursa `self.db.rollback()` yap ve orijinal exception'i (varsa) `raise ... from exc` ile koru, trace yazim hatasini sadece logla. Alternatif: `db.begin_nested()` savepoint pattern'i (projede zaten kullanilan konvansiyon — bkz. proje hafizasi "Savepoint pattern") ile step yazimini caller'in olasi bozuk transaction state'inden izole et.
- **Onem:** Yuksek · **Guven:** Dogrulanmali (bugun app/coach.py'deki tum cagri noktalari ic exception'lari yutuyor, yani su an tetiklenmiyor; ama dosyanin kendi savunmasi yok — gelecekte bir step bloguna DB yazan ve exception'i yutmayan yeni kod eklenirse aninda tetiklenir)

### [RT-003] `set_coach_memory_id` icinde eski-stil `session.query()` kullanimi
- **Sorun:** `app/PROJE.md`: "SQLAlchemy 2.x: `select()` / `session.execute()` tercih edilir; `session.query()` eski pattern." `set_coach_memory_id` (satir 183-189) `self.db.query(ReasoningTrace).filter(...).update(...)` kullaniyor — legacy Query API.
- **Kanit:** satir 183-189
- **Aksiyon:** `update(ReasoningTrace).where(...).values(...)` + `self.db.execute(...)` seklinde SQLAlchemy 2.x `update()` construct'ina gecir (bulk update icin `synchronize_session=False` esdegeri `execution_options` ile korunabilir).
- **Onem:** Dusuk · **Guven:** Kesin

### [RT-004] Her `step()` cagrisi ayri `db.commit()` yapiyor — paylasilan session'da erken/parcali commit riski
- **Sorun:** `step()` finally bloğu her step icin `self.db.commit()` cagiriyor (satir 169). `self.db` caller (CoachEngine.chat) ile paylasilan tek session oldugu icin, bu commit sadece trace satirini degil, o an session'da bekleyen TUM degisiklikleri (baska bir is mantiginin henuz commit etmedigi herhangi bir `db.add(...)`) de kalici hale getiriyor. Bugun app/action_executor.py'deki `propose_action`/`save_insight_action` kendi `db.commit()`'lerini hemen yaptigi icin pratikte cakisma gozlemlenmedi, ama bu TraceRecorder'in kendi ic tasarimindan degil, tesadufen caller'larin "commit-per-write" disiplininden kaynaklaniyor. Ileride "birden fazla DB yazimini tek transaction'da atomik yap" ihtiyaci dogarsa (orn. bir hafta sonraki bir refactor), step bloklari arasina sikisan bu commit'ler sessizce atomikligi bozar.
- **Kanit:** satir 168-172 (her step sonunda `self.db.commit()`)
- **Aksiyon:** Kritik degil, ama TraceRecorder'in "paylasilan session'da her step'i hemen commit eder" davranisini class docstring'ine acikca not dus (satir 86-93 civari) ki gelecekteki bir atomik-transaction refactor'unda bu yan etki gozden kacmasin.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RT-005] `close()` no-op — modul dokumantasyonundaki kullanim ornegiyle tutarli ama ölü kod
- **Sorun:** `close()` (satir 193-195) hicbir sey yapmiyor (`pass`). Modul docstring'indeki (satir 32-33) `finally: recorder.close()` orneginin var olma sebebi bu — ama fonksiyon bugun hicbir kaynak temizlemiyor, sadece gelecekteki bir ihtiyac icin placeholder. Bug degil ama not edilmeye deger: cagiran kod (`app/coach.py` satir 1860) bu no-op'a guveniyor gibi gorunuyor; session/kaynak temizligi gerekirse burada sessizce atlaniyor olabilir.
- **Kanit:** satir 193-195
- **Aksiyon:** Ya docstring'den "kaynagi temizler" cagrisimini kaldir (zaten "Su an no-op" diye belirtilmis, bu yeterli), ya da fonksiyonu tamamen kaldirip cagri noktasini sadelestir. Aksiyon opsiyonel, sadece netlik icin.
- **Onem:** Dusuk · **Guven:** Kesin

## Kapsam Disi Gozlem (bilgi amacli, bulgu degil)

`ReasoningTrace.created_at` (app/models.py satir 698) `server_default=func.now()` ile timezone-naive yaziliyor; bu alan `app/routers/coach.py`'deki `GET /api/coach/trace/{memory_id}` endpoint'inde `TraceStepOut.created_at: datetime` olarak serialize ediliyor (routers/coach.py satir 99, 402+). `docs/architecture.md`'nin belirttigi "`tzinfo=timezone.utc` eklenmeli, aksi halde JS 3 saat geri gosterir" kuralinin bu endpoint'te uygulanip uygulanmadigi bu denetimin kapsami disinda kaldi (dosya reasoning_trace.py degil, routers/coach.py). Ayri bir denetimde kontrol edilmesi onerilir.
