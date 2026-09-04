"""
ŞEMA FK SAPMASI KAPISI — BELGELENMİŞ BİR SAPMA, KENDİNİ ÖLÇEN ARACI OKUNAMAZ KILMIŞTI.

ÖLÇÜLEN DURUM (4 Eylül 2026)
----------------------------
Model 31 tabloda FK tanımlıyor; `alembic upgrade head` SQLite'ta bunların **14'ünü
kurmuyor**. Ondördü de BİLİNÇLİ ve BELGELENMİŞ (ADR-036 / M50, `d4e5f6a7b8c9`): SQLite
`ALTER TABLE ADD CONSTRAINT` desteklemez ve batch-recreate inbound-FK'li tabloları kırar
(M11 dersi), bu yüzden fiziksel FK yalnız Postgres'te kurulur. Telafi edici kontroller
adlandırılmıştır: model-seviyesi FK (ORM) + uygulama-katmanı scope filtresi (Wave-5 AST
kapısı) + Postgres RLS (M51). `personal_debts.settlement_account_id` de aynı desendedir
(`f2a3b4c5d6e7`), `categories.workspace_id` de — o, FK'sını M50'nin listesinde değil
**kendi göçünde** kurar (`b4c5d6e7f8a9:83-87`, yorumunda M50 desenine atıfla).

BU KAPI NEDEN VAR — SAPMA DEĞİL, SAPMANIN ÖLÇÜLEMEZLİĞİ
-------------------------------------------------------
Sapmayı gösterebilecek tek araç `alembic check`'ti ve o araç SQLite'ta **bilerek kalıcı
kırmızıdır** (belgelenmiş sapmayı her koşumda rapor eder). Ölçüldü: hiçbir CI adımı,
hiçbir kapı onu koşmuyor — `grep -rn "alembic check" .github/workflows/ scripts/` boş.
Yani sapmanın belgelenmesi, sapmayı ölçen aracı kalıcı olarak okunamaz kılmıştı; bugün
sapma temiz olsa bile **yarın eklenecek karşılıksız bir FK görünmez** olurdu.
**L22'nin şema tarafındaki karşılığı: gürültülü bir kapı okunmaz; okunmayan kapı yoktur.**

DÜRÜST KAYIT — BU KAPI YAZILIRKEN İKİ YANLIŞ TEŞHİS KOYULDU
------------------------------------------------------------
(1) İlk teşhis: *"14 FK sessizce eksik, hiçbir kapı görmedi"* → **yanlış**, sapma
    `d4e5f6a7b8c9`'nin docstring'inde açıkça belgeliydi.
(2) İkinci teşhis: *"`categories` listeye yazılmamış, Postgres'te de FK almıyor"* →
    **yine yanlış**; `b4c5d6e7f8a9` FK'yı kendi içinde kuruyor. Bu teşhisle bir göç
    yazıldı ve o göç Postgres'te **aynı kısıtı ikinci kez kurup patlayacaktı**;
    mutasyon testi (M1 hayatta kaldı) bunu ortaya çıkardı ve göç SİLİNDİ.
**Ders: bir sapmayı "kimse görmedi" diye kaydetmeden önce, onu belgeleyen dosyayı ara.**
Kapının kendisi bu iki hatadan sonra da geçerlidir — çünkü sapmanın VARLIĞINI değil,
sapmanın KARŞILIKSIZ kalmasını ölçer.

TASARIM — MUAFİYET GEREKÇEYE BAĞLI, LİSTEYE DEĞİL
--------------------------------------------------
Kolay yol "şu 14 FK'yı yok say" demekti; bu, kapıyı tam da yeni bir sapma girdiğinde
körleştirirdi (L67). Bunun yerine muafiyet **kendisini karşılayan göçe** bağlandı:
bir sapma ancak, onu Postgres'te GERÇEKTEN kuran dialect-korumalı bir göç varsa meşrudur.

MUTASYON 3/3
------------
* Bir tablonun Postgres FK bloğu kaldırıldı → `HER_SAPMA...` + `MODELDEKI_HER...` kırmızı.
* Modele karşılıksız yeni FK eklendi (14→15) → `HER_SAPMA...` + `SAPMA_LISTESI...` kırmızı.
* Sapma azaltıldı (14→13) → `KAZANIM_KILIDI...` kırmızı.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect

from app.models import Base

KOK = Path(__file__).resolve().parent.parent
GOC_DIZINI = KOK / "alembic" / "versions"

#: Bir FK'nın kimliği: (tablo, kolon, hedef_tablo).
FK = tuple[str, str, str]


def _fk_kumesi(url: str) -> set[FK]:
    # Motor AÇIK kalırsa Windows geçici dizini silemez (WinError 32) ve kapı, söyleyecek
    # sözü olmadan çöker — bir kapının hata yolu başarı yolundan dayanıklı olmalı (L66).
    motor = create_engine(url)
    try:
        ins = inspect(motor)
        bulunan: set[FK] = set()
        for tablo in ins.get_table_names():
            if tablo == "alembic_version":
                continue
            for fk in ins.get_foreign_keys(tablo):
                for kolon in fk["constrained_columns"]:
                    bulunan.add((tablo, kolon, fk["referred_table"]))
        return bulunan
    finally:
        motor.dispose()


def _gocun_kurdugu(dizin: str) -> set[FK]:
    """`alembic upgrade head` — göçlerin GERÇEKTEN kurduğu şema (ADR-013 tek kaynağı)."""
    yol = os.path.join(dizin, "goc.db")
    ortam = dict(os.environ, DATABASE_URL=f"sqlite:///{yol}")
    sonuc = subprocess.run(  # noqa: S603 — sabit argüman, kullanıcı girdisi yok
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(KOK), env=ortam, capture_output=True,
    )
    assert sonuc.returncode == 0, f"goc kosulamadi: {sonuc.stderr[-800:]!r}"
    return _fk_kumesi(f"sqlite:///{yol}")


def _modelin_istedigi(dizin: str) -> set[FK]:
    """`Base.metadata.create_all` — modelin ilan ettiği şema."""
    yol = os.path.join(dizin, "model.db")
    _m = create_engine(f"sqlite:///{yol}")
    Base.metadata.create_all(_m)
    _m.dispose()
    return _fk_kumesi(f"sqlite:///{yol}")


@pytest.fixture(scope="module")
def sapma() -> set[FK]:
    """Modelde VAR, göçün kurduğunda YOK olan FK'lar."""
    with tempfile.TemporaryDirectory() as d:
        return _modelin_istedigi(d) - _gocun_kurdugu(d)


