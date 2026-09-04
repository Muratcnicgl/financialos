# ADR-058 — Yedi kalite kapısı ve tavanların anlamı: tavan bir HEDEF değil, bir BORÇ DONDURUCUDUR

- **Durum:** Kabul edildi (4 Eylül 2026, Wave-Y / Y6 — geriye dönük kayıt)
- **Bağlam kodları:** BUG #306, #307, #308, #309, #310, #311, #338, #339
- **İlgili:** ADR-013 (şema tek kaynağı Alembic), ADR-001 (kural motoru karar verir)

## Bağlam

27 Ağustos 2026'dan önce bu depoda **statik analiz yoktu**, **coverage hiçbir yerde
ölçülmüyordu**, **API sözleşmesi dondurulmamıştı** ve **süitin internete çıkmasını
engelleyen hiçbir şey yoktu**. Yedi gün içinde yedi kapı kuruldu. Kapılar var ama
*neden öyle kurulduğu* commit mesajlarında dağınık kaldı — bu ADR o kararı toplar.

**Kapılar ve bugünkü tavanları (4 Eylül 2026 ölçümü):**

| Kapı | Dosya | Tavan | Tipi |
|---|---|---|---|
| ruff (dar küme `E9,F,B,S`) | `scripts/kalite_kapisi.py` | E9 **0** · F **202** · B **31** · S **63** | ratchet |
| Ölü kod | `scripts/olu_kod_kapisi.py` | çağrılmayan **0** | mutlak |
| Coverage | CI `--cov-fail-under` | **≥ %93** (ölçülen %94,02) | taban |
| Belge denetimi | `scripts/belge_denetimi.py` | ölü yönlendirme **0** | mutlak |
| Ağ kapısı | `tests/test_ag_kapisi.py` | süit dışarı çıkamaz | mutlak |
| API sözleşmesi | `tests/test_api_sozlesmesi.py` | 125 handler · 106 korumalı | donmuş |
| Kişisel veri | `tests/test_depo_kisisel_veri_kapisi.py` | hesap no/IBAN/kart **0** · e-posta **15** · banka **96** | iki kademeli |

## Karar

### 1. Tavan bir HEDEF değil, bir BORÇ DONDURUCUDUR

`F 202` "202 bulgu iyidir" demek **değildir**; "bugün 202 var, **203 olamaz**" demektir.
Mevcut borç dondurulur, büyümesi engellenir. Bu ayrım önemli çünkü tavanı hedef sanmak,
onu yükseltmeyi meşru bir "ayar" gibi gösterir.

### 2. Tavan AİLE BAZINDA tutulur, tek toplam DEĞİL

Tek toplam **takasa** izin verirdi: 5 kullanılmayan import temizlenip 5 yeni güvenlik
bulgusu eklendiğinde sayı aynı kalır ve kapı susardı. Aile bazında `S 63 → 64` kırmızıdır,
`F 202 → 197` olsa bile.

### 3. Araç sürümü baseline'da SABİTTİR ve tavandan ÖNCE doğrulanır

Linter sürümü değişince sayının anlamı değişir: zıplarsa sahte kırmızı, düşerse **gerçek
gerileme görünmez** olur. `kalite_kapisi` bu yüzden önce `ruff` sürümünü karşılaştırır.

### 4. Bir kapı reddettiğinde doğru cevap TAVANI YÜKSELTMEK DEĞİLDİR

**Ölçülen sicil:** kapılar bu dönemde değişiklikleri **en az sekiz kez** reddetti ve
her seferinde haklı çıktı — S310 `urlopen`, S603 `subprocess`, boş-durum fixture'ı,
imaj kişisel-veri, ve Wave-Y'de üç kez `S607`. Sekizinde de **tasarım** düzeldi, tavan değil.

`S607`'nin öyküsü bu kuralın kanıtıdır: `git ls-files` çağrısı depoda çoğaldıkça tavan
**üst üste üç kez yükselmişti**. `test_kacis_dizisi_kapisi.py` bunu fark edip dördüncüsünü
yazmayı reddetti. Wave-Y'de beşinci ve altıncı kopyalar yine yazıldı ve tavan yine kırıldı —
çözüm `scripts/kabuk.py` tek kaynağı oldu. **Kısmi yol artık tek yerde yaşıyor ve gerekçesi
orada yazılı.**

### 5. Kapsam dışı bırakılanlar ÖLÇÜLEREK seçildi, kanaatle değil

`B008` (229 bulgunun 229'u FastAPI `Depends()` deseni) · `S101` tests/ için (4.484 pytest
assert'i) · `DTZ` (212 — proje datetime'ı bilinçli naive UTC) · `I001`/`UP`/`format`
(sinyal yok, 403 dosyalık diff; toplu biçimlendirme gerçek değişikliği gizler).

### 6. Coverage eşiği `pyproject.toml`'a KONMAZ

Ölçüldü: oraya konduğunda tek dosyalık koşum da eşiğe tabi olur ve **%36,70 ile sahte
kırmızı** verir. Alt küme tam süit değildir; eşiğin orada anlamı yoktur.

## Alternatifler

* **Tüm bulguları temizleyip tavanı 0 yapmak:** F'nin 202'sinin 177'si kullanılmayan
  import; otomatik düzeltilebilir ama `__init__.py`/alembic'te bazıları yeniden-dışa-aktarım
  olabilir. Ölçülmeden `--fix` yapılamaz → ayrı, tek amaçlı iş olarak backlog'da.
* **Ruff'ın tüm kural setini açmak:** gürültü üretir, gürültülü kapı okunmaz (L22).
* **Kapıları uyarı seviyesine indirmek:** uyarı, okunmayan kapıdır — aynı L22.

## Sonuç

Kapılar bugün **defekt bulmuyor** (ölü kod hariç, o 4 gerçek bulgu vermişti). Değerleri
bulmakta değil **bundan sonrasını tutmakta**. Bir kapının "bugün bir şey bulmaması" onun
işe yaramadığını değil, borcun büyümediğini gösterir.
