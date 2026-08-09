# ADR-052 — Aksiyon reddi sinyalleri: karar TİPTE, teşhis AYRI alanda

- **Durum:** Kabul edildi (9 Ağustos 2026, BUG #273)
- **Bağlam kodları:** backlog `BE-006`, `RESIL-019`, `BE-005`
- **İlgili:** ADR-048 (aksiyon payload sözleşmesi), ADR-051 (sağlayıcı hata sınıflandırması),
  ADR-045 (prompt güvenliği), BUG #180 (ham finansal veri log'a düşmez)

## Bağlam

`propose_action` bir öneriyi reddettiğinde ortaya tek bir hata değil **bir karar** çıkar:

1. Kullanıcıya ne söyleyeceğiz? (öneri oluşmadıysa sessiz kalmak "Kaydettim." cümlesini
   ekranda bırakır — BUG #049 ailesi)
2. Modeli yeniden çağırmanın anlamı var mı?
3. Kullanıcının okuyabildiği akıl-yürütme izine (`TracePanel` "Gözlem" satırı) ne yazılacak?

Bu karar dört sinyalle taşınıyordu ve **sinyal serbest metindi**:

```python
raise ValueError("HESAP_BELIRSIZ")                       # app/action_executor.py
...
if "HESAP_BELIRSIZ" in str(e):    account_unclear = True # app/coach.py (ana akış)
elif "TARIH_BELIRSIZ" in str(e):  date_unclear = True
elif ("PAYLOAD_GECERSIZ" in str(e) or ...):  payload_invalid = True
```

ADR-051 aynı hatayı sağlayıcı katmanında kapatmıştı (karar metin taramasıyla veriliyordu);
burası **aynı sınıfın para yolundaki hâliydi**.

## Ölçüm (9 Ağustos 2026 — gerçek koç akışı, sahte sağlayıcı, her vaka ayrı DB)

**① Dal kopyalandı ve ayrıştı.** Dört sinyal × iki koç tüketicisi (ana akış + retry):

| sinyal | ana akış | retry akışı |
|---|---|---|
| `HESAP_BELIRSIZ` | ✅ | ✅ |
| `TARIH_BELIRSIZ` | ✅ | ❌ **dal hiç yoktu** |
| `PAYLOAD_GECERSIZ` | ✅ | ✅ |
| `OZET_PAYLOAD_CELISKISI` | ✅ | ✅ |

Retry gövdesi ana akıştan elle kopyalanmış, kopyalanırken bir dal düşmüştü. Sonuç: birinci
LLM çağrısı tool çağırmayıp retry'a düşen bir harcamada, özette tarih olup payload'da
olmadığında işlem **kaydedilmiyor** ve kullanıcıya **tarih sorusu da sorulmuyordu** — hata
`else` dalına düşüp `logger.error("retry propose_action hatasi: TARIH_BELIRSIZ")` olarak
yutuluyordu. Kullanıcı ekranda modelin özgün metnini görüyor, neyi düzeltmesi gerektiğini
öğrenemiyordu.

**② İç sinyal adı kullanıcının ekranındaydı.** `s.observation = f"Belirsizlik: {str(e)[:200]}"`
satırı `reasoning_traces.observation`'a yazılır ve `TracePanel.jsx` bunu "Gözlem" olarak
render eder. Dört sinyalin dördü de ham hâliyle ekrana çıkıyordu; üstelik "belirsizlik"
kelimesi payload reddi için yanlıştı.

**③ KVKK.** Sinyal ile teşhis aynı string olduğu için, sinyali loglayan kod kullanıcının
tutarlarını da logluyordu:
`propose_action payload reddedildi: OZET_PAYLOAD_CELISKISI: ozetteki tutar(lar) [3200.0] ile
payload amount=320.0 uyusmuyor` (iki ayrı satırda ölçüldü). BUG #180 ilkesi ham finansal
metnin log'a düşmemesini şart koşar; ilke burada sinyalin **biçimi** yüzünden delinmişti.

**④ Sessiz iki tüketici daha.** `POST /api/expenses/recurring/trigger-due` ve
`/api/incomes/trigger-due` reddi `except Exception → logger.error` ile yutup
`{"triggered": []}` dönüyordu; cevapta atlama nedenini taşıyan **alan yoktu** ve Cockpit
yalnız `triggered`'ı okuyordu. Bugünkü veriyle bu yolda ret üretmek zor (API şeması tutarı
ve hesabı zaten doğruluyor) — yani **canlı defekt değil, yapısal sessizlik**; ama gerçekleştiği
gün kullanıcı kirasının önerilmediğini ancak ay sonunda fark ederdi ve `last_triggered`
yazılmadığı için istek her gün yeniden denenip her gün sessizce düşerdi.

## Karar

Tek kaynak **`app/action_errors.py`**: `AksiyonReddi(ValueError)` tabanı + beş alt sınıf
(`HesapBelirsiz`, `TarihBelirsiz`, `PayloadGecersiz`, `OzetPayloadCeliskisi`,
`BilinmeyenAksiyon`).

1. **Karar TİPE bakar, metne değil.** Tüketici `except AksiyonReddi` yazar; hangi alt sınıfın
   geldiğini bilmek zorunda değildir. Kullanıcıya söylenecek cümle (`kullanici_mesaji`), ize
   yazılacak gerekçe (`gorunur_neden` → `iz_gozlemi`), retry kararı
   (`kullanicidan_bilgi_ister`) ve trace etiketi (`iz_ciktisi`) **sınıfın üzerindedir**.
   Yeni bir sinyal eklendiğinde hiçbir tüketici bir dalı unutamaz — unutulacak dal yoktur.
2. **Değer taşıyan teşhis `str(e)`ye girmez.** `str(e)` = `KOD: kullanıcı-dostu gerekçe`;
   tutar/ham değer yalnız `.teshis` alanındadır, loglanmaz ve persist edilmez. Dikkatsiz bir
   `logger.warning(str(e))` bile para sızdıramaz — string'de para yoktur.
3. **Retry kararı da sinyalin kendisindedir.** Eksik olan KULLANICI bilgisiyse (hesap/tarih)
   modeli yeniden çağırmak aynı eksikle aynı öneriyi ürettirir → retry yok. Eksik olan
   MODELİN payload'ıysa ikinci deneme değerlidir → retry var. (Eski kod bu ayrımı
   `not account_unclear and not date_unclear` olarak elle yazıyordu.)
