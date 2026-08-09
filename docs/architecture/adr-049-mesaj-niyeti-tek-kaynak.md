# ADR-049 — Mesajın NİYETİ tek kaynaktan çıkarılır; soru, gerçekleşmiş eylemi veto edemez

**Durum:** Kabul edildi · **Tarih:** 2026-08-08 · **Faz:** PUBLISH / backlog LLM boyutu (LLM-010)
**İlgili:** ADR-001 (Rules Engine karar verir, LLM açıklar), ADR-008 (iki katmanlı savunma),
ADR-046 (kategori kaydı — "karar ADDA değil BAYRAKTA" aynı sınıf), ADR-048 (payload sözleşmesi)
**Bug:** #267

## Bağlam

KURAL SIFIR şunu söyler: *"`propose_action` SADECE kullanıcı gerçekleşmiş bir eylemi bildirdiğinde
çağrılır."* Bu kuralın deterministik ön-filtresi `app/coach.py` içindeydi ve şöyle karar veriyordu:

```python
if is_question(msg):                                  # ← koşulsuz veto
    return False
if is_future_or_intent(msg) and not has_realized_action(msg):
    return False
return True
```

Yani tek bir bayrak **iki bağımsız soruyu** cevaplıyordu: "bu mesaj bir şey soruyor mu?" ve "bu
mesaj gerçekleşmiş bir olay bildiriyor mu?". Bir mesaj ikisi birden olabilir — ve insanlar tam
olarak böyle yazar.

### Ölçüm 1 — karışık mesaj (7/7 yanlış)

25 mesajlık korpus + FakeProvider ile uçtan uca koşum (aynı payload'ı öneren "sadık" sağlayıcı,
yani ölçülen şey koçun becerisi değil KAPI):

| Mesaj | `propose_action` sunuldu mu | Oluşan kayıt |
|---|---|---|
| "Bugün markette nakitten 320 TL harcadım" | evet | **1** |
| "Bugün markette nakitten 320 TL harcadım, bütçem ne durumda?" | **hayır** | **0** |
| "Nakitten 320 TL market alışverişi yaptım, ne kadar param kaldı?" | **hayır** | **0** |

Zarar iki katmanlı ve her ikisi de sessiz:

1. Kullanıcının bildirdiği harcama **hiç kaydedilmez**.
2. Koç, kullanıcının sorusunu **harcama öncesi** rakamlarla yanıtlar — cevap yanlıştır ama doğru
   görünür. Kullanıcının bunu fark etmesi için, söylediği şeyin kaydedilmediğini kendi başına
   keşfetmesi gerekir.

Not: `has_realized_action` aynı zamanda BUG #127'nin retry'ını tetikleyen sinyaldir. Karışık
mesajda `offer_propose=False` olduğu için **retry de devreye girmiyordu** — yani sistemin bu
durumu kurtarmak için yazılmış ikinci mekanizması da aynı bayrağa takılıyordu.

### Ölçüm 2 — yazım (20 token)

Desenler yalnız diakritikli yazımı tanıyordu. Telefon klavyesinde çok yaygın olan
"odedim / dusunuyorum / degerlendir" yazımında kapı **başka türlü** karar veriyordu.

Sinsilik kaynağı: CPython'un genişletilmiş büyük/küçük katlaması `ı ↔ I ↔ i` eşitliğini
**kendiliğinden** kurar, `ç/ş/ğ/ö/ü` için kurmaz. Yani `\bharcadım\b` deseni "harcadim"i yakalar,
`\bödedim\b` ise "odedim"i yakalamaz. Sorun harf harf değişiyordu; test edilen örnekte tesadüfen
çalışabiliyordu — bu yüzden yıllarca "diakritik sorunu yok" gibi göründü.

### Ölçüm 3 — sınıf taraması (L11): aynı defekt iki yerde daha

