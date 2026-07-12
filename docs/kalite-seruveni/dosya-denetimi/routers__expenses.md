# Denetim: app/routers/expenses.py

### [REX-001] last_triggered_year_month, kullanici onayindan ONCE isaretleniyor -> reddedilen/basarisiz gider bir daha hic tetiklenmiyor
- **Sorun:** trigger_due_expenses, propose_action ile PendingAction'i "pending" statusunde olusturur olusturmaz (satir 178-192), hemen ardindan exp.last_triggered_year_month = year_month yazip commit ediyor (satir 194-197). Dedup kontrolu (satir 166: `if exp.last_triggered_year_month == year_month: continue`) sadece bu alana bakiyor; PendingAction'in gercekten "executed" olup olmadigina bakmiyor. Kullanici bu oneriyi reddederse (`reject_pending_action` -> status=rejected) veya `execute_pending_action` bir nedenle basarisiz olursa (status=failed), last_triggered_year_month zaten o ay icin set edilmis oldugundan, ayni gider o ay bir daha ASLA yeniden onerilmez. Sonuc: gercekte odenmemis/kaydedilmemis bir gider, sistem tarafindan "bu ay halledildi" sayilir; kullanicinin cockpit'i gercek nakit durumunu yansitmaz (sessiz veri kaybi / sanal tutarlilik).
- **Kanit:** satir 166 (dedup kosulu), satir 194-197 (onay beklemeden dedup alaninin yazilmasi), app/action_executor.py satir 338-361 (reject_pending_action, source_recurring alanlarina veya last_triggered_year_month'a dokunmuyor)
- **Aksiyon:** last_triggered_year_month sadece action gercekten "executed" olduktan sonra (execute_pending_action icinde, source_recurring_type='expense' kontrolu ile) set edilmeli; ya da reject_pending_action/execute_pending_action(failed) akisinda source_recurring_id'si olan pending icin last_triggered_year_month geri alinmali (rollback).
- **Onem:** Kritik · **Guven:** Kesin

### [REX-002] created_at, timezone-aware UTC'ye cevrilmeden donuluyor (PROJE.md kuraliyla celisir)
- **Sorun:** ExpenseOut.created_at, RecurringExpense.created_at'i (Column(DateTime, default=datetime.utcnow) -> timezone-naive) dogrudan pydantic'e veriyor. list_expenses/create_expense/update_expense hicbirinde `tzinfo=timezone.utc` eklenmiyor. app/PROJE.md acikca: "Frontend'e tarih dönen her endpoint'te serialize öncesi tzinfo=timezone.utc ekle... Eksik bırakırsan Pydantic suffix'siz ISO string yayar, JS Türkiye saatinde 3 saat geri gösterir." diyor; referans olarak coach.py'deki _memory_to_history_item gosteriliyor. Bu router o pattern'i uygulamiyor.
- **Kanit:** satir 55 (ExpenseOut.created_at alani), satir 76 (list_expenses return), satir 94-98 (create_expense return), satir 115-119 (update_expense return); karsilastir app/PROJE.md "Datetime / Timezone" bolumu
- **Aksiyon:** ExpenseOut icin bir alan_validator/serializer ekleyip created_at'i `.replace(tzinfo=timezone.utc)` ile aware yapin (coach.py _memory_to_history_item pattern'i).
- **Onem:** Orta · **Guven:** Kesin

### [REX-003] update_expense, account_id degistiginde hesap sahipligini/varligini dogrulamiyor
- **Sorun:** create_expense, payload.account_id'nin `user.id`'ye ait gercek bir Account oldugunu dogruluyor (satir 87-92). update_expense ise ExpenseUpdate.model_dump(exclude_unset=True) ile gelen tum alanlari (account_id dahil) dogrudan setattr ile yaziyor (satir 115-116), account_id icin herhangi bir varlik/sahiplik kontrolu yok. Kullanici (veya ileride LLM tetiklemesi degil ama API tuketen baska bir client) var olmayan veya baska kullaniciya ait bir account_id gonderirse kayit sessizce yanlis/gecersiz account_id ile guncellenir; SQLite'ta FK constraint varsayilan olarak PRAGMA foreign_keys ON degilse enforce edilmez, dolayisiyla hata da firlamaz. trigger-due sonraki calismada bu account_id ile propose_action cagirir; _normalize_transaction_payload account'u bulamayinca (satir 104-107 orneginde oldugu gibi) sessizce None donebilir, ya da execute_pending_action asamasinda beklenmedik hata.
- **Kanit:** satir 43-50 (ExpenseUpdate.account_id: Optional[int], validation yok), satir 115-116 (kosulsuz setattr), karsilastir satir 86-92 (create_expense'deki dogrulama)
- **Aksiyon:** update_expense'te account_id payload'da varsa create_expense'deki gibi Account.user_id == user.id dogrulamasi ekleyin.
- **Onem:** Yuksek · **Guven:** Kesin

### [REX-004] day_of_month=29/30/31 olan giderler kisa aylarda sessizce hic tetiklenmiyor
- **Sorun:** Sorgu `RecurringExpense.day_of_month <= today.day` kosulunu kullaniyor (satir 159). day_of_month=31 olan bir gider, 31 gunu olmayan aylarda (Subat, Nisan, Haziran, Eylul, Kasim) today.day hicbir zaman 31'e ulasamayacagi icin o ay icin HICBIR ZAMAN tetiklenmez (last_triggered_year_month da set edilmedigi icin bir sonraki ayin trigger'inda da "gecmis ay icin telafi" mekanizmasi yok — sadece o anki ayin gunu kontrol ediliyor). Kullanici "ayin son gunu" niyetiyle 31 girdiginde, kisa aylarda gider sessizce atlanir ve dedup mekanizmasi da bunu "eksik" olarak isaretlemez (last_triggered_year_month o ay icin None kalir ama bir sonraki cagride yine ayni ay icin gun kosulu saglanamadigindan hicbir uyari/log uretilmez).
- **Kanit:** satir 159 (`RecurringExpense.day_of_month <= today.day`), model tanimi day_of_month = Field(..., ge=1, le=31) (satir 34) — 31'e izin veriyor ama ay-sonu clamp mantigi yok
- **Aksiyon:** day_of_month'u ayin gercek son gunune clamp edin (`min(exp.day_of_month, calendar.monthrange(today.year, today.month)[1])`) ya da UI'da "ayin son gunu" icin ayri bir secenek sunun.
- **Onem:** Orta · **Guven:** Kesin

### [REX-005] trigger_due_expenses genel except bloğu hatayı yutuyor, çağırana hiçbir sinyal dönmüyor
- **Sorun:** Her exp icin propose_action cagrisi try/except Exception ile sarilmis; hata sadece logger.error ile loglaniyor, `triggered` listesine hicbir "failed"/"error" girisi eklenmiyor (satir 206-207). Endpoint yalnizca `{"triggered": [...]}` donuyor. Frontend/cagiran taraf, bir giderin hangi nedenle atlandigini (orn. ValueError("HESAP_BELIRSIZ")) hicbir sekilde goremiyor; sessiz basarisizlik.
- **Kanit:** satir 177, 206-207
- **Aksiyon:** except bloğunda `triggered`'a paralel bir `skipped`/`errors` listesi doldurup response'a ekleyin, boylece cagiran taraf hangi giderlerin atlandigini gorebilsin.
- **Onem:** Dusuk · **Guven:** Dogrulanmali (davranissal tercih olabilir, ama sessiz hata loglama pratigi PROJE.md'nin "sessiz except: pass" uyarisina yakin)
