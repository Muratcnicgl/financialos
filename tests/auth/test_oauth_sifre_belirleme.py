"""
BUG #233 — GOOGLE ILE ACILAN HESABIN SIFRE ALMASININ HICBIR YOLU YOKTU.

Kullanici bildirimi (denetim disi, gercek kullanim): "Google ile giris yaptigim icin
Hesap bolumunde e-posta dogru gorunuyor ama sifre kismi 'eski sifreni gir, yeni sifre
belirle' mantiginda — benim eski sifrem yok."

Tespit edilen tam tablo (uc kapali kapi, tek kok: 'her hesabin sifresi vardir' varsayimi):

  1. `POST /auth/change-password` OAuth hesabinda 400 doner ("sifresi yok") — DOGRU davranis,
     ama alternatif SUNULMUYOR. Hesap paneli formu yine de "Mevcut sifren" ZORUNLU alaniyla
     ciziyordu: kullanicinin dolduramayacagi bir form (cikmaz sokak).
  2. `POST /auth/password-reset-request` sifresi OLMAYAN kullaniciya **hic e-posta gondermiyordu**
     (`if not user or not user.password_hash: return generic`). Yani "sifremi unuttum" da kapali.
     Uygulama kullaniciya "e-posta kayitliysa baglanti gonderildi" DIYOR ama gondermiyor —
     kullanici gelmeyecek bir postayi bekliyor.
  3. Sonuc: hesap TEK bir dis saglayiciya (Google) baglanmis durumda. Google erisimi kaybolursa
     (hesap kapanmasi, OAuth istemcisinin iptali/yanlis yapilandirilmasi, saglayici arizasi)
     kullanicinin TUM finansal verisi kalici olarak erisilemez hale geliyordu. Uygulamanin
     kendi kurtarma yolu (e-posta ile sifirlama) bu hesap sinifinda calismiyordu.

Cozumun guvenlik gerekcesi (neden oturum yeterli):
  `DELETE /api/users/me` (tum veriyi siler) ve `GET /api/users/me/export` (tum finansal
  veriyi doker) SADECE gecerli oturum ister — sifre sormaz. Yani oturum bu uygulamada zaten
  tam-yetki kimlik kanitidir. Sifresi OLMAYAN bir hesapta dogrulanacak "mevcut sifre" de
  yoktur. Bu yuzden `POST /auth/set-password` oturum sahibine acilir; buna karsilik sifresi
  OLAN hesapta KESINLIKLE reddedilir (aksi halde `change-password`'un mevcut-sifre
  dogrulamasi bu uctan atlatilirdi — asil risk budur, testi asagida).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.routers.auth as auth_mod
from app import auth as _auth
from app.dependencies import get_db
from app.main import app
from app.models import Base, User

OAUTH_EPOSTA = "google-kullanici@ornek.com"
SIFRELI_EPOSTA = "klasik@ornek.com"
MEVCUT_SIFRE = "Klasik-Sifre-123!"
YENI_SIFRE = "Belirlenen-Sifre-456!"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-do-not-use-in-prod-0123456789")
    monkeypatch.setenv("AUTH_ENABLED", "1")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "SMTP_FROM"):
        monkeypatch.delenv(k, raising=False)   # SMTP yok → dev token dönsün
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    # Google ile açılmış hesap: password_hash YOK (oauth callback böyle yaratır)
    s.add(User(name="google kullanicisi", email=OAUTH_EPOSTA, password_hash=None,
               oauth_provider="google", is_active=True))
    # Klasik hesap: şifresi var
    s.add(User(name="klasik", email=SIFRELI_EPOSTA,
               password_hash=_auth.hash_password(MEVCUT_SIFRE), is_active=True))
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    auth_mod._RATE.clear()
    c = TestClient(app)
    yield c
    app.dependency_overrides.clear()


def _basliklar(db, eposta: str) -> dict:
    u = db.query(User).filter(User.email == eposta).first()
    return {"Authorization": f"Bearer {_auth.create_access_token(u.id, int(u.token_version or 0))}"}


def _giris(client, eposta: str, sifre: str):
    return client.post("/api/auth/login", json={"email": eposta, "password": sifre})


# ============================================================
# 1. KULLANICININ BILDIRDIGI CIKMAZ SOKAK
# ============================================================

def test_233_oauth_kullanicisi_sifre_belirleyebilir(client, db):
    """Ana senaryo: 'eski sifrem yok' → mevcut sifre ISTEMEYEN bir yol olmali."""
    r = client.post("/api/auth/set-password", json={"new_password": YENI_SIFRE},
                    headers=_basliklar(db, OAUTH_EPOSTA))
    assert r.status_code == 200, r.text

    # Artık Google OLMADAN da girebilmeli — kilitlenme riski biten asıl kazanç
    assert _giris(client, OAUTH_EPOSTA, YENI_SIFRE).status_code == 200


def test_233_sifre_belirlenince_cagirana_gecerli_token_verilir(client, db):
    """Kullanıcı kendi işlemiyle dışarı atılmamalı (BUG #190 ile aynı ilke)."""
    r = client.post("/api/auth/set-password", json={"new_password": YENI_SIFRE},
                    headers=_basliklar(db, OAUTH_EPOSTA))
    yeni_access = r.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {yeni_access}"}).status_code == 200


def test_233_sifre_belirleme_diger_oturumlari_dusurur(client, db):
    """token_version artmalı: aynı anda açık başka bir oturum varsa ölür."""
    eski_baslik = _basliklar(db, OAUTH_EPOSTA)
    assert client.get("/api/auth/me", headers=eski_baslik).status_code == 200

    client.post("/api/auth/set-password", json={"new_password": YENI_SIFRE},
                headers=_basliklar(db, OAUTH_EPOSTA))

    assert client.get("/api/auth/me", headers=eski_baslik).status_code == 401


# ============================================================
# 2. ASIL RISK: bu uc, mevcut-sifre dogrulamasini ATLATMAK icin kullanilamaz
# ============================================================

def test_233_sifresi_olan_hesap_set_password_ile_sifre_degistiremez(client, db):
    """Çalınmış bir oturum, mevcut şifreyi BİLMEDEN şifreyi ele geçirememeli.

    Bu kapı olmadan `set-password` `change-password`'un tüm doğrulamasını anlamsız kılardı.
    """
    r = client.post("/api/auth/set-password", json={"new_password": YENI_SIFRE},
                    headers=_basliklar(db, SIFRELI_EPOSTA))
    assert r.status_code == 400, (
        f"Şifresi OLAN hesapta set-password kabul edildi ({r.status_code}) — "
        f"mevcut-şifre doğrulaması atlatılabilir"
    )
    # Eski şifre hâlâ geçerli, yenisi geçersiz
    assert _giris(client, SIFRELI_EPOSTA, MEVCUT_SIFRE).status_code == 200
    assert _giris(client, SIFRELI_EPOSTA, YENI_SIFRE).status_code == 401


def test_233_set_password_kimliksiz_reddedilir(client, db):
    r = client.post("/api/auth/set-password", json={"new_password": YENI_SIFRE})
    assert r.status_code == 401


def test_233_set_password_sifre_politikasina_tabi(client, db):
    """BUG #187 politikası burada da geçerli — yeni yol zayıf şifre kapısı açmamalı."""
    r = client.post("/api/auth/set-password", json={"new_password": "sifre123"},
                    headers=_basliklar(db, OAUTH_EPOSTA))
    assert r.status_code == 422, r.text


def test_233_sifre_belirledikten_sonra_degistirme_normal_akisa_doner(client, db):
    """Şifre belirlendikten sonra hesap 'klasik' olur: değiştirmek için mevcut şifre gerekir."""
    client.post("/api/auth/set-password", json={"new_password": YENI_SIFRE},
                headers=_basliklar(db, OAUTH_EPOSTA))

    ikinci = "Ikinci-Sifre-789!"
    # Mevcut şifre olmadan ikinci kez belirlenemez
    assert client.post("/api/auth/set-password", json={"new_password": ikinci},
                       headers=_basliklar(db, OAUTH_EPOSTA)).status_code == 400
    # Ama normal değiştirme yolu artık çalışır
    r = client.post("/api/auth/change-password",
                    json={"current_password": YENI_SIFRE, "new_password": ikinci},
                    headers=_basliklar(db, OAUTH_EPOSTA))
    assert r.status_code == 200, r.text


# ============================================================
# 3. KILITLENME KAPISI: "sifremi unuttum" OAuth hesabinda da calismali
# ============================================================

def test_233_sifresiz_hesaba_sifirlama_baglantisi_gonderilir(client, db):
    """Google erişimi kaybolursa uygulamanın KENDİ kurtarma yolu çalışmalı.

    Önceden `password-reset-request` şifresi olmayan kullanıcıda sessizce hiçbir şey
    yapmıyordu: kullanıcı "bağlantı gönderildi" mesajını okuyup gelmeyen postayı bekliyordu.
    """
    r = client.post("/api/auth/password-reset-request", json={"email": OAUTH_EPOSTA})
    assert r.status_code == 200
    token = r.json().get("_dev_token")
    assert token, "şifresiz hesaba sıfırlama bağlantısı ÜRETİLMEDİ — hesap kurtarılamaz"

    r2 = client.post("/api/auth/password-reset-confirm",
                     json={"token": token, "new_password": YENI_SIFRE})
    assert r2.status_code == 200, r2.text
    assert _giris(client, OAUTH_EPOSTA, YENI_SIFRE).status_code == 200


def test_233_kayitsiz_adres_yaniti_ayirt_edilemez(client, db):
    """L6/BUG #202: kurtarma yolu açılırken kullanıcı-enumerasyonu SIZDIRILMAMALI.

    Kayıtsız adres ile şifresiz kayıtlı adresin yanıtı gövde olarak ayırt edilebilir
    olmamalı (dev token'ı hariç — o yalnız non-prod kolaylığı ve zaten kayıtlıya özgü;
    burada asıl kontrol: mesaj metni ve durum kodu aynı).
    """
    a = client.post("/api/auth/password-reset-request", json={"email": OAUTH_EPOSTA})
    b = client.post("/api/auth/password-reset-request", json={"email": "yok@ornek.com"})
    assert a.status_code == b.status_code == 200
    assert a.json()["message"] == b.json()["message"]


# ============================================================
# 4. ARAYUZUN DOGRU FORMU CIZEBILMESI ICIN SOZLESME
# ============================================================

def test_233_me_hesabin_sifresi_olup_olmadigini_bildirir(client, db):
    """Panel doğru formu çizebilmek için bunu BİLMEK zorunda (cıkmaz sokağın kökü).

    `oauth_provider` bu soruya cevap DEĞİLDİR: e-posta+şifre ile açılmış bir hesap sonradan
    Google ile giriş yapınca da o alan dolar — ama şifresi durur.
    """
    oauth_me = client.get("/api/auth/me", headers=_basliklar(db, OAUTH_EPOSTA)).json()
    klasik_me = client.get("/api/auth/me", headers=_basliklar(db, SIFRELI_EPOSTA)).json()

    assert oauth_me["has_password"] is False
    assert klasik_me["has_password"] is True


def test_233_me_sifre_hashini_asla_dokmez(client, db):
    """Bayrak türetilmiş olmalı — hash'in kendisi API'ye sızmamalı (KVKK/D26 sınıfı)."""
    govde = client.get("/api/auth/me", headers=_basliklar(db, SIFRELI_EPOSTA)).json()
    assert "password_hash" not in govde
    assert MEVCUT_SIFRE not in str(govde)
