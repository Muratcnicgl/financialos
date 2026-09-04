# WAVE-Y LEDGER — yayın hattı (uygulamayı rayına oturtma)

**Hat tanımı:** `masterprompt-wave-y.md` · **Çıpa:** `7486e9c` (4 Eylül 2026)
**Başlangıç ölçümü:** 4 Eylül 2026, 13:37

> Bu defter Wave-Y'nin tek doğruluk kaynağıdır. Her hedef kapanışı kanıtıyla buraya
> yazılır; kanıtı olmayan satır **KANIT YOK** kalır ve hedef açık sayılır.

---

## §0.1 BAŞLANGIÇ ÖLÇÜMÜ (Y8'de aynı komutlar tekrar koşulacak)

| Ölçüm | Değer | Komut |
|---|---|---|
| Yerel HEAD | `fce4753` (çıpadan +5) | `git log -1` |
| **Canlı build damgası** | **`aed4b5fad0e6`** | `curl /api/meta` |
| **Drift** | canlı ≠ yerel — üstelik canlıdaki SHA, geçmiş yeniden yazıldığı için artık **var olmayan** bir commit | — |
| Canlı sağlık | health 200 · ready 200 | `curl` |
| Canlı göç sürümü | `c3d4e5f8a1b2` | sqlite |
| Kullanıcı | 6 | sqlite |
| MCP defteri | **281 satır** (4 Eyl raporunda 255'ti) | `wc -l` |
| Süit | 3.504 passed · 18 skipped | `pytest -q` |
| Coverage | %94,02 (CI'da ≥93 kilitli) | `pytest --cov` |

---

## ✅ Y1 — CANLI SÜRÜM DRİFT'İ SIFIRLANDI (4 Eylül 2026, 13:48)

### Kök neden — ÖLÇÜLDÜ, ve iki tane

**Bu bir ihmal değil, mekanizma eksikliğiydi.** Betanın 24 commit geride kalması
"deploy etmeyi unutmak"tan gelmiyordu; deploy edecek bir adım YOKTU.

1. **`app/version.py:71` — damga süreç başında donuyor.** Sürüm damgası
   `@lru_cache(maxsize=1)` ile tutuluyor; `git rev-parse HEAD` süreç ömrü boyunca bir kez
   okunuyor. Çalışma ağacı güncellense bile süreç eski kodu bellekte taşır. Canlı süreç
   bugün 09:21:35'te başlamış, o an HEAD `aed4b5f`'ti. **`/api/meta` yalan söylemiyordu —
   yalan söyleyen kod değil SÜREÇTİ.**
2. **`deploy/windows/baslat.ps1:34` — çalışan süreci görünce çıkıyor.** Port dinleniyorsa
   *"zaten calisiyor — dokunulmadi"* der. İdempotent olması **doğrudur** (sağlık görevi onu
   10 dakikada bir çağırıyor; ikinci uvicorn portu çakıştırırdı). Ama kimse `-Zorla`
   çağırmadığı için **bir kod güncellemesi canlıya hiç ulaşmıyordu.**

### ⚠️ Y1'İN "DONE" KRİTERİ DEĞİŞTİ — ve neden değiştiği burada yazılı

Masterprompt Y1'de *"deploy **`scripts/deploy.sh` ile** yapıldı (elle değil)"* diyordu.
**Bu kriter bu ortamda karşılanamaz ve karşılanmaya çalışılması zarar verirdi.** Ölçüldü:

```
scripts/deploy.sh:9   COMPOSE="docker compose -f docker-compose.prod.yml --env-file .env.prod"
```

`deploy.sh` **Docker yolu için** yazılmış. Canlı beta bu makinede Docker'sız koşuyor
(uvicorn + Tailscale Funnel, `deploy/windows/baslat.ps1`). Yani raporun
*"deploy.sh koştu mu? KANIT YOK"* satırının dürüst cevabı **"koşamaz"**dır.

Bu, **BUG #326'nın aynı sınıfıdır** (L64): bir adımın başka bir yolda olması, KULLANILAN
yolda olduğu anlamına gelmez. #326'da eksik olan göç adımıydı ve beta 24,5 saat kapalı
kaldı; burada eksik olan güncelleme adımıdır ve beta 24 commit geride kaldı.

**Yeni kriter:** deploy `deploy/windows/guncelle.ps1` ile yapılır.
*(Kriter sessizce değiştirilmedi; değişiklik gerekçesiyle buraya yazıldı — yoksa altı ay
sonra "deploy.sh koştu mu?" sorusu yine cevapsız kalırdı.)*

### Yapılan — `deploy/windows/guncelle.ps1` (BUG #339)

* **Ölçer:** canlı `/api/meta` damgası ↔ yerel HEAD. Eşitse hiçbir şey yapmaz.
* **Kirli ağacı REDDEDER:** kirli kopyadan deploy, hangi kodun canlıda olduğunu
  ölçülemez kılar (damga `+` alır ama `+` neyin eklendiğini söylemez).
* **Tek kaynağı çağırır:** `baslat.ps1 -Zorla`. Yedek + göç + sağlık mantığı
  **kopyalanmadı** — aynı kararı iki yerde tutmak, bir sonraki düzeltmede birini
  güncelleyip diğerini unutmak demektir.
* **KULLANIM-GATE:** sağlık 200 **yetmez** — eski süreç de 200 veriyordu. Betik yeniden
  başlattıktan sonra `/api/meta`yı okur ve damganın hedefe eşitliğini ÖLÇER; eşit
  değilse BAŞARISIZ sayar. Kök neden `@lru_cache` olduğu için kapanma kanıtı **yalnızca
  damganın tazelenmesidir.**

### Kanıt (4 Eylül 2026, 13:47–13:48)

| Adım | Çıktı |
|---|---|
| Deploy öncesi yedek | `data/backups/2026-09-04-134757.db` · **788 KB** · `integrity_check = ok` · 32 tablo · 6 kullanıcı |
| Güncelleme | `[guncelle] canli=aed4b5fad0e6  hedef=97bc72094af2` |
| Yeniden başlatma | `[baslat] zorla yeniden baslatma: PID 5496 durduruluyor` → `AYAKTA (PID 26212)` |
| **Doğrulama** | `[guncelle] TAMAM: canli damga 97bc72094af2 = hedef 97bc72094af2` |
| **Kesinti** | 13:48:06 → 13:48:12 ≈ **6 saniye** |
| Duman (dışarıdan) | funnel `health=200` · `ready=200` · `/api/meta` build `97bc72094af2` · sürüm `0.2.0` |
| `scripts/live_gate.py` | **TÜM ZORUNLU KAPILAR GEÇTİ (23 kontrol)**, çıkış 0 |
| Canlı göç sürümü | `c3d4e5f8a1b2` (kodun head'i ile aynı) |
| `alembic check` | **FAILED** — ve bu BEKLENEN: SQLite'ta belgelenmiş ADR-036 sapması (bkz. `tests/test_fk_sapmasi_kapisi.py`, 5 test geçiyor). Bu satır bir arıza değil, kayda geçmiş bir lehçe farkıdır. |

**KANIT YOK kalan tek alt madde:** kimlikli duman testi (giriş yapıp bir işlem okuma).
`live_gate.py` bunu `--email/--password` ile koşar; asistan kullanıcı parolası
kullanmaz/işlemez. `/api/ready` (DB + şema) ve 23 kimliksiz kontrol geçti; kimlikli
ayak Murat tek komutla koşabilir:
`python scripts/live_gate.py https://<adres> --email <e-posta> --password <parola>`

### Yan bulgu + kapı (aynı turda)

`guncelle.ps1` ilk yazımda **hiç ayrışmadı**. Hata satırı hatanın yeri değildi: PowerShell
5.1 **BOM'suz** dosyayı ANSI (cp1254) sayıyor, Türkçe karakterler dizge sınırını kaydırıyor,
ayrıştırıcı alakasız bir satırda patlıyor. Depodaki diğer üç betikte BOM **vardı** — yani
konvansiyon vardı ama **yazılı değildi**; yazılı olmayan konvansiyon bir sonraki dosyada
tutmaz. `tests/test_ps1_bom_kapisi.py` (2 test, **mutasyon 2/2**: BOM kaldırılınca ikisi de
kırmızı — nedensellik; BOM dururken hata sokulunca yalnız ayrıştırma testi kırmızı — kapsam).

*Kapsam notu: §10 "madem buradayız" yasağı gereği bu kapı ayrı bir iş sayılabilirdi. Y1'in
KURDUĞU yolu sessizce kırabilecek bir tuzak olduğu için içeride tutuldu; benzer bir tuzak
çıkarsa backlog'a yazılacak.*

### Operasyonel not (bir sonraki koşum için)

`powershell -File guncelle.ps1 | tail` **borusu kapanmıyor**: `Start-Process` ile açılan
uvicorn stdout tanıtıcısını miras alıyor, çağıran bekliyor. Betik 9 saniyede bitmişti,
bekleyen boruydu. Çıktıyı dosyaya yönlendir: `> logs/guncelle.out 2>&1`.

---

## Y2 — KESİNTİ KÖRLÜĞÜ ▸ SIRADAKİ
## Y0 — B0 BARINDIRMA KARARI ▸ BEKLİYOR
## Y3 — YAYIN + KAPI 9-12 ▸ BEKLİYOR
## Y4 — GERÇEK KULLANICI SİNYALİ ▸ BEKLİYOR
## Y5 — DEFTER SENKRONU ▸ BEKLİYOR
## Y6 — ADR BORCU ▸ BEKLİYOR

## Y7 — DEPO GÖRÜNÜRLÜĞÜ ▸ KARAR ALINDI, UYGULAMA BEKLİYOR

**Karar (Murat, 4 Eylül):** asıl depo **private kalır**; yanına **üretilmiş bir vitrin
deposu** açılır. Gerekçe: CV'de GitHub ve bu proje anılıyor, projenin görünmemesi amaca
aykırı — ama asıl depoyu açmak, iki hafta içinde **üçüncü** `git-filter-repo` + force-push
demekti (ölçüldü: e-posta 15 dosya · banka adı 96 dosya · gerçek tutar 15 dosya, aynısı
671 commit'lik geçmişte).

**Tasarım kararı — vitrin ELLE YAZILMAZ, ÜRETİLİR.** Elle yazılan vitrin bu deponun
kayıtlı hastalığına yakalanır (BUG #310: belgenin işaret ettiği şey diskte yok). Üretici
gerçek depoyu ölçer; sayı koşumdan gelir.

**Tasarım kararı — ALLOWLIST, denylist değil.** Üretici bir private→public boru hattıdır;
denylist yalnız *düşünülen* sızıntıyı yakalar. Sızıntı düşünülmeyenden gelir: commit
mesajları, mutlak dosya yolları (`C:\Users\<ad>\...`), ADR gövdelerindeki gerçek rakamlar,
`uygulanan-fixler.md`'nin 1.070 satırındaki bakiye örnekleri, hata çıktılarına gömülü
fixture verisi. Bu yüzden üretici **yalnızca açıkça izin verilmiş alanları** yayar (test
sayısı, coverage yüzdesi, kapı adı + tavanı, ADR başlığı, mutasyon skoru); listede olmayan
her şey **varsayılan olarak düşer**.

**Kapı üretimde değil, PUSH'tan hemen önce koşar:** üretilen dosyalar diskteyken taranır,
temizse yayınlanır. Mutasyon: vitrine bilerek gerçek bir rakam enjekte edilir → kapı
kırmızı vermeli.

## Y8 — KAPANIŞ KAPISI ▸ BEKLİYOR