4. **Birden çok ret varsa** `en_oncelikli()` seçer: önce kullanıcıdan bilgi isteyen ret sorulur
   (o cevaplanmadan payload'ı düzeltmek kullanıcıyı iki kez yorar).
5. **Koçun iki tüketicisi tek yardımcıya indi** (`CoachEngine._propose_tek_cagri`) — BE-005'in
   işaret ettiği kopya budur. Kapı, gövdenin `chat()` içine geri kopyalanmasını yasaklar.
6. **Sessizlik yasak:** recurring tetikleyiciler `atlanan: [{id, ad, neden}]` döner, Cockpit
   bunu uyarı kartı olarak çizer.

## Reddedilen alternatifler

- **`str(e)` yerine `e.args[0] == "HESAP_BELIRSIZ"`.** Alt-dizi tuzağını kapatır ama kararı
  hâlâ metne bağlı bırakır; asıl defekt (kopyalanan dalın ayrışması, teşhis-sinyal füzyonu,
  iç kodun ekrana çıkması) aynen kalırdı.
- **Sinyal başına ayrı bayrak (`account_unclear`, `date_unclear`, `payload_invalid`) korunsun,
  yalnız eksik dal eklensin.** Ölçülen defekti kapatır, sınıfını kapatmaz: bir sonraki sinyal
  ya da bir sonraki tüketici aynı unutmayı yeniden üretir (L42).
- **Enum + kod alanı taşıyan tek istisna sınıfı.** Karar verisi yine `if kod == ...`
  zincirlerine dağılırdı; alt sınıflar bu veriyi taşıyıcının kendisine bağlar.
- **HTTP durum kodlarıyla sinyalleme (recurring uçlarında 4xx).** Tek bir isteğin içinde
  bazı kayıtlar başarılı bazıları reddedilebilir — durum kodu bunu ifade edemez; kısmi başarı
  gövdede raporlanır.

## Sonuç

- Matris **1/8 hatalı → 0/8**; iz sızıntısı **4 → 0**; tutar içeren log satırı **2 → 0**.
- Kapı: `tests/test_aksiyon_sinyali_kapisi.py` (30 test — sözleşme, davranış matrisi (her
  sinyal × her tüketici), sızıntı, AST yapı kapıları) + `atlanan-duzenli-kayit.test.jsx` (3).
- AST kapıları kalıcıdır: (a) `app/` içinde istisna METNİNE bakan karar yasak, (b)
  `propose_action` yalnız tipli sinyal fırlatır, (c) `propose_action` çağıran her `try`
  bloğu `AksiyonReddi`yi adıyla yakalar, (d) kullanıcı mesajları `coach.py`'de kopyalanamaz.
- Mutasyon 6/6 kırmızı. Altıncı mutasyon kapının kendi kör noktasını buldu (satıra bölünmüş
  kopya ham metin taramasından kaçıyordu → kopya kapısı AST'ye taşındı).
