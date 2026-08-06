"""
BUG #241 SINIF TARAMASI (L11) — VARSAYILAN HESAP SEÇİMİ TEK KAYNAKTAN GEÇER.

Kullanıcı hesap belirtmediğinde parayı bir yere yazan beş yol vardı; **beşi de kendi
sorgusunu yazıyordu** ve hiçbiri EMANET hesabı dışlamıyordu:

    action_executor._execute_mark_debt_paid   (borç/alacak kapanışı)
    action_executor._execute_pay_credit_card  (kart ödemesinin nakit ayağı)
    routers/transactions._normalize           (hesapsız işlem → varsayılan hesap)
    routers/incomes.trigger-due               (düzenli gelir aksiyonunun hedefi)
    simulation_engine._find_default_cash_account (önizleme)

Zarar iki yönlü: (a) MC1 — emanet bakiyesine otomatik yol dokunamaz — ama seçiciler
emanet hesabı varsayılan yapabiliyordu; executor'ın guard'ı yüzünden ya işlem
bloklanıyor (sessiz çıkmaz sokak: trigger-due her onayda hata) ya da guard'sız yollarda
emanet para gerçekten hareket ediyordu. (b) Üç seçici SIRASIZDI (`.first()`), yani aynı
olayın uygulanması ve geri sarılması farklı hesaplara düşebilirdi (BUG #241 simetrisi).

Bu kapı, yeni bir "varsayılan hesap" seçicisinin sessizce eklenmesini engeller.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.account_rules import varsayilan_hesap, varsayilan_nakit_hesap
from app.models import Base, User, Account, AccountType

KOK = Path(__file__).resolve().parent.parent
APP = KOK / "app"

# Tarama "TEK hesap seçen" yolları arar: `account_type == AccountType.X` filtresi + aynı
# sorgu penceresinde `.first()`. Toplama yapanlar (`.all()` / sum) kapsam DIŞI — onlar hesap
# seçmez. Açık id ile arama (`Account.id == ...`) da seçim değildir: kullanıcı zaten seçmiştir.
# Kapsama girip tek kaynaktan geçmeyen bir yol varsa gerekçeli muaf olmalı (dosyada
# `# varsayilan-hesap-exempt: <gerekçe>` satırı şart).
# Şu an BOŞ: her seçici tek kaynaktan geçiyor (tek kaynağın kendisi `== tip` ile yazdığı
# için taramaya takılmaz). Yeni bir muafiyet eklenecekse gerekçesi koda da yazılmalı.
_MUAF: dict[str, str] = {}

_SECICI_DESEN = re.compile(r"account_type\s*==\s*AccountType\.")
_PENCERE = 6


def _varsayilan_hesap_secen_dosyalar() -> list[str]:
    """`account_type ==` filtresiyle TEK hesap seçen (.first()) app/ dosyaları."""
    bulunan = []
    for yol in sorted(APP.rglob("*.py")):
        satirlar = yol.read_text(encoding="utf-8").splitlines()
        for i, satir in enumerate(satirlar):
            if not _SECICI_DESEN.search(satir):
                continue
            pencere = "\n".join(satirlar[max(0, i - _PENCERE): i + _PENCERE + 1])
            if ".first()" not in pencere:
                continue
            if re.search(r"Account\.id\s*==", pencere):
                continue    # açık id ile arama — seçim değil
            bulunan.append(yol.relative_to(KOK).as_posix())
            break
    return bulunan


# ============================================================
# 1. KAPSAM TABANI (L11 — kapı kaç yolu ölçüyor)
# ============================================================

def _tek_kaynagi_kullanan_dosyalar() -> list[str]:
    """`varsayilan_hesap(` / `varsayilan_nakit_hesap(` ÇAĞIRAN app/ dosyaları (tanım hariç)."""
    bulunan = []
    for yol in sorted(APP.rglob("*.py")):
        if yol.name == "account_rules.py":
            continue
        metin = yol.read_text(encoding="utf-8")
        if re.search(r"varsayilan_(nakit_)?hesap\s*\(", metin):
            bulunan.append(yol.relative_to(KOK).as_posix())
    return bulunan


def test_kapsam_tabani_tek_kaynak_gercekten_kullaniliyor():
    """L23 tuzağı: bypass taraması boş liste döndürünce kapı 'her şey yolunda' der.
    Kapının bir şeyi ÖLÇTÜĞÜNÜ, tek kaynağın gerçek çağrı sayısıyla kanıtla."""
    kullananlar = _tek_kaynagi_kullanan_dosyalar()
    assert len(kullananlar) >= 4, (
        f"Varsayılan hesap tek kaynağını yalnız {len(kullananlar)} dosya kullanıyor "
        f"({kullananlar}) — seçiciler yeniden dağılmış ya da tarama bozulmuş olabilir"
    )


def test_hicbir_yol_kendi_varsayilan_hesap_sorgusunu_yazmiyor():
    """Yeni bir seçici eklenince MC1 (emanet) dışlaması sessizce atlanamaz."""
    eksikler = []
    for yol in _varsayilan_hesap_secen_dosyalar():
        metin = (KOK / yol).read_text(encoding="utf-8")
        if yol in _MUAF and re.search(r"#\s*varsayilan-hesap-exempt:\s*\S+", metin):
            continue
        eksikler.append(yol)
    assert not eksikler, (
        f"Bu dosyalar tek hesabı kendi sorgusuyla seçiyor (app/account_rules'tan geçmiyor ve "
        f"gerekçeli muaf da değil): {eksikler}. Emanet dışlaması (MC1) burada delinir."
    )


def test_muaf_listesi_bayat_degil():
    mevcut = set(_varsayilan_hesap_secen_dosyalar())
    bayat = sorted(set(_MUAF) - mevcut)
    assert not bayat, f"Muaf listesinde artık hesap seçmeyen dosyalar var: {bayat}"


def test_tarama_gercek_bir_bypass_i_yakaliyor():
    """Taramanın kendisi ölçülür (L11): elle yazılmış bir seçici deseni yakalanmalı."""
    ornek = (
        "acc = (db.query(Account)\n"
        "       .filter(Account.user_id == user_id,\n"
        "               Account.account_type == AccountType.cash)\n"
        "       .first())\n"
    )
    satirlar = ornek.splitlines()
    yakalandi = any(
        _SECICI_DESEN.search(s)
        and ".first()" in "\n".join(satirlar[max(0, i - _PENCERE): i + _PENCERE + 1])
        for i, s in enumerate(satirlar)
    )
    assert yakalandi, "Tarama deseni elle yazılmış varsayılan-hesap sorgusunu göremiyor"


def test_simulasyon_secicisi_emaneti_disliyor():
    """Sim ayrı bir dünyada (RAM) çalışır, sorgu yazamaz — parite metin seviyesinde kilitlenir."""
    metin = (APP / "simulation_engine.py").read_text(encoding="utf-8")
    govde = metin.split("def _find_default_cash_account")[1].split("\ndef ")[0]
    assert "is_emanet" in govde, (
        "Sim varsayılan nakit hesabı emaneti dışlamıyor → önizleme, gerçek executor'ın "
        "bloklayacağı bir sonucu gösterir (MC1 + sim↔executor paritesi)."
    )


# ============================================================
# 2. DAVRANIŞ — tek kaynağın sözleşmesi
# ============================================================

@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="test_user"))
    s.commit()
    yield s
    s.close()


def _acc(db, **kw):
    a = Account(user_id=1, name=kw.pop("name", "hesap"),
                account_type=kw.pop("account_type", AccountType.cash),
                balance=kw.pop("balance", 0.0), **kw)
    db.add(a); db.commit(); db.refresh(a)
    return a


def test_emanet_hesap_varsayilan_olamaz(db):
    _acc(db, name="Emanet", is_emanet=True, balance=20000.0)
    kendi = _acc(db, name="Enpara", balance=1000.0)
    assert varsayilan_nakit_hesap(db, 1).id == kendi.id


def test_secim_deterministik_en_kucuk_id(db):
    ilk = _acc(db, name="Enpara")
    _acc(db, name="Ziraat")
    assert varsayilan_nakit_hesap(db, 1).id == ilk.id


def test_tip_filtresi_calisir(db):
    _acc(db, name="Enpara", account_type=AccountType.cash)
    kart = _acc(db, name="Bonus", account_type=AccountType.credit_card)
    assert varsayilan_hesap(db, 1, tip=AccountType.credit_card).id == kart.id


def test_uygun_hesap_yoksa_none(db):
    _acc(db, name="Emanet", is_emanet=True)
    assert varsayilan_nakit_hesap(db, 1) is None


def test_baska_kullanicinin_hesabi_secilmez(db):
    db.add(User(id=2, name="baskasi")); db.commit()
    yabanci = Account(user_id=2, name="Yabancı", account_type=AccountType.cash, balance=5000.0)
    db.add(yabanci); db.commit()
    assert varsayilan_nakit_hesap(db, 1) is None
