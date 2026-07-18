# Denetim: app/cockpit_snapshot.py

> **⏳ GÜNCELLİK (M77, 18 Tem 2026):** Bu rapor Wave-2/3 döneminde alınmış bir **tarihsel denetim anlık görüntüsüdür**. Bulgular güncel koda karşı madde-madde YENİDEN doğrulanmadı. Örneklem doğrulaması (M77): kritik `rules_engine.md` bulgularından RE-001 (evaluate_credit_card_strategy ölü kod) ve RE-002 (quick-entry bağlı değil) İKİSİ DE düzeltilmiş çıktı; RULE boyutunda ölçülen stale oranı ~%42. Bir bulguyu kullanmadan önce `file:line`'ı güncel kodda DOĞRULA — satır numaraları kaymış, sorun düzeltilmiş olabilir. Düzeltme durumu: `git log` + `docs/kalite-seruveni/uygulanan-fixler.md`.


## Kapsam

Dosyanin tamami (107 satir) satir satir okundu. Iliskili dosyalar da kontrol edildi:
`app/rules_engine.py` (generate_cockpit, calculate_daily_limit), `app/cashflow.py`
(generate_forecast), `app/routers/premortem.py` ve `app/premortem.py` (bu snapshot'in
tek tuketicisi), `tests/test_cockpit_snapshot.py`, `tests/test_premortem_endpoint.py`.

---

### [CS-001] Premortem prompt'u crunch/lowest-balance verisini hicbir zaman gormuyor (yanlis anahtar adi)

- **Sorun:** `build_cockpit_snapshot` cikti sozlugunde alanlar `lowest_balance_tl`,
  `lowest_balance_date`, `crunch_count` adiyla uretiliyor (satir 33-35, 88-90). Ancak bu
  snapshot'in TEK tuketicisi olan `app/premortem.py::_user_prompt` bu alanlari hic okumuyor;
  bunun yerine var olmayan bir anahtar olan `crunch_day` icin `.get('crunch_day', '-')`
  cagiriyor (app/premortem.py:144). `CockpitSnapshot` TypedDict'inde `crunch_day` diye bir
  alan yok — dolayisiyla bu `.get()` cagrisi HER ZAMAN default degeri `'-'` doner, forecast
  gercekte cash-crunch tespit etmis olsa bile.
  Ayrica `lowest_balance_tl` ve `crunch_count` premortem prompt'una hic yazilmiyor (satir
  141-144'te sadece net_worth_tl, cashflow_30d_tl, cashflow_60d_tl okunuyor).
  Sonuc: bu dosyanin docstring'inde belirtilen amac ("Premortem prompt'una somut TL
  degerleri verir, LLM hallucination'ini azaltir" — satir 42) tam olarak en kritik veri
  turu icin (ne zaman nakit tukenir) basarisiz oluyor; LLM 6 ay sonraki basarisizlik
  senaryolarini nakit-krizi tarihinden tamamen habersiz uretiyor.
- **Kanit:** app/cockpit_snapshot.py satir 33-35, 88-90 (alan adlari) vs
  app/premortem.py satir 141-144 (tuketimi, ozellikle satir 144: `cockpit_snapshot.get('crunch_day', '-')`).
- **Aksiyon:** `app/premortem.py::_user_prompt` icindeki satir 144'u
  `cockpit_snapshot.get('lowest_balance_date', '-')` (ve ideal olarak
  `lowest_balance_tl` + `crunch_count` degerlerini de ekleyen ek satirlar) ile degistir.
- **Onem:** Kritik · **Guven:** Kesin

---

### [CS-002] 60 gunluk ufuktaki crunch/en-dusuk-bakiye verisi hesaplaniyor ama tamamen atiliyor

