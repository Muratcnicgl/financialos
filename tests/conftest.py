"""
Pytest paylaşılan fixture'ları.

BUG #078 fix (TEST-005/006): db_session artık CANLI production engine yerine her test için
izole in-memory SQLite (StaticPool) kullanır. Eskiden conftest production DB'ye create_all +
commit yapıyordu — canlı veri riski + testler arası sızıntı. Artık her test taze DB'de.
"""
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# ══════════════════════════════════════════════════════════════════════════
# BUG #286 — SÜİT `.env`'DEN BAĞIMSIZ OLMALI (bu blok app import'undan ÖNCE koşar)
# ══════════════════════════════════════════════════════════════════════════
# Geliştiricinin `.env`'i test SONUCUNU değiştirebiliyordu: `load_dotenv()` ortamda
# olmayan her anahtarı doldurur → aynı commit iki makinede farklı sonuç verir. Bu,
# projenin en temel iddiasını (deterministik süit) sessizce deliyordu.
#
# NEDEN FIXTURE YETMEZ: bu ayarların bir kısmı **import anında** okunur —
# `_compute_cors_origins()` modül seviyesinde koşar, `docs_url` app yaratımında belirlenir,
# SPA mount import sonunda eklenir. Fixture (test başına) o noktada ÇOK GEÇTİR.
# `load_dotenv()` **var olan** değişkeni EZMEZ; bu yüzden burada, app import edilmeden
# önce sabitliyoruz ve `.env` kazanamıyor.
TEST_ENV_SABITLERI = {
    "ENVIRONMENT": "development",        # production → fail-fast + docs kapalı + CORS daralır (BUG #178)
    "REGISTRATION_MODE": "open",         # invite_only → kayıt davet kodu ister (BUG #199)
    "REQUIRE_EMAIL_VERIFICATION": "0",   # kayıt akışını doğrulama adımına sokar (BUG #202)
    "SERVE_SPA": "0",                    # kök yolu arayüze çevirir (BUG #284)
    "FRONTEND_URL": "http://localhost:5173",  # CORS izinli origin listesini belirler
    # `/api/meta` KİMLİKSİZ bir uçtur; künyede yayınlanan adres testin konusudur
    # (BUG #205: kişisel adres yayınlanamaz). `.env`'deki gerçek adres sızarsa
    # `test_kisisel_eposta_sizmaz` geliştiriciye göre kırmızı/yeşil olur.
    "SUPPORT_EMAIL": "destek@ornek-urun.test",
    "AUTH_ENABLED": "false",             # ~900 test kimliksiz fallback yolunda koşar
    # ── BUG #349 — SÜİT, CANLI UYGULAMANIN LOG DOSYASINI SUSTURUYORDU ──
    # `app/main.py:73` `setup_logging()`'i **import anında** çağırır; yani `app.main`'i
    # içe aktaran HER pytest süreci, canlı betanın `logs/financialos.log` dosyasına kendi
    # `RotatingFileHandler`'ını bağlar. Dosya 10 MB'a ulaştığında rotasyon `os.rename` ile
    # yapılır ve Windows'ta **başka bir süreç dosyayı açık tuttuğu sürece bu imkânsızdır**.
    # 5 Eylül 2026 gecesi tam olarak bu oldu: dosya 10.485.727 bayta dayandı, rotasyon
    # düştü ve uygulama-seviyesi log **01:08'de dondu** — canlı `/api/health` 200 dönerken
    # tek satır bile yazılmıyordu (ölçüldü). Uygulama sağlamdı; körleşen şey gözlemiydi.
    # Süit, ölçtüğü sistemi bozamaz: log dizini test için ayrılır ve küçük tutulur.
    "LOG_DIR": "logs/test",
    "LOG_ROTATION_MAX_MB": "1",
    "LOG_ROTATION_BACKUP": "1",
}
for _anahtar, _deger in TEST_ENV_SABITLERI.items():
    os.environ[_anahtar] = _deger
os.environ.pop("SPA_DIST", None)

DAVRANIS_DEGISTIREN_ENV = tuple(TEST_ENV_SABITLERI) + ("SPA_DIST", "DATABASE_URL")

