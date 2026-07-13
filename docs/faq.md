# SSS (FAQ)

## Genel
**FinancialOS nedir?** Kişisel finansal işletim sistemi — nakit akışı, borç stratejisi,
hedefler, yapay zekâ finans koçu. Self-host (verin kendi sunucunda).

**Neden self-host?** Finansal veri en hassas kategoridir. Self-host = veri sizin
kontrolünüzde, üçüncü bulut hizmetine gitmez (KVKK-dostu).

## KVKK / Gizlilik
**Verilerim nerede?** Kendi sunucunuzdaki SQLite dosyasında. Şifreniz bcrypt ile
geri-döndürülemez hash'lenir.

**Yapay zekâ koçu verimi dışarı gönderir mi?** Koçu kullandığınızda cockpit özeti
seçtiğiniz LLM sağlayıcısına (örn. Gemini) gider — bu yurtdışı-aktarım olabilir.
Alternatif: **yerel Ollama** modeli (offline, veri makineden çıkmaz — `LLM_PROVIDER=ollama`).

**Verimi nasıl silerim/indiririm?** `DELETE /api/users/me` (KVKK silme, cascade) ·
`GET /api/users/me/export` (JSON taşınabilirlik). Detay: `docs/legal/kvkk-consent-v1.md`.

## TR Bağlamı
**Enflasyon?** FEAT-024 reel (enflasyon-düzeltilmiş) net değer gösterir — TR yüksek-enflasyon
ortamında borçlu için enflasyon borcu eritir.

**TEFAS fonu / döviz / altın?** Fiyat otomasyonu: TEFAS (pytefas cron). Döviz/altın TCMB EVDS
(API key). BIST hisse (yfinance/İş Yatırım). Bkz. ADR-029/031.

## Teknik
**Auth zorunlu mu?** Hayır — tek-kullanıcı lokal modda (`AUTH_ENABLED` kapalı) auth'suz
çalışır. Multi-user için `AUTH_ENABLED=1` + `SECRET_KEY`.

**Production?** `docs/deployment/README.md` — Docker Compose (Caddy otomatik HTTPS) veya systemd.
