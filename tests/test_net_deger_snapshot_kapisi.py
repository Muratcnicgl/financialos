"""
NET DEĞER SNAPSHOT KAPISI — BUG #292.

SORUN (canlı beta verisinde ölçüldü, 11 Ağu 2026): `_ensure_today_snapshot` "o gün için
kayıt VARSA dokunma" diyordu (`if q.first(): return`). Yeni kullanıcı kaydolup paneli ilk
açtığında henüz hiçbir hesabı yoktur → o günün snapshot'ı **0** yazılır. Aynı gün hesabını
ve işlemlerini girer, ama snapshot bir daha GÜNCELLENMEZ. Ertesi gün `catch_up_snapshots`
yalnız EKSİK günleri doldurur, var olan günü düzeltmez → kayıt gününün net değeri KALICI
olarak 0 kalır.

Canlı ölçüm — üç beta kullanıcısının ÜÇÜNDE de:
    uid 2:  gerçek  7.313,49  →  grafikte 0
    uid 3:  gerçek 20.353,70  →  grafikte 0
    uid 4:  gerçek 10.350,00  →  grafikte 0

İkinci etkisi daha sinsi: `coach_insights` net-değer trendi ve FEAT-017 borç ilerlemesi
"EN ESKİ snapshot"ı baz alır. Sahte 0 en eski kayıt olduğu için koç ertesi gün "net değerin
10.350 TL arttı" diyebilir — hiçbir şey artmamışken.

SÖZLEŞME (bu kapının koruduğu): **snapshot, o günün SON BİLİNEN durumudur.** Gün içinde
veri değişirse kayıt güncellenir; değişmezse DB'ye dokunulmaz (cockpit her açılışta çağrılır);
geçmiş günler asla ezilmez.

DERS (L53): "idempotent" iki farklı şey demektir — *bir kez yaz* (create-once) ve
*aynı sonuca yakınsa* (upsert). Docstring "idempotent" diyordu, kod create-once
uyguluyordu, sözleşme upsert gerektiriyordu. Bir günü temsil eden kayıt, o gün BİTMEDEN
yazılıyorsa create-once YANLIŞ cevaptır.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, User, Account, AccountType, NetWorthSnapshot, Workspace
from app.routers.cockpit import _ensure_today_snapshot
from app.rules_engine import generate_cockpit

BUGUN = date(2026, 8, 11)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="beta_kullanici"))
    s.commit()
    try:
        yield s
    finally:
        s.close()


def _cockpit(db_session) -> dict:
    return generate_cockpit(1, BUGUN, db_session)


def _snap(db_session, gun=BUGUN) -> NetWorthSnapshot | None:
    return (db_session.query(NetWorthSnapshot)
            .filter(NetWorthSnapshot.snapshot_date == gun).first())


# ══════════════════════════════════════════════════════════════════════════
# 1 — KÖK DEFEKT: kayıt günü içinde girilen veri snapshot'a yansımalı
# ══════════════════════════════════════════════════════════════════════════

def test_ayni_gun_girilen_veri_snapshota_yansir(db):
    """Altay senaryosu: boş panelde 0 yazılır, sonra hesap eklenir → snapshot düzelmeli."""
    # 1. Kullanıcı kaydoldu, paneli açtı — henüz hiçbir şeyi yok
    _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)
    assert float(_snap(db).net_worth_full) == 0.0, "boş panelde 0 beklenir (başlangıç durumu)"

    # 2. Aynı gün hesabını girdi
    db.add(Account(user_id=1, name="Maaş+yemek kartım",
                   account_type=AccountType.cash, balance=10350))
    db.commit()

    # 3. Paneli tekrar açtı
    _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)

    snap = _snap(db)
    assert float(snap.net_worth_full) == 10350.0, (
        "BUG #292: gün içinde girilen veri snapshot'a yansımıyor — net değer grafiği "
        "kayıt gününü kalıcı olarak 0 gösteriyor"
    )
    assert float(snap.cash) == 10350.0
    # Tek satır kalmalı — güncelleme, ikinci satır DEĞİL (uq_nws_user_date de bunu ister)
    assert db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.snapshot_date == BUGUN).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# 2 — GEÇMİŞ EZİLMEZ: dünkü kayıt bugünkü çağrıdan etkilenmez
# ══════════════════════════════════════════════════════════════════════════

def test_gecmis_gun_ezilmez(db):
    dun = BUGUN - timedelta(days=1)
    db.add(NetWorthSnapshot(user_id=1, snapshot_date=dun, net_worth_seen=999,
                            net_worth_full=999, cash=999, card_debt=0, loan_debt=0,
                            investment_value=0, receivables=0))
    db.commit()

    db.add(Account(user_id=1, name="kasa", account_type=AccountType.cash, balance=5000))
    db.commit()
    _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)

    assert float(_snap(db, dun).net_worth_full) == 999.0, "dünkü kayıt korunmalı"
    assert float(_snap(db, BUGUN).net_worth_full) == 5000.0


# ══════════════════════════════════════════════════════════════════════════
# 3 — GEREKSİZ YAZMA YOK: değer değişmediyse DB'ye dokunulmaz
# ══════════════════════════════════════════════════════════════════════════

def test_deger_degismediyse_yazma_yok(db):
    """Cockpit HER açılışta çağrılır; değişmemiş değer için UPDATE atmak boşuna yüktür.

    Mutasyon dersi (iki tur): bu test önce `id`/`created_at` karşılaştırıyordu — ikisi de
    UPDATE'te DEĞİŞMEZ, yani "hep yaz" mutasyonu kapıdan KAÇIYORDU. SQL yazması saymak da
    yetmedi: SQLAlchemy aynı değeri geri atayınca zaten UPDATE üretmez, ama **boş `commit()`
    yine de gider**. Sözleşme "DB'ye dokunulmaz" diyorsa commit de bir dokunuştur — ölçüm
    ikisini birden sayar.
    """
    from sqlalchemy import event

    db.add(Account(user_id=1, name="kasa", account_type=AccountType.cash, balance=5000))
    db.commit()

    _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)
    ilk_id = _snap(db).id

    yazmalar: list[str] = []

    def _sql_dinle(conn, cursor, statement, params, context, executemany):
        bas = statement.lstrip()[:6].upper()
        if bas in ("INSERT", "UPDATE") and "net_worth_snapshots" in statement:
            yazmalar.append(statement)

    commitler: list[int] = []

    def _commit_dinle(session):
        commitler.append(1)

    engine = db.get_bind()
    event.listen(engine, "after_cursor_execute", _sql_dinle)
    event.listen(db, "after_commit", _commit_dinle)
    try:
        for _ in range(3):  # panel üç kez daha açıldı, veri değişmedi
            _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)
    finally:
        event.remove(engine, "after_cursor_execute", _sql_dinle)
        event.remove(db, "after_commit", _commit_dinle)

    assert yazmalar == [], (
        f"değer değişmediği hâlde {len(yazmalar)} yazma yapıldı — cockpit her panel "
        f"açılışında çağrılır, bu boşuna DB yüküdür"
    )
    assert commitler == [], (
        f"değer değişmediği hâlde {len(commitler)} commit atıldı — SQLAlchemy aynı değeri "
        f"yazmasa bile transaction round-trip'i gerçektir"
    )
    assert _snap(db).id == ilk_id, "aynı satır kullanılmalı (yeni satır açılmamalı)"
    assert db.query(NetWorthSnapshot).count() == 1


# ══════════════════════════════════════════════════════════════════════════
# 4 — HER BİLEŞEN YANSIR: yalnız net değer değil, kırılım da güncellenir
# ══════════════════════════════════════════════════════════════════════════

def test_tum_bilesenler_guncellenir(db):
    _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)

    db.add_all([
        Account(user_id=1, name="kasa", account_type=AccountType.cash, balance=8000),
        Account(user_id=1, name="kart", account_type=AccountType.credit_card, balance=-3000),
        Account(user_id=1, name="fon", account_type=AccountType.investment, balance=12000),
    ])
    db.commit()
    _ensure_today_snapshot(db, 1, _cockpit(db), None, today=BUGUN)

    snap = _snap(db)
    ck = _cockpit(db)
    assert float(snap.cash) == ck["nakit_kasa"]
    assert float(snap.card_debt) == ck["kart_borcu"]
    assert float(snap.investment_value) == ck["yatirim_deger"]
    assert float(snap.net_worth_seen) == ck["net_deger"]


# ══════════════════════════════════════════════════════════════════════════
# 5 — WORKSPACE DALI: ws_id verilen yolda da güncelleme çalışır
# ══════════════════════════════════════════════════════════════════════════

def test_workspace_dalinda_da_guncellenir(db):
    """İki dal (ws_id var / yok) ayrı sorgu kullanıyor; ikisi de upsert olmalı."""
    db.add(Workspace(id=7, owner_user_id=1, name="Kişisel", is_personal=True))
    db.commit()

    _ensure_today_snapshot(db, 1, _cockpit(db), 7, today=BUGUN)
    assert float(_snap(db).net_worth_full) == 0.0

    db.add(Account(user_id=1, workspace_id=7, name="kasa",
                   account_type=AccountType.cash, balance=4200))
    db.commit()
    _ensure_today_snapshot(db, 1, _cockpit(db), 7, today=BUGUN)

    kayitlar = db.query(NetWorthSnapshot).filter(
        NetWorthSnapshot.snapshot_date == BUGUN).all()
    assert len(kayitlar) == 1, "workspace dalında ikinci satır açılmamalı"
    assert float(kayitlar[0].net_worth_full) == 4200.0
    assert kayitlar[0].workspace_id == 7
