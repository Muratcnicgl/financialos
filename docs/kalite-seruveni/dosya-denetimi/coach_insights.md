# Denetim: app/coach_insights.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


### [CI-001] extract_decision_rhythm eski dominant dilim insight'ini asla sweep etmiyor + counter_evidence hicbir zaman artmiyor
- **Sorun:** extract_decision_rhythm (satir 276-374) her calistiginda sadece O ANKI dominant dilim icin bir baslik uretir (`Buyuk kararlarin cogu {dominant_slot} dilminde`, satir 347). Baslik dilim adini icerdigi icin dilim degisince (orn. "sabah" -> "aksam") YENI bir CoachInsight satiri olusur, eski "sabah" satiri hicbir yerde dormant/invalidated'a dusurulmez - kategori diger 6 periyodik extractor'in (category_account_preference, action_rejection_pattern, breakthrough, setback) hepsinde bulunan "DORMANT SWEEP" pass'i burada YOK. Ayrica `is_supporting_evidence=True` sabit oldugu icin (satir 369) `counter_evidence_count` hicbir zaman artmiyor, dolayisiyla `_check_and_invalidate`'in (satir 199-235) `counter_evidence_count >= 3` kosulu bu insight tipi icin pratikte asla tetiklenmiyor.
- **Kanit:** satir 347 (title dilim adini iceriyor), satir 361-372 (sweep yok), satir 369 (is_supporting_evidence=True sabit)
- **Aksiyon:** Digerlerinde oldugu gibi, bu extractor sonunda `insight_type="decision_rhythm"` icin status='active' olan ve bu calismada uretilmeyen basliklari dormant'a dusuren bir sweep pass eklenmeli.
- **Onem:** Yuksek · **Guven:** Kesin

### [CI-002] extract_mc_reference_frequency: top-3 disina dusen ama sayisi hala >0 olan MC icin sweep yok
- **Sorun:** Dominant MC'ler icin sadece ilk 3 (`MC_REFERENCE_TOP_K=3`, satir 509-542) "active" olarak yazilir; count==0 olanlar ikinci donguyle (satir 545-577) "dormant" yapilir. Ama bir MC'nin count'u >0 olup top-3'e girmiyorsa (orn. rank 4-8 arasi, count=1-2), o MC ne ilk ne de ikinci dongude islenir. Eger bu MC onceki bir calismada top-3'teyken "active" (sort_priority=10) yazildiysa ve simdi top-3 disina dustuyse, kaydi HICBIR yerde guncellenmeden "active" ve eski icerikle kalici kalir - prompt'a (get_active_insights_for_prompt / format_insights_for_prompt) sonsuza kadar guncelliğini yitirmis bilgi olarak enjekte edilmeye devam eder.
- **Kanit:** satir 505-577 (iki dongu de sadece rank<=3 count>0 veya count==0 durumlarini kapsiyor; ara durum icin sweep yok)
- **Aksiyon:** category_account_preference / action_rejection_pattern'deki gibi, bu calismada "active" olarak yeniden yazilmayan mevcut aktif mc_reference_frequency insight'larini dormant'a dusuren bir sweep pass eklenmeli.
- **Onem:** Yuksek · **Guven:** Kesin

### [CI-003] explicit_red_line K1 regex'leri (mutlak_red, niyet_beyani, kesin_red) finansal alanla sinirli degil - "%0 false positive" iddiasiyla celisiyor
- **Sorun:** Modulun kendi yorum blogu (satir 1629-1632) K1 icin "False positive %0 olmasi sart - bu sebeple cok spesifik regex'ler" diyor. Ama `niyet_beyani` deseni (satir 1650-1657: `r"\b(?:...{2,50}?)\s+(?:istemiyorum|istemem|istemiyrum)\b"`) ve `mutlak_red`/`kesin_red` desenleri (satir 1643-1649, 1666-1673) HERHANGI bir konudaki "istemiyorum/asla .../kesinlikle ..." ifadesini yakalar - finans/para/kart/kredi kelimesi zorunlu degil. Ornek: kullanici "Bu filmi kesinlikle izlemem" veya "Bu konuyu konusmak istemiyorum" derse, bu 90 gun boyunca aktif kalan, sort_priority=15 (EN YUKSEK, satir 1686) ile V3_GOD_MODE_PROMPT'a "kullanicinin kendi sozune dayanir, kanit dogrudan" (satir 1795) diye enjekte edilen kalici bir "kirmizi cizgi" insight'ina donusur - halbuki alakasiz bir konu. Sadece `vaat` kategorisi (satir 1658-1665) finansal fiillerle sinirlanmis.
- **Kanit:** satir 1643-1657, 1666-1673, 1795, 1686
- **Aksiyon:** mutlak_red/niyet_beyani/kesin_red desenlerine finansal baglam anchoring (para/kart/kredi/harcama/borç/yatirim vb. kelime zorunlulugu) eklenmeli veya bu 3 kategori K2'ye (LLM nuance) devredilmeli.
- **Onem:** Yuksek · **Guven:** Kesin (mekanik davranis dogrulandi; urun niyeti teyidi gerekebilir)

