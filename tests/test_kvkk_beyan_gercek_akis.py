"""
D10 (BUG #231) — YAYINLANAN KVKK / VERİ-İŞLEYEN BEYANI GERÇEK VERİ AKIŞIYLA UYUŞMUYORDU.

Beyan (kullanıcıya `/api/legal/veri-isleyenler` ile SUNULUYOR, rıza kapısında okunuyor):
    "Gönderilmeyenler: ... **ham işlem listesi** (yalnız türetilmiş toplamlar ve
     kullanıcının kendi yazdığı metin gider)."
KVKK v2 §4 aktarımı "cockpit özeti: bakiyeler, borç/gelir toplamları, kırmızı çizgi
metinleriniz ve yazdığınız mesaj" ile sınırlıyordu.

Gerçek (denetimin canlı çalıştırdığı `_build_context_message` çıktısı):
    ## SON İŞLEMLER
      - 2026-08-05: -2.500,00 TL (saglik) — Psikiyatri kontrol - Dr. Ayse Kaya
    ## Yaklaşan Tahsilatlar
      - ... Ahmet Yilmaz → 5.000,00 TL (dugun borcu)
    ## Hesaplar
      - id=1 [cash] Garanti Vadesiz 1234

Yani: ham işlem listesi + **kullanıcının serbest metin açıklamaları** + **üçüncü kişilerin
adları** + hesap adları yurt dışındaki LLM sağlayıcısına gidiyor. İşlem açıklaması pratikte
ÖZEL NİTELİKLİ kişisel veri taşır (sağlık: "psikiyatri kontrol", inanç: "cemaat bağışı").
KVKK m.6 (özel nitelikli) ve m.9 (yurt dışına aktarım) AYRI ve BİLGİLENDİRİLMİŞ açık rıza
ister; yanlış kapsamla alınan rıza sakattır. Ayrıca alacak kaydındaki üçüncü kişinin
adı-tutarı, o kişi uygulamanın kullanıcısı bile değilken aktarılıyor.

Bu dosya "belgeyi düzelttik" ile yetinmez (L8/L9): beyanı GERÇEK AKIŞA bağlar. Koç bağlamına
yeni bir alan eklenirse ve beyan güncellenmezse kapı KIRILIR.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.coach import _build_context_message
from app.models import (
    Base, User, Account, AccountType, Transaction, TransactionType,
    PersonalDebt, DebtDirection, MasterCheckpoint, CheckpointType,
)

KOK = Path(__file__).resolve().parent.parent
ENVANTER = KOK / "docs" / "legal" / "veri-isleyen-envanteri.md"

# Bağlama giren her veri SINIFI için: (işaret metni, beyanda aranacak anahtar kelimeler)
_SINIFLAR = [
    ("HESAP-ADI-ISARETI", ["hesap ad"]),
    ("ACIKLAMA-ISARETI", ["açıklama", "serbest metin"]),
    ("UCUNCU-KISI-ISARETI", ["üçüncü kişi", "karşı taraf"]),
]


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def zengin_kullanici(db):
    """Her veri sınıfı için ayırt edici bir işaret taşıyan gerçekçi kullanıcı."""
    u = User(name="murat", email="gizli-eposta@ornek.com",
             password_hash="$2b$12$SIFREHASHISARETI0000000000000000000000000000000000000")
    db.add(u)
    db.commit()

    hesap = Account(user_id=u.id, name="HESAP-ADI-ISARETI", account_type=AccountType.cash,
                    balance=25000.0)
    db.add(hesap)
    db.commit()

    bugun = date.today()
    db.add(Transaction(
        user_id=u.id, account_id=hesap.id, amount=-2500.0,
        transaction_type=TransactionType.expense, category="saglik",
        description="ACIKLAMA-ISARETI Psikiyatri kontrol",
        transaction_date=datetime.combine(bugun, datetime.min.time()),
    ))
    db.add(PersonalDebt(
        user_id=u.id, counterparty="UCUNCU-KISI-ISARETI", amount=5000.0,
        direction=DebtDirection.receivable, due_date=bugun + timedelta(days=3),
        description="dugun borcu",
    ))
    db.add(MasterCheckpoint(
        user_id=u.id, title="KIRMIZI-CIZGI-ISARETI",
        description="KIRMIZI-CIZGI-ISARETI aciklamasi",
        checkpoint_type=CheckpointType.rule, priority=1, is_active=True,
    ))
    db.commit()
    return u


@pytest.fixture
def baglam(db, zengin_kullanici) -> str:
    """LLM sağlayıcısına fiilen giden metin."""
    metin, _ = _build_context_message(db, zengin_kullanici.id)
    return metin


# ============================================================
# 1. GERÇEKTE NE GİDİYOR (kapsam tabanı — L11)
# ============================================================

@pytest.mark.parametrize("isaret,_anahtarlar", _SINIFLAR)
def test_isaretler_baglamda_gercekten_gorunuyor(baglam, isaret, _anahtarlar):
    """Kapı tabanı: işaret bağlamda görünmüyorsa alttaki beyan kapısı boş koşar."""
    assert isaret in baglam, (
        f"{isaret} koç bağlamında bulunamadı — ya akış değişti ya fixture bozuldu; "
        "her iki halde de beyan kapısı körleşir, önce bu düzeltilmeli"
    )


# ============================================================
# 2. BEYAN GERÇEĞİ SÖYLÜYOR MU (asıl kapı)
# ============================================================

@pytest.mark.parametrize("isaret,anahtarlar", _SINIFLAR)
def test_giden_her_veri_sinifi_beyanda_yazili(baglam, isaret, anahtarlar):
    """Bağlama giren her veri sınıfı yayınlanan envanterde AÇIKÇA sayılmalı (KVKK m.10)."""
    assert isaret in baglam  # (1)'in güvencesi; burada bağlamı yeniden ölçmüyoruz
    metin = ENVANTER.read_text(encoding="utf-8").lower()
    assert any(a in metin for a in anahtarlar), (
        f"'{isaret}' sınıfındaki veri LLM'e gidiyor ama veri-işleyen envanterinde "
        f"({anahtarlar}) beyan edilmiyor — rıza yanlış kapsamla alınıyor"
    )


def test_beyan_ham_islem_listesi_gonderilmiyor_demiyor():
    """Denetimin yakaladığı YANLIŞ cümle geri gelmemeli."""
    metin = ENVANTER.read_text(encoding="utf-8").lower()
    assert not re.search(r"gönderilmeyenler[^#]*ham işlem listesi", metin, re.S), (
        "Envanter hâlâ 'ham işlem listesi gönderilmez' diyor — bu beyan YANLIŞ "
        "(## SON İŞLEMLER bloğu bağlamda literal olarak gidiyor)"
    )


def test_beyan_ozel_nitelikli_veri_uyarisi_iceriyor():
    """Serbest metin açıklama sağlık/inanç verisi taşıyabilir — KVKK m.6 uyarısı şart."""
    metin = ENVANTER.read_text(encoding="utf-8").lower()
    assert "özel nitelikli" in metin, (
        "Envanterde özel nitelikli veri uyarısı yok — kullanıcı açıklamaya 'psikiyatri "
        "kontrol' yazdığında bunun yurt dışına gittiğini bilmiyor"
    )


def test_beyan_ucuncu_kisi_verisi_uyarisi_iceriyor():
    """Alacak/borç karşı tarafı uygulamanın kullanıcısı bile değil; adı aktarılıyor."""
    metin = ENVANTER.read_text(encoding="utf-8").lower()
    assert "üçüncü kişi" in metin


# ============================================================
# 3. GERÇEKTEN GİTMEYENLER (beyanın diğer yarısı doğru mu)
# ============================================================

@pytest.mark.parametrize("sizmamali", [
    "SIFREHASHISARETI",     # şifre hash'i
    "gizli-eposta@ornek.com",  # e-posta adresi
])
def test_gitmediği_beyan_edilenler_gercekten_gitmiyor(baglam, sizmamali):
    """Beyanın 'gönderilmeyenler' yarısı da testle korunmalı (aksi halde bir gün sızar)."""
    assert sizmamali not in baglam, \
        f"{sizmamali!r} koç bağlamına sızmış — beyan bunun gönderilmediğini söylüyor"


# ============================================================
# 4. RIZA METNİ ↔ ENVANTER TUTARLILIĞI
# ============================================================

def test_riza_metni_guncel_surum_ile_ayni_kapsami_anlatiyor():
    """Rıza metni aktarım kapsamını envanterle aynı şekilde anlatmalı (iki belge çelişmesin)."""
    from app.routers.auth import KVKK_CONSENT_VERSION
    yol = KOK / "docs" / "legal" / f"kvkk-consent-{KVKK_CONSENT_VERSION}.md"
    assert yol.exists(), f"Yayınlanan rıza sürümü {KVKK_CONSENT_VERSION} için metin yok: {yol}"
    metin = yol.read_text(encoding="utf-8").lower()
    for beklenen in ("işlem açıklama", "üçüncü kişi", "özel nitelikli"):
        assert beklenen in metin, (
            f"Rıza metni ({KVKK_CONSENT_VERSION}) '{beklenen}' kapsamını anlatmıyor — "
            "kullanıcı neye rıza verdiğini bilmiyor"
        )


# ============================================================
# 5. RIZA TAZELEME — sürüm yükseltmek tek başına yetmez (L8)
# ============================================================

def test_eski_surumlu_kullanici_yeniden_onay_ister(db):
    """v2 onaylı kullanıcı v3 kapsamını onaylamamıştır — arayüz bunu görebilmeli."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.dependencies import get_db, get_current_user
    from app.routers.auth import KVKK_CONSENT_VERSION

    u = User(name="eski", email="eski@x.com", kvkk_consent_version="v2")
    db.add(u)
    db.commit()

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: u
    try:
        c = TestClient(app)
        r = c.get("/api/users/me/kvkk-consent")
        assert r.status_code == 200, r.text
        assert r.json()["yeniden_onay_gerekli"] is True
        assert r.json()["guncel_surum"] == KVKK_CONSENT_VERSION

        r2 = c.post("/api/users/me/kvkk-consent")
        assert r2.status_code == 200, r2.text
        assert r2.json()["yeniden_onay_gerekli"] is False

        db.refresh(u)
        assert u.kvkk_consent_version == KVKK_CONSENT_VERSION
        assert u.kvkk_consent_at is not None

        assert c.get("/api/users/me/kvkk-consent").json()["yeniden_onay_gerekli"] is False
    finally:
        app.dependency_overrides.clear()


def test_sunulan_kvkk_metni_onaylanan_surumle_ayni(db):
    """Kullanıcıya `/api/legal/kvkk` ile SUNULAN metin, onayladığı sürümün metni olmalı.

    Dosya adı router'da sabit yazılıydı: sürüm yükseltilince kullanıcı hâlâ ESKİ metni
    okuyordu (onay verdiği kapsam ile okuduğu kapsam ayrışıyordu).
    """
    from app.routers.legal import BELGELER
    from app.routers.auth import KVKK_CONSENT_VERSION
    dosya, _ = BELGELER["kvkk"]
    assert dosya == f"kvkk-consent-{KVKK_CONSENT_VERSION}.md", (
        f"Sunulan metin {dosya}, onaylanan sürüm {KVKK_CONSENT_VERSION} — ayrışma"
    )
