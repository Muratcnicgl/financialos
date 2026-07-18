# Denetim: app/routers/debt_strategy.py

> **M86 güncellik:** 🟢 GÜNCEL — RDS-001/002/003 aynen duruyor


> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RDS-001] Exception detayi HTTPException'a sizdiriliyor
- **Sorun:** `except Exception as e: raise HTTPException(status_code=500, detail=f"Strateji hesabi hatasi: {e}")` — herhangi bir alt katman hatasinin `str(e)` metni dogrudan HTTP yanitina yaziliyor. Ornegin DB baglanti hatasi, dosya yolu, ya da SQLAlchemy hata mesaji client'a gorunur hale gelebilir.
- **Kanit:** satir 79-81
- **Aksiyon:** Client'a jenerik bir mesaj don ("Strateji hesabi sirasinda beklenmeyen hata"), detayi sadece `logger.exception` ile sunucu logunda tut (zaten satir 80'de yapiliyor, bu yeterli — detail alanindaki `{e}` kaldirilmali).
- **Onem:** Orta · **Guven:** Kesin

### [RDS-002] `debt_payoff_months: dict` tip parametresiz — validation deligi
- **Sorun:** `StrategyOut.debt_payoff_months` alani `dict` olarak tanimli (generic, key/value tipsiz). Pydantic bu alanda anahtar/deger tipini dogrulamiyor; `app/debt_strategy.py`'deki `Dict[int, int]` sozlesmesiyle router seviyesinde hicbir kontrat garantisi yok. Ileride algoritma yanlislikla string/float doner ise (orn. bir refactor sirasinda) response_model bunu sessizce kabul eder.
- **Kanit:** satir 44
- **Aksiyon:** `debt_payoff_months: dict[int, int]` olarak daraltilmasi (Pydantic V2 + `from __future__ import annotations` zaten mevcut, generic alias sorunsuz calisir).
- **Onem:** Dusuk · **Guven:** Kesin

### [RDS-003] `extra_monthly` ust siniri (100_000) aciklanmayan magic number
- **Sorun:** `le=100_000.0` sabiti neden bu deger oldugu (ne is kurali, ne de kullanici verisiyle iliskisi) aciklanmadan gomulu. Gercek kullanicinin aylik ekstra odeme kapasitesi degisirse (orn. buyuk bir bonus/miras) sinir kodda arama yapmadan anlasilmiyor.
- **Kanit:** satir 65
- **Aksiyon:** Sabiti isimlendirilmis bir modul-seviyesi degiskene (`MAX_EXTRA_MONTHLY = 100_000.0`) tasi ve kisa bir yorum ekle, ya da mevcut sinirin nereden geldigini docstring'e not dus.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

Temiz notu: Dosyanin geri kalani (response modelleri, endpoint akisi, loglama, ADR-001 uyumu — algoritma karar veriyor/LLM yok) mimariyle tutarli. Kritik matematiksel hata, off-by-one, timezone-naive/aware celiskisi ya da sessiz except bulunamadi.
