"""
P1 (Wave-9 publish yolu) — ÇAPRAZ-KULLANICI ERİŞİM MATRİSİ (runtime kilidi).

Amaç: "B kullanıcısı, A'nın kaynağına ID'sini bilerek erişebilir mi?" sorusunu HER kaynak
ailesi için gerçek HTTP çağrısıyla yanıtlamak. Statik gate (test_scope_enforcement) kodun
şeklini denetler; bu dosya davranışı denetler. İkisi birlikte P1 kapısını oluşturur.

Beklenti: B'nin A'ya ait id ile yaptığı her istek 403 veya 404 döner (kaynak-gizleme —
OWASP: başkasının kaynağının VARLIĞI bile sızmamalı). 200/204 = SIZINTI.

Ek kapı: `test_id_alan_endpointler_matriste_kapsanir` — yeni bir `/{id}` endpoint'i eklenip
matrise yazılmazsa test KIRILIR. Böylece bu dosya zamanla bayatlamaz (Wave-5 dersi: kapsam
eksikliği sessizce büyür; BUG #162 tam da kapsam dışı kalan bir katmandan geçti).
"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.dependencies import get_db, get_current_user
from app.models import Base, User, Workspace, WorkspaceMembership, WorkspaceRole


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-cross-user-isolation-0123456789")


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    yield s
    s.close()


@pytest.fixture
def users(db):
    """İki BAĞIMSIZ kullanıcı — her biri kendi personal workspace'inde (gerçek beta senaryosu)."""
    a = User(name="kullanici_a")
    b = User(name="kullanici_b")
    db.add_all([a, b])
    db.commit()
    for u in (a, b):
        ws = Workspace(owner_user_id=u.id, name=f"{u.name} (Kişisel)", is_personal=True)
        db.add(ws)
        db.commit()
        db.add(WorkspaceMembership(workspace_id=ws.id, user_id=u.id, role=WorkspaceRole.owner))
        db.commit()
    return a, b


@pytest.fixture
def client(db, users):
    app.dependency_overrides[get_db] = lambda: db
    state = {"user": users[0]}
    app.dependency_overrides[get_current_user] = lambda: state["user"]
    c = TestClient(app)
    c._state_user = state
    yield c
    app.dependency_overrides.clear()


def _as(client, user):
    client._state_user["user"] = user


# ══════════════════════════════════════════════════════════════════════════════
# KAYNAK MATRİSİ — her aile: A yaratır, B ID ile saldırır
# ══════════════════════════════════════════════════════════════════════════════

def _account_payload():
    return {"name": "A'nın kasası", "account_type": "cash", "balance": 5000.0}


RESOURCES = [
    {
        "ad": "accounts",
        "create": ("POST", "/api/accounts", _account_payload()),
        "probes": [
            ("GET", "/api/accounts/{id}", None),
            ("PUT", "/api/accounts/{id}", {"name": "ele geçirildi"}),
            ("DELETE", "/api/accounts/{id}", None),
        ],
    },
    {
        "ad": "incomes",
        "create": ("POST", "/api/incomes",
                   {"name": "A maaş", "amount": 50000.0, "day_of_month": 15}),
        "probes": [
            ("PUT", "/api/incomes/{id}", {"name": "ele geçirildi"}),
            ("DELETE", "/api/incomes/{id}", None),
        ],
    },
    {
        "ad": "debts",
        "create": ("POST", "/api/debts",
                   {"counterparty": "A'nın borçlusu", "direction": "receivable", "amount": 1000.0}),
        "probes": [
            ("PUT", "/api/debts/{id}", {"amount": 1.0}),
            ("DELETE", "/api/debts/{id}", None),
        ],
    },
    {
        "ad": "checkpoints",
        "create": ("POST", "/api/checkpoints",
                   {"title": "A kırmızı çizgi", "description": "gizli",
                    "checkpoint_type": "red_line"}),
        "probes": [
            ("PUT", "/api/checkpoints/{id}", {"title": "ele geçirildi"}),
            ("DELETE", "/api/checkpoints/{id}", None),
        ],
    },
    {
        "ad": "envelopes",
        "create": ("POST", "/api/envelopes", {"category": "market", "monthly_amount": 3000}),
        "probes": [
            ("PUT", "/api/envelopes/{id}", {"monthly_amount": 1}),
            ("DELETE", "/api/envelopes/{id}", None),
        ],
    },
    {
        "ad": "wishlist",
        "create": ("POST", "/api/wishlist", {"item": "A'nın isteği", "amount": 900}),
        "probes": [
            ("POST", "/api/wishlist/{id}/resolve?status=bought", None),
        ],
    },
    {
        "ad": "goals",
        "create": ("POST", "/api/goals",
                   {"goal_type": "cash_target", "title": "A hedefi", "target_amount": 10000}),
        "probes": [
            ("GET", "/api/goals/{id}", None),
            ("PATCH", "/api/goals/{id}", {"title": "ele geçirildi"}),
            ("DELETE", "/api/goals/{id}", None),
            ("POST", "/api/goals/{id}/refresh", None),
            ("GET", "/api/goals/{id}/allocations", None),
            ("GET", "/api/goals/{id}/rules", None),
            ("POST", "/api/goals/{id}/rules",
             {"name": "sızma kuralı", "criteria": {"tx_type": "income"},
              "allocation_type": "full"}),
        ],
    },
]


