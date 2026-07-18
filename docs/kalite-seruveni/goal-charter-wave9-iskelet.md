# Goal Charter — WAVE-9 İSKELETİ (POST-DEPLOY GERÇEK-KULLANIM UX) — Murat kararı bekliyor

**Durum:** 🔲 TASLAK — Wave-8 Blok D (statik kapanış-hazırlığı) sırasında oluşturuldu. **Henüz aktif goal DEĞİL.**
**Tarih:** 2026-07-18 · **Öncül:** Wave-8 DEPLOY+PWA — statik tamam (Blok A + C), **canlı-deploy (Blok B) Murat Oracle VM'ini bekliyor.**
**Giriş durumu:** 1247 test / 5 skip · coverage %92 · hibrit DB · RLS · BIST+fon otomasyonu · PWA kodu hazır (canlı-gate deploy sonrası).

> ⚠️ **KRİTİK ÖN-KOŞUL:** Wave-9 **canlı deploy TAMAMLANMADAN başlamaz.** Bu wave'in tüm tezi "gerçek kullanımda ne
> acıtıyor" — o veri ancak Murat sistemi canlı sunucuda + telefondan günlük kullanınca doğar. Wave-8 Blok B (MB1/MB2)
> + KULLANIM-GATE'ler yeşil olmadan Wave-9 önceliklendirmesi spekülasyon olur (KURAL 12: kanıtsız iş yasak).

## 🎯 MURAT'A KARAR SORULARI (Wave-9 ön-koşulları — deploy sonrası)
1. **Canlı kullanımda EN ÇOK ne acıttı?** (2-4 hafta gerçek kullanım sonrası somut sürtünme listesi — bu wave'in girdisi.)
2. **Mobil PWA yeterli mi, eksik ne?** (Lighthouse/installable/offline canlı-gate sonucu + telefon deneyimi.)
3. **273 UX borcundan hangileri gerçekten görünür?** (backlog teorik; canlı kullanım gerçek önceliği belirler.)
4. **Yeni özellik mi, cila mı?** (Wave-9 = mevcut akışları pürüzsüzleştirme mi, yeni yetenek mi?)

## BLOK 0 — DEPLOY DOĞRULAMA (Wave-8'den devralınan, ön-koşul)
Wave-8 Blok B/D canlı-gate'leri Wave-9 başında YEŞİL olmalı:
- Canlı HTTPS + login + gerçek işlem → cockpit (KULLANIM-GATE) · 24s cron fiyat yazdı · Lighthouse PWA geçti · mobil uçtan uca.
- Değilse: Wave-9 başlamaz, Wave-8 kapanır önce (`milestone-101-wave8-kapanis` + GOAL TAMAM W8).

## BLOK A — GERÇEK-KULLANIM SÜRTÜNME TRİYAJI (kanıt-temelli)
Gerekçe: 273 UX borcu (backlog) TEORİK önceliklendirmeyle şişmiş; Wave-5/6 stale ölçümü gösterdi (%35 backlog sessizce
düzelmiş). Canlı kullanım = gerçek öncelik sinyali.
- Murat'ın 2-4 hafta gerçek kullanım notları → somut sürtünme maddeleri (backlog'a değil, GÖZLEME dayalı).
- Her madde: gerçekten mi acıtıyor (kullanım-frekansı × şiddet) yoksa teorik mi? R3 (kanıt: hangi ekranda, kaç kez).
- **GATE:** önceliklendirilmiş liste — her madde bir gerçek-kullanım gözlemine bağlı (spekülatif backlog maddesi DEĞİL).

## BLOK B — YÜKSEK-FREKANS AKIŞ CİLASI (KULLANIM-GATE'li)
Gerçek kullanımda en sık dokunulan akışlar (işlem girişi, cockpit okuma, koç sorusu) — mikro-sürtünme kaldırma.
- Adaylar (canlı kullanım doğrularsa): hızlı-giriş kısayolları, mobil klavye/input tipleri, offline-yazma kuyruğu (PWA),
  koç yanıt gecikmesi algısı. **HER kullanıcı-görünür iş = KULLANIM-GATE** (gerçek cihazda uçtan uca, mock değil).

## BLOK C — KAPANIŞ
Rapor + PROJE.md + Wave-10 iskelet + MCP GOAL TAMAM W9 + W1 rotasyonu.

## KAPSAM DIŞI (Wave-9)
- Kripto (kalıcı kapsam-dışı, Murat). Native/App Store (PWA yeterli, ADR-040). Yeni büyük mimari (Wave-9 = cila, genişleme değil).

## Not
Bu iskelet Wave-8 kapanmadan **finalize edilmez** — charter (Wave-8 Blok D): "273 UX borcu post-deploy gerçek kullanımla
önceliklenir". Yani Wave-9'un GERÇEK maddeleri ancak canlı deploy + gerçek kullanım verisiyle doldurulur. Bu dosya niyeti +
ön-koşulu + iskelet blokları belgeler; somut milestone listesi Murat'ın kullanım-geri-bildirimiyle netleşir.
