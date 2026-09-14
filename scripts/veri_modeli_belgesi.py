"""
Veri modeli belgesi — ÜRETİLİR, elle yazılmaz (DOCS-012 / BUG #473).

`docs/architecture/data-model.md` SQLAlchemy metadata'dan türer: tablo, sütun, tip, boşluk,
varsayılan, FK (+ silme kuralı), indeks/benzersizlik, denetim/saklama/kapsam konvansiyonları.
Elle yazılan ER belgesi ilk göçte bayatlar; bu belge `test_veri_modeli_belgesi_kapisi` ile
modelle aynı içerikte tutulur (backlog indeksiyle aynı desen: üretici tek, kapı üreticiyi çağırır).

Kullanım:
    python scripts/veri_modeli_belgesi.py --yaz     # belgeyi yeniden üretir
    python scripts/veri_modeli_belgesi.py           # yalnız stdout
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KOK))

HEDEF = KOK / "docs" / "architecture" / "data-model.md"
BASLIK = "<!-- OTOMATIK-VERI-MODELI — elle düzenleme; `python scripts/veri_modeli_belgesi.py --yaz` -->"


def _tip(col) -> str:
    try:
        return str(col.type)
    except Exception:  # noqa: BLE001 — tip adı gösterim amaçlıdır
        return col.type.__class__.__name__


def _varsayilan(col) -> str:
    d = col.default
    if d is None:
        sd = col.server_default
        return f"server: {getattr(sd, 'arg', sd)!s}" if sd is not None else ""
    arg = getattr(d, "arg", d)
    if callable(arg):
        return f"fn:{getattr(arg, '__name__', 'callable')}"
    return repr(arg)


def uret() -> str:
    from sqlalchemy import Float, Numeric

    from app import butunluk, denetim  # noqa: F401  (kurallar/denetim tabloları için)
    from app.models import Base
    from app.scheduler import SAKLAMA_KURALLARI

    denetlenen = denetim.denetlenen_tablolar()
    saklama = {k.tablo: k.gun for k in SAKLAMA_KURALLARI}
    satirlar = [BASLIK, "", "# Veri Modeli", "",
                "Bu belge `app/models.py` metadata'sından ÜRETİLİR (DOCS-012 / BUG #473). Konvansiyonlar:",
                "",
                "- **Para:** `Numeric(19,4)` (ADR-030, kuruş kesinliği; NUMERIC-030 kapısı). Kart bakiyesi BORÇ olarak pozitif.",
                "- **Zaman:** `created_at` sunucu UTC; kullanıcı günü `user_today()` ile (BUG #197/#237). Naive/aware karışımı DATA-007'de kayıtlı.",
                "- **Kapsam:** `user_id` + `workspace_id` (M43); sorgular `scope_filter`/`_scope` ile, istisna `# scope-exempt: <sebep>`.",
                "- **Denetim:** `user_id` + para sütunu olan tablolar `audit_log`'a flush kancasıyla yazar (BUG #418/#443); muaflar/ekler `app/denetim.py`.",
                "- **Bütünlük:** DB CHECK yerine ORM `before_flush` kuralları (`app/butunluk.py`, BUG #444–#447).",
                "- **Saklama:** `app/scheduler.py::SAKLAMA_KURALLARI` (gün); KVKK silme `app/data_subject.py` kaydı.",
                ""]
    for t in sorted(Base.metadata.sorted_tables, key=lambda x: x.name):
        rozet = []
        if t.name in denetlenen:
            rozet.append("denetlenir")
        if t.name in saklama:
            rozet.append(f"saklama {saklama[t.name]} gün")
        if "workspace_id" in t.c:
            rozet.append("workspace kapsamlı")
        satirlar.append(f"## `{t.name}`" + (f" — {', '.join(rozet)}" if rozet else ""))
        satirlar.append("")
        satirlar.append("| Sütun | Tip | Boş | Varsayılan | FK | Not |")
        satirlar.append("|---|---|---|---|---|---|")
        for c in t.columns:
            fk = ", ".join(f"{f.column.table.name}.{f.column.name}" + (f" ({f.ondelete})" if f.ondelete else "") for f in c.foreign_keys)
            notlar = []
            if c.primary_key:
                notlar.append("PK")
            if c.unique:
                notlar.append("unique")
            if c.index:
                notlar.append("index")
            if isinstance(c.type, Numeric) and not isinstance(c.type, Float):   # Float, Numeric'in alt sınıfı; oran/faiz para değil
                notlar.append("para")
            satirlar.append(f"| `{c.name}` | {_tip(c)} | {'evet' if c.nullable else 'hayır'} | {_varsayilan(c)} | {fk} | {' '.join(notlar)} |")
        ek = []
        for i in sorted(t.indexes, key=lambda x: x.name or ""):
            ek.append(f"{'unique ' if i.unique else ''}index `{i.name}` ({', '.join(c.name for c in i.columns)})")
        for cst in t.constraints:
            ad = cst.__class__.__name__
            if ad in ("UniqueConstraint", "CheckConstraint"):
                cols = ", ".join(getattr(c, "name", str(c)) for c in getattr(cst, "columns", []))
                ek.append(f"{ad} {getattr(cst, 'name', '') or ''} ({cols})".strip())
        if ek:
            satirlar.append("")
            satirlar.append("İndeks/kısıt: " + "; ".join(ek))
        satirlar.append("")
    return "\n".join(satirlar).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Veri modeli belgesini metadata'dan üretir.")
    ap.add_argument("--yaz", action="store_true", help="docs/architecture/data-model.md dosyasına yazar")
    a = ap.parse_args(argv)
    metin = uret()
    if a.yaz:
        HEDEF.write_text(metin, encoding="utf-8")
        print(f"yazildi: {HEDEF} ({metin.count(chr(10))} satir)")
    else:
        sys.stdout.write(metin)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
