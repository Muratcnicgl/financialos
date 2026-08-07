"""
KAPI — BUG #264 / ADR-046: üretim kodunda kategori ADINA bağlı karar YASAK.

Neden kapı (L3/L11): BUG #264 tek bir sabit kümenin hatası değildi, bir ALIŞKANLIKTI —
"şu kategoriler kart harcamasıdır", "şu kategoriler muhasebe işlemidir" bilgisi iki ayrı
modülde, iki ayrı sabit küme olarak yaşıyordu. Fix'i yazmak yetmez; aynı kümenin üçüncü
bir yerde yeniden doğmasını ölçen bir şey gerekir. Kararın tek kaynağı
`app/category_rules.py`; başka her yerde kategori slug'larından oluşan bir literal
koleksiyon, kararın oraya sızdığının işaretidir.

Kapının KENDİSİ de ölçülür (L3): kapsam tabanı assert'li — kütüphane/dizin değişikliği
taramayı sessizce körleştiremez (H25/BUG #217 dersi).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"

# Kategori slug'ları — bunlardan EŞİK kadarı tek bir literal koleksiyonda toplanmışsa,
# orada kategoriye bağlı bir karar veriliyor demektir.
_SLUGLAR = {
    "yemek", "eglence", "sigara", "alisveris", "market", "ulasim", "fatura", "saglik",
    "kira", "abonelik", "sigorta", "internet", "telefon", "diger",
    "transfer", "borc_odeme", "borc_geri_odeme", "kredi_taksiti", "borc", "kredi",
    "loan_payment", "debt_payment",
}
_ESIK = 3

# Gerekçeli muafiyetler. TAVAN vardır: liste büyüyorsa borç geri geliyor demektir.
_MUAF = {
    # Tek doğruluk kaynağının kendisi — varsayılan set burada tanımlanır (ADR-046 madde 3).
    "category_rules.py",
    # Öneri katmanı: metinden kategori TÜRETİR (QUICK_KEYWORDS / MERCHANT_KEYWORDS).
    # Karar değil kolaylık — kullanıcının verdiği kategoriyi asla ezmez (FEAT-034) ve
    # ürettiği değer yine kullanıcının kayıtlarıyla eşleşir.
    "transactions.py",
}
_MUAF_TAVANI = 2

# Kaldırılan sabitler: geri gelirlerse kapı kırmızıya döner.
_YASAK_ISIMLER = {"_CARD_CATEGORIES", "_PATTERN_EXCLUDED_CATEGORIES", "_EXCLUDED_SQL"}


def _py_dosyalari():
    return sorted(p for p in APP.rglob("*.py") if "__pycache__" not in p.parts)


def _literal_stringler(node: ast.AST) -> set:
    """Bir koleksiyon literalindeki string sabitler (Set/List/Tuple/Dict anahtarları)."""
    if isinstance(node, (ast.Set, ast.List, ast.Tuple)):
        ogeler = node.elts
    elif isinstance(node, ast.Dict):
        ogeler = [k for k in node.keys if k is not None]
    else:
        return set()
    return {o.value for o in ogeler if isinstance(o, ast.Constant) and isinstance(o.value, str)}


FRONTEND = Path(__file__).resolve().parent.parent / "frontend" / "src"

# Frontend'de kategori listesi tek kaynaktan gelir (src/lib/categories.js). Panel içinde
# yeniden tanımlanan liste, BUG #264'ün frontend ayağının geri gelmesidir: üç panel üç
# ayrı, birbirinden FARKLI liste kodluyordu ve kullanıcı setini hiçbir yerde kuramıyordu.
_FRONTEND_MUAF = {"categories.js"}


def _jsx_dosyalari():
    return sorted(p for p in FRONTEND.rglob("*.js*")
                  if p.suffix in (".js", ".jsx") and "node_modules" not in p.parts)


def _bayrak_erisimi(yol: Path, ad: str) -> bool:
    """Dosya bu bayrağı KOD olarak okuyor/yazıyor mu? (yorum ve docstring sayılmaz)

    Sayılan biçimler: `x.<ad>`, `<ad>=` (keyword arg / kwarg), `<ad> = ...` (kolon tanımı),
    `"<ad>"` sözlük anahtarı. Sayılmayan: `<ad>_mi(...)` çağrısı — o zaten tek kaynak.
    """
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    for d in ast.walk(agac):
        if isinstance(d, ast.Attribute) and d.attr == ad:
            return True
        if isinstance(d, ast.keyword) and d.arg == ad:
            return True
        if isinstance(d, ast.Name) and d.id == ad:
            return True
        if isinstance(d, ast.Constant) and d.value == ad:
            return True
    return False


def test_kapsam_tabani():
    """Kapı gerçekten bir şey tarıyor mu? (H25: taban assert edilmeden kapı sayılmaz)"""
    dosyalar = _py_dosyalari()
    assert len(dosyalar) >= 40, f"app/ taraması körleşmiş olabilir: {len(dosyalar)} dosya"
    assert any(p.name == "category_rules.py" for p in dosyalar)


def test_muafiyet_tavani_asilmadi():
    assert len(_MUAF) <= _MUAF_TAVANI, (
        "Kategori kararı yeni bir dosyaya sızdı ve muafiyetle kapatıldı. "
        "Muafiyet eklemek yerine kararı app/category_rules.py'ye taşı."
    )


@pytest.mark.parametrize("yol", _py_dosyalari(), ids=lambda p: p.name)
def test_kategori_kumesi_uretim_kodunda_YOK(yol: Path):
    """Kategori slug'larından oluşan literal koleksiyon = karar kaçmış demektir."""
    if yol.name in _MUAF:
        return
    agac = ast.parse(yol.read_text(encoding="utf-8"))
    for dugum in ast.walk(agac):
        bulunan = _literal_stringler(dugum) & _SLUGLAR
        assert len(bulunan) < _ESIK, (
            f"{yol.name}:{getattr(dugum, 'lineno', '?')} — {sorted(bulunan)} kategori "
            f"slug'ı tek bir literal koleksiyonda. Kategoriye bağlı karar tek kaynakta "
            f"olmalı (app/category_rules.py, ADR-046)."
        )


