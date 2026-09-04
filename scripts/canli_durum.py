"""
CANLI DURUM — kapalı beta ayakta mı? (BUG #328)

NEDEN VAR (ölçülen olay, 3-4 Eylül 2026): kapalı beta **24,5 saat kapalı kaldı ve kimse
fark etmedi.** Zaman çizelgesi `logs/servis.log`'tan:

    02/09 10:35  son basarili acilis
    03/09 08:50  ilk BASLATILAMADI  (goc uygulanmamis; schema_guard dogru davranip acmadi)
    ...          saglik gorevi 10 dakikada bir denedi -> 45 basarisiz deneme
    04/09 09:21  elle onarildi

Arıza **gürültülüydü ama görünmezdi**: her başarısızlık `logs/servis.log`'a yazıldı ve o
dosyaya kimse bakmadı. BUG #326 bu ÖZEL arızayı (uygulanmamış göç) kendi kendine çözüyor,
ama bir sonraki açılış hatası (SECRET_KEY, port çakışması, kapasite, bozuk .env) yine
aynı sessizlikle sürer. **L61: ölçen sistem, telafi eden ya da HABER VEREN sistem değildir.**

TASARIM — YENİ BİR KANAL İCAT ETMEZ, MEVCUT DESENİ KULLANIR. `scripts/ci_durum.py`
tam olarak bu sorunu uzak CI için çözmüştü (30+ koşum kırmızıydı, kimse görmüyordu) ve
çözümü şuydu: **operatörün ZATEN her gün yaptığı işe** — commit'e — bir satır iliştir.
Bu araç aynısını canlı servis için yapar. Toast/e-posta/webhook denenmedi: hepsi yeni bir
altyapı ve yeni bir sessiz-bozulma yüzeyi demek.

SINIRLARI BİLİNÇLİ:
  * **Kapı DEĞİL.** Commit'i asla engellemez; ağ/servis yoksa çalışma durmamalı.
  * Yeşilse **hiç konuşmaz** (`--sessiz`) — gürültü üreten uyarı okunmaz hâle gelir (L22).
  * Yalnız `127.0.0.1`'e bakar. Dış yolu (Tailscale/DNS) `saglik.ps1` ölçüyor; burada
    tekrar etmek iki farklı "canlı" tanımı üretirdi.

Çıkış kodu: 0 ayakta / bilinmiyor · 1 KAPALI (hook'tan çağrılabilir).
"""
from __future__ import annotations

import argparse
import http.client
import json
import sys
from pathlib import Path

# Windows konsolu cp1254'tur; bir GÖRÜNÜRLÜK aracı bir çıktı karakteri yüzünden çökemez
# (ci_durum.py ile aynı gerekçe — sessiz kalması da çökmesi de kabul edilemez).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

#: Bu araç YALNIZ loopback'e bakar ve bu bilinçli. İlk yazımda tam bir URL (`--url`)
#: alıyordu ve `urllib.request.urlopen` kullanıyordu; kalite kapısı bunu bir gerileme
#: olarak yakaladı (bandit S310 = "keyfi şema kabul eden urlopen"). Tavanı YÜKSELTMEK
#: yerine ihtiyaç kaldırıldı: yalnız 127.0.0.1'e HTTP konuşan bir araç için şema/host'u
#: dışarıdan almak zaten gereksiz bir yüzeydi. `http.client` ile şema belirsizliği yok.
#: (Projenin kendi dersi: bir ratchet kapısına doğru cevap çoğu zaman tavanı yükseltmek
#: değil, ihtiyacı ortadan kaldırmaktır.)
VARSAYILAN_HOST = "127.0.0.1"
VARSAYILAN_PORT = 8000
VARSAYILAN_YOL = "/api/health"
SERVIS_LOG = Path(__file__).resolve().parent.parent / "logs" / "servis.log"

AYAKTA = 0
KAPALI = 1


def saglik(host: str = VARSAYILAN_HOST, port: int = VARSAYILAN_PORT,
           yol: str = VARSAYILAN_YOL, zaman_asimi: float = 3.0) -> tuple[bool, str]:
    """(ayakta mı, kısa açıklama). Ağ hatası KAPALI sayılır — bilinmeyen 'ayakta' değildir."""
    baglanti = None
    try:
        baglanti = http.client.HTTPConnection(host, port, timeout=zaman_asimi)
        baglanti.request("GET", yol)
        durum = baglanti.getresponse().status
        return (True, "200") if durum == 200 else (False, f"HTTP {durum}")
    except Exception as e:  # noqa: BLE001 — bağlanamamak da KAPALI'dır
        return False, f"{type(e).__name__}"
    finally:
        if baglanti is not None:
            baglanti.close()


def son_hata(log: Path = SERVIS_LOG, kac: int = 3) -> list[str]:
    """
    Servis günlüğünün son hata satırları — "kapalı" demek yetmez, NEDEN kapalı olduğu
    da görünmeli. (Bugünün dersi: teşhis zaten dosyada duruyordu, kimse açmadı.)
    """
    try:
        satirlar = log.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    hatalar = [s for s in satirlar if "BASLATILAMADI" in s or "|" in s]
    return hatalar[-kac:]


def main() -> int:
    ap = argparse.ArgumentParser(description="Kapalı beta ayakta mı?")
    ap.add_argument("--port", type=int, default=VARSAYILAN_PORT)
    ap.add_argument("--sessiz", action="store_true", help="yalnız KAPALI ise çıktı ver")
    ap.add_argument("--json", action="store_true", help="makine-okur çıktı")
    a = ap.parse_args()

    ok, aciklama = saglik(port=a.port)
    adres = f"http://{VARSAYILAN_HOST}:{a.port}{VARSAYILAN_YOL}"

    if a.json:
        print(json.dumps({"ayakta": ok, "aciklama": aciklama, "url": adres},
                         ensure_ascii=False))
        return AYAKTA if ok else KAPALI

    if ok:
        if not a.sessiz:
            print(f"[canli] AYAKTA ({adres})")
        return AYAKTA

    print(f"[canli] !! KAPALI — {adres} cevap vermiyor ({aciklama}).")
    for s in son_hata():
        print(f"[canli]    {s.strip()[:150]}")
    print("[canli]    Baslatmak icin: .\\deploy\\windows\\baslat.ps1")
    return KAPALI


if __name__ == "__main__":
    raise SystemExit(main())