### [CI-004] _upsert_insight_absolute mevcut kaydi guncellerken last_evidence_at'i hic dokunmuyor
- **Sorun:** `_upsert_insight_absolute` (satir 398-453) yeni kayitta `last_evidence_at`'i set ediyor (satir 436: `now if evidence_count > 0 else None`) ama mevcut kaydi guncelleme yolunda (satir 446-452) bu alani ASLA guncellemiyor. Bu helper 6/8 extractor tarafindan kullaniliyor: mc_reference_frequency, question_typology, category_account_preference, action_rejection_pattern, breakthrough, setback. `format_insights_for_prompt` (satir 2124-2207) siralamayi `sort_priority DESC, last_evidence_at DESC NULLS LAST` (satir 2149-2151) ile yapiyor - yani bir insight ilk yazildiktan sonra her gun/periyodik dogrulanmaya devam etse bile last_evidence_at donup dolasip ilk olusum tarihinde kaliyor, gercekte "en taze dogrulanmis" olan insight'lar sirlamada yanlislikla daha eski gorunebiliyor.
- **Kanit:** satir 446-452 (existing.last_evidence_at set edilmiyor), satir 2149-2151 (siralama bu alana dayaniyor)
- **Aksiyon:** Guncelleme yolunda `existing.last_evidence_at = now if evidence_count > 0 else existing.last_evidence_at` eklenmeli.
- **Onem:** Orta · **Guven:** Kesin

### [CI-005] extract_decision_rhythm saat dilimi siniflandirmasi bare `.astimezone()` (sunucu yerel saatine) dayaniyor
- **Sorun:** satir 323: `local_dt = action.applied_at.replace(tzinfo=timezone.utc).astimezone()` - argumansiz `.astimezone()` Python'da SISTEMIN yerel saat dilimini kullanir. Proje genelinde PROJE.md/app/PROJE.md tum datetime islemlerinin "timezone-naive UTC" + acik `tzinfo=timezone.utc` disiplinine dayandigini soyluyor; burada ise kullanicinin gercek saat dilimi (Turkiye) yerine sunucu isletim sisteminin yerel saat dilimine sessizce guveniliyor. Gelistirme makinesi Turkiye'de oldugu icin bugun dogru calisiyor olabilir, ama sunucu farkli bir TZ (orn. UTC container/cloud) ile calistirilirsa gece/sabah/ogle/aksam siniflandirmasi sessizce kayar - hata firlatmaz, sadece yanlis dilime yazar.
- **Kanit:** satir 322-324
- **Aksiyon:** Kullanicinin saat dilimini acik bir sabit/konfigurasyon (orn. "Europe/Istanbul") ile sabitleyip `astimezone(ZoneInfo("Europe/Istanbul"))` kullanilmasi onerilir.
- **Onem:** Orta · **Guven:** Dogrulanmali (mevcut tek-kullanici/tek-makine kurulumunda risksiz olabilir, deployment degisirse aktif hataya donusur)

### [CI-006] _upsert_insight_absolute mevcut status'u kosulsuz eziyor - ileride "user_invalidated" ozelligi eklenirse kullanicinin duzeltmesini sessizce geri alir
- **Sorun:** format_insights_for_prompt docstring'i (satir 2132) "dormant/invalidated/user_invalidated DAHIL DEGIL" diye 3 statu bahsediyor; model kolonunda da 'invalidated' statu var (models.py satir 432). Ama `_upsert_insight_absolute`'in guncelleme yolu (satir 451: `existing.status = status`) mevcut statuye BAKMAKSIZIN periyodik hesaplanan yeni statuyu (active/dormant) yaziyor. Su an kod tabaninda 'user_invalidated' statusunu set eden bir endpoint yok (dogrulandi), yani bugun aktif bir hata degil - ama bu guard'in eksikligi, boyle bir "kullanici bu insight'i yanlis olarak isaretledi" ozelligi eklendigi an, bir sonraki periyodik extractor calismasinda kullanicinin duzeltmesini sessizce active/dormant'a geri dondurecek.
- **Kanit:** satir 446-452, models.py satir 432, coach_insights.py satir 2132
- **Aksiyon:** Guncelleme yolunda `if existing.status not in ("invalidated", "user_invalidated"): existing.status = status` gibi bir guard eklenmesi ileride ucuz bir korumadir.
- **Onem:** Dusuk (bugun aktif etkisi yok, ileriye donuk risk) · **Guven:** Dogrulanmali

