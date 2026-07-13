# Bug Archive Kanıtlama Turu (M25, 14 Tem 2026)

Wave-2 M6 dersi: MASTER-FIX-LIST bayat-açık çıkmıştı (16 P1 zaten kapalıydı, R3 ile
yakalandı). Aynı R3 disiplini Bug Archive'a: her "KAPANDI" iddiası disk-kanıtına
(commit / test / fixler.md / kod docstring) karşı doğrulandı.

## Yöntem (R3)
MCP Bug Archive'ı tek tek okumak yerine **disk kanıt indeksi** çıkarıldı — daha güvenilir
(R3: disk > memory). 4 kaynak taranıp `BUG #NNN` referansları çıkarıldı:
- git commit mesajları (`git log`) → 98 bug
- `docs/kalite-seruveni/uygulanan-fixler.md` → 57 bug
- `tests/**/*.py` → 52 bug
- `app/**/*.py` docstring (GUNCELLEMELER konvansiyonu) → 120 bug

**Toplam benzersiz: 141 bug (#1-#157).**

## Kategoriler

### ✅ KANITLI KAPANDI (44) — fixler.md + (test veya commit)
En güçlü kanıt (çoklu kaynak):
`#59,61,62,64,66,67,68,70,73,77-85,102,103,121-129,131-145,156,157`
Bunlar Kalite Serüveni + Wave-3 disiplinli dönemin bug'ları — fix + test + ledger üçlüsü.

### 🧪 TEST-KORUMALI (52) — dedicated test var (regresyon ağı)
`#19,27,40,42,43,49,58,67,68,70,73,78,79,81,84-96,99-106,109,110,113-116,119-124,127,141,142,154,157`
Bu bug'lar bir testle kilitli → yeniden açılırsa süit kırmızı verir.

### 📋 İDDİA / belge-kapalı (51) — commit/docstring var, dedicated test + fixler.md YOK
`#1,6,7,9,11,12,13,16-18,20-23,25,26,28-36,39,41,44-47,50-55,82,97,98,107,108,111,112,117,118,148-151,153,155`
Çoğu **Wave-1/2 erken bug'ları** (#1-55) — "BUG #NNN fix:" docstring konvansiyonu +
commit mesajı ile belgeli, ama test-per-bug + fixler.md ledger disiplini kurulmadan önce
kapatıldı. **Baseless değil** (kod docstring + commit kanıtı var) ama test-kanıtı yok →
katı ayrımda "iddia".

### 🔴 YENİDEN AÇILDI (0)
Bu kanıt-indeksi taramasında "KAPANDI iddia edilmiş ama kod hâlâ bug'ı içeriyor" bir vaka
**tespit edilmedi.** NOT (dürüst sınır): 141 bug'ın her biri için derin per-kod re-check
yapılMADI (pratik değil); ama en kritik 52'si test-korumalı (regresyon otomatik yakalar).
Wave-3 boyunca yapılan R3 doğrulamalarında (W3-003/024/026/028/029/033) "zaten-fix" çıkanlar
kaydedildi — hiçbiri "yeniden açık" değildi.

## Sonuç
- **Kanıt sağlamlığı dağılımı:** 44 çok-kaynak kanıtlı + 52 test-korumalı (örtüşür) + 51 belge-kapalı.
- **En büyük belirsizlik:** erken #1-55 (test yok) — ama bunlar çoğunlukla Wave-1/2 UX/koç
  davranış bug'ları, mevcut davranış sözleşmesi testleri (test_coach_*) dolaylı kapsar.
- **Öneri (otonom milestone adayı):** İDDİA listesindeki hâlâ-geçerli olanlar için
  karakterizasyon testi (yeniden-açılmayı önler) → M27 (coverage) turunda ele alınabilir.
- **Yeniden-açık bug YOK** → otonom milestone gerekmedi.
