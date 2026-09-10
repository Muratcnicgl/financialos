"""
MODEL ADI HÂLÂ VAR MI? — sağlayıcının KENDİ kataloğuna sorar (BUG #369).

NEDEN VAR
---------
Bu depoda **sabit model kimliği üç kez sessizce çürüdü** ve üçünde de belirti aynıydı:

  1. `meta-llama/llama-3.3-70b-instruct:free` OpenRouter kataloğundan kalktı. İstek
     ücretli sürüme yönlendi, bakiye $0 olduğu için **402 payment_required** döndü.
     Aylarca "kredi yok" sanıldı; hesapta kredi sorunu yoktu. (BUG #315)
  2. Cerebras bir modeli deprecate etti; ancak canlı bir eval koşumunda yakalandı.
  3. `minimax/minimax-m3:free` katalogdan kalktı (ölçüldü, 11 Eyl 2026 00:07):
     **404** — ve OpenRouter cevabın içinde doğrusunu bile söylüyordu
     ("use this slug instead: minimax/minimax-m3"). Zincirin GEÇERLİ TEK altın
     ölçüm halkası buydu; öldüğü için `data/eval_runs.jsonl`de 10 Eylül koşumunun
     BEŞ sağlayıcısı da `gecerli: false, pass_rate: 0.0` yazdı ve koç kalitesi
     ölçülemez oldu.

Üçünde de ortak ders: **model adı çürüdüğünde belirti daima "sağlayıcı bizi
istemiyor" biçiminde okunur.** Yanlış yerde aranır — prompt değiştirilir, model
büyütülür, kota tartışılır — oysa arıza tek bir dizgededir.

Ve üçünde de çürümeyi bulan şey bir kapı değil, AYLAR SONRA koşulan canlı bir
eval oldu. Depoda `DEFAULT_MODEL`e dokunan üç test var (`test_saglayici_modeli_kapisi`,
`test_env_yorum_tuzagi_kapisi`) ama hepsi ÇEVRİMDIŞI: adın KULLANILDIĞINI
doğruluyorlar, VAR OLDUĞUNU değil. Ölçülmeyen şey, sessizce çürüyen şeydir.

NE YAPAR
--------
Etkin model adını (env ezmesi varsa o, yoksa sınıfın `DEFAULT_MODEL`i) sağlayıcının
canlı kataloğuyla karşılaştırır.

    python -m scripts.model_canliligi            # tam rapor
    python -m scripts.model_canliligi --sessiz   # yalnız ÇÜRÜME varsa konuş
    python -m scripts.model_canliligi --kapi     # çürüme varsa çıkış kodu 1

NEDEN KAPI DEĞİL (varsayılan)
------------------------------
`ci_durum.py` ve `canli_durum.py` ile aynı sınıftandır: **ağa çıkar**. Ağsız bir
makinede kırmızı veren bir kapı, ölçtüğü şeyi değil bağlantıyı ölçer ve ilk
sahte kırmızıdan sonra `--no-verify` alışkanlığı doğurur. Bu yüzden varsayılan
davranış UYARMAKTIR; `--kapi` bilinçli çağıran içindir (ör. eval koşumundan önce).

NEDEN LİSTE ELLE YAZILMADI
---------------------------
Sağlayıcılar `app.coach.SAGLAYICI_ONEKLERI` ve `LLMProvider` alt sınıflarından
TÜRETİLİR (`NAME` ile eşleşerek). Elle bir beyaz liste tutmak, denetleyicinin
kendisini bayatlatırdı — bu deponun L79'u: *bir belgeyi (ve bir denetleyiciyi)
bayatlamaktan koruyan şey disiplin değil, TÜRETİLMİŞ olmasıdır.* Ölçüldü:
sekiz önekin sekizi de bir sınıfa eşleşiyor, eksik/fazla yok.

NEDEN YALNIZ OPENROUTER GERÇEKTEN ÖLÇÜLÜYOR
--------------------------------------------
Beş sağlayıcının katalog ucu elimizdeki anahtarlarla denendi (11 Eyl 2026):

    OpenRouter  200 — 437 model  (üstelik ANAHTARSIZ da açık → CI'da sırsız koşar)
    Groq        403 · Cerebras 403 · Anthropic 401 · Gemini 403

Yani dördü ölçülemiyor. Bunlar için "geçti" YAZILMAZ — `ÖLÇÜLEMEDİ` yazılır ve
gerekçesi görünür kalır (L45: bilinmeyen sıfır değildir). Sessiz bir eksik rapor,
bu depodaki tekrar eden arıza sınıfıdır; bir aracın kapsamı, kapsamadığını
söylediği kadar dürüsttür.
"""
from __future__ import annotations

# Windows konsolu cp1254'tur; bir GÖRÜNÜRLÜK aracı bir çıktı karakteri yüzünden çökemez
# (canli_durum.py, ci_durum.py, belge_denetimi.py, durum_ozeti.py ile aynı gerekçe).
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import urllib.error  # noqa: E402
import urllib.request  # noqa: E402
from pathlib import Path  # noqa: E402

