# ADR-061 — Milestone/tag disiplini bırakıldı; iş faz + BUG numarasıyla yürür

- **Durum:** Kabul edildi (karar 18 Temmuz 2026'da fiilen alındı · 7 Ağustos 2026'da
  `PROJE.md`'ye yazıldı · **4 Eylül 2026'da ADR'ye geçti**, Wave-Y / Y6)
- **İlgili:** ADR-058 (kapılar), Wave-Y masterprompt §Y6

## Bağlam

Proje 4 Mayıs – 18 Temmuz 2026 arasında **milestone/tag** disipliniyle yürüdü: her iş
paketi `milestone-NN` etiketiyle işaretlendi, `milestone-log.md`'ye yazıldı.

**Ölçüm (7 Ağustos 2026):**

| Gözlem | Değer |
|---|---|
| Toplam tag | 98 (+ sonradan `pre-kapali-beta`, `pre-wave-8` gibi geri-dönüş etiketleri) |
| **En son milestone tag'inin tarihi** | **18 Temmuz 2026** |
| O tarihten sonraki commit | 103 — **hepsi tag'siz** |
| `milestone-93` numarası | **iki ayrı işe** verilmiş (`wave7-kapanis` + `prod-docker-imaj`) |
| Hiç kullanılmayan numaralar | M44-M60, M97-M98, M101 |

Yani sistem **18 Temmuz'da fiilen ölmüştü** ve bunu kimse yazmamıştı. Ölü bir
numaralandırma sistemi zararsız değildir: `milestone-log.md` "güncel durum" gibi okunmaya
devam eder ve okuyan kişi 18 Temmuz'daki dünyayı bugünün dünyası sanır (BUG #310 sınıfı).

## Karar

1. **Milestone/tag disiplini BIRAKILDI.** Yeni iş paketleri tag almaz.
2. **İş şu üç eksende yürür:**
   * **Faz kodu** — publish yolunda `P0-P9`, kapalı betada `B0-B6`, koç hattında `K0-K7`,
     yayın hattında `Y0-Y8`.
   * **Denetim/backlog kodu** — `RULE-`, `SEC-`, `DATA-`, `FEAT-`, `BE-`, `LLM-`, `OBS-`…
   * **BUG numarası** — tek artan sayaç, tek resmî envanter `uygulanan-fixler.md`.
3. **`milestone-log.md` TARİHSEL ARŞİVDİR.** Güncel iş oraya yazılmaz. Dosya bu ADR'ye
   atıfla o şekilde etiketlenir.
4. **Geri-dönüş etiketleri (`pre-*`) devam eder** — onlar milestone değil, rollback
   noktasıdır ve farklı bir işe yarar.

## Alternatifler

* **Milestone sistemini canlandırmak:** iki ayrı işe aynı numaranın verilmiş olması ve 17
  numaranın hiç kullanılmaması, sistemin **elle tutulduğunu ve tutulmadığında sessizce
  bozulduğunu** gösteriyor. Canlandırmak, aynı elle-tutma borcunu geri getirirdi.
* **Otomatik tag üretmek (her sürüme):** sürüm damgası zaten `git HEAD`'den türetiliyor
  (BUG #294); ikinci bir kimlik sistemi kurmak, iki kaynağın ayrışması riskini getirir.
* **Hiçbir şey yazmamak (bugüne kadarki durum):** karar `PROJE.md`'de yazılıydı ama ADR'de
  değildi. Wave-Y'nin ölçtüğü boşluk buydu: **çıpadan bu yana 60 BUG kapandı, 7 kapı
  kuruldu, yeni bir hat açıldı, depo private yapıldı, geçmiş ikinci kez yeniden yazıldı —
  ve sıfır yeni ADR yazıldı.** Kararlar commit mesajlarında kalıyordu.

## Sonuç

Bu ADR yeni bir şey kararlaştırmıyor; **fiilen alınmış ama yalnız bir brifing dosyasında
duran bir kararı** mimari kayda geçiriyor. Bir kararın nerede yazılı olduğu, ne kadar
yaşayacağını belirler: `PROJE.md` her tur yeniden yazılır, ADR'ler birikir.
