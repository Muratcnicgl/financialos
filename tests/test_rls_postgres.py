"""
M51 (Wave-7) — Row-Level Security GATE (Postgres, DB-katmanı izolasyon 2. savunma).

Kanıt: RLS aktifken, uygulama filtresi (scope_filter) BYPASS edilse bile (ham `SELECT * FROM accounts`,
WHERE yok) Postgres yanlış workspace satırını DÖNDÜRMEZ. Superuser RLS'i bypass ettiğinden test
NON-superuser rol ile bağlanır.

GUNCELLEMELER:
  BUG #238 fix (denetim D22): bu dosya rolü ELDE yaratıyordu (`CREATE ROLE fos_app ...`) ve
    docstring'i onu "prod'daki `financialos` app-rolünü temsil eder" diye niteliyordu. Bu
    NİTELEME YANLIŞTI: prod compose uygulamayı `financialos` ile bağlıyordu ve o rol postgres
    imajının POSTGRES_USER'ı, yani BOOTSTRAP SUPERUSER'ıydı — superuser FORCE'a rağmen RLS'i
    bypass eder. Yani bu gate yeşil olsa bile prod'daki gerçek rolü hiç ölçmüyordu. Artık rol
    prod'un GERÇEK provizyon yoluyla (`scripts/provision_app_role.py`, entrypoint'in çağırdığı
    kod) kuruluyor + superuser'ın bypass ettiği davranışla ispatlanıyor.

Postgres yoksa SKIP (ana SQLite süiti bloklanmaz). Bu gate yalnız Postgres'te anlamlı.
CI'da PG_TEST_URL ile GERÇEKTEN koşar (BUG #238: eskiden her koşumda SKIP'ti).
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from scripts.provision_app_role import provision
from tests.pg_gate import postgres_url_or_skip, fresh_pg_database

APP_ROL = "fos_app"
APP_SIFRE = "gate-test-app-role-pw"


def _run_alembic(url: str):
    import os, subprocess, sys
    env = dict(os.environ, DATABASE_URL=url)
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=env, check=True,
                   capture_output=True)


@pytest.fixture
def rls_db():
    base = postgres_url_or_skip()
    url = fresh_pg_database(base, "fos_rls_gate")
    _run_alembic(url)  # RLS migration dahil head
    yield url
    # BUG #238: rol cluster-GENELİNDEDİR (veritabanına değil). Test yarıda kalsa bile
    # düşürülmezse sonraki koşum bayat şifreyle karşılaşır → temizlik teardown'a alındı.
    _rolu_dusur(url)


def test_rls_yanlis_workspace_sifir_satir(rls_db):
    """RLS GATE: yanlış workspace context → uygulama filtresi bypass edilse bile 0 satır."""
    # BUG #238: rol PROD'UN GERÇEK YOLUYLA kurulur — entrypoint'in çağırdığı aynı fonksiyon.
    # Elle `CREATE ROLE` yazılsaydı gate, prod'da fiilen kullanılan rolü değil kendi
    # kurgusunu ölçerdi (denetim D22'nin çürüttüğü tam olarak buydu).
    provision(rls_db, APP_ROL, APP_SIFRE)

    admin = create_engine(rls_db, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        # Seed (superuser → RLS bypass, kurulum): 1 user + 2 workspace + her ws'de 1 account.
        c.execute(text("INSERT INTO users (id, name, email) VALUES (1, 'murat', 'm@x.com')"))
        c.execute(text("INSERT INTO workspaces (id, owner_user_id, name, is_personal) VALUES (1,1,'WS1',true),(2,1,'WS2',false)"))
        c.execute(text("INSERT INTO accounts (user_id, workspace_id, name, account_type, balance, is_emanet) "
                       "VALUES (1,1,'A1','cash',100,false),(1,2,'A2','cash',200,false)"))
    admin.dispose()

    # Non-superuser bağlan (RLS ona uygulanır)
    # BUG #300: `str(url)` şifreyi `***` ile maskeler → rol şifresi kaybolur ve
    # bağlantı "password authentication failed" alır.
    app_url = make_url(rls_db).set(
        username=APP_ROL, password=APP_SIFRE).render_as_string(hide_password=False)
    app_eng = create_engine(app_url)

    def raw_count(conn):
        # UYGULAMA FİLTRESİ BYPASS: ham SELECT, WHERE workspace_id YOK
        return conn.execute(text("SELECT count(*) FROM accounts")).scalar()

    with app_eng.connect() as conn:
        # context WS1 → yalnız WS1 satırı
        conn.execute(text("SET app.current_workspace_id = '1'"))
        assert raw_count(conn) == 1
        names1 = [r[0] for r in conn.execute(text("SELECT name FROM accounts")).all()]
        assert names1 == ["A1"]

        # context WS2 → yalnız WS2 satırı
        conn.execute(text("SET app.current_workspace_id = '2'"))
        assert raw_count(conn) == 1
        assert [r[0] for r in conn.execute(text("SELECT name FROM accounts")).all()] == ["A2"]

        # KRİTİK GATE: yanlış/olmayan workspace → 0 satır (app filtresi bypass edilse bile DB korur)
        conn.execute(text("SET app.current_workspace_id = '999'"))
        assert raw_count(conn) == 0, "RLS yanlış workspace'i bloklamadı — DB-katmanı savunma DELİK"

        # context YOK (unset) → app-katmanı birincil, RLS tüm satırlara izin (2. savunma opt-in)
        conn.execute(text("RESET app.current_workspace_id"))
        assert raw_count(conn) == 2

    app_eng.dispose()

    # --- app-hook uçtan uca: workspace_scope → after_begin → GUC → RLS (ORM üzerinden) ---
    from sqlalchemy.orm import sessionmaker as _sm
    from sqlalchemy import event as _ev
    from app.rules_engine import workspace_scope, _active_workspace
    from app.models import Account
    hook_eng = create_engine(app_url)  # non-superuser fos_app
    HookSession = _sm(bind=hook_eng)

    @_ev.listens_for(HookSession, "after_begin")
    def _hook(session, transaction, connection):
        ws = _active_workspace.get()
        if ws is not None:
            connection.exec_driver_sql(
                "SELECT set_config('app.current_workspace_id', %s, true)", (str(ws),))

    s = HookSession()
    try:
        with workspace_scope(1):  # contextvar → hook GUC=1 → RLS
            assert s.query(Account).count() == 1
            assert [a.name for a in s.query(Account).all()] == ["A1"]
        s.rollback()
        with workspace_scope(999):  # yanlış ws → 0 satır (ORM sorgusu bile)
            assert s.query(Account).count() == 0
    finally:
        s.close(); hook_eng.dispose()

    # temizlik
    _rolu_dusur(rls_db)


def _rolu_dusur(url: str) -> None:
    """Rolü ve bağımlı yetkilerini düşürür. Rol yoksa sessizce geçer (teardown'da çağrılır)."""
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"),
                         {"r": APP_ROL}).scalar():
            admin.dispose()
            return
        for sql in (
            f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {APP_ROL}",
            f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {APP_ROL}",
            f"REVOKE USAGE ON SCHEMA public FROM {APP_ROL}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {APP_ROL}",
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {APP_ROL}",
            f"DROP ROLE IF EXISTS {APP_ROL}",
        ):
            c.execute(text(sql))
    admin.dispose()