KOK = Path(__file__).resolve().parent.parent
if str(KOK) not in sys.path:
    sys.path.insert(0, str(KOK))

# BUG #349 — sunucu olmayan her süreç kendi log dizinine yazar.
os.environ.setdefault("LOG_DIR", "logs/arac")

#: Katalogu ölçülebilen sağlayıcılar. Anahtar = `SAGLAYICI_ONEKLERI` öneki.
#: Değer, kimlik listesini döndüren bir çağrılabilir. Buraya yeni bir sağlayıcı
#: eklemenin ÖN KOŞULU, ucunun elimizdeki anahtarla gerçekten cevap verdiğini
#: ÖLÇMEKTİR — "muhtemelen çalışır" diye eklenen bir uç, sessiz bir ÖLÇÜLEMEDİ üretir.
KATALOG_UCU = "https://openrouter.ai/api/v1/models"

#: Ölçülemeyen sağlayıcılar ve ÖLÇÜLEN sebepleri (11 Eyl 2026). Metin, kullanıcıya
#: "neden bilmiyoruz"u söyler; boş bırakmak "sorun yok" gibi okunurdu.
OLCULEMEYEN = {
    "GROQ": "katalog ucu 403 (anahtar sohbette calisiyor, /models'e yetkisiz)",
    "CEREBRAS": "katalog ucu 403",
    "ANTHROPIC": "katalog ucu 401",
    "GEMINI": "katalog ucu 403",
    "TOGETHER": "anahtar yok",
    "DEEPINFRA": "anahtar yok",
    "OLLAMA": "yerel saglayici — bulut katalogu yok",
}


def _saglayici_siniflari() -> dict:
    """`NAME` (BÜYÜK) -> sağlayıcı sınıfı. Alt sınıf ağacından TÜRETİLİR.

    BUG #372 — TEST SAHTELERİ GERÇEK SAĞLAYICIYI GÖLGELİYORDU.
    `LLMProvider.__subclasses__()` CANLI bir kayıttır: o an bellekte var olan HER alt
    sınıfı verir, nerede tanımlandığına bakmaz. `tests/test_coach_eszamanlilik.py`
    içinde `class Sahte(LLMProvider)` var ve `NAME = "Gemini"` taşıyor — sözlükte
    "GEMINI" anahtarını GERÇEK `GeminiProvider`ın üstüne yazıyordu. O sahtenin
    `DEFAULT_MODEL`i olmadığı için Gemini "modelsiz" görünüp raporun dışında kalıyordu.

    Arıza SIRAYA VE ÇÖPE BAĞLIYDI: sahte sınıf hâlâ hayattaysa gölgeliyor, toplanmışsa
    gölgelemiyor. Bu yüzden yerelde YEŞİL, CI'da KIRMIZI verdi — "benim makinemde
    çalışıyor" sınıfının ta kendisi (ölçüldü: CI `backend-tests` iki koşum üst üste).

    Süzgeç: yalnız `app.coach` MODÜLÜNDE tanımlanmış sınıflar. Test sahteleri, notebook
    denemeleri ve ileride başka modüllere yazılacak adaptörler artık kaydı kirletemez."""
    from app.coach import LLMProvider

    def hepsi(sinif):
        for alt in sinif.__subclasses__():
            yield alt
            yield from hepsi(alt)

    return {
        getattr(s, "NAME", "").upper(): s
        for s in hepsi(LLMProvider)
        if getattr(s, "__module__", "") == "app.coach"
    }


def etkin_modeller() -> list[tuple[str, str]]:
    """(önek, GERÇEKTEN kullanılacak model adı) çiftleri.

    Env ezmesi (`<ÖNEK>_MODEL`) sınıfın varsayılanını bastırır — koşan şey odur,
    denetlenen de o olmalıdır. Aksi hâlde `.env`de bayat bir ad taşırken kapı
    yeşil kalırdı.
    """
    from app.coach import SAGLAYICI_ONEKLERI, saglayici_modeli

    siniflar = _saglayici_siniflari()
    cikti = []
    for onek in SAGLAYICI_ONEKLERI:
        sinif = siniflar.get(onek)
        model = saglayici_modeli(onek) or getattr(sinif, "DEFAULT_MODEL", None)
        # BUG #372'nin ikinci yüzü: ÇÖZÜLEMEYEN SAĞLAYICI SESSİZCE DÜŞMEZ.
        # Önceki hâl `continue` diyordu; sonuç, kapsamı olduğundan DAR bir raporu
        # tam görünmesiydi — bu aracın diğer sağlayıcılar için kınadığı davranışın
        # aynısı. Ad çözülemiyorsa satır KALIR, değeri boş gelir ve `rapor()`
        # ÖLÇÜLEMEDİ yazar (L45: bilinmeyen sıfır değildir).
        cikti.append((onek, model or ""))
    return cikti