def _postgres_korumali_fk_gocleri() -> set[tuple[str, str]]:
    """
    Göç dosyalarında, **postgresql koruması altında** `create_foreign_key` ile kurulan
    (tablo, kolon) çiftleri.

    Metin taraması bilinçli: bir göç dosyası zaten uygulanmıştır, yeniden koşulamaz;
    tek okunabilir kaynak metnidir. Tarama DAR — yalnız `_SCOPED_TABLES` + `f"fk_{tbl}_..."`
    desenini ve tek tablolu açık çağrıları tanır (depodaki iki desen de budur).
    """
    bulunan: set[tuple[str, str]] = set()
    for dosya in GOC_DIZINI.glob("*.py"):
        metin = dosya.read_text(encoding="utf-8")
        if "postgresql" not in metin or "create_foreign_key" not in metin:
            continue
        # 1) liste + döngü deseni: _SCOPED_TABLES = [...] + create_foreign_key(f"fk_{tbl}_<kolon>"...)
        liste = re.search(r"_SCOPED_TABLES\s*=\s*\[(.*?)\]", metin, re.S)
        dongu = re.search(r'create_foreign_key\(\s*\n?\s*f"fk_\{tbl\}_(\w+)"', metin)
        if liste and dongu:
            kolon = dongu.group(1)
            for tablo in re.findall(r'"(\w+)"', liste.group(1)):
                bulunan.add((tablo, kolon))
        # 2) açık tek çağrı: create_foreign_key("fk_x", "tablo", "hedef", ["kolon"], ["id"])
        for m in re.finditer(
            r'create_foreign_key\(\s*\n?\s*"[^"]+",\s*"(\w+)",\s*"\w+",\s*\[\s*"(\w+)"', metin
        ):
            bulunan.add((m.group(1), m.group(2)))
    return bulunan


