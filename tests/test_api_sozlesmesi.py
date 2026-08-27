"""
API SÖZLEŞME KAPISI (KAP-01 / BUG #306).

Bu test kırmızıya döndüğü an **API yüzeyini değiştirmişsindir**. Doğru tepki
`scripts/sozlesme_dondur.py` koşturup dosyayı yeşile boyamak DEĞİLDİR — o, kuralı
susturmaktır. Sözleşme yalnız bilinçli, gerekçesi `uygulanan-fixler.md`'ye yazılmış bir
kırılmada yeniden dondurulur.

NEDEN VAR (ölçüldü, 27 Ağu 2026): 93 yol / 125 handler taşıyan API'nin dondurulmuş hiçbir
tanımı yoktu; `docs/api-reference/README.md` ise `.gitignore`'daki olmayan bir dosyayı
kaynak gösteriyordu. Bir uç sessizce yol/metot/yanıt değiştirse ya da bir handler'dan
`Depends(get_current_user)` düşse süit yeşil kalır, kırılma canlı istemcide çıkardı.

ÜÇ AYRI ŞEYİ ÖLÇER — üçü de ayrı ayrı gerekli:
  1. `test_dondurulmus_sozlesme_kodla_ayni`   → yüzey değişti mi
  2. `test_kimliksiz_uclar_beklenen_listede`  → koruma sessizce düştü mü
  3. `test_sozlesme_ortamdan_bagimsiz`        → sözleşme makineye/ortama bağlı mı

(3) olmadan (1) sahte güvenlik olurdu: sözleşme ortama göre değişiyorsa CI ile yerel
farklı sonuç verir ve kapı "benim makinemde yeşil" sınıfına düşer (L59'un sınıfı).
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from scripts import sozlesme_dondur

# ══════════════════════════════════════════════════════════════════════════════
# KİMLİK DOĞRULAMASI GEREKTİRMEYEN UÇLAR — açık liste
# ══════════════════════════════════════════════════════════════════════════════
# 27 Ağu 2026'da 125 handler'ın bağımlılık ağacı tarandı: 106 korumalı, 19 kimliksiz.
# Aşağıdaki 19'un her biri TEK TEK incelendi ve kimliksiz olması gerektiği doğrulandı:
#
#   · auth akışının kendisi (kimlik almadan önce çağrılır)
#   · `/api/legal` — hukuki metinler, P4 gereği kimliksiz erişilir
#   · `/api/health`, `/api/ready`, `/api/meta` — künye/sağlık uçları (kimliksiz, BUG #205
#     ile kişisel veri sızmadığı ayrıca test ediliyor)
#   · `POST /api/user` — tek-kullanıcı kurulum kalıntısı; `auth_enabled()` açıkken
#     403 döner (BUG #174), yani çok-kullanıcı kurulumda fiilen kapalıdır.
#
# Bu listeye bir uç EKLENİYORSA, eklendiği commit'te neden kimliksiz olduğu yazılmalıdır.
# Listeden bir uç DÜŞÜYORSA (koruma eklendiyse) test doğal olarak kırmızıya döner ve
# liste güncellenir — o yön güvenlidir. Tehlikeli yön listeye SESSİZCE ekleme yapmaktır;
# bu yüzden liste kodda, diff'te görünür yerde durur.
KIMLIKSIZ_UCLAR = frozenset(
    {
        ("GET", "/"),
        ("GET", "/api/auth/callback/{provider}"),
        ("GET", "/api/auth/oauth/{provider}/login"),
        ("GET", "/api/auth/verify-email"),
        ("GET", "/api/health"),
        ("GET", "/api/legal"),
        ("GET", "/api/legal/{slug}"),
        ("GET", "/api/meta"),
        ("GET", "/api/meta/durum"),
        ("GET", "/api/ready"),
        ("POST", "/api/auth/change-email-confirm"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/auth/oauth/exchange"),
        ("POST", "/api/auth/password-reset-confirm"),
        ("POST", "/api/auth/password-reset-request"),
        ("POST", "/api/auth/refresh"),
        ("POST", "/api/auth/register"),
        ("POST", "/api/user"),
    }
)


@pytest.fixture(scope="module")
def canli_sozlesme() -> list[dict]:
    """Diskteki koddan üretilen sözleşme. Modül kapsamlı: app import'u bir kez yeter."""
    return sozlesme_dondur.sozlesme_uret()


