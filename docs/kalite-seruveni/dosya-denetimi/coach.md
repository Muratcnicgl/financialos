# Denetim: app/coach.py

### [CO-001] EMANET KASA halusinasyon filtresi gercekci LLM ciktisini yakalamiyor
- **Sorun:** `_EMANET_HEADER_RE = re.compile(r'\[5\.\s*EMANET KASA\]', re.IGNORECASE)` sadece
  koseli parantez + "5." + bosluk + "EMANET KASA" seklindeki BIREBIR literal formati eslestiriyor.
  Ayni dosyadaki kardes regex `_YC_HEADER_RE = re.compile(r'\[?\d*\.?\s*YENİ CHECKPOINT', ...)`
  koseli parantezi (`\[?`) VE numarayi (`\d*\.?`) opsiyonel yapmis — yani BUG #033 iter2 notunda
  ("numarali varyantlari da yakala") acikca YC icin yapilan esneklik EMANET icin hic uygulanmamis.
  Dosyanin kendi GUNCELLEMELER blogundaki BUG #012 notu da gozlemlenen gercek halusinasyon
  formatinin "EMANET KASA: Bu varlik yok" (parantezsiz, numarasiz duz baslik) oldugunu soyluyor —
  yani mevcut regex, belgelenmis gercek arizayi bile yakalamaz. LLM, prompttaki RAPOR FORMAT
  kural #13 geregi diger tum bolumleri "## N. Baslik" (markdown, parantezsiz) olarak yazdigi icin
  EMANET KASA'yi da ayni sekilde "## 5. EMANET KASA" yazma ihtimali yuksek — bu durumda
  `_postprocess_report` bu bolumu SILMEZ.