def _create_as_a(client, res) -> int:
    method, url, payload = res["create"]
    r = client.request(method, url, json=payload)
    assert r.status_code in (200, 201), (
        f"{res['ad']}: A kaynağı yaratamadı ({r.status_code}) — test kurulumu bozuk: {r.text[:300]}"
    )
    body = r.json()
    rid = body.get("id") if isinstance(body, dict) else None
    assert rid is not None, f"{res['ad']}: yaratılan kaynak id döndürmedi: {body}"
    return rid


@pytest.mark.parametrize("res", RESOURCES, ids=[r["ad"] for r in RESOURCES])
def test_b_kullanicisi_a_kaynagina_erisemez(client, users, res):
    """A kaynağı yaratır; B aynı id ile okumaya/yazmaya/silmeye çalışır → 403/404."""
    a, b = users
    _as(client, a)
    rid = _create_as_a(client, res)

    _as(client, b)
    sizinti = []
    for method, url_tpl, payload in res["probes"]:
        url = url_tpl.format(id=rid)
        r = client.request(method, url, json=payload)
        if r.status_code not in (403, 404):
            sizinti.append(f"{method} {url} → {r.status_code} (beklenen 403/404) {r.text[:160]}")
    assert not sizinti, f"{res['ad']} ÇAPRAZ-KULLANICI SIZINTISI:\n" + "\n".join(sizinti)


@pytest.mark.parametrize("res", RESOURCES, ids=[r["ad"] for r in RESOURCES])
def test_b_listelemede_a_kaynagini_gormez(client, users, res):
    """Liste uçları da sızdırmamalı: A'nın kaydı B'nin listesinde görünmemeli."""
    a, b = users
    _as(client, a)
    rid = _create_as_a(client, res)

    _as(client, b)
    liste_url = res["create"][1]
    r = client.get(liste_url)
    if r.status_code != 200:
        pytest.skip(f"{res['ad']}: liste ucu GET desteklemiyor ({r.status_code})")
    body = r.json()
    kayitlar = body if isinstance(body, list) else body.get("items", [])
    ids = [k.get("id") for k in kayitlar if isinstance(k, dict)]
    assert rid not in ids, f"{res['ad']}: A'nın kaydı (id={rid}) B'nin listesinde görünüyor"


def test_b_transaction_yaratirken_a_hesabini_kullanamaz(client, users):
    """Yazma tarafı IDOR: B, işlemi A'nın hesabına yazamaz (crafted account_id)."""
    a, b = users
    _as(client, a)
    r = client.post("/api/accounts", json=_account_payload())
    assert r.status_code in (200, 201)
    a_account_id = r.json()["id"]

    _as(client, b)
    r = client.post("/api/transactions", json={
        "account_id": a_account_id,
        "transaction_type": "expense",
        "amount": 100.0,
        "transaction_date": date.today().isoformat(),
        "description": "B'den A'nın hesabına sızma",
    })
    assert r.status_code in (400, 403, 404), (
        f"B, A'nın hesabına işlem yazabildi → {r.status_code}: {r.text[:200]}"
    )


def test_b_a_workspace_ini_header_ile_ele_geciremez(client, users, db):
    """X-Workspace-Id başlığıyla A'nın workspace'ine geçiş 403 olmalı (üyelik yok)."""
    a, b = users
    a_ws = db.query(Workspace).filter(Workspace.owner_user_id == a.id).first()
    _as(client, b)
    r = client.get("/api/accounts", headers={"X-Workspace-Id": str(a_ws.id)})
    assert r.status_code == 403, f"B, A'nın workspace'ine geçebildi → {r.status_code}"