- **`action_executor._DATE_KEYWORD_RE`** — "subatta / agustosta / eylulde" görülmüyordu. Bu desen
  `TARIH_BELIRSIZ` korumasını tetikler; görülmeyince koruma çalışmaz ve işlem **sessizce bugüne**
  yazılır (BUG #237/D17 ile aynı sonuç: kalıcı olarak yanlış gün). Kritik ayrıntı: bu desen
  sorunu **biliyordu** — `dün/bugün/geçen` için elle ASCII ikizi yazılmıştı (`d[uü]n|bugun|gecen`),
  ay adları için yazılmamıştı. Yani telafi elle yapılıyordu ve eksikti.
- **`coach_insights.QT_OPEN_PATTERN`** — `kac` yazılmış, `kaç` unutulmuştu. Bu sayaç **koçun kendi
  mesajlarını** ölçer ve koç düzgün Türkçe yazar; yani "Kaç lira ayırabilirsin?" gibi açık sorular
  hiç sayılmıyor, MI/OARS oranı olduğundan düşük görünüyor ve "direktif tarz" uyarısı haksız yere
  tetiklenebiliyordu (L22 ailesi: doğru sinyalin yanlış ölçümü, sinyalin yokluğu kadar zararlıdır).

Toplam: **20 token** iki yazımdan birinde eşleşmiyordu.

## Karar

1. **Niyet tek kaynaktan çıkarılır: `app/intent_rules.py`.** Sözleşme:

   ```
   propose_sunulsun = gerceklesmis  OR  (NOT soru AND NOT gelecek)
   ```

   Gerçekleşmiş eylem varsa **sorunun vetosu yoktur**. Yoksa soru da niyet de baskılar (eski
   davranış birebir korunur). Hiçbiri yoksa sunulur; ikinci katman prompt'tur (ADR-008).

2. **Karar üç bayrağı da taşır ve GEREKÇE üretir.** `MesajNiyeti.gerekce` reasoning trace'e
   düşer: "neden kaydetmedin?" sorusu log okumadan cevaplanabilir (BUG #253 ilkesi — kullanıcı
   kendi sistemini görebilmeli).

3. **Türkçe metin katlaması tek kaynak: `app/tr_text.py`.** Serbest metni desenle eşleştiren her
   yer önce `normalize()` uygular ve desenini **katlanmış** (diakritiksiz, küçük harf) yazar.
   Böylece "iki yazımı da desene elle eklemek" işi ortadan kalkar — unutulacak liste kalmaz
   (L26). `category_rules.TR_NORM/normalize` bu modülden re-export edilir; ikinci bir kopya yok.
   `normalize()` **uzunluk korur**, böylece normalize metinde bulunan eşleşme ofsetleri ham
   metinde de geçerlidir (alıntı çıkaran tüketiciler ham metinden keser).

4. **LLM sınıflandırıcı EKLENMEDİ.** Backlog LLM-010'un ikinci önerisi "belirsizler için küçük LLM
   intent classifier"dı. Uygulanmadı: bu bir **güvenlik kapısıdır**; ağ çağrısına ve modelin gününe
   bağlanırsa hem gecikme/kota maliyeti alır hem de deterministik olmayan bir katman KURAL SIFIR'ın
   önüne geçer. Deterministik kapı zemindir, prompt ikinci katmandır. (KURAL D1'in üç tetiği de
   HAYIR: geri dönüşü ucuz, cevap dış dünyada değil, yanlışlık sessiz kalmıyor — kapı ölçülüyor.)

5. **Soru tespitini genişletmek artık güvenlidir** ve genişletildi (soru eki çekimleri
   "sıralar mısın", talep gövdeleri "plan/sırala/açıkla/anlat"). Eski tasarımda `is_question`'a
   kelime eklemek, o kelimeyi içeren gerçek bir bildirimi yutabilirdi; bu yüzden liste dar
   tutulmuştu. Veto koşullu olduğu için bu bedel kalktı — **sözleşmeyi düzeltmek, listeyi
   büyütmeyi ucuzlattı.**

6. **Gerçekleşmiş-eylem listesi bilinçli olarak DAR kaldı.** Jenerik "-dı/-di" eki alınmadı:
   "borcum arttı" kullanıcı eylemi değildir ve bu bayrak retry'ı **zorlayan** sinyaldir — geniş
   tutulursa koç olmayan bir eylemi uydurmaya itilir (KURAL SIFIR'ın ters yönü).

## Sonuçlar

- Karışık mesajda harcama kaydedilir; korpusta yanlış **9/25 → 0/25** (düzgün yazım) ve
  **12/25 → 0/25** (diakritiksiz yazım). Uçtan uca **3/4 → 0/4** yanlış.
- Kırık token **20 → 0** (sekiz desen grubu, giriş noktalarından ölçüldü).
- Kalıcı kapı: `tests/test_niyet_kapisi.py` (156 test). İki yönlü:
  **davranış** (her vaka iki yazımla parametrize) + **drift kilidi** (desen literalleri modül
  namespace'i gezilerek toplanır ve katlanmış olmaları assert edilir — L27: kapı listeyi elle
  taşımaz; diakritikli bir literal eklenirse test kırmızı olur, çünkü o desen sessizce ölürdü).

## Reddedilen alternatifler

- **`is_question`e "geçmiş zaman varsa False dön" eklemek** (LLM-010'un birinci önerisi):
  konflasyonu düzeltmez, tersine çevirir — bu kez soru bayrağı gerçekleşmiş eylem yüzünden
  yalan söyler ve trace okunamaz hâle gelir. İki bayrak ayrı kalmalı, kararı sözleşme vermeli.
- **Desenlere ikinci yazımı elle eklemek:** kod tabanında zaten üç yerde denenmişti ve üçü de
  eksikti (`degil mi|değil mi` yazılmış, `kac|kaç` yazılmamış). Elle taşınan liste unutulur.
- **Kategori normalizasyonunu `category_rules`ta bırakıp oradan import etmek:** çağıran modüller
  "kategori kuralı" gibi okuduğu için fiilen üç yer daha kendi kısmi telafisini yazmıştı. Ad
  yanlış yerdeyse tek kaynak, tek kaynak sayılmıyor.
