"""
Uç (endpoint) envanteri — test kapsamının TEK kaynağı.

BUG #217: `app.routes` üzerinden uç türetmek FastAPI 0.141 ile SESSİZCE körleşti.
`include_router` artık alt yolları düzleştirmiyor; her router `_IncludedRouter` sarmalayıcısı
olarak duruyor ve `path`/`routes` alanları boş. Bu yüzden "parametresiz her GET ucunu tara"
diyen boş-durum testi 87 uçtan yalnız 1'ini (`/api/health`) çağırır hale gelmişti — yeşil
ama kör. Kapsam çöküşü hiçbir yerde alarm üretmedi.

Çözüm: envanter OpenAPI şemasından türetilir (FastAPI'nin kararlı kamu sözleşmesi, sarmalayıcı
iç yapısına bağlı değil) + kapsam TABANI assert edilir. Uç sayısı tabanın altına düşerse
test kırılır → kapsam bir daha sessizce daralamaz.
"""
from __future__ import annotations

from typing import Iterable

# Kapsam tabanı: bugün 87 yol var; parametresiz GET ~30, yol-parametreli ~40.
# Taban gerçek sayının altında ama çöküşü (0-2 uç) yakalayacak kadar yüksek tutulur.
MIN_PARAMETRESIZ_GET = 25
MIN_PARAMETRELI_YOL = 25


# BUG #235 (D21): burada bir zamanlar `/api/_test` ön ekli yolları eleyen bir filtre vardı.
# `tests/test_error_tracking.py` modül yüklenirken global `app`'e bilerek-çöken bir uç
# ekliyor ve kaldırmıyordu; filtre o kirliliği ENVANTER TARAFINDA gizliyordu. Kaynak
# düzeltildi (uç artık fixture ömürlü + `include_in_schema=False`), filtre KALDIRILDI:
# eleme burada dursaydı yeni bir test enjeksiyonu yine sessizce gizlenirdi (fail-closed).
# Kirliliğin kendisi artık `tests/test_global_app_kirliligi.py` ile dayatılıyor.


def tum_yollar(app) -> dict:
    """OpenAPI'deki tüm yollar: {yol: {metot(küçük harf): işlem}}."""
    return dict(app.openapi()["paths"])


def parametresiz_get_uclari(app, haric: Iterable[str] = ()) -> list[str]:
    """Yol parametresi olmayan (`{}` içermeyen) tüm GET uçları, `/api` altında.

    `haric` içindeki yollar elenir — her eleme GEREKÇELİ olmalıdır (çağıran tarafta yazılı).
    """
    haric = set(haric)
    yollar = [
        yol
        for yol, metotlar in tum_yollar(app).items()
        if yol.startswith("/api")
        and "{" not in yol
        and "get" in {m.lower() for m in metotlar}
        and yol not in haric
    ]
    assert len(yollar) >= MIN_PARAMETRESIZ_GET, (
        f"Uç envanteri çökmüş görünüyor: yalnız {len(yollar)} parametresiz GET ucu bulundu "
        f"(taban {MIN_PARAMETRESIZ_GET}). BUG #217 tekrar etmiş olabilir — envanter türetme "
        f"yolu (OpenAPI) kırıldıysa kapsam sessizce daralır. Bulunanlar: {sorted(yollar)}"
    )
    return sorted(yollar)


def yol_parametreli_uclar(app) -> list[str]:
    """`/api` altındaki, yol parametresi (`{...}`) içeren tüm yollar — metottan bağımsız.

    İzolasyon matrisi kapsam kilidi bunu kullanır: kullanıcıya ait bir kaynağa ID ile
    erişen her uç ya matriste ya gerekçeli istisna listesinde olmalıdır.
    """
    yollar = [yol for yol in tum_yollar(app) if yol.startswith("/api") and "{" in yol]
    assert len(yollar) >= MIN_PARAMETRELI_YOL, (
        f"Uç envanteri çökmüş görünüyor: yalnız {len(yollar)} yol-parametreli uç bulundu "
        f"(taban {MIN_PARAMETRELI_YOL}). BUG #217 tekrar etmiş olabilir. Bulunanlar: {sorted(yollar)}"
    )
    return sorted(yollar)
