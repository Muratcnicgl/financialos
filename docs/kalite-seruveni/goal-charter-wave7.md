# Goal Charter — WAVE-7: POSTGRESQL GEÇİŞİ + VERİ-KATMANI BORÇLARI (MEGA-CHARTER)

**Tarih:** 2026-07-18 · **Rollback tag:** `pre-wave-7` (3a0624e)
**Baseline:** `docs/kalite-seruveni/tam-proje-durum-raporu.md` (B4 veri modeli + B5 migration)
**Giriş durumu:** Wave-6 kapanışı · 1235 test · coverage %92 · auth ON · tek user id=1 · SQLite.

---

## ÜRÜN-DNA (Murat, 18 Tem 2026) — TARTIŞMA YOK
- Wave-7 = **PostgreSQL** (dev SQLite / prod Postgres hibrit) + **SBN-001** + Postgres'in dokunduğu veri-katmanı
  borçları. **LOKAL, para gerektirmez.** Otonom sona kadar sür.
- **DEPLOY → Wave-8'e ertelendi** (VPS parası). **MOBİL → Wave-8'e ertelendi** (deploy'a bağlı, HTTPS'siz yarım
  kalır). Bu wave İKİSİNİ DE YAPMAZ.
- **Kripto KAPSAM DIŞI** (Murat varlık sahibi değil).
- **273 backlog'un TAMAMI DEĞİL:** yalnız Postgres'in dokunduğu veri-katmanı borçları. Saf UX/kozmetik/refactor
  borcu Wave-8-sonrası (deploy sonrası gerçek kullanımla önceliklenecek). Bunları otonom "hepsini yaptım" diye
  kapatma — **KURAL 12.**

## DEĞİŞMEZ KURALLAR
Wave-2/3/4/5/6 charter'ları tam metin geçerli. KURAL 1/3/12, K10, D1, R3, W1-W8, ADR-001, **ADR-013 (Alembic tek
doğruluk, create_all prod'da YASAK), ADR-013a**, OTONOM KARAR + SELF-CORRECTION. Her milestone: **canlı-gate → tag →
push → MCP → milestone-log.** Charter Revize açık (ürün-DNA hariç) = tag `charter-revise-w7-<N>` + MCP. Tıkanıklıkta
OTONOM KARAR. Web asistana "ne yapayım" YASAK.

> ⚠️ **ERKEN-TAMAM YASAĞI:** "TAMAM" demeden TÜM agent'lar bitmiş + tam süit tek seferde koşulmuş olacak (Wave-5 erken-TAMAM hatası tekrarlanmasın).
>
> ⚠️ **KRİTİK CANLI-GATE:** Bu wave'de "SQLite yeşil" YETMEZ — her gate **Postgres'te de koşmalı.** Docker'da gerçek Postgres ayağa kaldırılacak.

---

# BLOK A — HİBRİT ALTYAPI (M49-M50)

**Blok gerekçesi:** B5 — prod-Postgres yolu ADR'de var, kodda TEST EDİLMEDİ.

### M49 — Postgres Docker + bağlantı katmanı
- **Çıktı:** docker-compose'a gerçek postgres servisi. `DATABASE_URL` dialect-aware (sqlite dev / postgresql prod).
  Havuz (pool), session Postgres'te çalışır.
- **GATE:** `docker compose up` → postgres sağlıklı → `curl /api/health` **Postgres arkasında 200.**
- **D1:** 2-3 referans (SQLAlchemy dual-dialect).
- **Tag:** `milestone-49-postgres-docker-baglanti`.

### M50 — Alembic multi-dialect
- **Çıktı:** Tüm migration HEM SQLite HEM Postgres'te koşuyor. SQLite-özel kalıplar (`batch_alter_table`, tip
  gevşekliği) Postgres'te patlar → düzelt. Temiz Postgres'ten `upgrade head` → tam şema.
- **GATE:** temiz postgres → `upgrade head` → tablo sayısı SQLite ile AYNI + `alembic check` temiz.
- **Tag:** `milestone-50-alembic-multi-dialect`.

---

# BLOK B — VERİ KATMANI DOĞRULAMA (M51-M52)

### M51 — Row-Level Security (RLS)
- **Gerekçe:** B23e — RLS gelene kadar izolasyonun TEK koruması uygulama katmanı. Postgres RLS = ikinci savunma
  (workspace_id policy). `scope_filter` (Wave-5 AST tarayıcı) + DB-katmanı RLS.
- **GATE:** Postgres'te RLS aktif → yanlış workspace context → **0 satır** (uygulama filtresi bypass edilse bile DB
  korur). Postgres-özel, gate Postgres'te koşmalı.
- **Tag:** `milestone-51-row-level-security`.

### M52 — Numeric/tip bütünlüğü iki dialect'te
- **Gerekçe:** B4 — para sütunları. SQLite gevşek, Postgres katı. Aynı Decimal iki DB'de aynı precision/scale mi?
- **GATE:** aynı işlem SQLite + Postgres → **bit-bire aynı Decimal.**
- **Tag:** `milestone-52-numeric-butunluk-dual-dialect`.