- **Sorun:** `flow_60 = generate_forecast(db, user_id, horizon_days=60)` cagrisi (satir 62)
  `summary` icinde `lowest_balance`, `lowest_date`, `crunch_count` alanlarini da uretir
  (bkz. app/cashflow.py satir 352-358 — bu alanlar horizon_days'ten bagimsiz her zaman
  doner). Ancak `build_cockpit_snapshot` `summary_60`'tan SADECE `net_flow` degerini alir
  (satir 87); `lowest_balance`, `lowest_date`, `crunch_count` 31-60 gun araligi icin hesaplanip
  sessizce cope atiliyor. Snapshot'taki `lowest_balance_tl`/`lowest_balance_date`/`crunch_count`
  alanlari SADECE ilk 30 gunu kapsiyor (satir 88-90, `summary_30`'dan).
  Pratik sonuc: 31-60. gunler arasinda ciddi bir nakit krizi olsa bile (`crunch_count`
  30 gunluk pencerede 0 gorunur), premortem LLM'i "cashflow_60d_tl" adinda pozitif/notr
  tek bir toplam net akis sayisi gorur ve altta yatan orta-vadeli krizi asla fark edemez —
  "gunun 45'inde bakiye eksiye dusuyor" bilgisi hicbir alanda yuzeye cikmiyor.
- **Kanit:** satir 62 (flow_60 hesaplaniyor), satir 68 (`summary_60` cikartiliyor), satir 87
  (sadece `net_flow` kullaniliyor), satir 88-90 (lowest_balance/date/crunch_count sadece
  `summary_30`'dan aliniyor).
- **Aksiyon:** Ya `crunch_count`/`lowest_balance_tl` alanlarini 30g+60g birlestirilmis
  (veya ayri `crunch_count_60d` gibi acik isimli) alanlarla genislet, ya da en azindan
  TypedDict/docstring'e "bu alanlar sadece ilk 30 gunu kapsar" notu ekleyerek premortem
  prompt yazarinin yanlis varsayimda bulunmasini engelle.
- **Onem:** Yuksek · **Guven:** Kesin

---

### [CS-003] generate_cockpit hata verince kritik alanlar sessizce 0.0 olur — "gercek sifir" ile ayirt edilemez

- **Sorun:** `generate_cockpit` exception firlatirsa `cockpit = {}` olur (satir 49-53) ve
  akabinde `net_worth_tl`, `cash_tl`, `card_debt_tl`, `loan_debt_tl`, `investment_tl`,
  `daily_limit_tl` hepsi `or 0.0` fallback'i ile sessizce 0.0'a duser (satir 81-85, 91).
  Snapshot ciktisinda bu durumu isaretleyen bir `partial`/`degraded`/`cockpit_ok` bayragi
  yok. `app/premortem.py` bu snapshot'i dogrudan LLM prompt'una yaziyor (satir 141:
  "Net deger: 0.0 TL") — LLM, DB/rules-engine hatasi sonucu uretilen sahte "net deger
  sifir" degerini gercek bir finansal durum sanip premortem senaryolarini bu yanlis
  temelde uretebilir. Kok vizyon ilkesi #2 (varsayim=hata) ve #5 (sanal zenginlik yasak
  — burada tersi: "sanal yoksulluk" sessizce enjekte ediliyor) ile gerilim halinde.
  Not: docstring bu davranisi bilerek belgeliyor ("kritik alanlar 0.0 olur", satir 45),
  yani kismen kasitli bir tasarim; ama tuketiciye hicbir sinyal gitmemesi risk tasiyor.
- **Kanit:** satir 49-53 (exception -> `cockpit = {}`), satir 81-85 + 91 (`or 0.0`
  fallback'leri), app/premortem.py satir 141 (dogrudan LLM promptuna yaziliyor).
- **Aksiyon:** `CockpitSnapshot`'a `cockpit_available: bool` (veya benzeri) alani ekle;
  `False` oldugunda premortem tarafinda ya LLM'e "finansal veri su an erisilemiyor" notu
  gecilsin ya da 503 donsun (mevcut `generate_premortem` zaten `PremortemError` icin 503
  donuyor — ayni disiplin cockpit-fetch basarisizligina da uygulanabilir).
- **Onem:** Orta · **Guven:** Dogrulanmali (tasarim tercihi olabilir, ama sinyal eksikligi acik)

---

### [CS-004] Gereksiz/olu isinstance dali: `(date, datetime)` — `datetime` zaten `date`'in alt sinifi

- **Sorun:** Satir 74'teki `isinstance(lowest_date_raw, (date, datetime))` kontrolu
  `datetime`'i ayrica listelemeye gerek birakmiyor; Python'da `datetime`, `date`'in alt
  sinifidir, dolayisiyla `isinstance(x, date)` tek basina her iki tipi de yakalar. Islevsel
  bir hataya yol acmiyor (yanlis pozitif/negatif yok), sadece yanitlayici okuyucuya "bu iki
  ayri kontrol gerekiyor" izlenimi veren kucuk bir netlik/olu-kod notu.
- **Kanit:** satir 74.
- **Aksiyon:** `isinstance(lowest_date_raw, date)` yeterli (datetime dahil); ya da niyet
  aciklamasi icin yorum eklenebilir. Zorunlu degil.
- **Onem:** Dusuk · **Guven:** Kesin

---

## Kontrol edilip TEMIZ bulunan noktalar (bilgi amacli)

- `net_worth_tl` icin `cockpit.get("net_deger")` (operasyonel, emanet ve alacaklar HARIC)
  kullanilmasi kok vizyon ilkesi #5 (sanal zenginlik yasak) ile UYUMLU — `net_deger_tam`
  (alacaklar dahil, stratejik) degil, dogru metrik secilmis.
- `calculate_daily_limit` (`app/rules_engine.py:131-135`) `days_remaining <= 0` durumunu
  koruyor, 0'a bolme/NaN riski snapshot'a sizmiyor.
- `compute_snapshot_hash` sadece `snapshot_at`'i haric tutuyor, `sort_keys=True` +
  sabit `separators` ile deterministik JSON uretiyor — hash stabil.
- `today = date.today()` kullanimi (satir 47) proje genelindeki lokal-saat konvansiyonuyla
  tutarli (bkz. app/cashflow.py docstring: "date.today() — lokal sistem saati").
- Cift-yuvarlama yok: `cockpit`/`summary` degerleri kaynakta zaten `round(...,2)` ile
  yuvarlanmis; bu dosya sadece `float()` cast yapiyor, tekrar yuvarlamiyor.
