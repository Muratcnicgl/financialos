# ADR-046 — Kategori kullanıcıya ait bir KAYITTIR; kod hiçbir kararı kategori ADINA bağlamaz

**Durum:** Kabul edildi · **Tarih:** 2026-08-07 · **Faz:** PUBLISH / P3.5.3 — H4 kuyruğu (masterprompt §1.2)
**İlgili:** ADR-042 (kişiselleştirme aşamalı), ADR-044 (para birimi tek kaynak — aynı sınıf borç),
ADR-036/037 (workspace köprüsü), ADR-001 (Rules Engine karar verir), ADR-013 (şema = Alembic)
**Bug:** #264 · **D1 araştırması:** `docs/kalite-seruveni/research-log.md` (2026-08-07)

## Bağlam

H4 ("para birimi / dil / saat dilimi / kategori seti kullanıcı başına") üç ayağından ikisi kapandı:
saat dilimi (#197/#237) ve para birimi görüntüleme (#256 / ADR-044). Kalan ayak ölçüldüğünde
sorunun "eksik özellik" değil **yapısal** olduğu görüldü: kod, kullanıcının parasıyla ilgili
kararları **sabit Türkçe kategori adlarına** bağlıyor.

Ölçüm (7 Ağu 2026, kaynak taraması):

1. **`app/action_executor.py:203` — PARA kararı.** `_CARD_CATEGORIES = {"yemek", "eglence",
   "sigara", "alisveris", "market"}`. Koç bir harcama kaydederken kategori bu kümedeyse işlem
   **kullanıcının kredi kartına** yönlendirilir (`account_id` + `is_card_expense=True` zorlanır).
   Yani "hangi hesaptan çıktı" sorusunun cevabı, kullanıcının kategorisini **hangi kelimeyle
   adlandırdığına** bağlı. Kendi setini kuran kullanıcı ("gıda", "market alışverişi", "food")
   bu kümeye hiç düşmez → yönlendirme sessizce ölür (L28). Tersi de doğru: kartını kapatmış ama
   "market" adını kullanan kullanıcının nakit harcaması karta yazılır.
2. **`app/rules_engine.py:1024` — UYARI kararı.** `_PATTERN_EXCLUDED_CATEGORIES` muhasebe
   işlemlerini (`transfer`, `borc_odeme`, `kredi_taksiti`, …) harcama-paterni analizinden çıkarır.
   Bu da ada bağlı: kullanıcı "borç kapama" yazdığı an dışlama ölür ve **borç ödemesi kişisel
   harcama artışı sayılır** → "harcaman %40 arttı" uyarısı yanlış çıkar. Sınıf taraması aynı
   listede hâlihazırda bir boşluk buldu: hızlı girişin ürettiği `borc_geri_odeme` (bkz.
   `routers/transactions.QUICK_KEYWORDS`) dışlama listesinde **yok**, yani bu defekt bugün
   tek-kullanıcı kurulumunda bile canlı.
3. **Arayüzde üç ayrı, birbirinden farklı sabit liste:** `Transactions.jsx` (`yemek, ulasim,
   fatura, eglence, sigara, …`), `IncomeDebt.jsx` (`abonelik, fatura, kira, sigorta, internet,
   telefon, diger`) ve `Budget.jsx`'in placeholder metni. Kullanıcı kendi kategorisini yazabiliyor
   (alan serbest metin) ama **hiçbir yerde kuramıyor, adlandıramıyor, silemiyor** — ve üç liste
   aynı uygulamada üç farklı gerçeklik gösteriyor.

Bu, ADR-044'ün kapattığı borcun aynısıdır: **anlam, veriden koda kaçmış.** Orada "TL" literali
grounding'i sessiz-yeşile düşürüyordu; burada kategori adı, paranın hangi hesaba yazılacağını
belirliyor.

## Karar

**1. Kategori bir kayıttır (`categories` tablosu), kullanıcı/workspace kapsamlı.** Alanlar:
`slug` (normalize, `Transaction.category` ile eşleşen değer), `ad` (görünen ad), `kart_varsayilani`
(bool), `sistem` (bool), `gizli` (bool). Kapsam deseni diğer tablolarla aynıdır (`user_id` +
`workspace_id`, ADR-036/037).

**2. `Transaction.category` serbest metin olarak KALIR.** Foreign key konulmaz. Gerekçe: (a)
geçmiş veri hiçbir koşulda kaybolmaz/kaymaz, (b) koç ve hızlı giriş metinden kategori türetir —
FK, bilinmeyen bir kategoriyle gelen kaydı **reddetmek** zorunda kalırdı ve kullanıcının işlemi
kaybolurdu (L2'nin tersi: sessiz kabul kadar kötü olan sessiz RET). Eşleşme `slug` üzerinden
kurulur; eşleşmeyen değer "kayıt yok" demektir, hata değil.

**3. Kod hiçbir kararı kategori ADINA bağlamaz — bayrağa bağlar.** `_CARD_CATEGORIES` ve
`_PATTERN_EXCLUDED_CATEGORIES` sabit kümeleri **kalkar**; yerlerine tek kaynak
`app/category_rules.py` gelir (`balance_rules.py` / `account_rules.py` kardeşi):
`kart_varsayilani_mi(db, user_id, ws, slug)` ve `sistem_kategorisi_mi(...)`. Karar veren tek yer
burasıdır; çağıranlar kendi kümesini yazamaz. Kapı: `tests/test_kategori_kapisi.py` — üretim
kodunda kategori adı literaline bağlı yeni karar eklenemez (kapsam tabanı assert'li, L11/L25).

**4. Varsayılan set TOHUMLANIR, dayatılmaz.** Yeni kullanıcı bugünkü davranışı birebir veren bir
başlangıç setiyle açılır; hepsini yeniden adlandırabilir, kart varsayılanını değiştirebilir,
gizleyebilir, silebilir. Tohumlama **idempotent**tir ve kategorisi hiç olmayan kullanıcıda okuma
yolundan da tetiklenir (migration sonrası açılmayan hesaplar için sessiz boşluk kalmasın).

**5. Sistem kategorisi ayrı bir sınıftır ve silinemez/yeniden adlandırılamaz.** `transfer`,
`borc_odeme`, `kredi_taksiti`, `borc_geri_odeme` gibi değerler kullanıcı harcaması değil muhasebe
işlemidir; `sistem=True` taşırlar ve harcama-paterni analizinden çıkarılırlar. Bu, sektörün
yerleşik ayrımıdır (YNAB API kategori kaynağında `internal: boolean`; Actual Budget'ta gelir grubu
silinemez) — ada değil bayrağa bağlı olması bizim eklediğimiz düzeltmedir.

**6. Silme = yeniden atama veya gizleme.** Kullanılmış bir kategori silinirken kullanıcı hedef
kategori seçer ve **mevcut işlemler oraya taşınır** (merge); hedef verilmezse silme reddedilir.
Artık kullanılmayan kategori için `gizli` bayrağı vardır — liste temizlenir, geçmiş bozulmaz.
(Actual Budget'ın "select which category the transactions should be moved to" akışı; YNAB'ın
`hidden` ayrımı.)

**7. Göç davranışı değiştirmez.** Migration her kullanıcı için: (a) varsayılan seti tohumlar,
(b) o kullanıcının verisinde geçen ayırt edici `Transaction.category` / `Envelope.category`
değerlerini kayda çevirir, (c) `kart_varsayilani` ve `sistem` bayraklarını **eski sabit kümelerden**
türetir. Sonuç: bugünkü kullanıcı için davranış birebir aynı; değişen tek şey **sahiplik**.

## Reddedilen alternatifler

- **`Transaction.category` → FK.** Referans bütünlüğü kazanır, ama koç/hızlı giriş yolunda
  bilinmeyen kategori gelen kaydı reddetmeyi zorunlu kılar (kullanıcının işlemi kaybolur) ve
  geçmiş veriyi göç anında eşleşmeye mecbur eder. Reddedildi (madde 2).
- **Kategori adlarını i18n sözlüğüne bağlamak.** Sorun dil değil sahiplik: İngilizce sabit set de
  kullanıcının seti değildir. i18n ayrı bir iştir ve kapalı beta (TR) için yayın-engeli değildir.
- **Kart yönlendirmesini tümüyle kaldırmak.** Kolaylık gerçek: "300 TL market" diyen kullanıcı
  hesabı belirtmiyor. Karar kalır, sahibi değişir.

## Sonuç / kapsam dışı

- **Kapsam dışı (bilinçli):** çok dilli arayüz (i18n), kategori grupları/alt kategoriler, kategori
  bazlı otomatik kural motoru. Bunlar ayrı ADR ister.
- **Kapı:** `tests/test_kategori_kapisi.py` (ada-bağlı karar yasağı + kapsam tabanı),
  `tests/test_kullanici_kategorileri.py` (davranış + göç + izolasyon).
