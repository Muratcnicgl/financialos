"""
FRONTEND API KAPISI (BUG #351 — 5 Eylül 2026).

NEDEN VAR
---------
`frontend/PROJE.md` yazılı bir mimari kural koyuyor:

    `frontend/src/api.js` — **tüm** backend çağrıları buradan geçer. `ApiError` fırlatır;
    panel'ler try/catch ile yakalar. Doğrudan fetch/axios çağrısı panel içine yazılmaz.

**Bu kuralı hiçbir şey zorlamıyordu.** Depoda 64 JSX/JS dosyası var ve frontend tarafında
statik analiz HİÇ yok (`kalite_kapisi` ruff'ı koşar, ruff Python içindir). Yani kural
yazılıydı ve ölçülmüyordu — `masterprompt-koc.md`'nin K2 bulgusunun aynısı: *kural kodda
var ama yalnız belgeleniyor, çalışma anında zorlanmıyor.*

Ölçüm (5 Eyl 2026): kuralın **tek** ihlali vardı — `components/SistemDurumu.jsx`.

MUAFİYET DOSYAYA DEĞİL, YAZILI GEREKÇEYE BAĞLI
-----------------------------------------------
O tek ihlal incelendi ve **haklı çıktı**, ama gerekçesi hiçbir yerde yazılı değildi.
`api.js`in `request()` sarmalayıcısı 401'de oturum kurtarmayı dener ve 2xx dışında
`ApiError` fırlatır; `SistemDurumu` ise tam olarak **giriş yapamayan** kullanıcı için
vardır ve orada `503` bir hata değil, **ölçümün kendisidir**. Sarmalayıcıdan geçirmek
bileşenin var olma sebebini yok ederdi.

Bu yüzden kapı "şu dosyayı atla" demez (bu, dosyayı kalıcı olarak körleştirirdi — L67);
`// api-kapisi-muaf: <gerekçe>` yorumu ister. Gerekçesiz muafiyet kabul edilmez
(`olu_kod_kapisi`nin MUAF sözlüğü ve `test_scope_enforcement`in `# scope-exempt`'i ile
aynı ilke — üçüncü kez aynı desen, bilinçli).

MUTASYON 3/3 — muafiyet yorumunu sil -> ihlal testi kirmizi (nedensellik) · yeni bir dosyaya
gerekcesiz fetch ekle -> ihlal testi kirmizi (kapsam) · tarayiciyi korlestir -> taban testi kirmizi
"""
from __future__ import annotations

import re
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
KAYNAK = KOK / "frontend" / "src"

#: `api.js` kuralın KENDİSİDİR; testler ise ürün yolu değildir.
HARIC_ADLAR = {"api.js"}

#: Doğrudan backend çağrısı: `fetch('/api/...')` ya da herhangi bir `axios` kullanımı.
_CAGRI = re.compile(r"""\bfetch\s*\(\s*['"`]/api/|\baxios\b""")

#: Gerekçeli muafiyet işareti. Çağrının ÜSTÜNDEKİ satırlarda aranır.
_MUAF = "api-kapisi-muaf:"

#: Muafiyet yorumu çağrıdan en fazla bu kadar satır önce olabilir — gerekçe çağrının
#: YANINDA dursun, dosyanın başında unutulmuş bir yorum olmasın.
MUAF_PENCERESI = 12

#: Tarayıcı boşa düşerse kapı geçmez, BOZULUR (bugün 64 dosya var).
KAPSAM_TABANI = 30


def _dosyalar() -> list[Path]:
    return [p for p in sorted(KAYNAK.rglob("*"))
            if p.suffix in {".jsx", ".js"}
            and p.name not in HARIC_ADLAR
            and ".test." not in p.name]


def _ihlaller(dosyalar: list[Path] | None = None) -> list[str]:
    out: list[str] = []
    for yol in (dosyalar if dosyalar is not None else _dosyalar()):
        satirlar = yol.read_text(encoding="utf-8").splitlines()
        for i, satir in enumerate(satirlar):
            if not _CAGRI.search(satir):
                continue
            pencere = satirlar[max(0, i - MUAF_PENCERESI):i]
            if not any(_MUAF in s for s in pencere):
                out.append(f"{_gorunen(yol)}:{i + 1}")
    return out


def _gorunen(yol: Path) -> str:
    """Depo içindeyse göreli yol; değilse (sentetik test dosyası) düz ad."""
    try:
        return yol.relative_to(KOK).as_posix()
    except ValueError:
        return yol.name


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    """Hiç dosya bulamayan bir tarayıcı 'ihlal yok' diyemez (vakumsal yeşil yasağı)."""
    dosyalar = _dosyalar()
    assert len(dosyalar) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(dosyalar)} frontend kaynağı tarandı "
        f"(taban {KAPSAM_TABANI}). Bu 'ihlal yok' DEMEK DEĞİLDİR."
    )


def test_BACKEND_cagrilari_api_js_ten_gecer():
    """`frontend/PROJE.md`'nin yazılı kuralı, ilk kez ÖLÇÜLÜYOR."""
    ihlal = _ihlaller()
    assert not ihlal, (
        "Bu satırlar backend'i `api.js`i atlayarak çağırıyor ve gerekçesi yazılı değil:\n  "
        + "\n  ".join(ihlal)
        + "\n\nDoğru cevap sırasıyla: (1) çağrıyı `api.js`e taşı — sarmalayıcı kimlik, "
          "workspace başlığı, 401 kurtarma ve `ApiError` sözleşmesini getirir; "
          "(2) gerçekten sarmalayıcıdan geçmemesi gerekiyorsa çağrının ÜSTÜNE "
          f"`// {_MUAF} <gerekçe>` yaz. Gerekçesiz muafiyet kabul edilmez."
    )


def test_MUAFIYET_gerekcesiz_olamaz(tmp_path):
    """MUTASYON: gerekçesiz bir çağrı eklenirse kapı ateş etmeli; gerekçeliyse etmemeli."""
    gerekcesiz = tmp_path / "Gerekcesiz.jsx"
    gerekcesiz.write_text("const r = await fetch('/api/ready');\n", encoding="utf-8")
    assert _ihlaller([gerekcesiz]), "Kapı gerekçesiz doğrudan çağrıyı kaçırdı"

    gerekceli = tmp_path / "Gerekceli.jsx"
    gerekceli.write_text(
        f"// {_MUAF} 503 burada hata degil, olcumun kendisi\n"
        "const r = await fetch('/api/ready');\n", encoding="utf-8")
    assert not _ihlaller([gerekceli]), "Kapı yazılı gerekçeyi görmedi"


def test_MUAFIYET_UZAK_bir_yorumla_alinamaz(tmp_path):
    """Gerekçe çağrının YANINDA durmalı; dosyanın başındaki eski bir yorum yetmez.

    Aksi hâlde bir dosyaya bir kez muafiyet yazmak, o dosyayı sonsuza kadar körleştirirdi
    (L67 — bir kapı, kendi açıklaması yüzünden kör kalamaz).
    """
    uzak = tmp_path / "Uzak.jsx"
    uzak.write_text(
        f"// {_MUAF} eski bir gerekce\n"
        + "\n".join(f"const x{i} = {i};" for i in range(MUAF_PENCERESI + 3))
        + "\nconst r = await fetch('/api/ready');\n", encoding="utf-8")
    assert _ihlaller([uzak]), (
        "Çağrıdan çok uzaktaki bir muafiyet yorumu kabul edildi — bu, dosyayı kalıcı "
        "olarak körleştirir."
    )