---

# BLOK C — SBN-001 + NET-WORTH KÖK NEDEN (M53)

### M53 — net-worth işaret konvansiyonu tek kaynak
- **Gerekçe:** SBN-001 (backfill_net_worth kredi/kart geçmiş net-değer hatası) + BUG #161 (kart ödemesi borcu
  artırıyordu) **AYNI AİLE** — işaret hatası tekrar ediyor. Yamamak yerine kök çözüm.
- **Çıktı:** borç/varlık işaret konvansiyonu kaç yerde (grep) → **tek kaynağa topla** (M82 action_type deseni) → tüm
  net-worth/backfill/cockpit hesaplarını oradan geçir.
- **GATE:** gerçek kredi+kart+hesap verisiyle net-worth → elle hesap → EŞİT. İki dialect.
- **Tag:** `milestone-53-net-worth-isaret-tek-kaynak`.

---

# BLOK C2 — HİSSE OTOMASYON CANLI DOĞRULAMA (M53 sonrası)

**Blok gerekçesi:** R3 tanısı (18 Tem) — fon otomasyonu TAM çalışıyor (tefas bugün yazdı), **hisse otomasyonu YAZILMIŞ
AMA HİÇ İŞLETİLMEMİŞ.** yfinance bu ortamda bloklu (dış kısıt, kod eksiği değil). İş Yatırım fallback kodda var ama canlı
HİÇ denenmemiş (PriceHistory `isyatirim` source=0). 0 hisse hesabı. **Bu, `transactions=0` ile aynı hastalık: yeşil test,
sıfır gerçek çalışma.**

### M-hisse — İş Yatırım fallback + uçtan uca BIST
1. 1 gerçek BIST hesabı ekle (örnek THYAO veya bir gerçek pozisyon).
2. `get_stock_price` İş Yatırım fallback dalını CANLI test et — fiyat dönüyor mu.
3. `fetch_for_account(asset_type='stock')` → PriceHistory'ye `isyatirim` source satırı düştü mü.
4. **GATE (KULLANIM-GATE — gerçek veriyle uçtan uca):** gerçek BIST hesabı → scheduler job → PriceHistory'de
   `isyatirim` source > 0 + cockpit'te hisse değeri göründü.
5. **İş Yatırım da bu ortamda erişilemezse:** OTONOM KARAR (b) yaz — "hisse otomasyonu kod-tam, canlı doğrulama
   Wave-8 deploy ortamına ertelendi, dış-kısıt yfinance+isyatirim lokal blok", tag'le, GEÇ. **Körlemesine "tamam" DEME.**
- **NOT:** Bu milestone iki-dialect gate'ine tabi DEĞİL (Postgres-ilgisiz), yalnız kendi KULLANIM-GATE'ine tabi.
- **Tag:** `milestone-stock-price-verification`.

---

# BLOK D — POSTGRES'İN DOKUNDUĞU VERİ-KATMANI BORÇLARI (M92+)

**Blok gerekçesi:** 273 backlog'dan yalnız Postgres geçişinin ZATEN dokunduğu DATA maddeleri.
- **Önce R3 AYIKLAMA:** backlog'dan DATA + BE-persistence etiketli, Postgres'te davranış değiştiren maddeleri ayıkla
  (örnek: SQLite-varsayan sorgu, dialect-bağımlı tarih/JSON işlemi, eksik index, cascade drift).
- **Her ayıklanan madde:** kök neden + iki-dialect fix + test.
- **GİRMEZ:** saf UX/kozmetik/refactor → Wave-8'e etiketle bırak.
- **GATE:** her fix iki dialect'te yeşil. Bitince **"Postgres-ilgili borç kapandı, saf-UX borç Wave-8'e ertelendi, N madde"** raporla.
- **Tag'ler:** `milestone-92-...` ve sonrası (ayıklanan madde sayısına göre).

---

# BLOK E — KAPANIŞ (M92+ son)
- **Çıktı:** `tam-proje-durum-raporu` güncelle (Postgres + B4/B5 farkları + kapanan borç listesi). `PROJE.md` güncelle
  (hibrit DB). **ADR-Postgres yaz** (hibrit + RLS + dual-dialect Alembic). Wave-8 iskeleti: **DEPLOY + MOBİL birlikte**
  (VPS parası + Apple $99 + PWA-vs-RN kararı Murat'a bırakılacak — iskelette D1 ile PWA-vs-RN ön-analiz hazır olsun).
- **MCP:** GOAL TAMAM W7 + W1 rotasyonu (Working State observation sayısını kontrol et).
- **Tag:** `milestone-<son>-wave7-kapanis`.

---

## BİTİRME
**DUR.** "GOAL TAMAM WAVE-7" + kapanış raporu (kazanç / açık / borç / çelişkiler + kaç backlog maddesi kapandı kaç
ertelendi). **DEPLOY/MOBİL'e GEÇME — Wave-8, Murat kararı.**

## BAŞLA
`pre-wave-7` tag + charter dosyası. Sonra M49.