# ══════════════════════════════════════════════════════════════════════════════
# KAPSAM KİLİDİ — matris bayatlayamaz
# ══════════════════════════════════════════════════════════════════════════════

# Matris dışı bırakılan `/{id}` uçları — her biri GEREKÇELİ (sessiz boşluk yok)
MATRIS_DISI = {
    "/api/actions/{action_id}/approve": "PendingAction kişisel-bağlı; tests/security + actions testleri kapsıyor",
    "/api/actions/{action_id}/edit": "aynı — PendingAction sahiplik filtresi (user_id) testli",
    "/api/actions/{action_id}/reject": "aynı — PendingAction sahiplik filtresi (user_id) testli",
    "/api/premortem/{action_id}": "PendingAction sahiplik filtresi (user_id) + status kapısı testli",
    "/api/simulate/{action_id}": "PendingAction sahiplik filtresi (user_id) testli",
    "/api/coach/trace/{memory_id}": "ReasoningTrace user_id filtresi + 404 kaynak-gizleme testli (coach testleri)",
    "/api/goals/allocations/{allocation_id}": "ebeveyn Goal sahipliği doğrulanıyor; goals ownership testleri kapsıyor",
    "/api/goals/rules/{rule_id}": "ebeveyn Goal sahipliği doğrulanıyor; goals ownership testleri kapsıyor",
    "/api/expenses/recurring/{expense_id}": "RecurringExpense scope_filter; expenses testleri kapsıyor",
    "/api/transactions/{txn_id}": "Transaction scope_filter; transactions testleri + yukarıdaki IDOR testi kapsıyor",
    "/api/workspaces/{workspace_id}": "workspace üyelik kapısı ayrı test dosyasında (test_workspaces_api)",
    "/api/workspaces/{workspace_id}/invite": "aynı — workspace izin matrisi testli",
    "/api/workspaces/{workspace_id}/members/{target_user_id}": "aynı — workspace izin matrisi testli",
    "/api/auth/callback/{provider}": "kullanıcı kaynağı değil (OAuth sağlayıcı adı)",
    "/api/auth/oauth/{provider}/login": "kullanıcı kaynağı değil (OAuth sağlayıcı adı)",
    "/api/fund-price/tefas-link/{fund_code}": "kullanıcı kaynağı değil (piyasa verisi)",
    "/api/prices/currency/{currency_code}": "kullanıcı kaynağı değil (piyasa verisi)",
    "/api/prices/gold/{gold_type}": "kullanıcı kaynağı değil (piyasa verisi)",
}


def _matris_kapsami() -> set[str]:
    kapsanan = set()
    for res in RESOURCES:
        for _, url_tpl, _ in res["probes"]:
            kapsanan.add(url_tpl)
    return kapsanan


def test_id_alan_endpointler_matriste_kapsanir():
    """Her `/{...}` parametreli API ucu ya matriste ya da gerekçeli MATRIS_DISI'nda olmalı.

    Yeni endpoint eklenip izolasyon testi yazılmazsa bu test kırılır — kapsam kendiliğinden
    daralamaz (Wave-5'te izolasyon kapsamının sessizce eksik kalması BUG #162'ye yol açtı).
    """
    kapsanan = _matris_kapsami()

    def normalize(path: str) -> str:
        """Matris şablonu `{id}` kullanır; gerçek yol `{account_id}` vb. Query string atılır."""
        import re
        return re.sub(r"\{[a-z_]+\}", "{id}", path.split("?", 1)[0])

    kapsanan_norm = {normalize(u) for u in kapsanan}
    disi_norm = {normalize(u) for u in MATRIS_DISI}

    eksik = []
    for r in app.routes:
        path = getattr(r, "path", "")
        if not path.startswith("/api") or "{" not in path:
            continue
        n = normalize(path)
        if n in kapsanan_norm or n in disi_norm:
            continue
        eksik.append(path)

    assert not eksik, (
        "İzolasyon matrisinde kapsanmayan ID'li endpoint(ler) — RESOURCES'a ekle ya da "
        "MATRIS_DISI'na GEREKÇE yaz:\n" + "\n".join(sorted(set(eksik)))
    )