### [CI-007] Bircok extractor `db.query()` (legacy) kullaniyor - app/PROJE.md'nin "SQLAlchemy 2.x: select()/session.execute() tercih edilir" kuraliyla celisiyor
- **Sorun:** app/PROJE.md acikca "SQLAlchemy 2.x: select() / session.execute() tercih edilir; session.query() eski pattern" diyor. Dosyada extract_decision_rhythm (satir 297-309) select() kullanirken, extract_mc_reference_frequency (467), extract_question_typology (679), extract_category_account_preference (851, 856-866, 929-937), extract_action_rejection_pattern (1001-1014, 1078-1086), extract_breakthrough (1161-1177, 1180-1188, 1326-1334), extract_setback (1408-1424, 1427-1435, 1582-1590), extract_explicit_red_line_k1 (1723-1741), extract_explicit_red_line_k2 (1981-1994) ve format_insights_for_prompt (2143-2155) hepsi legacy `db.query(...)` kullaniyor.
- **Kanit:** ornek satirlar: 467, 851, 1001, 1161, 1408, 1723, 1981, 2143
- **Aksiyon:** Kod tabaninin geri kalaniyla tutarlilik icin bu sorgular `select()`/`db.execute()` pattern'ine tasinmali (fonksiyonel bir hata degil, dokumante edilmis konvansiyon ihlali).
- **Onem:** Dusuk · **Guven:** Kesin

### [CI-008] explicit_red_line_k1 dedup anahtari (title) match konumuna duyarli - near-duplicate ifadeler ayri insight satirlari olusturuyor
- **Sorun:** `_erl_extract_match_text` (satir 1689-1696) eslesme etrafindan dinamik bir alinti cikarip title'a gomuyor (satir 1769: `title = f"Kirmizi cizgi [{category}]: {excerpt}"`), dedup ise bu title uzerinden UNIQUE constraint + `_erl_already_processed` ile yapiliyor (satir 1699-1709). Kullanicinin ayni kirmizi cizgiyi biraz farkli ifadelerle (orn. "artik bir daha kredi cekmem" vs "bir daha asla kredi cekmem soz") iki ayri mesajda soylemesi, iki farkli excerpt -> iki farkli title -> iki AYRI CoachInsight satiri anlamina geliyor; konsolide olmasi gereken tek bir davranissal sinyal boluniyor.
- **Kanit:** satir 1689-1696, 1768-1769, 1773-1776
- **Aksiyon:** Dedup'i title yerine (user_id, insight_type, category, matched normalized phrase) gibi daha kararli bir anahtara tasimak veya K2 asamasinda konsolidasyon garanti edilmeli (mevcut K2 tasarimi zaten bunu kismen yapiyor - ama K1 seviyesinde satir sayisi yine de sismis oluyor).
- **Onem:** Dusuk · **Guven:** Dogrulanmali

### [CI-009] extract_decision_rhythm: esitlikte max() "gece" dilimine sistematik onyargili
- **Sorun:** `dominant_slot = max(slot_counts, key=slot_counts.get)` (satir 330) - `slot_counts` dict'i `TIME_SLOTS` sirasiyla (gece, sabah, ogle, aksam) olusturuluyor (satir 318). Python'un `max()` fonksiyonu esitlik durumunda ilk karsilasilan max degeri dondurur, yani orn. gece=3, sabah=3, ogle=1, aksam=1 gibi tam bir esitlikte her zaman "gece" secilir - dokumante edilmemis, muhtemelen istenmeyen bir onyargi.
- **Kanit:** satir 318, 330
- **Aksiyon:** Esitlik durumunu acikca ele alan bir tie-break (orn. esitlikte insight yazma) eklenebilir; kritik degil ama sessiz bir varsayim.
- **Onem:** Dusuk · **Guven:** Kesin
