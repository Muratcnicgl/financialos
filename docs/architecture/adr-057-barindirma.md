# ADR-057 — Kapalı beta barındırma kararı (B0)

**Durum:** KABUL EDİLDİ · **Tarih:** 4 Eylül 2026 · **Hat:** Wave-Y / Y0
**Karar veren:** ölçüt uygulandı (Wave-Y §0.6: *"Murat'a sorma. Karar gerekiyorsa seç,
uygula, sonucu bildir"*). Murat **veto** hakkını saklı tutar.

> **Bu ADR bir yöntem değişikliği de kaydeder.** `masterprompt-kapali-beta.md` §5 şöyle
> bitiyordu: *"Kararı Murat verir… asistan araci üç seçeneği ölçüp sunar, **seçmez**."*
> Bu kural **24 gün boyunca kararın açık kalmasına** sebep oldu: her tur seçenekler
> yeniden sunuldu, karar hiç verilmedi. Wave-Y bunu bilinçli olarak tersine çevirdi.
> Sunmak, karar vermek değildir.

---

## Bağlam

Kapalı beta 11 Ağustos'tan beri Murat'ın kendi Windows makinesinde, **Tailscale Funnel**
üzerinden `financialos.<tailnet>.ts.net` adresinde yayında. B0 ("hangi barındırma?")
11 Ağustos'ta soruldu ve **4 Eylül'e kadar açık kaldı**; B4 (yayın) ve kapı 9-12 ona
bağlı olduğu için kapalı beta bitirilemedi.

### Karar anına gelen YENİ ölçümler (11 Ağustos'taki nottan sonra)

| Ölçüm | Değer | Karara etkisi |
|---|---|---|
| **Kaçırılan iş telafisi** | `kacirilan_isleri_telafi_et()` **5 planlı işin 5'ini** kapsıyor (BUG #302, 12 Ağu) | B0 notunun A'ya yazdığı **2. bedel maddesi kapandı**: makine kapalıyken atlanan cron'lar açılışta telafi ediliyor. Not *"bu iddia B4'te ölçülecek"* diyordu — bugün ölçüldü. |
| **DNS arızası (BUG #303)** | 4 Eylül: Cloudflare **6/6 çözdü**, Google **6/6 çözdü**, `/api/health` ad üzerinden **200** | *"Davetliler giremiyor"* bugün **yanlış**. Alan adı alma gerekçesi **aciliyetini yitirdi**; kalıcılık ve bağımsızlık gerekçesi duruyor. |
| **Beta kullanımı** | 13 Ağustos'tan beri sistemdeki tek etkinlik kurucununki (5 davetliden 2'si hiç girmedi) | 7/24 çalışmanın **bugünkü** değeri düşük; gerçek kullanıcı sinyali yokken aylık gider bağlamak erken. |
| **Y2 kararı (a)** | Makine kapalı = **kesinti**, ve artık **alarm çalar** | A'nın 1. bedeli (PC kapalıyken kapalı) artık **sessiz değil**: her gece ölçülüyor ve raporlanıyor. Bedel görünür hâle geldiği için kabul edilebilir. |

### Bugün ölçülen fiyatlar

| Seçenek | Bedel (bugün) | Kalıcı URL | 7/24 | Kurulum |
|---|---|---|---|---|
| **A — kendi makine + Cloudflare Tunnel + alan adı** | alan adı ~**10,44 $/yıl** (Cloudflare Registrar, maliyetine; ≈29 TL/ay) | ✅ | ❌ | En hızlı — `cloudflared` kurulumu asistanda |
| **B — Hetzner CX22 + alan adı** | **€3,79/ay** (≈€45/yıl) + alan adı | ✅ | ✅ | Orta; `deploy.sh` Docker yolu hazır |
| **C — Oracle Always Free + alan adı** | alan adı | ✅ | ✅ | **Kapasite kuyruğu — süresi belirsiz**, ölçülmedi (Murat'ın beyanı) |
| **D — ücretsiz alan adı (eu.org) + A** | **0** | ✅ | ❌ | **Elle onay: günler–haftalar** |

*(Hetzner 15 Haziran 2026'da bir fiyat düzenlemesi yaptı; CX22 için bugün okunan değer
€3,79/ay. Alan adı fiyatı 11 Ağustos ölçümünden; tescil fiyatları yılda bir değişir.)*

---

## Karar

**A seçildi: kendi makine + Cloudflare Tunnel + SATIN ALINMIŞ alan adı.**

### Ölçüt uygulaması (Wave-Y beraberlik kuralı: *en ucuz + geri dönülebilir olan kazanır*)

1. **Kalıcı URL zorunlu.** Geçici tünel adresleri her yeniden başlatmada değişir ve
   telefona kurulmuş PWA'yı kırar. Dört seçeneğin dördü de bunu sağlıyor → ayırt etmiyor.
2. **En ucuz.** D (0 TL) en ucuz görünüyor **ama alınabilir değil**: eu.org onayı elle
   yapılıyor ve günler–haftalar sürüyor. **B0 zaten 24 gündür bekliyor; bir kararı yeni
   bir kuyrukla değiştirmek karar vermek değildir.** Alınabilir olanların en ucuzu **A**
   (10,44 $/yıl), B'nin **beşte biri**.
3. **Geri dönülebilirlik.** A→B geçişi davetliler açısından **görünmezdir**: alan adı
   Murat'ın; A'da Cloudflare Tunnel onu kendi makinesine, B'de aynı ad VPS'in IP'sine
   yönelir. Telefondaki PWA aynı origin'i kullanır, **kısayol bozulmaz**. Yani A, B'yi
   dışlamıyor — B'ye giden yolu **ucuzlatıyor**.
4. **7/24 farkı bugün ne kadar önemli?** Ölçüldü: 23 gündür dışarıdan hiç kullanım yok.
   Kullanıcısı olmayan bir servise aylık gider bağlamak, ölçülmemiş bir ihtiyaca ödeme
   yapmaktır. Ve A'nın kesintisi artık **sessiz değil** (Y2) — bedeli her gün raporlanıyor.

### C neden elendi
Kapasite kuyruğu **ölçülmedi** ve süresi bilinmiyor. Ölçülmemiş bir beklentiye karar
bağlamak, kararı ertelemenin başka adıdır (L45: bilinmeyen, "yakında" değildir).

### B'ye geçiş TETİKLEYİCİLERİ (şimdiden yazılı — "sonra bakarız" değil)

Aşağıdakilerden **biri** gerçekleşirse B'ye geçilir; karar yeniden tartışılmaz:

* **P8 (açık beta) açılıyorsa.** Kapalı betada makine-kapalı kabul edilebilir; açık betada
  değildir (`masterprompt-kapali-beta.md` §5 md. 3).
* **Erişilebilirlik raporu 7 günlük pencerede %90'ın altına inerse** ve o kesintilerin
  sebebi makinenin kapalı olmasıysa (`python -m scripts.erisilebilirlik_raporu`).
* **Kurucu dışında düzenli kullanan en az 2 kullanıcı** varsa (Y4'ün ölçtüğü tablo).

---

## Sonuç ve tek insan adımı

Murat'a **seçenek listesi gitmez**; tek talimat gider:

> **Cloudflare Registrar'dan bir alan adı al** (`domains.cloudflare.com`).
> Yıllık ~**10,44 $**, maliyetine satılıyor, yenilemede zam yok, WHOIS gizliliği ücretsiz.
> Adı sen seç (ör. `financialos.app` yerine daha ucuz bir uzantı da olur — fiyat satın
> alma ekranında görünür). Aldıktan sonra alan adını söylemen yeterli.

Gerisi asistanda: `cloudflared` kurulumu, tünelin alan adına bağlanması, TLS, `deploy.sh`/
`live_gate.py` yeni ortamda koşumu, kapı 9-12'nin kanıtlanması (Y3).

**Bu harcama bu fazın tek zorunlu masrafıdır** ve ADR-057 ile gerekçesi yazılıdır.

---

## Alternatifler ve neden seçilmediler

* **B (VPS) şimdi:** 7/24 verir ama aylık gider getirir; ölçülen kullanım sıfırken bu,
  ihtiyacı kanıtlanmamış bir abonelik olur. A→B görünmez olduğu için ertelemenin bedeli yok.
* **C (Oracle):** ölçülmemiş bir kuyruk. Karar, beklemeye eşit olur.
* **D (eu.org):** gerçekten 0 TL, ama teslim süresi belirsiz. 24 gün bekleyen bir maddeyi
  yeni bir belirsiz beklemeye bağlamak, kararın kendisini iptal eder. *(Murat isterse eu.org
  başvurusu paralel açılabilir; gelirse alan adı yenilenmez — bu bir iptal değil, ucuzlatma
  olur.)*
* **Alan adı almamak (mevcut `.ts.net` ile devam):** BUG #303 bugün geçerli değil ama
  arızanın **kendisi ölçüldü** ve tekrar edebilir; ayrıca `.ts.net` adresi Tailscale'e
  bağımlıdır, B'ye geçişte **URL değişir ve PWA kırılır**. Alan adı, geri dönülebilirliğin
  ön koşuludur.
