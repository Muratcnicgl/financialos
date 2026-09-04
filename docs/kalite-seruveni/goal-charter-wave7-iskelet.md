# Goal Charter — WAVE-7 İSKELETİ (Murat'a ürün-DNA soruları)

> ## ℹ️ 5 Eylül 2026 DENETİMİ — GİRİŞ DURUMU SAYILARI ARTIK YANLIŞ
>
> Aşağıda *"1235 test · coverage %92 · tek user id=1"* yazıyor. **Bugün ölçülen:
> 3.527 test (+18 skipped, 5 Eyl gecesi) · coverage %94,02 (**4 Eyl ölçümü** — bu gece
> yeniden ölçülmedi) · CI eşiği `--cov-fail-under=93` · beş kullanıcı
> (kurucu profili u5, u1 DEĞİL).** Yani bu belge bir plan olarak değil, 18 Temmuz
> 2026'nın fotoğrafı olarak okunmalı.
>
> Belgedeki *"4 kapsam-dışı blok Murat'ın kararını bekliyor"* çerçevesi de aşıldı:
> Wave-Y §0.6 kararı tersine çevirdi (*"karar gerekiyorsa seç, uygula, bildir;
> Murat veto eder"*) — gerekçesi `docs/architecture/adr-057-barindirma.md` başında
> yazılı: eski kural kararın **24 gün açık kalmasına** sebep olmuştu.
> Aktif hatlar: `masterprompt-koc.md` · `wave-y-ledger.md`.

**Durum:** 🔲 TASLAK — Wave-6 kapanışında (M91) oluşturuldu. **Henüz aktif goal DEĞİL.**
**Tarih:** 2026-07-18 · **Öncül:** Wave-6 İÇ SAĞLAMLAŞTIRMA (M82-M91) TAMAM.
**Giriş durumu:** 1235 test · coverage %92 · auth ON · tek user id=1 · flaky yok.

> Wave-6 iç kaliteyi (RULE motoru, backlog/denetim doğrulama, coverage/mutasyon, ADR) sağlamlaştırdı. Wave-7 YÖNÜ
> artık Murat'ın ürün-DNA kararına bağlı — aşağıdaki 4 kapsam-dışı blok "aç/açma" kararı bekliyor.

## 🎯 MURAT'A ÜRÜN-DNA SORULARI (Wave-7 yönünü bunlar belirler)

Wave-4/5/6 boyunca **KAPSAM DIŞI** tutulan 4 büyük blok. Her biri ayrı, bilinçli bir "aç" kararı gerektiriyor:

1. **VPS / canlı-deploy?** Docker Compose + Caddy M80'de statik-doğrulandı ama canlı hiç koşulmadı (docker CLI dev'de yok).
   - *Aç dersen:* bir VPS'e (öğrenci-bütçe) gerçek `docker compose up` + Caddy TLS + canlı smoke + backup daemon.
   - *Soru:* VPS'in var mı / bütçen? Yoksa Wave-7 yine iç-kalite mi?
2. **PostgreSQL + RLS?** Şu an SQLite (tek-dosya, KVKK-dostu). Aile/multi-user gerçekten kullanılacaksa Postgres+RLS.
   - *Bağlı borç:* goals.user_id NOT NULL sıkılaştırma (M75'te SQLite batch-recreate riski nedeniyle ertelendi) Postgres'te kolay.
   - *Soru:* Aile hesabını gerçekten kullanacak biri var mı? Yoksa SQLite yeterli (transactions=0 hâlâ geçerli olabilir).
3. **Kripto (Numeric 28,8 + CoinGecko)?** ADR-031 kripto'yu Wave-4'e ertelemişti (satoshi hassasiyeti + regülasyon).
   - *Soru:* Portföyünde kripto var mı / izlemek istiyor musun? Yoksa TL+fon+BIST yeterli.
4. **Mobil (PWA → RN+Expo)?** ADR-009/032 (032 hâlâ TASLAK). MOB backlog'da 12 madde PWA/RN altyapısı bekliyor.
   - *Soru:* Telefondan mı kullanacaksın (PWA hızlı kazanım) yoksa masaüstü yeterli mi?

## Wave-6'nın bıraktığı İÇ-KALİTE girdileri (kapsam-dışı açılmasa da yapılabilir)

- **SBN-001 (CANLI BUG, M86):** `backfill_net_worth._balance_at` hesap-tipsiz undo → kredi/kart geçmiş net-değeri
  yanlış. Script M73'te koşuldu → geçmiş snapshot'larda latent hata. **Düzelt + geçmiş snapshot'ları yeniden-üret.**
- **273 hâlâ-açık backlog maddesi (M85):** çoğu mimari refactor (coach.py 2641 satır god-module bölme, service/repo
  katmanı, config merkez) + altyapı (OTel/Prometheus/Sentry, lint/mypy/gitleaks, CHECK-constraint) + UX borcu (35 UX açık).
- **UX katmanı (M85 en ham boyut):** modal a11y (role/Escape/focus-trap), aria-label, 44px, açık-tema renk tutarlılığı.
- **DevOps hattı:** ruff/mypy/gitleaks/pip-audit/cov-fail-under CI kapıları (DEVOPS-002/007/012/013).
- **Mutasyon testi genişletme (M88 önerisi):** coach.py'nin dallı yardımcılarında geniş mutmut turu.

## KAPSAM DIŞI hatırlatma
Yukarıdaki 4 blok (VPS/PostgreSQL/kripto/mobil) Murat AÇIK karar vermeden AÇILMAZ (Wave-4/5/6 ÜRÜN-DNA sürekliliği).

## Wave-7 başlarken (M-ilk)
1. Murat'ın 4 soruya cevabıyla bu iskeleti tam charter'a çevir (yön + kapsam).
2. `git tag pre-wave-7`.
3. Milestone-log Wave-7 bölümü.
