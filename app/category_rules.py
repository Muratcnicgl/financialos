"""
BUG #264 / ADR-046 — KATEGORİ KARARLARI: TEK DOĞRULUK KAYNAĞI.

`balance_rules.py` bir işlemin bakiyeye ETKİSİNİ, `account_rules.py` "hangi hesaba"
sorusunu tek yere topladı. Bu modül de **kategoriye bağlı kararları** tek yere toplar.

Önceden iki ayrı yerde, iki sabit Türkçe küme karar veriyordu:

    action_executor._CARD_CATEGORIES = {"yemek","eglence","sigara","alisveris","market"}
        → bir harcamanın KREDİ KARTINA yazılıp yazılmayacağı (PARA kararı)
    rules_engine._PATTERN_EXCLUDED_CATEGORIES = {"transfer","borc_odeme",...}
        → hangi harcamanın "artış" uyarısına gireceği (UYARI kararı)

Yani kullanıcının parasıyla ilgili kararlar, kategorisini **hangi kelimeyle adlandırdığına**
bağlıydı. Kendi setini kuran kullanıcıda ("gıda", "market alışverişi") her iki kural da
sessizce ölüyordu (L28); tersi de doğru — kartını kapatmış ama "market" adını kullanan
kullanıcının nakit harcaması karta yazılıyordu.

Sözleşme: karar ADDA değil BAYRAKTA (`Category.kart_varsayilani` / `Category.sistem`).
Çağıran hiçbir modül kendi kategori kümesini yazmaz. Kapı: `tests/test_kategori_kapisi.py`.

YAZMA/OKUMA AYRIMI (önemli): `rules_engine` DB'ye **asla yazmaz** (app/PROJE.md). Bu yüzden
tohumlama okuma yolundan TETİKLENMEZ — okuma tarafı kaydı olmayan kullanıcıda belgeli
varsayılan haritaya düşer (davranış bugünküyle birebir aynı kalır). Tohumlama yalnız yazma
yollarında olur: kullanıcı yaratımı ve Alembic göçü.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from sqlalchemy.orm import Session

from app.models import Category
from app.workspace_deps import scope_filter


# ============================================================
# NORMALİZE — gövde `app/tr_text.py`'de (BUG #267)
# ============================================================
#
# BUG #267 fix: bu iki isim burada TANIMLI değil, `app.tr_text`ten RE-EXPORT edilir.
# Sebep: aynı katlama koç mesajı sınıflandırmasında, tarih anahtar kelimelerinde ve
# hesap adı eşleşmesinde de gerekiyordu; kategori modülünden import etmek "kategori
# kuralı" gibi okunuyordu ve fiilen üç yer daha kendi kısmi telafisini yazmıştı.
# İsimler geriye uyumlu tutuldu (mevcut çağıranlar değişmedi).
from app.tr_text import TR_NORM, normalize  # noqa: F401  (re-export — tek kaynak)


# ============================================================
# VARSAYILAN SET (tohumlanır — dayatılmaz, ADR-046 madde 4)
# ============================================================
#
# Bu set BUGÜNKÜ davranışı birebir üretir: `kart_varsayilani=True` olanlar eski
# `_CARD_CATEGORIES` kümesidir, `sistem=True` olanlar eski `_PATTERN_EXCLUDED_CATEGORIES`
# kümesidir. Göç sonrası hiçbir kullanıcı için davranış değişmez; değişen tek şey SAHİPLİK
# (kullanıcı bunları yeniden adlandırabilir, kart varsayılanını çevirebilir, gizleyebilir).
#
# TEK BİLİNÇLİ DAVRANIŞ DÜZELTMESİ: `borc_geri_odeme` (hızlı girişin ürettiği slug —
# `routers/transactions.QUICK_KEYWORDS`) eski dışlama listesinde YOKTU, yani borç ödemesi
# kişisel harcama paterni sayılıyor ve "harcaman arttı" uyarısını tetikleyebiliyordu.
# Bu bir defektti; sistem kategorisi olarak işaretlendi (BUG #264 sınıf taraması).

_VARSAYILAN_SET: List[Dict] = [
    # (slug, ad, kart_varsayilani, sistem)
    {"slug": "yemek",      "ad": "Yemek",           "kart_varsayilani": True,  "sistem": False},
    {"slug": "eglence",    "ad": "Eğlence",         "kart_varsayilani": True,  "sistem": False},
    {"slug": "sigara",     "ad": "Sigara",          "kart_varsayilani": True,  "sistem": False},
    {"slug": "alisveris",  "ad": "Alışveriş",       "kart_varsayilani": True,  "sistem": False},
    {"slug": "market",     "ad": "Market",          "kart_varsayilani": True,  "sistem": False},
    {"slug": "ulasim",     "ad": "Ulaşım",          "kart_varsayilani": False, "sistem": False},
    {"slug": "fatura",     "ad": "Fatura",          "kart_varsayilani": False, "sistem": False},
    {"slug": "saglik",     "ad": "Sağlık",          "kart_varsayilani": False, "sistem": False},
    {"slug": "kira",       "ad": "Kira",            "kart_varsayilani": False, "sistem": False},
    {"slug": "abonelik",   "ad": "Abonelik",        "kart_varsayilani": False, "sistem": False},
    {"slug": "sigorta",    "ad": "Sigorta",         "kart_varsayilani": False, "sistem": False},
    {"slug": "internet",   "ad": "İnternet",        "kart_varsayilani": False, "sistem": False},
    {"slug": "telefon",    "ad": "Telefon",         "kart_varsayilani": False, "sistem": False},
    {"slug": "diger",      "ad": "Diğer",           "kart_varsayilani": False, "sistem": False},
    # Sistem kategorileri — muhasebe işlemi, kişisel harcama DEĞİL. Silinemez/yeniden
    # adlandırılamaz (YNAB `internal`, Actual Budget "gelir grubu silinemez").
    {"slug": "transfer",         "ad": "Transfer",         "kart_varsayilani": False, "sistem": True},
    {"slug": "borc_odeme",       "ad": "Borç ödeme",       "kart_varsayilani": False, "sistem": True},
    {"slug": "borc_geri_odeme",  "ad": "Borç geri ödeme",  "kart_varsayilani": False, "sistem": True},
    {"slug": "kredi_taksiti",    "ad": "Kredi taksiti",    "kart_varsayilani": False, "sistem": True},
    {"slug": "borc",             "ad": "Borç",             "kart_varsayilani": False, "sistem": True},
    {"slug": "kredi",            "ad": "Kredi",            "kart_varsayilani": False, "sistem": True},
    {"slug": "loan_payment",     "ad": "Kredi ödemesi",    "kart_varsayilani": False, "sistem": True},
    {"slug": "debt_payment",     "ad": "Borç ödemesi",     "kart_varsayilani": False, "sistem": True},
]

# Okuma yolunun (yazmayan) fallback haritası — kaydı olmayan kullanıcıda bugünkü davranış.
_VARSAYILAN_HARITA: Dict[str, Dict] = {c["slug"]: c for c in _VARSAYILAN_SET}


def varsayilan_set() -> List[Dict]:
    """Tohumlanacak varsayılan kategori tanımlarının kopyası (çağıran mutasyona uğratamaz)."""
    return [dict(c) for c in _VARSAYILAN_SET]


# ============================================================
# OKUMA (yazmaz — rules_engine bu yolu kullanır)
# ============================================================

def kategori_haritasi(
    db: Session,
    user_id: int,
    workspace_id: Optional[int] = None,
) -> Dict[str, Dict]:
    """Kullanıcının kategori haritası: `slug -> {ad, kart_varsayilani, sistem, gizli}`.

    Kaydı yoksa **varsayılan haritaya** düşer ve DB'ye YAZMAZ (rules_engine sözleşmesi).
    Tohumlama yazma yollarının işidir (`kategorileri_tohumla`).
    """
    rows = (
        db.query(Category)
        .filter(scope_filter(Category, user_id, workspace_id))
        .all()
    )
    if not rows:
        return {s: dict(c) for s, c in _VARSAYILAN_HARITA.items()}
    return {
        r.slug: {
            "ad": r.ad,
            "kart_varsayilani": bool(r.kart_varsayilani),
            "sistem": bool(r.sistem),
            "gizli": bool(r.gizli),
        }
        for r in rows
    }


def kart_varsayilani_mi(
    db: Session,
    user_id: int,
    slug: Optional[str],
    workspace_id: Optional[int] = None,
) -> bool:
    """Bu kategoride hesap belirtilmemiş harcama kredi kartına mı yönlendirilsin?

    Eski `_CARD_CATEGORIES` üyeliğinin kullanıcıya ait hâli. Bilinmeyen kategori → False
    (kullanıcının tanımlamadığı bir ad için parayı karta yazmak varsayımdır — §1.1 yasak).
    """
    kayit = kategori_haritasi(db, user_id, workspace_id).get(normalize(slug))
    return bool(kayit and kayit["kart_varsayilani"])


def sistem_slug_kumesi(
    db: Session,
    user_id: int,
    workspace_id: Optional[int] = None,
) -> Set[str]:
    """Harcama-paterni analizinden çıkarılacak slug'lar (eski `_PATTERN_EXCLUDED_CATEGORIES`).

    Muhasebe işlemleri kişisel harcama değildir: transfer, borç ödeme, kredi taksiti.
    """
    return {
        slug for slug, k in kategori_haritasi(db, user_id, workspace_id).items()
        if k["sistem"]
    }


def sistem_kategorisi_mi(
    db: Session,
    user_id: int,
    slug: Optional[str],
    workspace_id: Optional[int] = None,
) -> bool:
    """Tek slug için `sistem` bayrağı (silme/yeniden adlandırma yasağının da dayanağı)."""
    kayit = kategori_haritasi(db, user_id, workspace_id).get(normalize(slug))
    return bool(kayit and kayit["sistem"])


# ============================================================
# YAZMA (tohumlama — yalnız kullanıcı yaratımı ve Alembic göçü)
# ============================================================

def kategorileri_tohumla(
    db: Session,
    user_id: int,
    workspace_id: Optional[int] = None,
    *,
    commit: bool = False,
) -> int:
    """Varsayılan seti bu kullanıcı için tohumlar. **Idempotent** — var olanı ezmez.

    Kullanıcının kendi düzenlemesi korunur: aynı slug zaten varsa dokunulmaz (yeniden
    adlandırdığı ya da kart varsayılanını çevirdiği kategori geri alınmaz).

    Dönüş: eklenen satır sayısı.
    """
    mevcut = {
        s for (s,) in db.query(Category.slug)
        .filter(scope_filter(Category, user_id, workspace_id))
        .all()
    }
    eklenen = 0
    for tanim in _VARSAYILAN_SET:
        if tanim["slug"] in mevcut:
            continue
        db.add(Category(
            user_id=user_id,
            workspace_id=workspace_id,
            slug=tanim["slug"],
            ad=tanim["ad"],
            kart_varsayilani=tanim["kart_varsayilani"],
            sistem=tanim["sistem"],
        ))
        eklenen += 1
    if eklenen:
        db.flush()
        if commit:
            db.commit()
    return eklenen
