# ADR-059 — SQLite'ta `alembic check` KALICI OLARAK KIRMIZIDIR; ölçüm ayrı bir kapıya taşındı

- **Durum:** Kabul edildi (4 Eylül 2026, Wave-Y / Y6 — mevcut sapmanın resmî kaydı)
- **Bağlam kodları:** BUG #241, #264, M11, M40, M50
- **İlgili:** ADR-013 (şema tek kaynağı Alembic), ADR-036/037 (workspace veri modeli),
  ADR-038 (hibrit DB: dev SQLite / prod PostgreSQL)

## Bağlam

`alembic check`, model ile göçlerin ayrışıp ayrışmadığını söyler. Bu depoda **hiç
koşulmuyordu**. 4 Eylül 2026'da R3 gereği koşuldu ve **başarısız** çıktı:

```
FAILED: New upgrade operations detected:
  add_fk categories.workspace_id -> workspaces.id
  add_fk personal_debts.settlement_account_id -> accounts.id
```

Tam envanter alındı (model FK'ları ↔ göçün kurduğu FK'lar, 31 tablo): SQLite'ta
**14 FK kurulmuyor** — `alembic check`'in gösterdiği 2 değil.

**Ve 14'ü de bilinçlidir.** `alembic/versions/d4e5f6a7b8c9_workspace_id_fks_postgres.py`
(M50, Wave-7, 18 Temmuz 2026) bunu docstring'inde yazıyor: SQLite `ALTER TABLE ADD
CONSTRAINT` desteklemez ve batch-recreate, **inbound-FK'li tabloları kırar** (M11 dersi).
Bu yüzden fiziksel FK yalnız PostgreSQL'de kurulur. Telafi edici kontroller adlandırılmış:
model-seviyesi FK (ORM ilişkisi) + uygulama-katmanı scope filtresi (Wave-5 AST kapısı) +
PostgreSQL RLS (M51). `personal_debts.settlement_account_id` de aynı desende
(`f2a3b4c5d6e7`, dialect-korumalı), `categories.workspace_id` de — o, FK'sını M50'nin
listesinde değil **kendi göçünde** kurar (`b4c5d6e7f8a9:83-87`).

## Karar

### 1. Sapma kabul edilir ve KAYIT ALTINA ALINIR

SQLite'ta bu 14 FK'nın bulunmaması bir arıza değil, **belgelenmiş bir lehçe farkıdır**.
Dolayısıyla `alembic check` bu depoda SQLite'ta **kalıcı olarak kırmızıdır** ve bu
beklenen davranıştır.

### 2. `alembic check` bir KAPI OLARAK KULLANILAMAZ — ve asıl sorun buydu

Kalıcı kırmızı bir araç okunmaz (L22). Ölçüldü:
`grep -rn "alembic check" .github/workflows/ scripts/` → **boş**. Yani sapmanın
belgelenmesi, o sapmayı ölçen tek aracı **kalıcı olarak okunamaz kılmıştı**. Şema bugün
temiz olsa bile **yarın eklenecek karşılıksız bir FK görünmez** olurdu.

### 3. Ölçüm ayrı bir kapıya taşınır: `tests/test_fk_sapmasi_kapisi.py`

Kapı sapmanın **varlığını** değil, sapmanın **karşılıksız kalmasını** ölçer:

> Bir FK'nın SQLite'ta kurulmaması ancak, onu PostgreSQL'de **gerçekten kuran**
> dialect-korumalı bir göç varsa meşrudur.

Muafiyet **elle yazılan bir listeye değil, karşılığına** bağlıdır (L67) — liste yazılsaydı,
bir göçün Postgres bloğu silindiğinde kapı kör kalırdı. Ayrıca ratchet (sapma 14'ten
büyüyemez) ve kazanım kilidi (küçülürse tavan düşer) vardır. **Mutasyon 3/3.**

## Alternatifler

* **SQLite'ta batch-recreate ile FK eklemek:** M11'de denendi ve **inbound-FK'li tabloları
  kırdı**. Canlı beta verisini bir migration'a emanet etmek anlamına gelirdi.
* **Modelden FK tanımlarını kaldırmak:** ORM ilişkileri ve PostgreSQL bütünlüğü kaybolurdu;
  prod tarafında gerçek bir koruma feda edilmiş olurdu.
* **`alembic check`'i CI'ya eklemek:** kalıcı kırmızı verirdi; ya CI hep kırmızı kalır ya
  da "bu kırmızıyı yok say" alışkanlığı doğar — ikisi de kapıyı öldürür.
* **Sapmayı hiç kaydetmemek (bugüne kadarki durum):** kaydedilmemiş bir sapma, bir sonraki
  turda "yeni bulunmuş bir defekt" gibi görünür. Nitekim bu ADR yazılırken **iki kez yanlış
  teşhis** koyuldu (aşağıda).

## Dürüst kayıt — bu ADR yazılırken iki yanlış teşhis

1. *"14 FK sessizce eksik, hiçbir kapı görmedi"* → **yanlış**; sapma `d4e5f6a7b8c9`'nin
   docstring'inde açıkça belgeliydi. **Ders: "kimse görmedi" demeden önce BELGELEYEN
   dosyayı ara** (L67).
2. *"`categories` listeye yazılmamış, PostgreSQL'de de FK almıyor"* → **yine yanlış**;
   kendi göçünde kuruyor. Bu teşhisle düzeltici bir göç **yazıldı** ve o göç PostgreSQL'de
   **aynı kısıtı ikinci kez kurup patlayacaktı**. **Mutasyon testinin M1'i hayatta kalması**
   bunu ortaya çıkardı ve göç silindi.

**Mutasyon yalnız testi değil, TEŞHİSİ de sınar.**

## Sonuç

Şemada defekt yok; eksik olan **ölçümdü** ve kapatıldı. `alembic check`'in kırmızısı
bundan sonra bir arıza değil, bu ADR'ye yapılan bir atıftır.
