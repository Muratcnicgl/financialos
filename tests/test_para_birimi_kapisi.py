"""
PARA BİRİMİ KAPISI (BUG #256 / H4) — "tek kaynak" iddiasını ölçen statik kapı.

NEDEN
-----
Para biçimlendirme bu projede **yedi ayrı yerde** bağımsız yazılmıştı:
backend'de `rules_engine._tl` + `action_executor._fmt` + yüzlerce elle `" TL"` soneki
+ `grounding` deseninin içindeki `TL` literali; frontend'de `api.js formatTL` +
`DebtStrategy` yerel `TL()` + iki modalın kendi `toLocaleString`'u. Aynı kuralın çok
yerde kodlanması bu projenin en pahalı hata sınıfıdır (BUG #161 / SBN-001 ailesi).

Tek kaynağa indirmek YETMEZ — **geri sızmayı ölçen bir kapı olmadan** bir sonraki
özellik yeni bir `" TL"` ekler ve kimse fark etmez. Bu dosya o kapıdır.

KAPININ KENDİ KAPSAMI (L11 / H25)
---------------------------------
"Hepsini tarıyorum" diyen her kapı, taradığı yüzeyi assert etmelidir; bu projede en az
dört kapı kapsamı ölçülmediği için sessizce ölü bulundu (#217, #250, #252). Bu yüzden
aşağıda taranan dosya sayısı ve envanter toplamı için TABAN/TAVAN assert'leri var.

MUAFİYET
--------
Gerçekten metin olan (koç prompt'u, değerlendirme fixture'ı) yerler `MUAF_ENVANTER`
sözlüğünde **sayısıyla** tutulur. Sayı yalnız AZALABİLİR: yeni bir sabit eklemek kapıyı
kırar. Bu, "muafiyet listesi sessizce şişer" tuzağına karşıdır (L27).
"""
from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent
APP = KOK / "app"
FRONT = KOK / "frontend" / "src"

PARA_ISARETLERI = ("TL", "₺")

# --------------------------------------------------------------------------- backend

# Gerekçeli muafiyet: dosya -> (izin verilen sabit sayısı, neden).
# SAYI YALNIZ AZALABİLİR (kapı, artışı kırmızı yapar).
MUAF_ENVANTER: dict[str, tuple[int, str]] = {
    "app/money_format.py": (4, "TEK KAYNAK — etiket/simge burada tanımlanır"),
    "app/coach.py": (5, "V3 sistem prompt'u: LLM'e verilen ÖRNEK cümleler (konuşma metni, biçimlendirme değil)"),
    "app/coach_eval.py": (3, "değerlendirme fixture'ları — kullanıcının yazdığı varsayılan mesajları taklit eder"),
    "app/premortem.py": (2, "LLM prompt talimatı ('somut TL etki tahmin et') — konuşma metni"),
    "app/auth.py": (2, "yanlış-pozitif: 'ACCESS_TTL_MIN'/'REFRESH_TTL_DAYS' içindeki TTL"),
    "app/routers/user.py": (1, "422 mesajı: para birimi kilidinin GEREKÇESİNİ anlatır (ADR-042)"),
    # BUG #266: payload şablonundaki `<TL>` LLM'e gösterilen YER TUTUCUDUR — kullanıcıya
    # tutar basmaz, biçimlendirme yapmaz. Prompt metni (app/coach.py muafiyetiyle aynı sınıf).
    "app/action_schema.py": (1, "prompt şablonu yer tutucusu `<TL>` — kullanıcıya tutar basmaz"),
    # BUG #277: üslup sözleşmesinin ÖLÇÜM korpusu — koçun gerçek cümlelerini taklit eden
    # ihlal/meşru örnekleri (coach_eval fixture muafiyetiyle aynı sınıf). Bu dosya hiçbir
    # tutar biçimlendirmez; korpustan "TL"yi atmak, yanlış-pozitif ölçümünü gerçek koç
    # metninden uzaklaştırırdı — kapıyı memnun etmek için ölçümü zayıflatmak olurdu.
    "app/uslup_kurallari.py": (5, "üslup ölçüm korpusu: koç cümlelerini taklit eden fixture metinleri"),
}

BACKEND_TABAN_DOSYA = 60      # app/ altında taranması beklenen en az .py dosyası
# BUG #277: 20 → 25. Artış SESSİZ değil: yeni muafiyet satırı + gerekçe + bu yorum aynı
# commit'te yazıldı. Kapının amacı tutar BİÇİMLENDİRMESİNİ tek kaynağa bağlamaktır;
# eklenen 5 sabit ölçüm fixture'ıdır, biçimlendirme değil.
BACKEND_TAVAN_SABIT = 25      # tüm app/ genelinde izin verilen toplam sabit (22 muaf + pay)