# ══════════════════════════════════════════════════════════════════════════
# BUG #289 — SÜİT CANLI VERİTABANINA BAĞLANAMAZ (bu blok app import'undan ÖNCE koşar)
# ══════════════════════════════════════════════════════════════════════════
# ÖLÇÜLEN DEFEKT (11 Ağu 2026, canlı beta DB'si): `scheduler_runs` tablosunda 50 satırın
# TAMAMI `weekly_smoke_test` — içlerinde `RuntimeError: smoke boom`, yani testin ürettiği
# satırlar gerçek kullanıcıların defterinde. Uçtan uca ölçüm (canlı DB'nin kopyası üzerinde
# tüm süit) `api_call_log: 252 → 254` gösterdi — LLM maliyet defteri (BUG #274) test
# çağrılarıyla kirleniyordu.
#
# NEDEN FIXTURE YETMEZ: `db_session` fixture'ı izoledir (BUG #078) ama ~20 test dosyası
# `app.database.SessionLocal`'i DOĞRUDAN kullanır; o modül `DATABASE_URL`'i **import
# anında** okur. Fixture o noktada çok geçtir — engine çoktan canlı dosyaya bağlanmıştır.
# Koruma, testin ne yaptığına değil, sürecin neye BAĞLANABİLDİĞİNE dayanmalı.
#
# ESCAPE HATCH: `scripts/suite_db_izolasyon_kontrolu.py` sızıntıyı ÖLÇMEK için süiti canlı
# DB'nin bir kopyasına yönlendirir. Bu sabit onu da ezerse araç her zaman "temiz" derdi —
# sahte yeşil. O yüzden araç `FINANCIALOS_SUITE_DB_OVERRIDE=1` ile burayı devre dışı bırakır.
if os.getenv("FINANCIALOS_SUITE_DB_OVERRIDE") == "1":
    SUIT_DB_URL = os.environ.get("DATABASE_URL", "")
else:
    import atexit as _atexit
    import tempfile as _tempfile
    from pathlib import Path as _Path

    _suit_db_dizin = _tempfile.mkdtemp(prefix="financialos_suit_")
    _suit_db_yolu = _Path(_suit_db_dizin) / "suit.db"
    SUIT_DB_URL = f"sqlite:///{_suit_db_yolu.as_posix()}"
    os.environ["DATABASE_URL"] = SUIT_DB_URL

    @_atexit.register
    def _suit_db_temizle() -> None:
        import shutil
        shutil.rmtree(_suit_db_dizin, ignore_errors=True)

# ══════════════════════════════════════════════════════════════════════════
# BUG #307 — TESTTE AĞ KAPISI (bu blok da app import'undan ÖNCE koşar)
# ══════════════════════════════════════════════════════════════════════════
# ÖLÇÜLEN DEFEKT (27 Ağu 2026): süitin dışarı çıkmasını engelleyen HİÇBİR ŞEY yoktu.
#   $ grep -niE 'socket|urlopen|httpx' tests/conftest.py   -> (ağ ile ilgili satır yok)
#   $ git grep -c 'pytest.mark.llm'     -- tests/          -> 0
#   $ git grep -c 'pytest.mark.network' -- tests/          -> 0
# `pyproject.toml` üç marker tanımlıyor (`llm`, `network`, `slow`) ve ÜÇÜ DE HİÇ
# KULLANILMAMIŞ — yani "CI'da default skip" diye yazılan koruma ölü yapılandırmaydı.
#
# Oysa `app/` içinde beş modül dışarı çağırıyor: `app/coach.py` (ÜCRETLİ LLM),
# `app/llm_cost.py`, `app/fund_tracker.py:316` (`urlopen`),
# `app/price_providers/evds_client.py:80` ve `fx_live.py:69` (`requests.get`).
# Unutulan tek bir mock, 3125 testlik süitte sessizce gerçek istek atardı: para yanar,
# dış servisin o anki durumu testi kırmızı/yeşil yapar (deterministiklik ölür) ve
# geliştiricinin `.env`'indeki gerçek anahtar bunu YEREL'de görünmez kılar — BUG #297'nin
# (L59) tam sınıfı.
#
# NEDEN FIXTURE YETMEZ: bazı istemciler modül yüklenirken kurulur; ayrıca bir sızıntı
# fixture kurulmadan (import/collection sırasında) da olabilir. Kapı bu yüzden modül
# seviyesinde açılır, autouse fixture yalnız test başına GERİ YÜKLER.
#
# İZİN VERİLEN TEK ŞEY LOOPBACK: `TestClient` soket açmaz (ASGI üzerinden konuşur) ama
# `PG_TEST_URL` CI'da `127.0.0.1:55432`'e bağlanır (BUG #295) — dual-dialect kapıları
# ölmesin diye loopback açık kalır.
#
# BİLİNÇLİ GERÇEK ÇAĞRI: `@pytest.mark.network` — ölü marker böylece canlanır.
import socket as _socket


