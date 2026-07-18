# Denetim: app/routers/premortem.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [RPM-001] "cached" alani hep False donuyor, snapshot_hash hic karsilastirilmiyor
- **Sorun:** Router her cagrida `compute_snapshot_hash(snapshot)` hesaplayip `persist_premortem`'e geciriyor ve DecisionJournal.cockpit_snapshot_hash alanina yaziyor (app/premortem.py satir 296/306). Ancak bu hash hicbir zaman mevcut DJ kaydindaki eski hash ile karsilastirilmiyor. Sonuc: `PremortemResponse.cached` alani satir 121'de sabit `False` donuyor — degistirilemez, hicbir kod yolu `True` uretemez. Bu, hash altyapisinin (Bridgewater pattern, cockpit_snapshot.py docstring'i) bir caching/idempotency kontrolu icin tasarlandigini ama router'da hic kullanilmadigini gosteriyor.
- **Kanit:** satir 92-93 (hash hesaplanir), satir 108 (kullanilmadan persist edilir), satir 121 (`cached=False` sabit)
- **Aksiyon:** Ya `cached` alanini kaldirip API sozlesmesini sadelestir, ya da persist_premortem cagrisindan once mevcut DJ kaydi çekilip `existing.cockpit_snapshot_hash == snapshot_hash` ise LLM'i tekrar cagirmadan mevcut `premortem_scenarios`'i donduren gercek bir cache yolu ekle. Su anki haliyle her cagri (ayni pending action icin arka arkaya tiklansa bile) gercek bir LLM cagrisi tetikliyor — maliyet + gecikme israfi.
- **Onem:** Yuksek · **Guven:** Kesin

### [RPM-002] persist_premortem() cagrisi try/except disi — DB hatasi ham 500 olarak sizar
- **Sorun:** `generate_premortem` cagrisi (satir 96-106) `PremortemError` icin try/except ile sarilmis ve kullaniciya 503 + Turkce mesaj donduruyor. Ama hemen sonrasindaki `persist_premortem(db, action, current_user.id, result, snapshot_hash)` (satir 108) hicbir try/except icinde degil. `persist_premortem` icinde `session.commit()` var (app/premortem.py satir 312) — bir IntegrityError/OperationalError burada patlarsa FastAPI'nin default exception handler'i devreye girer, kullaniciya Turkce olmayan/ham stack trace tabanli bir 500 doner ve LLM'den basariyla gelen sonuc kaybolur (kullanici tekrar LLM cagrisi yapmak zorunda kalir).
- **Kanit:** satir 108
- **Aksiyon:** `persist_premortem` cagrisini try/except (SQLAlchemyError) ile sarip DB hatasinda da tutarli bir HTTPException (orn. 500 + Turkce mesaj) dondur; boylece hem tutarli hata formati hem de LLM sonucunun bosa gitmesi loglanir.
- **Onem:** Orta · **Guven:** Dogrulanmali (SQLAlchemy hatasi normalde nadir ama olasi)

### [RPM-003] action_context alanlari tip dogrulamasi yok (amount_tl string olabilir)
- **Sorun:** `payload_dict.get("amount") or 0.0` (satir 82) ve `payload_dict.get("rationale") or payload_dict.get("reason")` (satir 89) hicbir tip kontrolu yapmadan `action.payload` JSON'undan gelen degerleri direkt `action_context` dict'ine koyuyor. `action_context` tipi `dict` (Pydantic modeli yok), bu yuzden `amount` alani orn. `"1500"` (string) ya da `{"currency": "TL"}` (nested dict) gibi beklenmeyen bir JSON degeri tasiyorsa hicbir validasyon hatasi firlamaz — sadece LLM'e bozuk/format-disi bir baglam metni gider (app/premortem.py `_user_prompt` satir 131: `f"  Tutar: {action_context.get('amount_tl', 0.0)} TL"`). Bu, "LLM matematige guvenilmez" ilkesiyle dogrudan celismez (LLM zaten hesap yapmiyor) ama LLM'in yanlis/tutarsiz bir tutari senaryolara "gercek" gibi yansitmasina yol acabilir.
- **Kanit:** satir 82, 89
- **Aksiyon:** `payload_dict.get("amount")` icin `isinstance(..., (int, float))` kontrolu ekleyip gecersiz tipte 0.0'a dus; boylece LLM baglaminda sessizce bozuk veri gitmesi engellenir.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RPM-004] Status kontrolu ile execute arasinda TOCTOU (yaris durumu) potansiyeli
- **Sorun:** Satir 62'de `action.status != ActionStatus.pending` kontrol edilip sonra ~yarim saniye suren senkron bir LLM cagrisi yapiliyor (docstring satir 5: "LLM cagrisi senkron — kullanici UI'da bekler"). Bu sure icinde aynı action_id icin `/api/actions/{id}/execute` gibi baska bir endpoint aksiyonu yurutup status'u degistirebilir; premortem yine de calisip DecisionJournal'a executed olmus bir aksiyon icin "hayali" senaryo yazabilir. Tek-kullanicili MVP'de dusuk riskli (ayni kullanicinin es zamanli iki istek atmasi gerekir) ama mimari olarak status kontrolu ile persist arasinda tekrar dogrulama yok.
- **Kanit:** satir 62-69 (kontrol) vs satir 108 (persist — status tekrar kontrol edilmiyor)
- **Aksiyon:** Ihtiyac gorulurse `persist_premortem` oncesi action.status'u tekrar oku/kontrol et; MVP kapsaminda dusuk oncelikli, sadece not dusuluyor.
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [RPM-005] Genel exception yakalama yok — provider disi beklenmeyen hatalar loglanmadan 500 doner
- **Sorun:** `run_premortem` fonksiyonunda sadece `PremortemError` yakalaniyor (satir 101). `build_cockpit_snapshot` kendi icinde hatalari yutuyor (partial snapshot donuyor) ama `compute_snapshot_hash` veya `json.dumps` gibi cagrilar teorik olarak (orn. serialize edilemeyen bir deger) exception firlatirsa, bu router seviyesinde hic loglanmadan FastAPI'nin default 500'une duser — `logger.error` cagrisi yalnizca `PremortemError` path'inde var.
- **Kanit:** satir 92-106
- **Aksiyon:** Genis bir `except Exception` blogu eklemek yerine (ki bu "sessiz except" riskini artirir), en azindan kritik olmayan yardimci cagrilarin (`compute_snapshot_hash`) da hata durumunda loglanmasi icin ust seviyede bir log noktasi dusunulebilir. Dusuk oncelik — bugunku kod tabaninda bu satirlarin pratikte exception firlatma ihtimali cok dusuk.
- **Onem:** Dusuk · **Guven:** Dogrulanmali