def _backend_dosyalar() -> list[Path]:
    return [p for p in sorted(APP.rglob("*.py")) if "__pycache__" not in str(p)]


def _docstring_idleri(agac: ast.AST) -> set[int]:
    ids: set[int] = set()
    for d in ast.walk(agac):
        if isinstance(d, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if d.body and isinstance(d.body[0], ast.Expr) and isinstance(d.body[0].value, ast.Constant) \
                    and isinstance(d.body[0].value.value, str):
                ids.add(id(d.body[0].value))
    return ids


def backend_envanter() -> dict[str, int]:
    """Dosya -> docstring DIŞINDA para işareti taşıyan string sabit sayısı."""
    sonuc: dict[str, int] = {}
    for p in _backend_dosyalar():
        rel = str(p.relative_to(KOK)).replace("\\", "/")
        try:
            agac = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        doc_ids = _docstring_idleri(agac)
        n = 0
        for d in ast.walk(agac):
            if isinstance(d, ast.Constant) and isinstance(d.value, str) and id(d) not in doc_ids:
                if any(i in d.value for i in PARA_ISARETLERI):
                    n += 1
        if n:
            sonuc[rel] = n
    return sonuc


def test_backend_kapsam_tabani():
    """Kapı gerçekten app/ altını geziyor mu (kütüphane/patika değişimi kapıyı körleştirmesin)."""
    dosyalar = _backend_dosyalar()
    assert len(dosyalar) >= BACKEND_TABAN_DOSYA, (
        f"tarama yüzeyi çöktü: {len(dosyalar)} dosya (taban {BACKEND_TABAN_DOSYA})"
    )


def test_backend_para_sabiti_yalniz_gerekceli_yerlerde():
    envanter = backend_envanter()
    ihlaller = []
    for rel, adet in sorted(envanter.items()):
        izin, _neden = MUAF_ENVANTER.get(rel, (0, ""))
        if adet > izin:
            ihlaller.append(f"{rel}: {adet} sabit (izin {izin})")
    assert not ihlaller, (
        "Backend'de gerekçesiz para birimi sabiti var — tutar üreten yer "
        "`money_format.format_para` kullanmalı:\n  " + "\n  ".join(ihlaller)
    )


def test_backend_muafiyet_listesi_sismedi():
    """L27: muafiyet listesi sessizce büyüyemez; toplam tavan assert'li."""
    toplam = sum(backend_envanter().values())
    assert toplam <= BACKEND_TAVAN_SABIT, (
        f"para sabiti toplamı {toplam} > tavan {BACKEND_TAVAN_SABIT} — muafiyet listesi şişiyor"
    )
    for rel, (izin, neden) in MUAF_ENVANTER.items():
        assert len(neden) >= 15, f"{rel}: muafiyet gerekçesi çok kısa"
        assert (KOK / rel).exists(), f"{rel}: muafiyet listesinde ama dosya yok (liste bayat)"


def test_backend_ikinci_bir_bicimlendirici_yok():
    """`_tl` ve `_fmt` gövdeleri tek kaynağa DEVRETMELİ (kendi implementasyonlarını taşımamalı)."""
    for rel, ad in (("app/rules_engine.py", "_tl"), ("app/action_executor.py", "_fmt")):
        kaynak = (KOK / rel).read_text(encoding="utf-8")
        agac = ast.parse(kaynak)
        fn = next((d for d in ast.walk(agac)
                   if isinstance(d, ast.FunctionDef) and d.name == ad), None)
        assert fn is not None, f"{rel}: {ad} kayboldu — kapı ölçtüğü şeyi bulamıyor"
        # Docstring'i AT: fonksiyonun docstring'i eski kalıbı (':,.2f') TARİF ediyor —
        # metin taraması onu ihlal sanardı (yanlış-pozitif; L11 ailesi).
        govde_dugumleri = fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                                          and isinstance(fn.body[0].value, ast.Constant)
                                          and isinstance(fn.body[0].value.value, str)) else fn.body
        govde = "\n".join((ast.get_source_segment(kaynak, d) or "") for d in govde_dugumleri)
        assert "tr_sayi" in govde, (
            f"{rel}:{ad} kendi biçimlendirmesini yapıyor — `money_format.tr_sayi`'ya devretmeli"
        )
        assert ":,." not in govde, f"{rel}:{ad} gövdesinde ham format kalıbı kaldı"


def test_grounding_tek_kaynaktan_besleniyor():
    """Doğrulama katmanı etiketi kendi yazmamalı (yoksa para birimi değişince sessiz-yeşil)."""
    kaynak = (KOK / "app" / "grounding.py").read_text(encoding="utf-8")
    kod = " ".join(t.string for t in tokenize.generate_tokens(io.StringIO(kaynak).readline)
                   if t.type not in (tokenize.COMMENT, tokenize.STRING))
    assert "taninan_etiketler" in kod
    assert "TL" not in kod