@pytest.fixture(scope="module")
def dondurulmus_sozlesme() -> list[dict]:
    yol = sozlesme_dondur.SOZLESME_YOLU
    assert yol.exists(), (
        f"Dondurulmuş sözleşme yok: {yol}\n"
        "Üretmek için: python scripts/sozlesme_dondur.py"
    )
    return json.loads(yol.read_text(encoding="utf-8"))


def test_dondurulmus_sozlesme_kodla_ayni(canli_sozlesme, dondurulmus_sozlesme):
    """Dondurulmuş dosya, diskteki route ağacıyla birebir aynı olmalı."""
    canli_imza = sozlesme_dondur.imzalar(canli_sozlesme)
    donmus_imza = sozlesme_dondur.imzalar(dondurulmus_sozlesme)

    # Önce insan-okunur fark: hata mesajında NE değiştiği görünsün, 2939 satırlık
    # JSON diff'i değil.
    eklenen = [i for i in canli_imza if i not in donmus_imza]
    silinen = [i for i in donmus_imza if i not in canli_imza]
    assert not (eklenen or silinen), (
        "API YÜZEYİ DEĞİŞTİ.\n"
        + ("\n".join(f"  + {i}" for i in eklenen) if eklenen else "")
        + ("\n" if eklenen and silinen else "")
        + ("\n".join(f"  - {i}" for i in silinen) if silinen else "")
        + "\n\nBu BİLİNÇLİ bir değişiklikse: python scripts/sozlesme_dondur.py"
        "\nve gerekçesini docs/kalite-seruveni/uygulanan-fixler.md'ye yaz."
    )

    # İmzalar aynıysa ayrıntı da aynı olmalı (imza her alanı taşımaz: örn. `zorunlu`).
    assert canli_sozlesme == dondurulmus_sozlesme, (
        "İmzalar aynı ama ayrıntı farklı (parametre zorunluluğu/tipi değişmiş olabilir).\n"
        "Farkı görmek için: python scripts/sozlesme_dondur.py --kontrol"
    )


def test_kimliksiz_uclar_beklenen_listede(canli_sozlesme):
    """Hiçbir uç, açık listeye yazılmadan kimlik doğrulamasız hâle gelemez.

    Sözleşme diff'i (yukarıdaki test) bunu zaten yakalar; bu test HANGİ ucun korumasız
    kaldığını ADIYLA söyler. `koruma` alanı boşalan bir handler burada tek başına listelenir.
    """
    olculen = {(k["metot"], k["yol"]) for k in canli_sozlesme if k["kimlik"] == "kimliksiz"}

    beklenmeyen = sorted(olculen - KIMLIKSIZ_UCLAR)
    assert not beklenmeyen, (
        "KİMLİK DOĞRULAMASI OLMAYAN YENİ UÇ(LAR):\n"
        + "\n".join(f"  {m} {y}" for m, y in beklenmeyen)
        + "\n\nKoruma kazara mı düştü? Öyleyse `Depends(get_current_user)` geri konur."
        "\nBilerek kimliksizse KIMLIKSIZ_UCLAR listesine gerekçesiyle eklenir."
    )

    artik = sorted(KIMLIKSIZ_UCLAR - olculen)
    assert not artik, (
        "Bu uçlar artık korumalı (ya da kaldırılmış) — listeden çıkarılmalı:\n"
        + "\n".join(f"  {m} {y}" for m, y in artik)
    )


def test_sozlesme_ortamdan_bagimsiz():
    """Betik kendi ortamında koştuğunda da AYNI sözleşmeyi üretmeli.

    Süit ortamı `tests/conftest.py` tarafından sabitleniyor (AUTH_ENABLED=false,
    SERVE_SPA=0, süit DB'si …); betik ise `_env_sabitle()` ile bambaşka bir ortam kurar.
    İkisi de aynı dondurulmuş dosyayla eşleşiyorsa sözleşme ortamdan bağımsızdır.

    Alt süreç şart: aynı süreçte `app.main` bir kez import edilir, ortamı değiştirmek
    onu yeniden okumaz — in-process bir deneme hiçbir şey ölçmez, yalnız yeşil görünürdü.
    """
    sonuc = subprocess.run(
        [sys.executable, str(sozlesme_dondur.REPO_KOK / "scripts" / "sozlesme_dondur.py"), "--kontrol"],
        cwd=str(sozlesme_dondur.REPO_KOK),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert sonuc.returncode == 0, (
        "Betik kendi ortamında FARKLI bir sözleşme üretti — sözleşme ortama bağlı.\n"
        f"stdout: {sonuc.stdout}\nstderr: {sonuc.stderr}"
    )