class AgCagrisiEngellendi(RuntimeError):
    """Testte dışarı çıkan bir çağrı yakalandı."""


_LOOPBACK = frozenset({"127.0.0.1", "::1", "localhost", "localhost.localdomain", "0.0.0.0", ""})


def _yerel_mi(adres) -> bool:
    """Adres loopback mı? Tuple (host, port…), str (AF_UNIX) ve bilinmeyen biçimleri kapsar."""
    if isinstance(adres, (tuple, list)) and adres:
        host = adres[0]
    elif isinstance(adres, (str, bytes)):
        return True  # AF_UNIX soketi makinenin dışına çıkmaz
    else:
        return False
    # `getaddrinfo(None, port)` SUNUCU BAĞLAMA çağrısıdır (AI_PASSIVE) — dışarı çıkmaz.
    # Bunu engellemek kapıyı fazla geniş yapar ve yerel dinleyici kuran testleri kırardı;
    # `test_loopback_acik_kalir` bu sınıfın yalnız bir örneğini ölçer, kural burada durur.
    if host is None:
        return True
    if isinstance(host, bytes):
        host = host.decode("utf-8", "replace")
    return str(host).strip("[]") in _LOOPBACK


def _hata(hedef, kanal: str) -> AgCagrisiEngellendi:
    return AgCagrisiEngellendi(
        "\n".join(
            (
                f"TESTTE AĞ ÇAĞRISI ENGELLENDİ ({kanal}): {hedef!r}",
                "Süit dışarı çıkamaz: gerçek çağrı para yakar (LLM), testi dış servisin o anki",
                "durumuna bağlar ve geliştiricinin .env'i yüzünden yerelde görünmez kalır.",
                "Muhtemel sebep: ilgili modül için mock/monkeypatch unutuldu",
                "  (app/coach.py · fund_tracker.py · price_providers/evds_client.py · fx_live.py).",
                "Bilinçli ve gerekli bir dış çağrıysa testi `@pytest.mark.network` ile işaretle.",
            )
        )
    )


_GERCEK_GETADDRINFO = _socket.getaddrinfo
_GERCEK_CONNECT = _socket.socket.connect
_GERCEK_CONNECT_EX = _socket.socket.connect_ex
_GERCEK_CREATE_CONNECTION = _socket.create_connection


def _ag_kapisini_kapat() -> None:
    """Loopback dışına çıkan her soket girişimini anlaşılır bir hatayla düşür."""

    def getaddrinfo(host, port, *a, **kw):
        # Ad çözümlemesi de bir ağ çağrısıdır (hedefin adını dış çözümleyiciye sızdırır)
        # ve hatayı BURADA vermek mesaja hedefin ADINI koyar — connect'te yalnız IP olurdu.
        if not _yerel_mi((host, port)):
            raise _hata(host, "getaddrinfo")
        return _GERCEK_GETADDRINFO(host, port, *a, **kw)

    def connect(self, adres):
        if not _yerel_mi(adres):
            raise _hata(adres, "connect")
        return _GERCEK_CONNECT(self, adres)

    def connect_ex(self, adres):
        if not _yerel_mi(adres):
            raise _hata(adres, "connect_ex")
        return _GERCEK_CONNECT_EX(self, adres)

    def create_connection(adres, *a, **kw):
        if not _yerel_mi(adres):
            raise _hata(adres, "create_connection")
        return _GERCEK_CREATE_CONNECTION(adres, *a, **kw)

    _socket.getaddrinfo = getaddrinfo
    _socket.socket.connect = connect
    _socket.socket.connect_ex = connect_ex
    _socket.create_connection = create_connection