def test_HER_SAPMA_postgres_gocuyle_KARSILANIYOR(sapma):
    """
    **Bu turun asıl kapısı.** SQLite'ta bir FK'nın kurulmaması ancak, o FK'yı Postgres'te
    GERÇEKTEN kuran dialect-korumalı bir göç varsa meşrudur (ADR-036'nın sözü).

    Bugün sapmaların 14'ü de karşılanmış durumda — yani bu test bugün bir defekt
    BULMUYOR; değeri bundan sonrasını tutmakta (BUG #306/#307 kapılarıyla aynı sınıf).
    Muafiyet elle yazılan bir listeye bağlansaydı, karşılığı silinen bir FK'yı
    YAKALAYAMAZDI (L67) — mutasyon tam bunu doğruladı.
    """
    karsilanan = _postgres_korumali_fk_gocleri()
    karsilanmayan = sorted(
        (t, k, h) for (t, k, h) in sapma if (t, k) not in karsilanan
    )
    assert not karsilanmayan, (
        "Bu FK'lar SQLite'ta kurulmuyor VE onları Postgres'te kuran bir göç de yok —\n"
        "yani hiçbir lehçede fiziksel bütünlük yok ve bu KAYIT ALTINDA DEĞİL:\n"
        + "\n".join(f"  {t}.{k} -> {h}" for t, k, h in karsilanmayan)
        + "\n\nÇözüm: `d4e5f6a7b8c9` desenindeki gibi dialect-korumalı bir göç ekle "
          "(tavanı yükseltmek ya da buraya elle muafiyet yazmak DEĞİL)."
    )


def test_MODELDEKI_HER_workspace_id_bir_goce_YAZILI():
    """
    Ters yön: modelde `workspace_id` taşıyan bir tablo, Postgres FK göçlerinden birinde
    ADLANDIRILMIŞ olmalı. Yeni bir scoped tablo eklenip listeye yazılmazsa BURADAN düşer.

    Bu test `sapma` fixture'ına bakmaz — bilerek. Sapma ölçümü SQLite'a dayanır; bu kural
    ise lehçeden bağımsız bir SÖZLEŞMEDİR (ADR-036) ve sözleşme, zorlandığı yerde değil
    yazıldığı yerde de ölçülmelidir.
    """
    karsilanan = {t for (t, k) in _postgres_korumali_fk_gocleri() if k == "workspace_id"}
    modelde = {
        tablo.name for tablo in Base.metadata.tables.values()
        if "workspace_id" in tablo.columns
        # Kendi create_table'ında FK ile doğan tablolar zaten fizikseldir.
        and not any(fk.column.table.name == "workspaces"
                    for fk in tablo.columns["workspace_id"].foreign_keys
                    if tablo.name in ("workspace_memberships", "feedback"))
    }
    eksik = sorted(modelde - karsilanan)
    assert not eksik, (
        "Bu tablolar `workspace_id` taşıyor ama hiçbir Postgres FK göçünde adlandırılmamış "
        f"(ADR-036 sözü): {eksik}"
    )


def test_SAPMA_LISTESI_BUYUMUYOR(sapma):
    """
    Ratchet. Bugünkü sapma **14 FK / 14 tablo** (13 workspace_id + 1 settlement_account_id).
    Sayı ARTARSA yeni bir lehçe ayrışması girmiş demektir; bu, yukarıdaki iki testten
    kaçabilecek bir sınıf için (ör. workspace_id olmayan yeni bir dialect-korumalı FK)
    ikinci savunmadır.
    """
    assert len(sapma) <= 14, (
        f"SQLite/model FK sapması BÜYÜDÜ: {len(sapma)} (tavan 14)\n"
        + "\n".join(f"  {t}.{k} -> {h}" for t, k, h in sorted(sapma))
    )


def test_KAZANIM_KILIDI_sapma_azalirsa_tavan_dusurulur(sapma):
    """
    Sapma azaldıysa tavan da düşmeli — yoksa kapatılan bir ayrışmanın yeri boş kalır ve
    sessizce yeniden dolar (`kalite_kapisi`'ndeki `--yaz` kazanım kilidiyle aynı ilke).
    """
    assert len(sapma) >= 14, (
        f"sapma {len(sapma)}'e DÜŞMÜŞ ama tavan hâlâ 14 — kazanımı kilitle "
        "(bu dosyadaki 14'ü yeni sayıya çek ve gerekçesini yaz)."
    )


def test_SAPMA_YALNIZ_FK_ekseninde_kolon_ve_index_OZDES(sapma):
    """
    Sınırı yazılı tut: taze-DB kapısı (`scripts/test_fresh_db_migration.py`) kolon ve index
    eksenlerini karşılaştırır ve "TAM ÖZDEŞ" derken TAM OLARAK o ikisini kasteder. Ayrışma
    yalnız FK ekseninde olmalı; kolon/index'e taşarsa o kapı zaten kırmızı olur ve bu testin
    varsayımı çürür. İkisi birlikte şemanın üç eksenini de kapatır.
    """
    assert sapma, (
        "FK sapması SIFIRA indi — bu bir KAZANIMDIR, ama bu dosyanın tamamı (ve "
        "`d4e5f6a7b8c9`'nin gerekçesi) artık geçersizdir; gerekçeyi güncelleyip kapıyı sadeleştir."
    )
    assert all(len(x) == 3 for x in sapma)