# ── BUG #238 (denetim D22): prod rol seçiminin RLS'i etkisizleştirdiğinin DAVRANIŞ kanıtı ──

def test_superuser_force_rls_e_ragmen_bypass_eder(rls_db):
    """Prod eskiden bootstrap SUPERUSER ile bağlanıyordu. Bu testin gösterdiği şey, o kurulumda
    RLS diye bir 2. savunmanın HİÇ olmadığıdır: aynı sorgu, aynı yanlış workspace bağlamı,
    aynı FORCE'lu tablo — superuser hepsini görür, app rolü sıfır satır görür."""
    provision(rls_db, APP_ROL, APP_SIFRE)
    su = create_engine(rls_db, isolation_level="AUTOCOMMIT")
    try:
        with su.connect() as c:
            assert c.execute(text("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                             ).scalar() is True, "test kurgusu: admin bağlantısı superuser değil"
            c.execute(text("INSERT INTO users (id, name, email) VALUES (1,'m','m@x.com')"))
            c.execute(text("INSERT INTO workspaces (id, owner_user_id, name, is_personal) "
                           "VALUES (1,1,'WS1',true)"))
            c.execute(text("INSERT INTO accounts (user_id, workspace_id, name, account_type, "
                           "balance, is_emanet) VALUES (1,1,'A1','cash',100,false)"))
            # FORCE ROW LEVEL SECURITY tabloda AÇIK — yine de superuser'a uygulanmaz.
            zorlanmis = c.execute(text(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                "WHERE relname = 'accounts'")).scalar()
            assert zorlanmis is True, "migration RLS'i ENABLE+FORCE etmemiş (kapı ölçemez)"
            c.execute(text("SET app.current_workspace_id = '999'"))  # YANLIŞ workspace
            assert c.execute(text("SELECT count(*) FROM accounts")).scalar() == 1, (
                "beklenmedik: superuser RLS'e takıldı — bu testin premisi güncellenmeli"
            )
    finally:
        su.dispose()

    # Aynı sorgu, provizyon edilmiş app rolüyle → RLS uygulanır.
    # BUG #300: `str(url)` şifreyi `***` ile maskeler → rol şifresi kaybolur ve
    # bağlantı "password authentication failed" alır.
    app_url = make_url(rls_db).set(
        username=APP_ROL, password=APP_SIFRE).render_as_string(hide_password=False)
    app_eng = create_engine(app_url)
    try:
        with app_eng.connect() as c:
            c.execute(text("SET app.current_workspace_id = '999'"))
            assert c.execute(text("SELECT count(*) FROM accounts")).scalar() == 0, (
                "app rolü RLS'i bypass etti — prod'da DB-katmanı savunma yok demektir"
            )
    finally:
        app_eng.dispose()
        _rolu_dusur(rls_db)


def test_provizyon_edilen_rol_rls_e_tabidir(rls_db):
    """Provizyon scripti (entrypoint'in çağırdığı kod) rolü gerçekten RLS'e tabi yaratıyor mu?
    `NOSUPERUSER` ama `BYPASSRLS` bir rol de savunmayı sessizce kaldırırdı."""
    provision(rls_db, APP_ROL, APP_SIFRE)
    eng = create_engine(rls_db)
    try:
        with eng.connect() as c:
            r = c.execute(text("SELECT rolsuper, rolbypassrls, rolcanlogin, rolcreatedb, "
                               "rolcreaterole FROM pg_roles WHERE rolname = :r"),
                          {"r": APP_ROL}).one()
        assert r.rolsuper is False, "app rolü SUPERUSER — RLS tamamen etkisiz"
        assert r.rolbypassrls is False, "app rolü BYPASSRLS — RLS sessizce atlanır"
        assert r.rolcanlogin is True, "app rolü login olamıyor — uygulama bağlanamaz"
        assert r.rolcreatedb is False and r.rolcreaterole is False, (
            "app rolüne gereksiz yönetim yetkisi verilmiş (en az yetki ilkesi)"
        )
    finally:
        eng.dispose()
        _rolu_dusur(rls_db)


def test_provizyon_idempotent_ve_sifresiz_calismaz(rls_db):
    """Her deploy'da koşar (entrypoint) → ikinci koşum patlamamalı; şifresiz rol yaratılmamalı."""
    provision(rls_db, APP_ROL, APP_SIFRE)
    provision(rls_db, APP_ROL, APP_SIFRE + "-yeni")  # şifre güncellenir, hata vermez
    try:
        with pytest.raises(ValueError):
            provision(rls_db, APP_ROL, "")
        with pytest.raises(ValueError):
            provision(rls_db, "fos_app; DROP TABLE users", APP_SIFRE)  # rol adı beyaz listeli
    finally:
        _rolu_dusur(rls_db)
