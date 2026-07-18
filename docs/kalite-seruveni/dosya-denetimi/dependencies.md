# Denetim: app/dependencies.py

> **M86 güncellik:** 🟡 KISMEN-BAYAT — bulgular duruyor ama JWT-öncesi çerçeve bayat


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [DP-001] get_db exception path'inde rollback yok
- **Sorun:** get_db (satir 17-23) sadece finally blogunda db.close() cagiriyor. Bir router icinde exception firlarsa (orn. IntegrityError, ValueError, HTTPException disi bir hata) generator'a exception `throw()` edilir, ancak try/finally sadece close() yapar, rollback() yapmaz. SQLAlchemy session'i pending/failed transaction durumunda kapatilirsa, bagli connection pool'a kirli state ile donebilir; sonraki istekte ayni connection tekrar kullanildiginda "This transaction is inactive" gibi ikincil hatalar veya sessizce yarim-commit edilmis veri riski olusabilir. Standart FastAPI+SQLAlchemy pattern'i genelde `except: db.rollback(); raise` ekler.
- **Kanit:** satir 19-23
- **Aksiyon:** `try/except Exception: db.rollback(); raise/finally: db.close()` seklinde genisletilmesi degerlendirilmeli.
- **Onem:** Orta · **Guven:** Dogrulanmali

### [DP-002] db.query() legacy pattern - PROJE.md kuraliyla celisiyor
- **Sorun:** app/PROJE.md acikca "SQLAlchemy 2.x: select() / session.execute() tercih edilir; session.query() eski pattern" diyor. Satir 36'da `db.query(User).order_by(User.id.asc()).first()` legacy `.query()` API'sini kullaniyor. Fonksiyonel bir hata degil (SQLAlchemy 2.x'te .query() hala calisir) ama dosyanin kendisi projenin stil kuralina uymuyor; get_current_user her router'da Depends edilen kritik bir fonksiyon oldugu icin ornek/precedent etkisi var.
- **Kanit:** satir 36
- **Aksiyon:** `db.execute(select(User).order_by(User.id.asc())).scalars().first()` ile degistirilmesi degerlendirilmeli.
- **Onem:** Dusuk · **Guven:** Kesin

### [DP-003] "ilk kullanici" varsayimi User.id.asc() ile id kararliligina bagimli
- **Sorun:** Docstring (satir 28) "ilk olusturulan User'i doner" diyor ve bunu User.id.asc() ile garantiliyor. Bu SQLite AUTOINCREMENT olmadan (varsayilan INTEGER PRIMARY KEY rowid davranisi) id yeniden kullanilabilir teorik durumda dogru olmayabilir; ayrica scripts/setup_data.py drop_all+create_all yaptigi icin normal akiste sorun yok, ancak manuel olarak birden fazla User satiri DB'ye eklenmis/silinmis bir senaryoda "ilk olusturulan" ile "en kucuk id" ayrisabilir. Bu bir bug degil, dokumante edilmemis bir varsayim; tek-kullanici MVP kapsaminda risk dusuk.
- **Kanit:** satir 28, 36
- **Aksiyon:** Bilgi amacli not; multi-user gecisinde (docstring satir 31-34) bu varsayimin JWT ile degistirilecegi zaten planlanmis. Aksiyon gerekmez.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

## Genel Degerlendirme

Dosya kucuk ve odakli; Rules Engine / LLM ayrimi ile ilgisi yok (bu dosya sadece DB session ve auth dependency'si saglar), Master Checkpoint veya finansal matematikle dogrudan etkilesimi yok. Kritik seviyede bulgu yok. En onemli konu DP-001 (rollback eksikligi) — cok kullanicili/yuk altinda connection pool kirlenmesi riski tasir ama tek-kullanici MVP + SQLite senkron kullanimda pratikte az goruculuk yaratir.