def openrouter_katalogu(zaman_asimi: int = 30) -> tuple[set[str] | None, str]:
    """(kimlik kümesi, hata). Ağ yoksa (None, sebep) — sıfır DEĞİL, BİLİNMEYEN."""
    try:
        with urllib.request.urlopen(KATALOG_UCU, timeout=zaman_asimi) as c:  # noqa: S310
            veri = json.load(c)
        return {m["id"] for m in veri.get("data", []) if m.get("id")}, ""
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:  # noqa: BLE001 — ağ hatası aracı düşürmemeli
        return None, type(e).__name__


def _oneri(katalog: set[str], model: str) -> str:
    """Çürümüş ad için katalogdan en yakın makul karşılık.

    `:free` düşmüşse ücretli hâli katalogda durur — BUG #315 ve #369'un ikisinde de
    olan tam olarak buydu, o yüzden önce ona bakılır.
    """
    if model.endswith(":free") and model[: -len(":free")] in katalog:
        return model[: -len(":free")]
    kok = model.split(":", 1)[0]
    yakin = sorted(k for k in katalog if k.split(":", 1)[0] == kok)
    return yakin[0] if yakin else ""


def rapor(etkin: list[tuple[str, str]], katalog: set[str] | None,
          katalog_hatasi: str = "") -> tuple[list[str], list[tuple[str, str, str]]]:
    """(rapor satırları, çürüyenler). AĞA ÇIKMAZ — katalog dışarıdan verilir.

    Ağ çağrısından bilinçli olarak AYRI: kapının kendisi ancak çevrimdışı
    sınanabiliyorsa sınanmış olur. Bu depoda yazılan denetleyicilerin bir kısmı
    yanlış çıkmıştı (biri boş küme üzerinde koşup "hepsi geçti" diyordu); bir
    denetleyiciye "çalışıyor" demeden önce onu KIRMAYI denemek gerekir —
    `tests/test_model_canliligi_kapisi.py` üç mutasyonla tam olarak bunu yapar.

    `katalog is None` = katalog ÖLÇÜLEMEDİ (ağ yok / uç düştü). Bu ÇÜRÜME DEĞİLDİR:
    bilinmeyeni çürüme saymak, ağsız bir makinede sahte kırmızı üretir ve uyarıyı
    okunmaz kılar (L22).
    """
    satirlar: list[str] = []
    curuyen: list[tuple[str, str, str]] = []
    for onek, model in etkin:
        if onek == "OPENROUTER":
            if katalog is None:
                satirlar.append(f"  {onek:<11} {model:<52} ÖLÇÜLEMEDİ (katalog: {katalog_hatasi})")
            elif model in katalog:
                satirlar.append(f"  {onek:<11} {model:<52} VAR")
            else:
                oneri = _oneri(katalog, model)
                ek = f" — katalogda: {oneri}" if oneri else ""
                satirlar.append(f"  {onek:<11} {model:<52} ÇÜRÜMÜŞ{ek}")
                curuyen.append((onek, model, oneri))
        elif not model:
            satirlar.append(f"  {onek:<11} {'(ad cozulemedi)':<52} ÖLÇÜLEMEDİ "
                            f"(saglayici sinifi bulunamadi — kayit kirlenmis olabilir)")
        else:
            satirlar.append(f"  {onek:<11} {model:<52} ÖLÇÜLEMEDİ ({OLCULEMEYEN.get(onek, '?')})")
    return satirlar, curuyen


def main() -> int:
    ayristirici = argparse.ArgumentParser(description="Etkin model adlari saglayici katalogunda VAR MI?")
    ayristirici.add_argument("--sessiz", action="store_true",
                             help="yalnizca CURUME varsa konus (pre-commit icin)")
    ayristirici.add_argument("--kapi", action="store_true",
                             help="curume varsa cikis kodu 1 (bilincli cagiran icin)")
    args = ayristirici.parse_args()

    katalog, katalog_hatasi = openrouter_katalogu()
    satirlar, curuyen = rapor(etkin_modeller(), katalog, katalog_hatasi)

    if args.sessiz:
        # Sessiz kipte ÖLÇÜLEMEDİ haber değildir (kalıcı durum); yalnız çürüme konuşur.
        for onek, model, oneri in curuyen:
            ek = f" → {oneri}" if oneri else ""
            print(f"[model] ÇÜRÜMÜŞ MODEL ADI: {onek}={model} saglayici katalogunda YOK{ek}")
    else:
        print("MODEL ADI SAGLAYICI KATALOGUNDA VAR MI — hepsi SIMDI olculdu\n")
        for s in satirlar:
            print(s)
        olculen = sum(1 for s in satirlar if "ÖLÇÜLEMEDİ" not in s)
        print(f"\n  {olculen}/{len(satirlar)} saglayici gercekten olculdu; "
              f"{len(curuyen)} curume bulundu.")
        if curuyen:
            print("\n  Curumus bir ad, 'saglayici bizi istemiyor' gibi gorunur (402/404/429).")
            print("  Yeni adi ELE SECME — ucretsiz+tool destekli adaylari GERCEK altin")
            print("  senaryoyla olcup sec (bkz. OpenRouterProvider'in secim notu).")

    return 1 if (args.kapi and curuyen) else 0


if __name__ == "__main__":
    raise SystemExit(main())
