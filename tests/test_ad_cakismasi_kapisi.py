"""
AD ÇAKIŞMASI KAPISI (BE-013 / BUG #352 — 5 Eylül 2026).

NEDEN VAR — ÖLÜ KOD KAPISININ KÖR BÖLGESİ
------------------------------------------
`scripts/olu_kod_kapisi.py` bir fonksiyonun ÖLÜ olup olmadığını, **adının kaç yerde
geçtiğini** sayarak belirler. Bu, ad benzersiz olduğu sürece çalışır. Değilse çalışmaz:

5 Eylül 2026'da ölçüldü ki `get_db` **iki modülde** tanımlıydı — `app/database.py` ve
`app/dependencies.py` — gövdeleri birebir aynıydı ve **`app/database.py`'deki hiç
kullanılmıyordu** (ne bir modül ne de 94 test dosyasından biri oradan alıyordu). Ama
`get_db` adı depoda yüzlerce kez geçtiği için ölü kod kapısı onu "kullanılıyor" saydı ve
**0 ölü fonksiyon** raporladı. Yani kapı yalan söylemedi; **ölçemediğini ölçebildiğini
sandı** (L45: bilinmeyen ≠ sıfır).

Ve o ölü kopya zararsız değildi: FastAPI'de `app.dependency_overrides` anahtarı FONKSİYON
NESNESİDİR. Bir router yanlışlıkla ikinci kopyayı kullansaydı, testlerin yalıtımı o router
için GEÇERSİZ olur ve test sessizce GERÇEK veritabanına giderdi — kırmızı test olarak
değil, **"yeşil ama yanlış"** olarak.

NE ZORLAR
---------
`app/` altında modül düzeyinde aynı public adı paylaşan fonksiyonlar bir ALLOWLIST'te
gerekçesiyle durmak zorunda. Yeni bir çakışma eklenirse burada düşer ve yazan kişi iki
şeyden birini yapar: adı ayırır, ya da çakışmayı gerekçesiyle kaydeder — **böylece ölü kod
kapısının kör bölgesi hiçbir zaman sessiz kalmaz.**

Çakışmalar yasak DEĞİL (farklı modüllerde `dogrula`, `kaydet` gibi Türkçe fiiller meşrudur);
yasak olan **habersiz** çakışmadır.

MUTASYON 2/2 — allowlist'ten bir ad cikar -> kapi kirmizi (nedensellik) ·
tarayiciyi korlestir -> kapsam tabani kirmizi (vakumsal yesil yasagi)
"""
from __future__ import annotations

import ast
import collections
from pathlib import Path

KOK = Path(__file__).resolve().parent.parent
UYGULAMA = KOK / "app"

#: Bilinen ve GEREKÇELİ çakışmalar. Her biri iki farklı modülde meşru olarak yaşıyor;
#: ölü kod kapısı bu adlar için ölçüm yapamaz, o yüzden burada görünür duruyorlar.
BILINEN_CAKISMALAR: dict[str, str] = {
    "dogrula": "action_schema (payload şeması) · capacity (kapasite kuralı) — farklı alanlar, aynı fiil",
    "durum": "capacity (kapasite durumu) · routers/meta (HTTP durum ucu) — biri saf, biri endpoint",
    "ihlaller": "capacity (kapasite ihlalleri) · uslup_kurallari (üslup ihlalleri) — iki ayrı kural kümesi",
    "kaydet": "error_tracking (hata kaydı) · eval_store (eval koşum kaydı) — iki ayrı defter",
}

#: Tarayıcı boşa düşerse kapı geçmez, BOZULUR. Bugün app/ altında 400'den fazla ad var.
KAPSAM_TABANI = 200


def _public_adlar(kok: Path | None = None) -> dict[str, list[str]]:
    """Modül düzeyi public fonksiyon adı → onu tanımlayan dosyalar."""
    sayac: dict[str, list[str]] = collections.defaultdict(list)
    for yol in sorted((kok or UYGULAMA).rglob("*.py")):
        if "__pycache__" in str(yol):
            continue
        try:
            agac = ast.parse(yol.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover — bozuk dosya ayrı kapının işi
            continue
        for dugum in agac.body:
            if isinstance(dugum, (ast.FunctionDef, ast.AsyncFunctionDef)) and not dugum.name.startswith("_"):
                sayac[dugum.name].append(yol.name)
    return dict(sayac)


def _cakismalar(adlar: dict[str, list[str]]) -> dict[str, list[str]]:
    return {ad: yerler for ad, yerler in adlar.items() if len(yerler) > 1}


def test_KAPSAM_TABANI_tarayici_bozuksa_kapi_BOZULUR():
    """Hiç ad bulamayan bir tarayıcı 'çakışma yok' diyemez."""
    adlar = _public_adlar()
    assert len(adlar) >= KAPSAM_TABANI, (
        f"KAPI BOZUK: yalnız {len(adlar)} public ad tarandı (taban {KAPSAM_TABANI})."
    )


def test_AD_CAKISMALARI_GEREKCESIYLE_kayitli():
    """Habersiz çakışma yasak — çünkü ölü kod kapısı o adı ÖLÇEMEZ."""
    cakisan = _cakismalar(_public_adlar())
    kayitsiz = {ad: yerler for ad, yerler in cakisan.items() if ad not in BILINEN_CAKISMALAR}
    assert not kayitsiz, (
        "Aynı public adı paylaşan yeni fonksiyonlar var. Bu adlar için ölü kod kapısı "
        "ÖLÇÜM YAPAMAZ (ad sayımına dayanır) — biri ölü olsa bile 'kullanılıyor' sayılır:\n"
        f"  {kayitsiz}\n"
        "İki doğru cevaptan biri: adı ayır, ya da `BILINEN_CAKISMALAR`'a GEREKÇESİYLE ekle."
    )


def test_ALLOWLIST_BAYAT_kalamaz():
    """Çakışma çözülürse allowlist de küçülmeli — yoksa kör bölge kâğıt üzerinde yaşar."""
    cakisan = _cakismalar(_public_adlar())
    fazlalik = sorted(set(BILINEN_CAKISMALAR) - set(cakisan))
    assert not fazlalik, (
        "Bu adlar artık çakışmıyor; allowlist'ten çıkarılmalı (kazanım kilidi):\n"
        f"  {fazlalik}"
    )


def test_get_db_TEK_yerde_tanimli():
    """BE-013 regresyon kilidi — `dependency_overrides` anahtarı fonksiyon NESNESİDİR.

    İkinci bir `get_db` geri gelirse, testlerin yalıtımı onu kullanan router için
    sessizce geçersiz olur ve test GERÇEK veritabanına gider.
    """
    yerler = _public_adlar().get("get_db", [])
    assert yerler == ["dependencies.py"], (
        f"`get_db` tek kaynakta olmalı (dependencies.py); bulunan: {yerler}"
    )