- **Kanit:** satir 1318 (`_EMANET_HEADER_RE` tanimi), satir 1320 (`_YC_HEADER_RE` — kiyaslama),
  satir 1368 (kullanim), satir 50-53 (BUG #012 docstring notu — gozlemlenen gercek format).
- **Aksiyon:** `_EMANET_HEADER_RE`'yi `_YC_HEADER_RE` ile ayni esneklikte yaz:
  `r'\[?5?\.?\s*EMANET KASA\]?'` (parantez ve numara opsiyonel) + gerekirse "EMANET KASA:"
  duz-baslik varyantini da kapsayacak sekilde genislet.
- **Onem:** Kritik · **Guven:** Dogrulanmali (LLM'in gercek cikti formatini calistirmadan
  %100 kesinlestiremem, ama regex asimetrisi ve BUG #012 kaniti guclu isaret).

### [CO-002] Sahte tamamlama guvenlik agi sadece koseli-parantezli metni yakaliyor
- **Sorun:** Prompt'taki "SAHTE TAMAMLAMA YASAĞI" kurali LLM'in "kaydedildi", "işlendi",
  "eklendi", "hesaba geçirildi" gibi duz Turkce cumleler yazmasini yasakliyor (satir 127-129).
  Ama bunu runtime'da temizleyen `_FAKE_CONFIRM_RE` (satir 1330-1333) SADECE
  `[...kaydedildi...]` gibi koseli parantez ICINE alinmis metni yakaliyor
  (`\[[^\]]*(?:kaydedildi|...)[^\]]*\]`). Retry'i tetikleyen `_FAKE_NIYET_RE` (satir 1336-1345)
  ise sadece GELECEK/NIYET kaliplarini yakaliyor ("kaydetmek üzereyim", "onay bekliyorum" vb.),
  GECMIS ZAMAN sahte-tamamlama iddialarini ("Harcamanı kaydettim.", "İşlem kaydedildi.")
  yakalamiyor. Sonuc: LLM propose_action cagirmadan duz metinde "Kaydettim." yazarsa —
  ne retry tetiklenir (satir 1691-1694, `_FAKE_NIYET_RE` eslesmiyor, text bos da degil)
  ne de `_postprocess_report` bunu temizler (satir 1402-1404, parantez yok) — kullaniciya
  hicbir DB yazimi olmadan "islendi" izlenimi giden metin oldugu gibi ulasir.
- **Kanit:** satir 1330-1333 (`_FAKE_CONFIRM_RE`), satir 1336-1345 (`_FAKE_NIYET_RE`),
  satir 1402-1404 (`_postprocess_report` kullanim), satir 1691-1694 (retry kosulu).
- **Aksiyon:** `_FAKE_CONFIRM_RE`'yi parantez zorunlulugu olmadan da (cumle sonu "." veya
  satir sonu ile) eslesecek sekilde genislet, veya `_FAKE_NIYET_RE`'ye gecmis-zaman
  tamamlama fiillerini de ekleyip retry kapsamina al.
- **Onem:** Kritik · **Guven:** Kesin (regex kapsam farki koddan dogrudan okunuyor; LLM'in
  bu ifadeyi gercekten uretip uretmeyecegi olasilikli ama prompt bunu ACIKCA yasakliyor —
  yani riskin var oldugu belgelenmis).

### [CO-003] AnthropicProvider tool-aware history adapter'i kullanmiyor — role="tool" dogrudan gonderiliyor
- **Sorun:** `GroqProvider`, `CerebrasProvider`, `OpenRouterProvider` gecmis mesajlari
  `_to_openai_messages()` ile OpenAI formatina cevirip gonderiyor (satir 986, 1045, 1096).
  `GeminiProvider._raw_chat` da kendi ozel donusum donguisune sahip (satir 836-862, "tool"
  rolunu atliyor). Ama `AnthropicProvider._raw_chat` (satir 775-801) `messages` parametresini
  HICBIR donusumden gecirmeden dogrudan `self.client.messages.create(..., messages=messages)`'a
  veriyor. `CoachEngine._load_history()` (satir 1507-1526) donen sozlukler
  `{"role": ..., "content": ..., "tool_calls_json": ..., "tool_call_id": ...}` seklinde — Anthropic
  API'si sadece "user"/"assistant" rolunu kabul eder, "tool" rolu ve fazladan
  `tool_calls_json`/`tool_call_id` anahtarlari Anthropic mesaj semasinda gecersizdir. Bir onceki
  turda propose_action cagrildiysa (CoachMemory'de role="tool" satiri olusur — satir 1835-1839),
  bu satir hala history penceresindeyken (`max_history_turns` icinde) Anthropic'e dogrudan
  gonderilir.
- **Kanit:** satir 775-801 (AnthropicProvider._raw_chat, donusumsuz `messages=messages`),
  satir 986/1045/1096 (kiyasla: digerleri `_to_openai_messages` kullaniyor), satir 1507-1526
  (`_load_history` donen ham format), satir 1835-1839 (role="tool" CoachMemory kaydi).
- **Aksiyon:** AnthropicProvider icin de Anthropic'in tool_use/tool_result content-block
  formatina uygun bir adapter yaz (digerleriyle ayni desende), role="tool" satirlarini
  Anthropic'in "user" + tool_result content block'una cevir.
- **Onem:** Yuksek · **Guven:** Kesin (kod karsilastirmasindan acik; su an LLM_PROVIDER
  varsayilan "gemini" ve fallback zincirinde Anthropic yok — satir 1246 — bu yuzden bugun
  aktif calisan yol degil, ama `LLM_PROVIDER=anthropic` secildigi an ilk tool-cagrili
  konusmadan sonra kirilir).

### [CO-004] `uyarilar` anahtari cockpit dict'te yok — trace/observability olu kod
- **Sorun:** `cockpit_dict.get("uyarilar", [])` cagriliyor (satir 1569) ama
  `generate_cockpit()` (`app/rules_engine.py:790`) dondugu sozlukte anahtar "alerts" —
  "uyarilar" hicbir zaman mevcut degil. Sonuc: `uyarilar` her zaman `[]`, RULE_CHECK trace
  adiminin `s.observation` alani her zaman "Aktif uyari: 0" yazar (gercek uyari sayisi ne
  olursa olsun) ve `if uyarilar:` bloguna (satir 1572-1574) hicbir zaman girilmez — reasoning
  trace'e gercek uyari kodlari asla yazilmaz.
- **Kanit:** satir 1569 (`cockpit_dict.get("uyarilar", [])`), `app/rules_engine.py:790`
  (`"alerts": alerts,`), karsilastir `app/coach.py:582-585` (ayni dosyada dogru anahtar
  "alerts" kullanilmis).
- **Aksiyon:** `"uyarilar"` -> `"alerts"` olarak duzelt.
- **Onem:** Orta · **Guven:** Kesin.

### [CO-005] is_question() yanlis-pozitifi propose_action'i sert biciimde bloke ediyor, kurtarma yolu yok
- **Sorun:** `is_question()` (satir 78-89) "yoksa", "ne yap", "analiz", "incele", "stratej"
  gibi kelime gecen HER mesaji soru sayiyor — bu kelimeler gercek bir eylem bildirimi
  icinde de gecebilir (orn. "300 TL nakitten harcadim yoksa kart limiti dolacakti").
  BUG #023 oncesi bu siniflandirma LLM'in takdirindeydi (yanlis olsa da geri donus sansi
  vardi); simdi kod seviyesinde sert bir kapiya donusturuldu: `is_q=True` ise
  `active_tools = [SAVE_INSIGHT_SCHEMA]` (satir 1584) — yani propose_action LLM'e
  SUNULMUYOR bile, LLM ne kadar dogru siniflandirsa da cagiramaz. Kurtarma mekanizmasi olan
  BUG #043/#045 retry blogu acikca `not is_q` sartiyla calisiyor (satir 1692) — yani
  is_question yanlis-pozitif verdiyse bu retry hic devreye girmez; sadece "is_q ve metin
  bossa" (satir 1756) retry'i calisir ki bu da salt-metin retry'idir, propose_action'i
  zorlamiyor. Sonuc: gercek bir harcama/gelir bildirimi sessizce hic kaydedilmeden gecebilir.
- **Kanit:** satir 78-89 (`is_question`), satir 1583-1584 (`active_tools` secimi),
  satir 1691-1694 (retry `not is_q` sarti), satir 1756 (is_q icin yalniz metin-retry).
- **Aksiyon:** is_question() yanlis-pozitiflerini azalt (orn. "yoksa" tek basina degil,
  cumle sonu soru kaliplariyla birlikte degerlendir) VEYA is_q=True oldugunda bile LLM
  aslinda eylem bildirdiyse tespit edip tools'u genisletecek bir ikinci-gecis kontrolu ekle.
- **Onem:** Orta · **Guven:** Dogrulanmali (heuristic false-positive orani calistirilmadan
  olculemez, ama mantik zinciri koddan kesin).

### [CO-006] `_CLARIFY_MSG` tum sahte-tamamlama senaryolarinda ayni "harcama" sorusunu soruyor
- **Sorun:** `_FAKE_CONFIRM_RE` eslestiginde (satir 1402-1404) her zaman sabit
  `_CLARIFY_MSG = "Hangi hesaptan harcadın? ..."` (satir 1334) eklenir — action_type context'i
  ne olursa olsun (orn. mark_debt_paid / sell_investment senaryosunda da ayni "harcadin mi"
  sorusu cikar), bu da kullaniciya anlamsiz/yanlis baglamli bir soru gosterir.
- **Kanit:** satir 1334, satir 1402-1404.
- **Aksiyon:** Genel bir "Aksiyon netlesmedi, tekrar yazar misin?" mesaji kullan veya
  action_type baglamina gore mesaji parametrize et.
- **Onem:** Dusuk · **Guven:** Kesin (metnin baglamdan bagimsizligi kodda acik).

### [CO-007] Bolum numaralandirma yorumlarinda tekrar (kozmetik)
- **Sorun:** Dosya ici `# === N. Baslik ===` yorum bloklari icinde numara iki kez tekrarlaniyor:
  "3. OPENAI-UYUMLU..." (satir 373) ve "3. RETRY YARDIMCI" (satir 434); "11. FALLBACK PROVIDER"
  degil ama "11. OPENROUTER PROVIDER" (satir 1071) ve "11. PROVIDER FACTORY" (satir 1180);
  "14. BUG #033 fix..." (satir 1315) ve "14. COACH ENGINE" (satir 1444).
- **Kanit:** satir 373, 434, 1071, 1180, 1315, 1444.
- **Aksiyon:** Numaralandirmayi sirali hale getir (kod davranisini etkilemiyor, sadece
  okunabilirlik).
- **Onem:** Dusuk · **Guven:** Kesin.
