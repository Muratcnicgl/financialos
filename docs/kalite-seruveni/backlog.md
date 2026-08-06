# FinancialOS — Improvement Backlog (Kalite Serüveni)

**Başlangıç:** 6 Temmuz 2026 · **Durum:** 1. tur tamamlandı — **521 kanıta dayalı madde / 18 kategori**.

> **Düzeltme (7 Ağu 2026):** bu dosya yıllardır "520" diyordu; `sections/` altındaki gerçek madde
> sayısı **521**'dir (FEAT 40 değil **41**). Ölçüm: her boyut dosyasında `### [KOD-NNN]` blok sayımı.
> **Güncel durum dağılımı (6 Ağu 2026 ölçümü):** 145 KAPALI · 272 AÇIK · 79 KISMEN · 25 DURUMSUZ.
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

## Öne çıkan canlı bug'lar (öncelikli düzeltme)
- **RULE-001** — `str(acc.account_type)` enum'da `"AccountType.cash"` döner → `account_type` kriterli GoalRule hiçbir işlemi yakalamıyor (sessiz ölü kural). Tek satır fix.
- **RULE-002/003/004/005** — kart asgari ödeme sabitleniyor + kesim günü modulo / `statement_day_eff` / ayın-1'i dal hataları (yanlış kart stratejisi mesajı).
- **RULE-006/040** — para `float` + banker's rounding → net_deger/progress/baseline kuruş sürüklenmesi.
- **FE-002** — dinamik Tailwind renkleri prod build'de purge oluyor (görünmez renk bug'ı).
- **FE-026** — hesap adı `.ad` vs `.name` tutarsızlığı (latent kırılma).
- **BE-009 / API-004 / RESIL-016** — `/api/coach/chat` tüm hataları HTTP 200 ile gizliyor.
- **SEC-001** — auth tamamen yok; `get_current_user` ilk kullanıcıyı döndürüyor (mobile/multi-user öncesi kritik).
- **DATA-003** — SQLite FK pragma kapalı; `ondelete` tanımları hiç çalışmıyor.

## Sıradaki adımlar (2. tur)
1. **Tekilleştirme + önceliklendirme:** Kategoriler arası çakışan maddeleri (ör. float-para RULE/DATA/BE; hata-yönetimi BE/API/RESIL) birleştir; P0/P1/P2 ata.
2. **P0 canlı bug sprinti:** Yukarıdaki bug listesi — düşük efor, yüksek etki; BUG #NNN konvansiyonuyla düzelt.
3. **Temel altyapı:** pytest'e geçiş + FakeProvider (TEST) → refactor'lar için güvenlik ağı; sonra config (BE-012), Decimal-para (DATA-001), auth iskeleti (SEC-001).
4. **Uygulanan her madde** commit mesajında `[KOD-NNN]` ID ile referanslanır (DOCS-013), backlog'da durum güncellenir.
