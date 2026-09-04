"""
NPM ÜRETİM DENETİMİ — "açık var" ile "ölçemedim" AYRI SONUÇLARDIR (BUG #329).

ÖLÇÜLEN OLAY (4 Eylül 2026): CI arka arkaya iki koşumda kırmızıydı ve düşen tek adım
`npm audit --omit=dev --audit-level=high` idi. Backend (3435 test) ve e2e geçiyordu.
Logdaki gerçek sebep bir güvenlik açığı DEĞİLDİ:

    npm warn audit 503 Service Unavailable - POST
        https://registry.npmjs.org/-/npm/v1/security/audits/quick
    { error: 'Service Unavailable' }
    npm error audit endpoint returned an error
    Error: Process completed with exit code 1

Adım **7 dakika** denedi ve düştü. `npm audit` çıkış kodu 1'i İKİ ayrı durum için
kullanıyor: (a) yüksek/kritik açık bulundu, (b) denetim ucu cevap vermedi. Kapı ikisini
aynı renge boyayınca, üçüncü tarafın kesintisi projeyi kırmızıya çekiyor.

NEDEN ÖNEMLİ: bu proje bir kez **30 koşum boyunca kırmızı kaldı ve kimse fark etmedi**
(BUG #295-#300). Kırmızının normalleşmesi, gerçek bir açığı görünmez yapar. Yani "her
ihtimalde kırmızı" tavrı güvenliği artırmaz, AZALTIR.

SÖZLEŞME — ÜÇ AYRI SONUÇ:
    TEMIZ      (0)  yüksek/kritik yok            → sessiz
    ACIK_VAR   (1)  yüksek/kritik VAR            → KIRMIZI, yayını durdurur
    OLCULEMEDI (0)  uç cevap vermedi (503/ağ)    → GÜRÜLTÜLÜ uyarı, ama durdurmaz
`OLCULEMEDI`'nin 0 dönmesi bilinçli ve bedeli yazılı: o koşumda üretim bağımlılıkları
DENETLENMEMİŞTİR. Sessizce geçmez — çıktı bunu büyük harfle söyler ve bir sonraki koşum
yeniden dener. Alternatif (kırmızı yapmak) ölçüldü: kırmızıyı normalleştiriyor.

npm'i CI ADIMI çalıştırır (`... --json > audit.json || true`); bu betik yalnızca
çıktıyı sınıflandırır. Gerekçe aşağıda.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

TEMIZ = 0
ACIK_VAR = 1
OLCULEMEDI = 0  # bilinçli: durdurmaz — gerekçe yukarıda

AGIR = ("high", "critical")


#: NEDEN BETIK npm'I KENDISI CALISTIRMIYOR: ilk yazimda `subprocess.run([...])` vardi ve
#: kalite kapisi bunu gerileme olarak yakaladi (bandit S603). Tavani yukseltmek yerine
#: ihtiyac kaldirildi — npm'i CI adimi calistirir, bu betik yalnizca CIKTIYI SINIFLANDIRIR.
#: Sonuc daha da iyi: is bolunmesi netlesti (kabuk calistirir, Python karar verir) ve
#: siniflandirici artik gercek npm ciktilariyla dosyadan test edilebiliyor — ag da,
#: alt surec de gerekmiyor. (Bu turda ucuncu kez: kapi tavani degil tasarimi duzeltti.)


def siniflandir(cikti: str) -> tuple[str, str]:
    """
    npm çıktısını (stdout) sınıflandırır: ("temiz"|"acik"|"olculemedi", açıklama).

    SAF: ağ/dosya yok, yalnız metin. Kapı bu yüzden gerçek 503 çıktısıyla test edilebilir.
    """
    try:
        d = json.loads(cikti)
    except (ValueError, TypeError):
        return "olculemedi", "npm çıktısı JSON değil (uç hata döndürmüş olabilir)"

    # npm, uç hatasında da JSON basabiliyor: {"error": {...}} ya da {"error": "..."}
    hata = d.get("error")
    if hata:
        mesaj = hata.get("summary") or hata.get("detail") if isinstance(hata, dict) else str(hata)
        return "olculemedi", f"denetim ucu hata döndürdü: {str(mesaj)[:120]}"

    ozet = (d.get("metadata") or {}).get("vulnerabilities")
    if ozet is None:
        return "olculemedi", "çıktıda 'metadata.vulnerabilities' yok — denetim tamamlanmamış"

    agir = {k: ozet.get(k, 0) for k in AGIR}
    if any(agir.values()):
        return "acik", f"yüksek/kritik açık: {agir}"
    return "temiz", f"yüksek/kritik yok ({ozet})"


def dosyadan(yol: Path) -> tuple[str, str]:
    """`npm audit --json` çıktısının yazıldığı dosyayı sınıflandırır."""
    try:
        return siniflandir(yol.read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        # Dosya yoksa npm hiç koşamamıştır — bu da "ölçemedim"dir, "temiz" DEĞİL (L28).
        return "olculemedi", f"denetim çıktısı okunamadı: {type(e).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser(description="npm ÜRETİM bağımlılık denetimi")
    ap.add_argument("--dosya", default="frontend/audit.json",
                    help="`npm audit --omit=dev --json` çıktısının yazıldığı dosya")
    a = ap.parse_args()

    sonuc, aciklama = dosyadan(Path(a.dosya))

    if sonuc == "acik":
        print(f"[npm-denetim] KIRMIZI — {aciklama}")
        print("[npm-denetim] Uretim bagimliligindaki acik kullaniciya ulasan koddadir.")
        return ACIK_VAR
    if sonuc == "olculemedi":
        print(f"[npm-denetim] !! OLCULEMEDI — {aciklama}")
        print("[npm-denetim] !! Denetim ucu cevap vermedi (503/ag) ya da cikti eksik.")
        print("[npm-denetim] !! BU KOSUMDA URETIM BAGIMLILIKLARI DENETLENMEMISTIR.")
        print("[npm-denetim] !! Kirmizi YAPILMIYOR: ucuncu tarafin kesintisi kirmiziyi")
        print("[npm-denetim] !! normallestirir ve gercek bir acigi gorunmez kilar.")
        return OLCULEMEDI
    print(f"[npm-denetim] temiz — {aciklama}")
    return TEMIZ


if __name__ == "__main__":
    raise SystemExit(main())
