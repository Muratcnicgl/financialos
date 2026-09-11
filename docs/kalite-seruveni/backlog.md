# FinancialOS — Improvement Backlog (Kalite Serüveni)

**Başlangıç:** 6 Temmuz 2026 · **Durum:** 1. tur tamamlandı — **521 kanıta dayalı madde / 18 kategori**.

> **Düzeltme (7 Ağu 2026):** bu dosya yıllardır "520" diyordu; `sections/` altındaki gerçek madde
> sayısı **521**'dir (FEAT 40 değil **41**). Ölçüm: her boyut dosyasında `### [KOD-NNN]` blok sayımı.
> **Güncel durum dağılımı (7 Ağu 2026 ölçümü, akşam):** 152 KAPALI · **262 AÇIK** · 82 KISMEN · 25 DURUMSUZ.
> (Ölçüm: `sections/*.md` içinde `- **Durum:** 🔲/🟡` sayımı. Ara noktalar: 6 Ağu 145/272/79 →
> SEC turu 150/267 → BUG #265 turu 152/262/82.)
**Yöntem:** Gerçek kod denetimi (`file:line`) + en iyi uygulamalar / benzer ürünler / akademik kaynak. Kopyalama değil entegrasyon. Her madde bir geliştirici tarafından ek araştırma olmadan uygulanabilir.

## Kök vizyon (bağlam)
Ata sürüm **"Sovereign OS"**: tamamen yerel, internetsiz, **Qwen 2.5** ile kendi işlemcisinde çalışan finansal analiz sistemi; checkpoint (hafıza) + mantık motoru. Arayüz **Streamlit** ("160 IQ Strateji Odası", "Canlı Nakit Akışı"), backend `/api/coach`, borç-eritme projeksiyon grafiği. → Bugünkü **FastAPI + React + Rules Engine + LLM fallback** mimarisinin doğrudan atası. (Gemini kök sohbetleri kullanıcı tarafından not defterine aktarılıyor; geldiğinde `docs/architecture/origin-vision.md`'ye işlenecek — bkz. DOCS-010.)

## Prensipler (değişmez)
- Rules Engine karar verir, LLM açıklar. Hiçbir madde bu ayrımı bozmaz.
- LLM asla doğrudan DB yazmaz: propose → onay → execute.
- Master Checkpoint enforcement kod seviyesinde kalır.
- Türkçe alan adları korunur. ADR-001 yasaklı kelimesi hiçbir yeni metinde kullanılmaz (doğrulandı: 0 sızıntı).

## Kategoriler (520 madde)

| Kod | Kategori | Madde | Dosya |
|-----|----------|-------|-------|
| BE | Backend mimari & kod kalitesi | 40 | [sections/BE.md](sections/BE.md) |
| RULE | Rules Engine & finansal doğruluk | 40 | [sections/RULE.md](sections/RULE.md) |
| LLM | Coach / AI orkestrasyon | 40 | [sections/LLM.md](sections/LLM.md) |
| UX | Ürün & kullanıcı deneyimi | 40 | [sections/UX.md](sections/UX.md) |
| FEAT | Finansal ürün özellikleri (yeni yetenek) | 41 | [sections/FEAT.md](sections/FEAT.md) |
| DATA | Veri modeli & DB | 35 | [sections/DATA.md](sections/DATA.md) |
| SEC | Güvenlik, gizlilik, auth (KVKK) | 35 | [sections/SEC.md](sections/SEC.md) |
| FE | Frontend mimari & kod kalitesi | 35 | [sections/FE.md](sections/FE.md) |
| TEST | Test & QA | 35 | [sections/TEST.md](sections/TEST.md) |
| MOB | Mobil & PWA & offline | 25 | [sections/MOB.md](sections/MOB.md) |
| OBS | Gözlemlenebilirlik & operasyon | 25 | [sections/OBS.md](sections/OBS.md) |
| API | API tasarımı & sözleşme | 20 | [sections/API.md](sections/API.md) |
| PERF | Performans | 20 | [sections/PERF.md](sections/PERF.md) |
| RESIL | Dayanıklılık & hata yönetimi | 20 | [sections/RESIL.md](sections/RESIL.md) |
| DEVOPS | CI/CD, build, tooling | 20 | [sections/DEVOPS.md](sections/DEVOPS.md) |
| A11Y | Erişilebilirlik & i18n | 20 | [sections/A11Y.md](sections/A11Y.md) |
| DOCS | Dokümantasyon & DX | 15 | [sections/DOCS.md](sections/DOCS.md) |
| DVIZ | Raporlama & görselleştirme | 15 | [sections/DVIZ.md](sections/DVIZ.md) |
| **TOPLAM** | **18 kategori** | **521** | |

## Öne çıkan öncelikli maddeler

> **Bu liste ELLE yazılıyordu ve 11 Eyl 2026'da ölçüldü:** "canlı bug" diye sunduğu yedi
> maddenin BEŞİ bölüm dosyalarında ✅ kapalıydı (RULE-001, DATA-003, SEC-001, RULE-006,
> FE-002). DURUM-INDEX'in 48 gün geride kalmasıyla aynı hastalık (L79). Artık SEÇİM elle
> (`scripts/backlog_ozeti.py:ONCELIKLI_KODLAR`), DURUM `sections/`ten türetilir ve
> `tests/test_backlog_tutarliligi_kapisi.py` bloğun güncel olduğunu dayatır.

<!-- OTOMATIK-ONCELIK:BASLA — elle düzenleme; `python scripts/backlog_ozeti.py --yaz` -->

**Üretildi:** `scripts/backlog_ozeti.py` · seçim elle, durum `sections/`ten · **4 açık / 10 kapandı**

- 🔲 **FE-026** — Hesap alan adı tutarsızlığı: `.ad` vs `.name` (latent bug) (açık)
- 🟡 **BE-009** — Merkezî exception handler yok — `chat` endpoint hataları 200 ile gizliyor (kısmen)
- 🟡 **API-004** — `/api/coach/chat` hata durumunda HTTP 200 dönüyor — sözleşme ihlali (kısmen)
- 🟡 **RESIL-016** — Chat endpoint tüm hataları yutup 200 dönüyor — hata görünmez, retry yok (kısmen)

<details><summary>Kapananlar</summary>

- ✅ **RULE-001** — `_matches` account_type kriteri hiçbir zaman eşleşmiyor (enum str bug) — CANLI HATA ✅ UYGULANDI (BUG #059) (kapandı)
- ✅ **RULE-002** — Kart asgari ödemesi başlangıç bakiyesine sabitleniyor (yanlış amortisman) ✅ UYGULANDI (BUG #079) (kapandı)
- ✅ **RULE-003** — `evaluate_credit_card_strategy` — `days_to_statement` modulo yanlış ay uzunluğuyla (kapandı)
- ✅ **RULE-004** — Kart stratejisi `today.day > statement_day` — `statement_day_eff` yerine ham değer (kapandı)
- ✅ **RULE-005** — Kart stratejisi `today.day > 1` koşulu ayın 1'ini yanlış dala atıyor (kapandı)
- ✅ **RULE-006** — Para hesaplarında `float` + `round()` banker's rounding sürüklenmesi (kapandı)
- ✅ **RULE-040** — Modüller arası para tipi tutarsızlığı: Account=Float, Goal=Numeric — köprüde hassasiyet kaybı (kapandı)
- ✅ **FE-002** — Dinamik Tailwind sınıfları prod build'de purge oluyor (renkler kaybolur) — GERÇEK BUG (kapandı)
- ✅ **SEC-001** — Kimlik doğrulama tamamen yok — `get_current_user` ilk kullanıcıyı döndürüyor (kapandı)
- ✅ **DATA-003** — SQLite `PRAGMA foreign_keys=ON` hiçbir yerde ayarlanmıyor — FK/ON DELETE sessizce kapalı (kapandı)

</details>

<!-- OTOMATIK-ONCELIK:BITTI -->

## Sıradaki adımlar (2. tur)
1. **Tekilleştirme + önceliklendirme:** Kategoriler arası çakışan maddeleri (ör. float-para RULE/DATA/BE; hata-yönetimi BE/API/RESIL) birleştir; P0/P1/P2 ata.
2. **P0 canlı bug sprinti:** Yukarıdaki bug listesi — düşük efor, yüksek etki; BUG #NNN konvansiyonuyla düzelt.
3. **Temel altyapı:** pytest'e geçiş + FakeProvider (TEST) → refactor'lar için güvenlik ağı; sonra config (BE-012), Decimal-para (DATA-001), auth iskeleti (SEC-001).
4. **Uygulanan her madde** commit mesajında `[KOD-NNN]` ID ile referanslanır (DOCS-013), backlog'da durum güncellenir.
