r"""
API SÖZLEŞME DONDURMA (KAP-01 / BUG #306).

ÖLÇÜLEN DEFEKT (27 Ağu 2026, seen-backend karşılaştırması):
`docs/api-reference/README.md` API şemasının kaynağı olarak "repo kökü `openapi.json`"
diyordu. O dosya `.gitignore:71` ile YOK SAYILIYOR ve diskte hiç yok:

    $ git ls-files | grep -i openapi   → (boş)
    $ ls openapi.json                  → No such file or directory
    $ git check-ignore -v openapi.json → .gitignore:71

Yani 93 yol / 125 handler taşıyan bir API'nin **dondurulmuş hiçbir tanımı yoktu**; belge
ise olmayan bir dosyayı işaret ediyordu. Sonuç: bir uç sessizce yol/metot/yanıt değiştirse
ya da bir handler'dan `Depends(get_current_user)` düşse, süit yeşil kalır — kırılma canlı
istemcide (PWA + kapalı beta kullanıcıları) ortaya çıkar. Bu, BUG #287/#288 ailesinin
("test yeşil, kullanıcıda patlar") tam olarak sınıfı.

NEDEN HAM OpenAPI YETMEZ — ölçülerek öğrenildi:
`app.openapi()` çıktısında **125 handler'ın 125'i "kimliksiz" görünüyor.** Sebep, auth'un
`OAuth2PasswordBearer`/`HTTPBearer` ile değil `get_current_user(request: Request)` içinde
Authorization başlığı elle okunarak yapılması (`app/dependencies.py:50`) — FastAPI bunu
`security` alanına yazamaz. Yani yalnız OpenAPI'yi dondurmak, **korumanın kalkmasını
göremeyen** bir sözleşme üretirdi; kapı en çok değer üreteceği yerde kör olurdu.
Bu yüzden sözleşme İKİ kaynaktan derlenir:
  · yüzey (parametre/gövde/yanıt) → `app.openapi()`
  · kimlik/yetki               → rotanın `dependant` ağacı (aşağıdaki `_bagimlilik_adlari`)

Kullanım:
    .\venv\Scripts\python.exe scripts/sozlesme_dondur.py             # dosyayı yeniden üret
    .\venv\Scripts\python.exe scripts/sozlesme_dondur.py --kontrol   # fark var mı (EXIT=1)

Bu betik yalnız SÖZLEŞME BİLİNÇLİ DEĞİŞTİĞİNDE çalıştırılır. `tests/test_api_sozlesmesi.py`
kırmızıya döndüğünde doğru tepki betiği koşturup dosyayı yeşile boyamak DEĞİLDİR — önce
API yüzeyini neden değiştirdiğin `uygulanan-fixler.md`'ye yazılır (KURAL R3).

GUNCELLEMELER
-------------
BUG #306 fix: dosya oluşturuldu (KAP-01).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_KOK = Path(__file__).resolve().parent.parent
SOZLESME_YOLU = REPO_KOK / "docs" / "api-reference" / "api-sozlesmesi.json"

# `python scripts/sozlesme_dondur.py` ile doğrudan koşulduğunda `app` paketi yolda değildir
# (pytest yolunda rootdir zaten ekli olur). Diğer betiklerle aynı kalıp.
if str(REPO_KOK) not in sys.path:
    sys.path.insert(0, str(REPO_KOK))

# ══════════════════════════════════════════════════════════════════════════════
# KİMLİK/YETKİ BAĞIMLILIKLARI
# ══════════════════════════════════════════════════════════════════════════════
# Bu küme TAHMİN DEĞİL, ölçüm: 27 Ağu 2026'da 125 handler'ın bağımlılık ağacı taranıp
# 2+ kez geçen tam nitelikli adlar sayıldı. Çıkan liste (handler'ların kendisi hariç):
#
#   120  app.dependencies.get_db                      ← sadece DB oturumu, koruma DEĞİL
#   106  app.dependencies.get_current_user
#    76  app.workspace_deps.active_workspace_id
#    62  app.workspace_deps.require_write
#     2  app.workspace_deps.require_workspace
#     2  app.workspace_deps.get_active_membership
#
# `get_db` bilinçli olarak DIŞARIDA: kaldırılması bir yetki kaybı değil, derhal 500'dür.
# Yeni bir koruma bağımlılığı eklenirse buraya YAZILMALI; yazılmazsa onu kullanan uç
# "kimliksiz" görünür ve sözleşme diff'i bunu ilk üretimde gösterir.
KORUMA_BAGIMLILIKLARI = frozenset(
    {
        "app.dependencies.get_current_user",
        "app.workspace_deps.active_workspace_id",
        "app.workspace_deps.require_write",
        "app.workspace_deps.require_workspace",
        "app.workspace_deps.get_active_membership",
    }
)


def _env_sabitle() -> None:
    """Betik olarak koşarken ortamı sabitle — sözleşme ortamdan BAĞIMSIZ olmalı.

    · `DATABASE_URL` in-memory'ye çekilir: sözleşme çıkarmak için DB gerekmez ve bu
      betiğin CANLI dosyaya bağlanma ihtimali tamamen kapanır (BUG #289'un sınıfı).
    · `SERVE_SPA=0`: açıkken `frontend/dist` yoksa `app/spa.py` bilerek fail-fast eder
      (CI'da ve temiz klonda `dist` yoktur) — sözleşme çıkarmanın SPA ile işi yok.
    · `ENVIRONMENT=development`: production fail-fast'i sır ister; sözleşme istemez.
    · `SECRET_KEY`: yoksa `app/auth.py` RuntimeError verir. Değeri kullanılmıyor.

    NOT: pytest yolunda bu fonksiyon ÇAĞRILMAZ — orada ortamı `tests/conftest.py` app
    import edilmeden önce zaten sabitliyor. İkisinin aynı sözleşmeyi ürettiği
    `tests/test_api_sozlesmesi.py::test_sozlesme_ortamdan_bagimsiz` ile ölçülür.
    """
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["SERVE_SPA"] = "0"
    os.environ["ENVIRONMENT"] = "development"
    os.environ.setdefault("SECRET_KEY", "sozlesme-dondurma-icin-kullanilmayan-anahtar-0123")
    # BUG #349 — `app.main` import edildiği an `setup_logging()` koşar ve CANLI betanın
    # `logs/financialos.log` dosyasına döner bir handler bağlanır. Windows'ta ikinci bir
    # tutucu, canlı uygulamanın log rotasyonunu imkânsız kılar ve uygulama sessizce
    # loglamayı bırakır (5 Eyl 2026'da ölçüldü). Sunucu OLMAYAN her süreç kendi dizinine yazar.
    os.environ.setdefault("LOG_DIR", "logs/arac")
    os.environ.pop("SPA_DIST", None)


def _rotalar(app: Any):
    """`app.routes` ağacını gezip (yol, APIRoute) üretir.

    FastAPI 0.141'de `include_router` rotaları DÜZLEŞTİRMEZ; `_IncludedRouter` altında
    orijinal router'ı ve prefix'i saklar. Bunu gezmeyen bir tarayıcı `app.routes`'ta
    yalnız 2 APIRoute görür (`/` ve `/api/health`) ve 123 ucu sessizce kaçırır —
    ilk yazımda tam olarak bu oldu, ölçümle yakalandı.
    """
    from fastapi.routing import APIRoute, _IncludedRouter

    def gez(rotalar, onek: str = ""):
        for r in rotalar:
            if isinstance(r, APIRoute):
                yield onek + r.path, r
            elif isinstance(r, _IncludedRouter):
                baglam = getattr(r, "include_context", None)
                yield from gez(
                    r.original_router.routes, onek + (getattr(baglam, "prefix", "") or "")
                )
            elif hasattr(r, "routes"):
                yield from gez(r.routes, onek)

    yield from gez(app.routes)


def _tam_ad(cagri: Any) -> str:
    """Bağımlılığın tam nitelikli adı. `require_write()` gibi fabrikalar `<locals>._dep`
    döndürür; ad oraya kadar kırpılır — yoksa sözleşmede 62 tane ayırt edilemez `_dep`
    görünürdü (`require_write` ile `require_workspace` aynı ada sahip)."""
    modul = getattr(cagri, "__module__", "?")
    nitelik = getattr(cagri, "__qualname__", None) or getattr(cagri, "__name__", repr(cagri))
    if ".<locals>" in nitelik:
        nitelik = nitelik.split(".<locals>")[0]
    return f"{modul}.{nitelik}"


def _bagimlilik_adlari(dependant: Any, gorulen: set[int] | None = None) -> set[str]:
    """Rotanın bağımlılık ağacındaki TÜM adlar (geçişli). Handler'ın kendisi de dâhildir;
    çağıran taraf onu ayıklar."""
    gorulen = gorulen if gorulen is not None else set()
    adlar: set[str] = set()
    if dependant.call is not None:
        adlar.add(_tam_ad(dependant.call))
    for alt in dependant.dependencies:
        if id(alt) in gorulen:
            continue
        gorulen.add(id(alt))
        adlar |= _bagimlilik_adlari(alt, gorulen)
    return adlar


def _sema_adi(sema: dict | None) -> str | None:
    """OpenAPI şema düğümünden okunabilir bir ad çıkarır.

    `$ref` varsa son parça (`#/components/schemas/AccountOut` → `AccountOut`).
    `anyOf`/`allOf` sarmalıysa içindeki ref'ler `|` ile birleşir (Optional[X] bu şekil).
    Hiç ref yoksa ilkel tip adı döner; o da yoksa `gomulu`.
    """
    if not sema:
        return None
    if "$ref" in sema:
        return sema["$ref"].rsplit("/", 1)[-1]
    for anahtar in ("anyOf", "allOf", "oneOf"):
        if anahtar in sema:
            parcalar = [_sema_adi(alt) for alt in sema[anahtar]]
            temiz = [p for p in parcalar if p]
            if temiz:
                return "|".join(temiz)
    if "items" in sema:
        ic = _sema_adi(sema["items"])
        return f"dizi[{ic}]" if ic else "dizi"
    tip = sema.get("type")
    if isinstance(tip, str):
        return tip
    return "gomulu"


def _govde_semasi(islem: dict) -> str | None:
    govde = islem.get("requestBody")
    if not govde:
        return None
    icerik = govde.get("content", {})
    for ortam in sorted(icerik):
        return _sema_adi(icerik[ortam].get("schema"))
    return "govdesiz"


def _yanit_semalari(islem: dict) -> dict[str, str]:
    cikti: dict[str, str] = {}
    for kod, tanim in sorted((islem.get("responses") or {}).items()):
        icerik = tanim.get("content") or {}
        if not icerik:
            cikti[str(kod)] = "govdesiz"
            continue
        ortam = sorted(icerik)[0]
        cikti[str(kod)] = _sema_adi(icerik[ortam].get("schema")) or "gomulu"
    return cikti


def _parametreler(islem: dict) -> list[dict]:
    cikti = []
    for p in islem.get("parameters") or []:
        cikti.append(
            {
                "ad": p.get("name"),
                "yer": p.get("in"),
                "zorunlu": bool(p.get("required", False)),
                "tip": _sema_adi(p.get("schema")) or "bilinmiyor",
            }
        )
    return sorted(cikti, key=lambda d: (d["yer"] or "", d["ad"] or ""))


def sozlesme_uret() -> list[dict]:
    """Diskteki koddan sözleşmeyi üretir. Determinist: aynı kod → aynı çıktı.

    Ortamı DEĞİŞTİRMEZ; çağıranın sorumluluğu (betik yolunda `_env_sabitle()`,
    test yolunda `tests/conftest.py`).
    """
    from app.main import app

    # `app.openapi()` sonucu app üzerinde önbelleklenir; iki kez üretmenin farkı olmasın
    # diye önbellek temizlenir (aynı süreçte hem test hem betik koşabilir).
    app.openapi_schema = None
    sema = app.openapi()
    yollar = sema.get("paths", {})

    # Rota nesnelerini (yol, metot) ile indeksle — kimlik bilgisi yalnız burada var.
    korumalar: dict[tuple[str, str], list[str]] = {}
    for yol, rota in _rotalar(app):
        adlar = _bagimlilik_adlari(rota.dependant)
        koruma = sorted(adlar & KORUMA_BAGIMLILIKLARI)
        for metot in set(rota.methods) - {"HEAD", "OPTIONS"}:
            korumalar[(yol, metot.upper())] = koruma

    sozlesme: list[dict] = []
    for yol in sorted(yollar):
        for metot in sorted(yollar[yol]):
            if metot.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            islem = yollar[yol][metot]
            koruma = korumalar.get((yol, metot.upper()))
            sozlesme.append(
                {
                    "yol": yol,
                    "metot": metot.upper(),
                    "kimlik": "korumali" if koruma else "kimliksiz",
                    "koruma": koruma if koruma is not None else [],
                    "parametreler": _parametreler(islem),
                    "istek_govdesi": _govde_semasi(islem),
                    "yanitlar": _yanit_semalari(islem),
                }
            )
    return sozlesme


def imza(kayit: dict) -> str:
    """Tek satırlık, göze çarpan imza — diff'te NE değiştiğini insan okusun diye.

    Örnek:
      POST /api/accounts korumali params=[header:X-Workspace-Id] govde=AccountCreate -> 201:AccountOut 422:HTTPValidationError
    """
    params = ",".join(f"{p['yer']}:{p['ad']}" for p in kayit["parametreler"]) or "-"
    yanit = " ".join(f"{k}:{v}" for k, v in sorted(kayit["yanitlar"].items())) or "-"
    return (
        f"{kayit['metot']} {kayit['yol']} {kayit['kimlik']} "
        f"params=[{params}] govde={kayit['istek_govdesi'] or '-'} -> {yanit}"
    )


def imzalar(sozlesme: list[dict]) -> list[str]:
    return sorted(imza(k) for k in sozlesme)


def serilestir(sozlesme: list[dict]) -> str:
    """Diske yazılacak metin. `ensure_ascii=False` — Türkçe anahtar/ad okunur kalsın.
    Satır sonu DAİMA `\\n` (bkz. `.gitattributes`): ölçüm makineye bağlı olmamalı."""
    return json.dumps(sozlesme, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def _diskteki() -> str:
    if not SOZLESME_YOLU.exists():
        return ""
    return SOZLESME_YOLU.read_text(encoding="utf-8").replace("\r\n", "\n")


def main(argv: list[str] | None = None) -> int:
    ayristirici = argparse.ArgumentParser(
        description="API sözleşmesini üretir veya dondurulmuş dosyayla karşılaştırır."
    )
    ayristirici.add_argument(
        "--kontrol",
        action="store_true",
        help="Yazma; fark varsa 1 ile çık (CI kapısı).",
    )
    secenek = ayristirici.parse_args(argv)

    _env_sabitle()
    sozlesme = sozlesme_uret()
    metin = serilestir(sozlesme)
    korumali = sum(1 for k in sozlesme if k["kimlik"] == "korumali")

    if secenek.kontrol:
        if _diskteki() == metin:
            print(f"sozlesme guncel: {len(sozlesme)} handler ({korumali} korumali)")
            return 0
        print("SOZLESME FARKI: dondurulmus dosya diskteki koddan farkli.", file=sys.stderr)
        print(f"  dondurulmus : {SOZLESME_YOLU}", file=sys.stderr)
        print("  ayrintili fark: python -m pytest tests/test_api_sozlesmesi.py", file=sys.stderr)
        print("  BILINCLI degisiklikse: python scripts/sozlesme_dondur.py", file=sys.stderr)
        return 1

    SOZLESME_YOLU.parent.mkdir(parents=True, exist_ok=True)
    with open(SOZLESME_YOLU, "w", encoding="utf-8", newline="\n") as dosya:
        dosya.write(metin)
    print(f"yazildi: {SOZLESME_YOLU}")
    print(f"handler: {len(sozlesme)} · korumali: {korumali} · kimliksiz: {len(sozlesme) - korumali}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