def _ag_kapisini_ac() -> None:
    """Kapıyı kaldır — yalnız `@pytest.mark.network` işaretli testler için."""
    _socket.getaddrinfo = _GERCEK_GETADDRINFO
    _socket.socket.connect = _GERCEK_CONNECT
    _socket.socket.connect_ex = _GERCEK_CONNECT_EX
    _socket.create_connection = _GERCEK_CREATE_CONNECTION


_ag_kapisini_kapat()

from app.models import Base, User  # noqa: E402 — env sabitlenmeden app import EDİLMEZ

# Şemayı süit DB'sine kur: `SessionLocal`'i doğrudan kullanan testler tablo bekler.
# ADR-013 `create_all` yasağı ÜRETİM içindir; conftest açıkça muaftır.
from app.database import engine as _suit_engine  # noqa: E402

Base.metadata.create_all(_suit_engine)


@pytest.fixture(autouse=True)
def _neutralize_dotenv_auth(monkeypatch):
    """M61: .env'de AUTH_ENABLED=true var (gerçek app login ister). Testler .env'e BAĞLI
    OLMAMALI — auth gerektiren testler kendi fixture'ında `monkeypatch.setenv` ile açar.
    Autouse (auth test fixture'larından ÖNCE koşar) → onların setenv'i kazanır; diğer ~900
    test fallback yolunda koşar. ENVIRONMENT de nötrlenir (settings fail-fast dev).

    BUG #227 (D06): kimlik doğrulama varsayılanı artık AÇIK (fail-closed) — "değişkeni
    silmek" onu kapatmıyor. Fallback yolunu isteyen testler için burada AÇIKÇA kapatılır;
    bu, gerçek bir yerel kurulumun yapması gerekenle aynı hareket (`AUTH_ENABLED=false`).

    BUG #286 (11 Ağu 2026): bu korumanın KAPSAMI tahminle kurulmuştu. `.env`'e kapalı
    beta için `REGISTRATION_MODE=invite_only` yazıldığı gün süit kırmızıya döndü
    (`test_register_basarili_token_doner`) — çünkü liste yalnız `AUTH_ENABLED` ve
    `ENVIRONMENT`'ı sayıyordu. Aynı sınıf: koruma var, kapsamı ölçülmemiş (L11/H25).
    Liste artık `tests/test_env_bagimsizligi_kapisi.py` ile KAYNAKTAN doğrulanıyor:
    davranış değiştiren bir env okuması eklenip buraya yazılmazsa o kapı kırmızıya döner.
    """
    # Modül seviyesinde sabitlenen değerler test başına GERİ YÜKLENİR: bir test onları
    # değiştirirse (monkeypatch olmadan) sonraki testler etkilenmesin.
    for anahtar, deger in TEST_ENV_SABITLERI.items():
        monkeypatch.setenv(anahtar, deger)
    monkeypatch.delenv("SPA_DIST", raising=False)
    # BUG #289: bir test `DATABASE_URL`'i değiştirirse sonraki testler canlı dosyaya
    # düşmesin — süit DB'si test başına geri yüklenir.
    if SUIT_DB_URL:
        monkeypatch.setenv("DATABASE_URL", SUIT_DB_URL)


@pytest.fixture(autouse=True)
def _ag_kapisi(request):
    """Ağ kapısını test başına geri yükler; `@pytest.mark.network` işaretliyse açar.

    Modül seviyesinde kapatılmış olması yetmez: bir test kapıyı (bilerek ya da bir
    monkeypatch yan etkisiyle) kaldırırsa sonraki testler korumasız kalırdı — koruma
    testin ne yaptığına değil, süreç durumuna dayanmalı (BUG #289'un dersi).
    """
    if request.node.get_closest_marker("network"):
        _ag_kapisini_ac()
        try:
            yield
        finally:
            _ag_kapisini_kapat()
    else:
        _ag_kapisini_kapat()
        yield


@pytest.fixture
def db_session():
    """İzole in-memory DB session — her test kendi taze DB'sinde, canlı veriye dokunmadan."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # in-memory DB tek bağlantıda yaşar; StaticPool şart
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def test_user(db_session):
    """Test için temiz user (izole in-memory DB'de — cleanup gerekmez)."""
    user = User(name="test_user")
    db_session.add(user)
    db_session.commit()
    yield user
