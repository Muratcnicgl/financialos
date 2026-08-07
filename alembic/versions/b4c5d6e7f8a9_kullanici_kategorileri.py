"""P3.5.3 (BUG #264 / ADR-046): categories tablosu — kategori kullaniciya ait bir KAYITTIR

Kod, kullanicinin parasiyla ilgili iki karari sabit Turkce kategori ADLARINA bagliyordu:
`_CARD_CATEGORIES` (harcama krediye mi yazilsin) ve `_PATTERN_EXCLUDED_CATEGORIES` (hangi
harcama uyari analizine girsin). Kendi setini kuran kullanicida iki kural da sessizce
oluyordu. Karar artik bu tablodaki `kart_varsayilani` / `sistem` bayraklarinda.

GOC DAVRANISI DEGISTIRMEZ (ADR-046 madde 7): her defter icin (a) varsayilan set tohumlanir,
(b) o defterde gecen ayirt edici kategori degerleri kayda cevrilir, (c) bayraklar ESKI sabit
kumelerden turetilir. Bugunku kullanici icin davranis birebir ayni; degisen tek sey SAHIPLIK.

Asagidaki set TARIHSEL bir anlik gorntudur (Alembic konvansiyonu: migration uygulama kodunu
import etmez, gecmis donar). Guncel kaynak: `app/category_rules.py`.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-07
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


# (slug, ad, kart_varsayilani, sistem) — tarihsel anlik goruntu, bkz. dosya basligi.
_TOHUM = [
    ("yemek", "Yemek", True, False),
    ("eglence", "Eğlence", True, False),
    ("sigara", "Sigara", True, False),
    ("alisveris", "Alışveriş", True, False),
    ("market", "Market", True, False),
    ("ulasim", "Ulaşım", False, False),
    ("fatura", "Fatura", False, False),
    ("saglik", "Sağlık", False, False),
    ("kira", "Kira", False, False),
    ("abonelik", "Abonelik", False, False),
    ("sigorta", "Sigorta", False, False),
    ("internet", "İnternet", False, False),
    ("telefon", "Telefon", False, False),
    ("diger", "Diğer", False, False),
    ("transfer", "Transfer", False, True),
    ("borc_odeme", "Borç ödeme", False, True),
    ("borc_geri_odeme", "Borç geri ödeme", False, True),
    ("kredi_taksiti", "Kredi taksiti", False, True),
    ("borc", "Borç", False, True),
    ("kredi", "Kredi", False, True),
    ("loan_payment", "Kredi ödemesi", False, True),
    ("debt_payment", "Borç ödemesi", False, True),
]

_TOHUM_SLUGLAR = {t[0] for t in _TOHUM}


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("workspace_id", sa.Integer(), nullable=True),
        sa.Column("slug", sa.String(length=50), nullable=False),
        sa.Column("ad", sa.String(length=50), nullable=False),
        # M50 dialect-aware boolean: server_default sa.false() (Postgres 'false', SQLite 0)
        sa.Column("kart_varsayilani", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sistem", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("gizli", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "workspace_id", "slug", name="uq_category_user_ws_slug"),
    )
    # Model `id`'yi index'li tanımlar (repo konvansiyonu — bkz. error_logs/rate_limit_hits);
    # temiz-DB kilidi (`scripts/test_fresh_db_migration.py`) şema eşitliğini dayatır.
    op.create_index("ix_categories_id", "categories", ["id"])
    op.create_index("ix_categories_workspace_id", "categories", ["workspace_id"])

    bind = op.get_bind()
    dialect = bind.dialect.name

    # Postgres'te workspace_id fiziksel FK (d4e5f6a7b8c9 deseni; SQLite'ta mantiksal)
    if dialect == "postgresql":
        op.create_foreign_key(
            "fk_categories_workspace_id", "categories", "workspaces",
            ["workspace_id"], ["id"],
        )

    # ---- Defter listesi: (user_id, workspace_id) ikilileri -------------------
    # 1) Her workspace bir defterdir; sahibi tohumu alir.
    defterler = [
        (r[0], r[1]) for r in bind.execute(
            text("SELECT owner_user_id, id FROM workspaces")
        ).fetchall()
    ]
    # 2) Hic workspace'i olmayan kullanicilar (legacy/dev kurulumu) — workspace_id NULL.
    defterler += [
        (r[0], None) for r in bind.execute(text(
            "SELECT u.id FROM users u "
            "WHERE NOT EXISTS (SELECT 1 FROM workspaces w WHERE w.owner_user_id = u.id)"
        )).fetchall()
    ]

    for user_id, ws_id in defterler:
        # (a) varsayilan set
        for slug, ad, kart, sistem in _TOHUM:
            bind.execute(
                text(
                    "INSERT INTO categories "
                    "(user_id, workspace_id, slug, ad, kart_varsayilani, sistem, gizli) "
                    "VALUES (:u, :w, :s, :a, :k, :y, :g)"
                ),
                {"u": user_id, "w": ws_id, "s": slug, "a": ad,
                 "k": bool(kart), "y": bool(sistem), "g": False},
            )

        # (b) bu defterde GERCEKTEN kullanilan, tohumda olmayan kategoriler
        if ws_id is not None:
            kosul = "workspace_id = :w"
            params = {"w": ws_id}
        else:
            kosul = "user_id = :u AND workspace_id IS NULL"
            params = {"u": user_id}

        kullanilan = set()
        for tablo, kolon in (("transactions", "category"), ("envelopes", "category")):
            rows = bind.execute(
                text(f"SELECT DISTINCT {kolon} FROM {tablo} "
                     f"WHERE {kosul} AND {kolon} IS NOT NULL AND {kolon} <> ''"),
                params,
            ).fetchall()
            kullanilan.update(r[0] for r in rows)

        for ham in sorted(kullanilan):
            slug = (ham or "").strip()[:50]
            if not slug or slug in _TOHUM_SLUGLAR:
                continue
            bind.execute(
                text(
                    "INSERT INTO categories "
                    "(user_id, workspace_id, slug, ad, kart_varsayilani, sistem, gizli) "
                    "VALUES (:u, :w, :s, :a, :k, :y, :g)"
                ),
                # Kullanicinin kendi kategorisi: ne kart varsayilani ne sistem — bugunku
                # davranis da buydu (eski sabit kumelerin hicbirinde degildi).
                {"u": user_id, "w": ws_id, "s": slug, "a": slug,
                 "k": False, "y": False, "g": False},
            )

    # RLS: workspace kapsamli her tablo 2. savunmayi tasir (ADR-038 / f5a6b7c8d9e0)
    if dialect == "postgresql":
        op.execute("ALTER TABLE categories ENABLE ROW LEVEL SECURITY")
        op.execute("ALTER TABLE categories FORCE ROW LEVEL SECURITY")
        op.execute(
            "CREATE POLICY ws_isolation ON categories USING ("
            "nullif(current_setting('app.current_workspace_id', true), '') IS NULL "
            "OR workspace_id = nullif(current_setting('app.current_workspace_id', true), '')::int"
            ")"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP POLICY IF EXISTS ws_isolation ON categories")
    op.drop_index("ix_categories_workspace_id", table_name="categories")
    op.drop_index("ix_categories_id", table_name="categories")
    op.drop_table("categories")
