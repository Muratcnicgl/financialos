"""
B1 / BUG #279 — KAPALI BETA DAVET KAPISININ **KAPSAMI**.

Premis düzeltmesi (11 Ağu 2026): kapalı beta charter'ının taslağı "allowlist yok" diyordu;
ölçüm bunu çürüttü — `app/beta_access.py` var, production'da fail-closed, hem klasik kayıt
hem OAuth kapıdan geçiyor (BUG #199 + BUG #226/D05) ve davranış testleri de var
(`tests/test_beta_invite_access.py`, `tests/auth/test_oauth_davet_kapisi.py`).

Eksik olan DAVRANIŞ değil KAPSAM ölçümüydü (L11/H25 — bu projede en az dört kapı böyle ölü
bulundu): hiçbir şey "hesap yaratabilen KAÇ yol var ve kaçı kapıdan geçiyor?" sorusunu
sormuyordu. Dördüncü bir kayıt yolu eklendiği gün süit yeşil kalır, kapalı beta sessizce
açılırdı. Bu dosya o soruyu KAYNAKTAN sorar.

Kilitlenen üç sözleşme:
  1. `User(...)` satırı yaratan her yol BİLİNİR ve her birinin kapısı YAZILIDIR; yeni yol
     doğduğu anda bu kapı kırmızıya döner (kapsam tabanı = 3).
  2. Kayıt DIŞINDAKİ tüketiciler (workspace daveti) `hesap_acabilir_mi()` ile sorar;
     allowlist dışı adrese sessizce davet gitmez (BUG #279).
  3. `BetaInvite` sorgusu router katmanında YAZILMAZ — kapı kuralı `beta_access`'tedir
     (L46: kopya değil içe aktarma). Tarama AST'dedir, ham metin değil: yorum satırındaki
     "BetaInvite" kelimesi kapıyı tetiklemez, gerçek kullanım tetikler (BUG #273 dersi).
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Workspace, WorkspaceMembership, WorkspaceRole
from app.beta_access import davet_olustur, hesap_acabilir_mi, eposta_daveti_bul

APP_KOK = Path(__file__).resolve().parents[1] / "app"


# ══════════════════════════════════════════════════════════════════════════
# 1. KAPSAM: hesap yaratabilen her yol biliniyor mu?
# ══════════════════════════════════════════════════════════════════════════

# Yol → (kapı fonksiyonu, gerekçe). Yeni bir yol eklenirse BURAYA da yazılmalı;
# yazılmazsa `test_kapsam_tabani` kırmızıya döner. Liste "muafiyet" değil ENVANTERDİR:
# her satır bir kapı ADI taşır ve o kapının fiilen çağrıldığı ayrıca doğrulanır.
BEKLENEN_YOLLAR: dict[tuple[str, str], tuple[str, str]] = {
    ("routers/auth.py", "register"): (
        "invite_required",
        "Klasik kayıt: davet KODU ile (BUG #199).",
    ),
    ("routers/auth.py", "oauth_callback"): (
        "invite_required",
        "OAuth: kod alanı yok, kapı E-POSTA eşleşmeli davetle kurulur (BUG #226/D05).",
    ),
    ("routers/user.py", "create_user"): (
        "auth_enabled",
        "Tek-kullanıcı kurulum kalıntısı; AUTH açıkken 403 döner (BUG #174). "
        "Canlı ortam AUTH_ENABLED=true olduğu için bu yol prod'da KAPALIDIR.",
    ),
}


def _kullanici_yaratan_yollar() -> dict[tuple[str, str], ast.FunctionDef]:
    """`User(...)` çağrısı yapan (dosya, fonksiyon) çiftlerini KAYNAKTAN çıkarır."""
    bulunan: dict[tuple[str, str], ast.FunctionDef] = {}
    for yol in sorted(APP_KOK.rglob("*.py")):
        agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
        for dugum in ast.walk(agac):
            if not isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for alt in ast.walk(dugum):
                if not isinstance(alt, ast.Call):
                    continue
                f = alt.func
                ad = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
                if ad == "User":
                    rel = yol.relative_to(APP_KOK).as_posix()
                    bulunan[(rel, dugum.name)] = dugum
                    break
    return bulunan


def test_kapsam_tabani_hesap_yaratan_yol_sayisi():
    """Hesap yaratabilen yol sayısı tabanın ÜSTÜNE çıkarsa kapı kırmızıya döner.

    Bu, kapının kendisidir: yeni bir kayıt yolu eklendiğinde davranış testleri onu
    görmez (kendi uçlarını test ederler), bu kapı görür.
    """
    bulunan = set(_kullanici_yaratan_yollar())
    beklenen = set(BEKLENEN_YOLLAR)

    yeni = bulunan - beklenen
    assert not yeni, (
        "Hesap yaratabilen YENİ yol(lar) bulundu ama davet kapısı envanterine yazılmamış: "
        f"{sorted(yeni)}. Her yol ya `beta_access` kapısından geçmeli ya da gerekçesi "
        "BEKLENEN_YOLLAR'a yazılmalı."
    )
    kayip = beklenen - bulunan
    assert not kayip, (
        f"Envanterdeki yol(lar) kaynakta yok: {sorted(kayip)}. Yol kaldırıldıysa envanter "
        "de güncellenmeli (ölü envanter, kapının kapsamını sessizce küçültür)."
    )
    assert len(bulunan) == 3, f"Kapsam tabanı 3 iken {len(bulunan)} bulundu: {sorted(bulunan)}"


@pytest.mark.parametrize("anahtar", sorted(BEKLENEN_YOLLAR))
def test_her_yol_kapisini_fiilen_cagiriyor(anahtar):
    """Envanterde kapı ADI yazmak yetmez — o kapı fonksiyonun İÇİNDE çağrılmalı."""
    kapi_adi, gerekce = BEKLENEN_YOLLAR[anahtar]
    dugum = _kullanici_yaratan_yollar()[anahtar]
    cagrilan = {
        (a.func.id if isinstance(a.func, ast.Name) else a.func.attr)
        for a in ast.walk(dugum) if isinstance(a, ast.Call)
        and isinstance(a.func, (ast.Name, ast.Attribute))
    }
    assert kapi_adi in cagrilan, (
        f"{anahtar[0]}::{anahtar[1]} kullanıcı yaratıyor ama `{kapi_adi}()` çağırmıyor. "
        f"Envanter gerekçesi: {gerekce}"
    )


def test_router_katmani_betainvite_sorgulamaz():
    """Kapı kuralı tek kaynakta kalsın: router'lar `BetaInvite`'ı doğrudan kullanamaz.

    AST taraması — yorum satırındaki 'BetaInvite' kelimesi kapıyı TETİKLEMEZ (BUG #273'te
    ham metin taramasının kör noktası ölçülmüştü).

    KAPININ KENDİ KÖR NOKTASI (mutasyon M6 buldu): ilk yazımda yalnız `Name`/`Attribute`
    düğümlerine bakılıyordu; `from app.models import BetaInvite` bir **ImportFrom**'dur ve
    kapıdan sessizce geçiyordu — yani kopya geri gelse kapı yeşil kalırdı. İçe aktarma da
    taranır.
    """
    ihlaller: list[str] = []
    for yol in sorted((APP_KOK / "routers").rglob("*.py")):
        agac = ast.parse(yol.read_text(encoding="utf-8"), filename=str(yol))
        for dugum in ast.walk(agac):
            if isinstance(dugum, ast.Name) and dugum.id == "BetaInvite":
                ihlaller.append(f"{yol.name}:{dugum.lineno}")
            elif isinstance(dugum, ast.Attribute) and dugum.attr == "BetaInvite":
                ihlaller.append(f"{yol.name}:{dugum.lineno}")
            elif isinstance(dugum, (ast.Import, ast.ImportFrom)):
                for takma in dugum.names:
                    if takma.name == "BetaInvite" or takma.asname == "BetaInvite":
                        ihlaller.append(f"{yol.name}:{dugum.lineno} (import)")
    assert not ihlaller, (
        "Router katmanı BetaInvite'ı doğrudan kullanıyor: " + ", ".join(ihlaller) +
        " — davet kuralı `app/beta_access.py`'de tek kaynaktır (L46)."
    )


# ══════════════════════════════════════════════════════════════════════════
# 2. `hesap_acabilir_mi` sözleşmesi
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-davet-kapsam-0123456789abcdef")
    monkeypatch.setenv("AUTH_ENABLED", "true")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("REGISTRATION_MODE", "invite_only")
    from app import rate_limit
    rate_limit.reset()


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


def test_davetsiz_adres_hesap_acamaz(db):
    assert hesap_acabilir_mi(db, "yabanci@example.com") is False


def test_davetli_adres_hesap_acabilir(db):
    davet_olustur(db, email="davetli@example.com")
    assert hesap_acabilir_mi(db, "davetli@example.com") is True


def test_mevcut_kullanici_hesap_acabilir_sayilir(db):
    """Zaten hesabı olan biri (davetini tüketmiş) yeniden davet gerektirmez."""
    db.add(User(email="var@example.com", name="Var"))
    db.commit()
    assert hesap_acabilir_mi(db, "var@example.com") is True


def test_acik_modda_herkes_acabilir(db, monkeypatch):
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    assert hesap_acabilir_mi(db, "herhangi@example.com") is True


def test_bos_adres_fail_closed(db):
    """Boş/None adres 'açabilir' sayılmaz — yanlış tarafa düşme (L5 fail-closed)."""
    assert hesap_acabilir_mi(db, "") is False
    assert hesap_acabilir_mi(db, None) is False


def test_buyuk_harf_ve_bosluk_normalize_edilir(db):
    davet_olustur(db, email="karisik@example.com")
    assert hesap_acabilir_mi(db, "  KARISIK@Example.COM ") is True


def test_kullanilmis_davet_hesap_actirmaz(db):
    """Tek kullanımlık: tüketilmiş davet ikinci kişiye kapı açmaz."""
    d = davet_olustur(db, email="tek@example.com")
    from app.beta_access import davet_kullan
    kullanici = User(email="baska@example.com", name="X")
    db.add(kullanici)
    db.flush()
    davet_kullan(db, d, kullanici.id)
    db.commit()
    assert eposta_daveti_bul(db, "tek@example.com") is None
    assert hesap_acabilir_mi(db, "tek@example.com") is False


def test_epostasiz_davet_adresle_eslesmez(db):
    """Yalnız-kod davetler OAuth/e-posta yolunu AÇMAZ (BUG #226 gerekçesi korunur)."""
    davet_olustur(db, note="genel kod")
    assert eposta_daveti_bul(db, "birisi@example.com") is None
    assert hesap_acabilir_mi(db, "birisi@example.com") is False


# ══════════════════════════════════════════════════════════════════════════
# 3. Workspace daveti: allowlist dışı adrese SESSİZCE gitmez
# ══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def ws_client(db):
    owner = User(email="owner@example.com", name="Owner")
    db.add(owner)
    db.flush()
    ws = Workspace(name="Aile", is_personal=False, owner_user_id=owner.id)
    db.add(ws)
    db.flush()
    db.add(WorkspaceMembership(workspace_id=ws.id, user_id=owner.id,
                               role=WorkspaceRole.owner))
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: db.get(User, owner.id)
    c = TestClient(app)
    c.headers.update({"X-Workspace-Id": str(ws.id)})
    yield c, ws
    app.dependency_overrides.clear()


def test_allowlist_disi_adrese_workspace_daveti_reddedilir(ws_client):
    """Owner, hiç kayıt olamayacak birine davet gönderemez — ve NEDENİNİ öğrenir."""
    c, ws = ws_client
    r = c.post(f"/api/workspaces/{ws.id}/invite",
               json={"email": "yabanci@example.com", "role": "viewer"})
    assert r.status_code == 400, f"Allowlist dışı adrese davet gitti ({r.status_code})"
    detay = r.json()["detail"]
    assert "beta" in detay.lower(), f"Ret gerekçesi kullanıcıya anlatılmıyor: {detay}"


def test_davetli_adrese_workspace_daveti_gecer(ws_client, db):
    c, ws = ws_client
    davet_olustur(db, email="davetli@example.com")
    r = c.post(f"/api/workspaces/{ws.id}/invite",
               json={"email": "davetli@example.com", "role": "viewer"})
    assert r.status_code == 201, r.text[:300]
    assert r.json()["invite_link"]


def test_acik_modda_workspace_daveti_engellenmez(ws_client, monkeypatch):
    """Kapı yalnız kapalı betada iş görür; açık kayıtta akışı ağırlaştırmaz (L6)."""
    monkeypatch.setenv("REGISTRATION_MODE", "open")
    c, ws = ws_client
    r = c.post(f"/api/workspaces/{ws.id}/invite",
               json={"email": "herhangi@example.com", "role": "viewer"})
    assert r.status_code == 201, r.text[:300]
