"""
PostgreSQL uygulama rolü provizyonu (idempotent) — BUG #238 (denetim D22).

NEDEN: `docker-compose.prod.yml` uygulamayı postgres imajının `POSTGRES_USER`'ı ile
bağlıyordu. Bu rol cluster'ın **bootstrap SUPERUSER**'ıdır ve superuser
`ALTER TABLE ... FORCE ROW LEVEL SECURITY`'ye RAĞMEN RLS'i bypass eder. Yani ADR-038/M51'in
"workspace izolasyonunun DB-katmanı 2. savunması" beyanı prod'da fiilen YOKTU: uygulama
katmanındaki `scope_filter` tek bir uçta unutulduğunda (BUG #162 tam olarak böyle olmuştu)
arkada duran hiçbir savunma kalmıyordu.

BU SCRIPT: şema sahibi (bootstrap) rolüyle bağlanır ve uygulamanın koşacağı NON-superuser
rolü yaratır/günceller + gerekli yetkileri verir. Her deploy'da `alembic upgrade head`
SONRASINDA koşar (docker-entrypoint.sh, web modu) — yeni migration'ın yarattığı tablolar da
yetkilendirilsin diye. Tekrar koşması zararsızdır (idempotent).

Rol tasarımı:
  - LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE **NOBYPASSRLS** → RLS bu role UYGULANIR.
  - Yalnız DML (SELECT/INSERT/UPDATE/DELETE) + sequence kullanımı. DDL YOK: şemayı
    migration (sahip rolü) değiştirir, uygulama değiştiremez.

Kullanım:
    python -m scripts.provision_app_role                 # env'den (deploy yolu)
    python -m scripts.provision_app_role --rol fos_app --sifre ... --admin-url postgresql://...

Env:
    MIGRATION_DATABASE_URL   şema sahibi bağlantısı (yoksa DATABASE_URL)
    APP_DB_ROLE              yaratılacak rol (varsayılan: fos_app)
    APP_DB_PASSWORD          rolün şifresi (ZORUNLU — boşsa fail-fast)
"""
from __future__ import annotations

import argparse
import os
import re
import sys

from sqlalchemy import create_engine, make_url, text

VARSAYILAN_ROL = "fos_app"

# Rol adı SQL'e format() ile gömülür (DDL'de bind parametresi kullanılamaz) — dar bir
# beyaz liste ile sınırla; quote_ident zaten kaçışlar ama girdiyi hiç bulaştırmayalım.
_GECERLI_ROL = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")

# Idempotent rol yaratma/güncelleme. NOBYPASSRLS açıkça yazılır: rol sonradan elle
# değiştirilmişse (veya eski bir deploy superuser bırakmışsa) bu koşum onu geri alır.
_ROL_SQL = """
DO $do$
DECLARE r text := :rol; p text := :sifre;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
        EXECUTE format('CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                       'NOBYPASSRLS PASSWORD %L', r, p);
    ELSE
        EXECUTE format('ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE '
                       'NOBYPASSRLS PASSWORD %L', r, p);
    END IF;
END
$do$;
"""

# Yetkiler: mevcut tablolar + bundan sonra SAHİP rolünün yaratacağı tablolar (migration).
_YETKI_SQL = [
    "GRANT USAGE ON SCHEMA public TO {rol}",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {rol}",
    "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {rol}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {rol}",
    "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {rol}",
]


def provision(admin_url: str, rol: str, sifre: str) -> None:
    """`rol`'ü NON-superuser olarak yaratır/günceller ve DML yetkilerini verir (idempotent)."""
    if not _GECERLI_ROL.match(rol):
        raise ValueError(f"gecersiz rol adi: {rol!r} (beklenen: ^[a-z_][a-z0-9_]*$)")
    if not sifre:
        raise ValueError("APP_DB_PASSWORD bos — sifresiz app rolu yaratilmaz (fail-fast)")

    eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with eng.connect() as conn:
            conn.execute(text(_ROL_SQL), {"rol": rol, "sifre": sifre})
            for sql in _YETKI_SQL:
                conn.execute(text(sql.format(rol=f'"{rol}"')))
            # Kanıt: rol gerçekten RLS'e tabi mi? (superuser/BYPASSRLS ise savunma yok)
            satir = conn.execute(text(
                "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :r"
            ), {"r": rol}).one()
            if satir.rolsuper or satir.rolbypassrls:
                raise RuntimeError(
                    f"'{rol}' RLS'i bypass ediyor (super={satir.rolsuper}, "
                    f"bypassrls={satir.rolbypassrls}) — DB-katmani 2. savunma etkisiz"
                )
    finally:
        eng.dispose()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="PostgreSQL uygulama rolu provizyonu (idempotent)")
    ap.add_argument("--admin-url", default=None, help="sema sahibi baglantisi")
    ap.add_argument("--rol", default=None)
    ap.add_argument("--sifre", default=None)
    a = ap.parse_args(argv)

    admin_url = a.admin_url or os.getenv("MIGRATION_DATABASE_URL") or os.getenv("DATABASE_URL", "")
    if not admin_url:
        print("[provision] DATABASE_URL yok — atlaniyor.", file=sys.stderr)
        return 0
    if make_url(admin_url).get_backend_name() != "postgresql":
        # Dev SQLite (hibrit, ADR-038): RLS yok, rol kavrami yok → no-op.
        print("[provision] postgres degil (dev SQLite) — rol provizyonu atlandi.")
        return 0

    rol = a.rol or os.getenv("APP_DB_ROLE") or VARSAYILAN_ROL
    sifre = a.sifre if a.sifre is not None else os.getenv("APP_DB_PASSWORD", "")
    provision(admin_url, rol, sifre)
    print(f"[provision] '{rol}' rolu hazir (NOSUPERUSER/NOBYPASSRLS, DML yetkili).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
