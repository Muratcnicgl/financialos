"""
AĞ KAPISI KAPISI (KAP-02 / BUG #307).

`tests/conftest.py` süitin dışarı çıkmasını engelliyor. Bu dosya o korumanın GERÇEKTEN
çalıştığını ölçer — koruma yazmak ile korumanın işlemesi ayrı şeylerdir (L28: bir kez
yeşil, sürekli yeşil demek değildir).

Ölçülen defekt (27 Ağu 2026): kapı yokken `pyproject.toml`'daki `llm`/`network`/`slow`
markerlarının üçü de **hiç kullanılmamıştı** — "CI'da default skip" diye yazılan koruma
ölü yapılandırmaydı. `app/` içinde beş modül dışarı çağırıyor ve biri ÜCRETLİ
(`app/coach.py`); unutulan tek bir mock sessizce gerçek istek atardı.

Burada dört şey ayrı ayrı ölçülür:
  1. Dört ayrı kanaldan (urlopen · requests · create_connection · socket.connect) çıkış
     engelleniyor mu — kapı tek bir kütüphaneye bağlı olmamalı.
  2. Loopback AÇIK kalıyor mu — `PG_TEST_URL` CI'da `127.0.0.1:55432`'e bağlanır; kapı
     dual-dialect kapılarını öldürmemeli (BUG #295'in tersine düşmek).
  3. `TestClient` çalışmaya devam ediyor mu — süitin ana aracı ASGI üzerinden konuşur,
     soket açmaz; açsaydı kapı 3000+ testi kırardı.
  4. Hata mesajı hedefi ADIYLA söylüyor mu — "engellendi" demek yetmez, hangi modülün
     mock'unun unutulduğunu bulmak dakikalar değil saniyeler almalı.
"""
from __future__ import annotations

import socket
import threading
import urllib.error
import urllib.request

import pytest

from tests.conftest import AgCagrisiEngellendi

# Bu adreslere GERÇEKTEN gidilmez — kapı onları görmeden düşürür. Yine de bilinçli olarak
# var-olmayan bir alan adı seçildi: kapı bir gün delinirse test ağa çıkıp yavaşlamasın.
DIS_HOST = "engellenmis-hedef.invalid"
DIS_URL = f"https://{DIS_HOST}/veri"


def test_urlopen_engellenir():
    """`app/fund_tracker.py:316` bu kanalı kullanır."""
    with pytest.raises(AgCagrisiEngellendi) as hata:
        urllib.request.urlopen(DIS_URL, timeout=5)
    assert DIS_HOST in str(hata.value)


def test_requests_engellenir():
    """`app/price_providers/evds_client.py:80` ve `fx_live.py:69` bu kanalı kullanır."""
    requests = pytest.importorskip("requests")
    with pytest.raises(Exception) as hata:
        requests.get(DIS_URL, timeout=5)
    # requests kendi istisnasına sarabilir; zincirde bizim hatamız olmalı.
    metin = str(hata.value) + str(getattr(hata.value, "__cause__", ""))
    assert "TESTTE AĞ ÇAĞRISI ENGELLENDİ" in metin or isinstance(
        hata.value, AgCagrisiEngellendi
    ), f"beklenen kapı hatası değil: {hata.value!r}"


def test_create_connection_engellenir():
    with pytest.raises(AgCagrisiEngellendi):
        socket.create_connection((DIS_HOST, 443), timeout=5)


def test_ham_soket_connect_engellenir():
    """Kütüphaneyi atlayıp doğrudan sokete inen bir bağımlılık da geçememeli."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with pytest.raises(AgCagrisiEngellendi):
            s.connect(("93.184.216.34", 80))  # IP: ad çözümlemesini de atlar
    finally:
        s.close()


def test_hata_mesaji_yol_gosterir():
    """Mesaj, hangi modülün mock'unun unutulmuş olabileceğini söylemeli."""
    with pytest.raises(AgCagrisiEngellendi) as hata:
        socket.create_connection((DIS_HOST, 443), timeout=5)
    metin = str(hata.value)
    assert "app/coach.py" in metin
    assert "pytest.mark.network" in metin


def test_loopback_acik_kalir():
    """CI'daki PostgreSQL (127.0.0.1:55432) kapıya takılmamalı — gerçek bir yerel
    dinleyiciye gerçek bir bağlantı kurularak ölçülür."""
    dinleyici = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    dinleyici.bind(("127.0.0.1", 0))
    dinleyici.listen(1)
    port = dinleyici.getsockname()[1]

    kabul_edildi: list[bool] = []

    def kabul_et():
        baglanti, _ = dinleyici.accept()
        kabul_edildi.append(True)
        baglanti.close()

    is_parcacigi = threading.Thread(target=kabul_et, daemon=True)
    is_parcacigi.start()
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=5):
            pass
        is_parcacigi.join(timeout=5)
    finally:
        dinleyici.close()

    assert kabul_edildi == [True], "loopback bağlantısı kurulamadı — kapı fazla geniş"


def test_testclient_calismaya_devam_eder():
    """Süitin ana aracı ASGI üzerinden konuşur; kapı onu kırarsa 3000+ test ölürdü."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as istemci:
        yanit = istemci.get("/api/health")
    assert yanit.status_code == 200


@pytest.mark.network
def test_network_isaretli_test_kapiyi_acar():
    """Ölü marker canlandı: `@pytest.mark.network` bilinçli dış çağrıya izin verir.

    Gerçekten dışarı ÇIKMAZ (bu süit para/ağ yakmaz) — ölçülen şey, kapının artık
    devrede olmaması: çağrı `AgCagrisiEngellendi` yerine normal bir ağ hatasıyla düşer.
    """
    with pytest.raises(Exception) as hata:
        socket.create_connection((DIS_HOST, 443), timeout=3)
    assert not isinstance(hata.value, AgCagrisiEngellendi), (
        "@pytest.mark.network kapıyı açmadı"
    )
    assert isinstance(hata.value, (socket.gaierror, OSError))


def test_kapi_network_testinden_sonra_geri_gelir():
    """Marker'lı testten sonra koruma kendiliğinden geri dönmeli.

    Dosya sırası garanti değil ama bu test tek başına da anlamlı: her testin başında
    autouse fixture kapıyı yeniden kapatır, yani hangi sırada koşarsa koşsun kapalı olmalı.
    """
    with pytest.raises(AgCagrisiEngellendi):
        socket.create_connection((DIS_HOST, 443), timeout=3)
