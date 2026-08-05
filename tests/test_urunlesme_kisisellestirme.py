"""
P3.5 (Wave-9) — ÜRÜNLEŞME: tek-kullanıcı DNA'sının sökülmesi.

Murat'ın direktifi (4 Ağu 2026): "kullanıcı sorununu da çözmek lazım publish etmeden…
başka kullanıcıların kendi verileri, kendi öznel kurallarını ekleyebileceği şekilde
ayarlanmış tam versiyona düzeltmek gerek."

Bu dosya, sistemin BAŞKA birinin hayatına göre sabitlenmediğini kilitler:

  BUG #166 — kullanıcıya/LLM'e giden metinlerde gerçek kişi adı ("Murat'ın borç
             serüveni", "Murat'in gerekcesi") vardı; her kullanıcıya o isimle sesleniyordu.
  BUG #167 — Türkçe normalize tablosu 'ö' harfini **Kiril 'о' (U+043E)** ile eşliyordu;
             normalize edilen kategori DB'ye böyle yazılıyor, sonraki eşleşme/gruplama
             sessizce kırılıyordu.
  BUG #168 — hesap-belirtme kontrolü BANKA MARKALARINI koda gömüyordu (`enpara`, `ziraat`);
             başka banka kullanan kullanıcının cümlesi "hesap belirsiz" sayılıyordu.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def kullanici(db):
    """Murat DEĞİL: kendi bankası ve kendi hesap adlarıyla yeni bir kullanıcı."""
    u = User(name="Zeynep")
    db.add(u)
    db.commit()
    db.add_all([
        Account(user_id=u.id, name="Papara", account_type=AccountType.cash, balance=5000.0),
        Account(user_id=u.id, name="Vakıf Kart", account_type=AccountType.credit_card,
                balance=-1200.0, credit_limit=20000.0),
    ])
    db.commit()
    return u


# ── BUG #167: Türkçe normalize saf ASCII üretmeli ─────────────────────────────

def test_turkce_normalize_ascii_uretir():
    """'ö' Kiril 'о' ile eşlenirse DB'ye bozuk kategori yazılır (sessiz veri bozulması)."""
    from app.action_executor import _cat_normalize

    out = _cat_normalize("ÖĞLE YEMEĞİ")
    assert all(ord(ch) < 128 for ch in out), (
        f"Normalize ASCII dışı karakter üretti: {[hex(ord(c)) for c in out if ord(c) >= 128]}"
    )
    assert out == "ogle yemegi"


def test_turkce_normalize_tum_harfler():
    from app.action_executor import _cat_normalize
    assert _cat_normalize("ÇĞIÖŞÜ çğıöşü") == "cgiosu cgiosu"


# ── BUG #168: hesap tespiti kullanıcının KENDİ hesap adlarını tanımalı ────────

def _propose_expense(db, user, mesaj: str):
    from app.action_executor import propose_action
    return propose_action(
        db=db, user_id=user.id, action_type="add_transaction",
        payload={"transaction_type": "expense", "amount": 200.0, "category": "market"},
        summary="200 TL market", user_message=mesaj,
    )


def test_kullanicinin_kendi_hesap_adi_taninir(db, kullanici):
    """'Papara'dan 200 TL market' → hesap BELİRTİLMİŞ sayılmalı (marka koda gömülü değil)."""
    pa = _propose_expense(db, kullanici, "Papara'dan 200 TL market aldım")
    assert pa is not None and pa.id


def test_bilinmeyen_hesap_hala_reddedilir(db, kullanici):
    """Regresyon: gerçekten hesap belirtilmemişse eski koruma (BUG #042) sürmeli."""
    with pytest.raises(ValueError, match="HESAP_BELIRSIZ"):
        _propose_expense(db, kullanici, "200 TL market aldım")


def test_jenerik_kelimeler_calismaya_devam_eder(db, kullanici):
    """'kart', 'nakit', 'hesap' gibi jenerik kelimeler her kullanıcıda çalışır."""
    for mesaj in ("kartla 200 TL market", "nakitten 200 TL market", "hesabımdan 200 TL market"):
        pa = _propose_expense(db, kullanici, mesaj)
        assert pa is not None


# ── BUG #166: kişiye özel iz statik kapısı ───────────────────────────────────

# Runtime'da kullanıcıya veya LLM'e ULAŞAN metinlerde yasak (yorum satırları kapsam dışı —
# onlar geliştirici notu; ayrı temizlik turunun konusu).
YASAK_IZLER = [
    r"\bMurat\b", r"\bEfe\b", r"\bRezan\b", r"\bİçgil\b", r"\bIcgil\b",
    r"\bEnpara\b", r"\bZiraat\b", r"\bGaranti\s+(kredi|kart|hesab)",
    # BUG #205 (H10): KİŞİSEL e-posta adresi de bir izdir. Şifre sıfırlama şablonunda
    # gerçek bir gmail adresi gömülüydü ve bu kapı onu KAÇIRIYORDU (yalnız isim/marka
    # arıyordu). Yabancı bir kullanıcının aldığı ilk resmî e-posta, ürün yerine bir
    # şahsın gmail'ine yönlendiriyordu — güven + KVKK "veri sorumlusu" beyanıyla çelişir.
    r"[\w\.\-]+@(gmail|hotmail|outlook|yahoo|yandex)\.[a-z]+",
]

# P3.5/H2 (2. tur): kapsam TÜM app/ + frontend/src — ve artık YORUMLAR DA dahil.
# Gerekçe: yorumdaki "Murat'ın 5-kredi durumu" gibi ifadeler kod okuyanı (ve bir sonraki
# değişikliği yapanı) tek-kullanıcı varsayımına geri çeker; ürün DNA'sı orada da temiz olmalı.
_TARANAN_DOSYALAR = (
    sorted((_ROOT / "app").rglob("*.py"))
    + sorted((_ROOT / "frontend" / "src").rglob("*.jsx"))
    + sorted((_ROOT / "frontend" / "src").rglob("*.js"))
)


def _kod_satirlari(path: Path) -> list[tuple[int, str]]:
    """Dosyanın TÜM satırları (yorum/docstring dahil — H2 2. tur)."""
    if "__pycache__" in str(path) or ".test." in path.name or "node_modules" in str(path):
        return []
    return list(enumerate(path.read_text(encoding="utf-8").splitlines(), 1))


def test_llm_ve_kullanici_metinlerinde_kisi_adi_yok():
    """BUG #166 kilidi: app/ ve frontend/src'de gerçek kişi adı veya banka markası olamaz.

    Bu kapı olmasa, bir sonraki prompt düzenlemesinde isim geri sızar ve yeni kullanıcıya
    'Murat'ın borç serüveni' diye seslenir.
    """
    ihlal = []
    for path in _TARANAN_DOSYALAR:
        for lineno, line in _kod_satirlari(path):
            for kalip in YASAK_IZLER:
                if re.search(kalip, line):
                    ihlal.append(f"{path.relative_to(_ROOT).as_posix()}:{lineno}: {line.strip()[:110]}")
    assert not ihlal, (
        "Kişiye özel iz (kullanıcıya/LLM'e ulaşan metinde) — jenerikleştir:\n" + "\n".join(ihlal)
    )