@pytest.mark.parametrize("yol", _py_dosyalari(), ids=lambda p: p.name)
def test_kaldirilan_sabitler_geri_gelmedi(yol: Path):
    metin = yol.read_text(encoding="utf-8")
    agac = ast.parse(metin)
    for dugum in ast.walk(agac):
        if isinstance(dugum, ast.Assign):
            for hedef in dugum.targets:
                if isinstance(hedef, ast.Name) and hedef.id in _YASAK_ISIMLER:
                    pytest.fail(
                        f"{yol.name}:{dugum.lineno} — '{hedef.id}' geri geldi. Kategori "
                        f"kararı sabit kümeye değil `Category` bayrağına bağlıdır (ADR-046)."
                    )


def test_kart_karari_tek_yerden_verilir():
    """`kart_varsayilani` bayrağını okuyan tek yer category_rules'tır; çağıranlar
    bayrağı kendileri sorgulayıp kendi eşiklerini uyduramaz."""
    # `kart_varsayilani_mi(...)` ÇAĞIRMAK serbest — karar zaten tek kaynaktan alınıyor.
    # Yasak olan bayrağı KENDİ okuyup yorumlamak. Ölçüm AST ile: yorum/docstring sayılmaz.
    okuyanlar = sorted({p.name for p in _py_dosyalari()
                        if _bayrak_erisimi(p, "kart_varsayilani")})
    # category_rules (tanım+okuma), models (kolon), categories router (CRUD).
    assert set(okuyanlar) <= {"category_rules.py", "models.py", "categories.py"}, (
        f"kart_varsayilani beklenmedik dosyalarda okunuyor: {okuyanlar}"
    )


def test_sistem_bayragi_tek_yerden_yorumlanir():
    """Aynı kural `sistem` bayrağı için: yorumlayan tek yer category_rules.

    `rules_engine` dışlamayı tek kaynaktan ALIR; `Category.sistem`'i kendisi sorgulayıp
    kendi kümesini kurmaz (kurarsa ikinci bir doğruluk kaynağı doğar)."""
    kaynak = (APP / "rules_engine.py").read_text(encoding="utf-8")
    assert "sistem_slug_kumesi(" in kaynak, "rules_engine dışlamayı tek kaynaktan almalı"

    okuyanlar = sorted({p.name for p in _py_dosyalari() if _bayrak_erisimi(p, "sistem")})
    assert set(okuyanlar) <= {"category_rules.py", "models.py", "categories.py"}, (
        f"`sistem` bayrağı beklenmedik dosyalarda yorumlanıyor: {okuyanlar}"
    )


# ============================================================================
# FRONTEND — aynı borç, aynı kapı (üç panel üç ayrı liste kodluyordu)
# ============================================================================

def test_frontend_kapsam_tabani():
    dosyalar = _jsx_dosyalari()
    assert len(dosyalar) >= 30, f"frontend taraması körleşmiş olabilir: {len(dosyalar)} dosya"
    assert any(p.name == "categories.js" for p in dosyalar), "tek kaynak modülü yok"


@pytest.mark.parametrize("yol", _jsx_dosyalari(), ids=lambda p: p.name)
def test_frontend_sabit_kategori_listesi_YOK(yol: Path):
    """Panel içinde kategori slug'larından oluşan dizi = liste yeniden kodlanmış demektir.

    Ölçüm: tek bir `[...]` / `{...}` literalinde EŞİK kadar bilinen slug. `datalist`/`select`
    içinde kullanıcının kayıtlarından map edilen listeler bu kapıya takılmaz (literal değil).
    """
    if yol.name in _FRONTEND_MUAF:
        return
    metin = yol.read_text(encoding="utf-8")
    # Satır bazlı değil, literal-blok bazlı bak: JS'i AST'siz tararken en yakın ölçüm,
    # aynı köşeli/süslü parantez bloğu içindeki tırnaklı sabitler.
    for blok in re.findall(r"[\[{][^\[\]{}]*[\]}]", metin, flags=re.S):
        bulunan = {m for m in re.findall(r"['\"]([a-z_ ]{3,30})['\"]", blok)} & _SLUGLAR
        assert len(bulunan) < _ESIK, (
            f"{yol.name} — {sorted(bulunan)} kategori slug'ı tek bir literalde. Kategori "
            f"listesi kullanıcının kayıtlarından gelir (src/lib/categories.js, ADR-046)."
        )


def test_frontend_kaldirilan_listeler_geri_gelmedi():
    yasak = {"COMMON_CATEGORIES", "EXPENSE_CATEGORIES"}
    for yol in _jsx_dosyalari():
        metin = yol.read_text(encoding="utf-8")
        for ad in yasak:
            # Yorumda ADI GEÇEBİLİR (neden kaldırıldığını anlatan not) — atama yasak.
            assert not re.search(rf"^\s*(const|let|var)\s+{ad}\b", metin, flags=re.M), (
                f"{yol.name} — '{ad}' geri geldi. Kategori listesi tek kaynaktan gelir (ADR-046)."
            )
