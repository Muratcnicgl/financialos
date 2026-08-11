# MAIN GOAL — KAPALI BETA

**Hedef:** FinancialOS, Murat'ın adını tek tek verdiği 3-10 kişinin telefonunda ve bilgisayarında
çalışsın; bu kişilerin yaşadığı her sorun teşhis edilebilir bir kayıt olarak Murat'a dönsün.

**Bu faz geliştirme fazı değildir.** Ölçüt "kaç özellik" değil, **kaç gerçek kullanıcı, kaç gün,
kaç geri bildirim**.

**Yöneten belgeler:**
- `docs/kalite-seruveni/masterprompt-kapali-beta.md` (faz sınırları, gerekçe, bitiş ölçütü —
  **§0 premis düzeltmesiyle başlar, önce o okunur**)
- `docs/kalite-seruveni/charter-kapali-beta.md` (B0-B6 iş emri, kapı tablosu)
- Taban: `ara-durum-raporu-2026-08-11.md` (`47c8ec7`) + `master-durum-raporu-2026-08-06.md`
- Hat: `masterprompt-publish.md` P6 + P7. **Yeni faz/Wave üretilmez.**

## ⚠️ PREMİS DÜZELTMESİ (11 Ağu, ölçüldü — işe başlamadan oku)

İlk taslak B1/B2'yi "diskte yok, sıfırdan yazılacak" diye tanımlıyordu. **Ölçüm çürüttü:**

| Sanılan | Gerçek |
|---|---|
| Geri bildirim sistemi yok | **VAR** — `Feedback` modeli + migration + `app/routers/feedback.py` + `FeedbackWidget` (App.jsx'te kalıcı) + 6 test |
| Operatör okuma yüzeyi yok | **VAR** — `scripts/beta_triage.py` (BUG #209), e-posta maskeli, hatalar yan yana |
| Allowlist yok | **VAR ve fail-closed** — `app/beta_access.py`; klasik kayıt **ve** OAuth (BUG #226/D05) |
| Yedek/geri yükleme provası yok | **VAR** — `backup.py`/`restore.py` + `tests/test_backup_restore_drill.py`; eksik olan **canlı** prova |
| Sürüm damgası yok | **VAR** — `app/version.py`, `/api/meta`, Login ekranı, compose enjeksiyonu, testli |
| Korelasyon kimliği yok | **DOĞRU** — bu fazın tek sıfırdan işi |

**Sonuç:** B1/B2 artık "sıfırdan yaz" değil **"ÖLÇ → kapsam boşluğunu kapat → kapıyı kilitle"**.
**Var olan çalışan modülü yeniden yazmak YASAK** (L46: kopya değil içe aktarma).
**Yeni ders L52:** *delta raporda geçmemek, diskte olmamak değildir; envanter sorusu envantere
sorulur.*

**Bloklar:** B0 barındırma kararı (insan-kapısı) · B1 davet kapısının **kapsamı** · B2 geri
bildirimin **teşhis alanları** · B3 **korelasyon kimliği** (+ damganın canlı ayağı) · B4 yayın
(deploy/HTTPS/PWA/SMTP/**canlı yedek provası**) · B5 davetli paketi (karşılama + kurulum;
KVKK/şartlar/silme var) · B6 haftalık beta ritmi (`beta_triage.py` üstüne).

**KAPSAM DIŞI — açma:** yeni özellik · **var olan çalışan yapıyı yeniden yazmak** · backlog mercek
turu (251 açık madde) · i18n · çok para birimi · açık beta (P8) · Play Store TWA (P9) · LLM-002
caching · geriye dönük BUG ledger toplama. Tek istisna: davetliden gelen **teşhis edilmiş**
defektin normal BUG akışıyla düzeltilmesi.

**Murat'ın elle yapacağı TEK liste (KURAL 3 — başkasını delege etme):** alan adı satın alma · DNS
kaydı · canlı sırların girilmesi · davetli e-posta listesi · canlı DB'de yıkıcı işlem onayı.

**Ritim (istisnasız):** **ÖLÇÜM** → bulgu → davranış seviyesinde KIRMIZI test → düzelt → mutasyon
kontrolü (sözdiziminden gelen kırmızı sahtedir, L40) → sınıf taraması (L11) → tam süit → ayrı
commit + ledger satırı. **Ölçmeden kod yazmak yasak.**

**Numaralar:** BUG **#279**'dan başlar. Sıradaki ADR **054** (dizinde 56 dosya; yazmadan önce
doğrula). Rollback etiketi `pre-kapali-beta` işe başlamadan atılır. Alembic taban head:
`c5d6e7f8a9b0`. Test tabanı: 2969 backend / 175 vitest / 6 e2e.

**Kapı ilkesi:** bu fazda yazılan her kapı **taradığı yüzeyi sayar** ve taban altına düşerse
kırmızıya döner. Kapsamsız kapı ölü kapıdır (L11/H25) — bu projede en az dört kapı böyle ölü
bulundu. Yanlış-pozitif çıktığında kapıyı gevşetme, **kesinleştir** (L51).

**Sessizlik başarı değildir (L47):** geri bildirim gelmiyorsa ayrımı kullanım sayısıyla yap
(kullanıcı başına gerçek işlem kaydı + oturum günü). Kullanım düşükse sorun geri bildirimde değil,
üründe ya da davettedir.

**İlk üç adım:**
1. `pre-kapali-beta` etiketi.
2. **B0:** üç barındırma seçeneğini bugünkü gerçek fiyat/adımla ölç (kaynak göstererek,
   `research-log.md`'ye yaz) + A seçeneğinin scheduler bedelini **ölç**; tek mesajlık karar notu
   hazırla, aynı mesajda davetli e-posta listesini ve alan adı tercihini iste. Fiyat araştırması
   senin işin, seçim Murat'ın.
3. Karar beklerken **B1 + B2 + B3** yürütülebilir — hiçbiri canlı ortama bağlı değil. Her biri
   ÖLÇÜM adımıyla başlar.

**Faz biter ki P8 konuşulsun — üçü birden:** (1) en az 3 davetli × en az 14 gün gerçek kullanım
(sayıyla), (2) her geri bildirim maddesi ya BUG'a dönmüş ya gerekçeli reddedilmiş — işlenmemiş
madde yok (`beta_triage.py --tumu` çıktısı), (3) **canlı** yedekten geri yükleme provası en az bir
kez koşulmuş (yerel otomatik prova yerine geçmez).

**Not:** coverage %93 rakamı 6 Ağustos ölçümüdür; 11 Ağustos'ta yeniden ölçülmedi (KANIT YOK). Bu
turda `pytest --cov` ile ölçülüp kayda geçirilecek.