# -------------------------------------------------------------------------- frontend

FRONT_TABAN_DOSYA = 40
FRONT_MUAF = {
    "lib/money.js",           # tek kaynak
    "api.js",                 # yalnız geriye-uyum re-export'u
}


def _front_dosyalar() -> list[Path]:
    return [p for p in sorted(FRONT.rglob("*"))
            if p.suffix in (".js", ".jsx")
            and not p.name.endswith((".test.js", ".test.jsx"))
            and "__fixtures__" not in str(p)]


def _yorumsuz(metin: str) -> str:
    """JS yorumlarını at — yorumdaki 'TL' kelimesi davranış değildir (yanlış-pozitif)."""
    metin = re.sub(r"/\*.*?\*/", "", metin, flags=re.S)
    metin = re.sub(r"^\s*//.*$", "", metin, flags=re.M)
    metin = re.sub(r"\{/\*.*?\*/\}", "", metin, flags=re.S)
    return metin


def test_frontend_kapsam_tabani():
    dosyalar = _front_dosyalar()
    assert len(dosyalar) >= FRONT_TABAN_DOSYA, (
        f"frontend tarama yüzeyi çöktü: {len(dosyalar)} dosya (taban {FRONT_TABAN_DOSYA})"
    )


def test_frontend_ham_para_etiketi_yok():
    """JSX içinde elle yazılmış ' TL' / '(TL)' / '>TL<' kalmamalı."""
    desen = re.compile(r"[^\w]TL\b|\(TL\)|>TL<")
    ihlaller = []
    for p in _front_dosyalar():
        rel = str(p.relative_to(FRONT)).replace("\\", "/")
        if rel in FRONT_MUAF:
            continue
        for i, satir in enumerate(_yorumsuz(p.read_text(encoding="utf-8")).splitlines(), 1):
            if desen.search(satir):
                ihlaller.append(f"{rel}:{i}: {satir.strip()[:90]}")
    assert not ihlaller, (
        "Frontend'de ham para etiketi var — `formatPara()` / `paraEtiketi()` kullan:\n  "
        + "\n  ".join(ihlaller)
    )


def test_frontend_ikinci_bicimlendirici_yok():
    """`Intl.NumberFormat` / `toLocaleString` yalnız tek kaynakta kurulabilir."""
    ihlaller = []
    for p in _front_dosyalar():
        rel = str(p.relative_to(FRONT)).replace("\\", "/")
        if rel in FRONT_MUAF:
            continue
        govde = _yorumsuz(p.read_text(encoding="utf-8"))
        for i, satir in enumerate(govde.splitlines(), 1):
            if "currency-exempt:" in satir:
                continue
            if "Intl.NumberFormat" in satir or re.search(r"\.toLocaleString\(", satir):
                # tarih biçimlendirme muaf (para değil)
                if "toLocaleDateString" in satir or "DateTimeFormat" in satir:
                    continue
                ihlaller.append(f"{rel}:{i}: {satir.strip()[:90]}")
    assert not ihlaller, (
        "Frontend'de ikinci bir sayı/para biçimlendiricisi kuruluyor — `lib/money.js` kullan "
        "ya da satıra `// currency-exempt: <neden>` yaz:\n  " + "\n  ".join(ihlaller)
    )


def test_api_js_yalniz_yeniden_disa_aktarir():
    """api.js formatlama GÖVDESİ taşımamalı (tek kaynak lib/money.js)."""
    kaynak = (FRONT / "api.js").read_text(encoding="utf-8")
    assert "export { formatSayi as formatTL" in kaynak, "geriye-uyum re-export'u kayboldu"
    assert "new Intl.NumberFormat" not in kaynak, "api.js yeniden kendi biçimlendiricisini kurmuş"


# --------------------------------------------------------------- kapının mutasyonu

def test_kapi_ihlali_gercekten_yakalar(tmp_path, monkeypatch):
    """
    Kapı kendi işini yapıyor mu: sahte bir ihlal dosyası eklenince kırmızıya dönmeli.
    (Kapının kendisini test etmeyen kapı, ölçtüğünü varsayar — L11 ailesi.)
    """
    sahte = FRONT / "_kapi_mutasyon_deneme.jsx"
    sahte.write_text("export const X = () => <span>1.234,56 TL</span>;\n", encoding="utf-8")
    try:
        with pytest.raises(AssertionError):
            test_frontend_ham_para_etiketi_yok()
    finally:
        sahte.unlink()
    # mutasyon geri alınınca yeşile dönmeli
    test_frontend_ham_para_etiketi_yok()
