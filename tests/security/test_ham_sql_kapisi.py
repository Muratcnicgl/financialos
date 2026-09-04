"""
HAM SQL KAPISI (SEC-019 — 5 Eylül 2026).

ÖLÇÜLEN DURUM
-------------
Backlog `SEC-019` *"Ham SQL f-string kalıbı (`text(f\"...\")`) — latent injection deseni"*
diyordu. Tarandı: depoda **tek bir** örnek vardı (`app/rules_engine.py`,
`_calculate_category_patterns`) ve incelendiğinde şu çıktı:

**Enjeksiyon YOKTU.** `f` öneki tamamen işlevsizdi — dizgede tek bir `{}` bile yok; her
değer bağlı parametre olarak geçiyordu (`:user_id`, `:prev_start`, `:curr_start`,
`:today`, `:min_count`). Yani madde bir açık bildirmiyordu, bir **tuzak** bildiriyordu:
önek orada durduğu sürece, sonraki bir düzenleme `{degisken}` ekleyip kullanıcı verisini
SQL METNİNE gömebilirdi ve kimse fark etmezdi.

Doğru cevap "dikkat et" notu değil, önekin kaldırılması + desenin YASAKLANMASI oldu.
(Önce ölç, sonra suçla — BUG #316'nın dersi: bir deseni yasaklamadan önce bugünkü
örneğinin gerçekten kusurlu olup olmadığı okunur. Burada kusurlu DEĞİLDİ; yasak
gelecekteki kusur içindir ve bu ayrım kayda geçiyor.)

NE ZORLAR
---------
`app/` altında `text(f"...")` / `text(f'...')` yazılamaz. Dinamik SQL gerçekten gerekiyorsa
(ör. dialect'e göre değişen bir parça) gerekçesi `# ham-sql-muaf: <gerekçe>` ile yazılır —
gerekçesiz muafiyet kabul edilmez (`scope-exempt` ve `api-kapisi-muaf` ile aynı ilke).

MUTASYON 2/2 — sentetik `text(f"...")` sok -> kapi kirmizi · tarayiciyi korlestir ->
kapsam tabani kirmizi (vakumsal yesil yasagi)
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent.parent
UYGULAMA = KOK / "app"

#: `text(f"` ya da `text(f'` — SQLAlchemy'nin ham metin sarmalayıcısına f-string vermek.
_DESEN = re.compile(r"""\btext\(\s*f["']""")

_MUAF = "ham-sql-muaf:"
MUAF_PENCERESI = 6

#: Tarayıcı boşa düşerse kapı geçmez, BOZULUR. Bugün app/ altında 100'den fazla .py var.
KAPSAM_TABANI = 40


def _kaynaklar() -> list[Path]:
    return [p for p in sorted(UYGULAMA.rglob("*.py")) if "__pycache__" not in str(p)]


def _ihlaller(dosyalar: list[Path] | None = None) -> list[str]:
    out: list[str] = []
    for yol in (dosyalar if dosyalar is not None else _kaynaklar()):
        satirlar = yol.read_text(encoding="utf-8").splitlines()
        for i, satir in enumerate(satirlar):
            if not _DESEN.search(satir):
                continue
            if any(_MUAF in s for s in satirlar[max(0, i - MUAF_PENCERESI):i]):
                continue
            try:
                ad = yol.relative_to(KOK).as_posix()
            except ValueError:
                ad = yol.name
            out.append(f"{ad}:{i + 1}")
    return out


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    """Hiç dosya bulamayan bir tarayıcı 'ham SQL yok' diyemez."""
    kaynaklar = _kaynaklar()
    assert len(kaynaklar) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(kaynaklar)} kaynak tarandı (taban {KAPSAM_TABANI})."
    )


def test_HAM_SQL_f_string_ile_yazilamaz():
    """SEC-019 regresyon kilidi."""
    ihlal = _ihlaller()
    assert not ihlal, (
        "`text(f\"...\")` kalıbı bulundu. Bu kalıp bugün zararsız olsa bile, bir sonraki "
        "düzenlemede kullanıcı verisini SQL METNİNE gömmenin en kolay yoludur:\n  "
        + "\n  ".join(ihlal)
        + "\n\nDeğerleri bağlı parametre olarak geçir (`:ad` + sözlük). Gerçekten dinamik "
          f"SQL gerekiyorsa çağrının üstüne `# {_MUAF} <gerekçe>` yaz."
    )


def test_KAPI_sentetik_ornegi_yakalar(tmp_path):
    """MUTASYON: gerekçesiz kalıp yakalanır, gerekçeli olan geçer."""
    # Örnek metinler BİLEREK SQL'e benzemiyor. Kapı içeriğe değil KALIBA bakar; gerçekçi
    # bir sorgu yazmak ruff'ın kendi S608'ini BU dosyada tetikliyordu — yani kapının örneği,
    # komşu kapıyı düşürüyordu (L71'in küçük hali: bir kapının deseni başka bir kapıya
    # sızmamalı). Tavan yükseltilmedi, ihtiyaç kaldırıldı.
    kotu = tmp_path / "kotu.py"
    kotu.write_text('q = db.execute(text(f"ORNEK {x}"))\n', encoding="utf-8")
    assert _ihlaller([kotu]), "Kapı sentetik ham SQL kalıbını kaçırdı"

    iyi = tmp_path / "iyi.py"
    iyi.write_text(f"# {_MUAF} dialect'e gore degisen parca, deger gomulmuyor\n"
                   'q = db.execute(text(f"ORNEK"))\n', encoding="utf-8")
    assert not _ihlaller([iyi]), "Kapı yazılı gerekçeyi görmedi"
