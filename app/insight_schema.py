"""
İçgörü (kalıcı hafıza) sözleşmesi — TEK KAYNAK (BUG #268).

`action_schema.py` `propose_action`'ın payload'ını sözleşmeye bağladı (BUG #266 / ADR-048).
Koçun İKİNCİ tool'u `save_insight` ise aynı işlemden geçmemişti: argümanlar ham
indeksleniyor (`inp["content"]`), doğrulanmıyor ve hata yalnız log'a düşüyordu.

------------------------------------------------------------------------------
ÖLÇÜM (8 Ağu 2026 — FakeProvider ile gerçek koç akışı, her vaka ayrı DB)
------------------------------------------------------------------------------
| Tool argümanı                | Ölçülen davranış                                   |
|------------------------------|----------------------------------------------------|
| `content` anahtarı yok       | KeyError yutuldu; kayıt YOK, koç "Not aldım." dedi |
| `content` bir nesne (dict)   | **TÜM KOÇ İSTEĞİ ÇÖKTÜ** (PendingRollbackError)    |
| `expires_at: "gelecek ay"`   | ValueError yutuldu; kayıt YOK, koç "Not aldım."    |
| `dedup_key` yok (2. çağrı)   | UNIQUE ihlali; kayıt YOK, koç "Not aldım."         |
| `priority: "cok_kritik"`     | sessizce `normal`e düştü                           |

İkinci satır sözleşme ihlalinden fazlası: `save_insight_action` başarısız INSERT'ten sonra
session'ı **rollback etmeden** bırakıyor, sonraki `commit()` (reasoning trace adımı)
`PendingRollbackError` fırlatıyor ve kullanıcının o mesajı komple hata dönüyor. Bu, projenin
kendi anti-pattern listesindeki maddedir: *"loop içinde `db.rollback()` yerine
`db.begin_nested()` — IntegrityError'da session zehirlenmesin."*

------------------------------------------------------------------------------
ÜÇÜNCÜ VE EN SESSİZ BULGU — "critical = asla unutulmamalı" BİR VAAT DEĞİL, BİR YALANDI
------------------------------------------------------------------------------
Tool açıklaması LLM'e şunu söylüyordu: *"critical: asla unutulmamalı."* Ama enjeksiyon
(`coach_insights.format_insights_for_prompt`) sıralamayı `sort_priority` (int) +
`last_evidence_at` ile yapıp **`limit(5)`** uygular. `save_insight_action` bu iki alanın
İKİSİNİ DE yazmıyordu → kullanıcının kendi ağzından çıkan gerçek varsayılan 5 ile en altta,
`last_evidence_at` NULL olduğu için de eşitlikte en sonda kalıyordu.

Ölçüm: 6 çıkarıcı gözlemi (sort_priority=10) + kullanıcının *"asla kredi çekmeyeceğim"*
beyanı (critical) → enjekte edilen blokta **beyan HİÇ YOK**, beş rutin gözlem var.
Yani koç, kullanıcının "bunu asla unutma" dediği şeyi tam olarak unutuyordu. `InsightPriority`
enum'u yazılıyor ama HİÇBİR YERDE okunmuyordu (dekoratif alan — L21 sınıfı: sinyal
hesaplanıyor ama karar veren katmana hiç ulaşmıyor).

------------------------------------------------------------------------------
BAŞARISIZLIK YÖNÜ — BU MODÜL BİLİNÇLİ OLARAK #266'DAN FARKLI DAVRANIR
------------------------------------------------------------------------------
ADR-048'de kural "uygulanamayacak öneri DOĞMAZ"dı: orada yanlış tutarı UYGULAMAK,
uygulamamaktan kötüdür. Burada denge terstir — **içerik yüktür, gerisi etikettir**:

  · `content` yoksa ya da metne dönüşmüyorsa → REDDET (hatırlanacak bir şey yok, üstelik
    nesne DB'ye yazılamaz).
  · `dedup_key` yoksa/boşsa → İÇERİKTEN TÜRET (kaydı bir etiket eksikliği yüzünden
    kaybetmek, kaydın kendisini kaybetmektir; boş anahtar zaten UNIQUE indeksi patlatıyordu).
  · `category`/`priority` sözleşme dışıysa → BELGELİ VARSAYILANA düş (aşağı yönde:
    tanınmayan bir öncelik "critical" sayılamaz) ve düşüşü çağırana BİLDİR — sessizce değil.
  · `expires_at` çözülemiyorsa → SÜREYİ düşür, GERÇEĞİ tut.

Yani: yükü metadata yüzünden kaybetme; ama davranışı değiştiren metadata'yı sessizce kabul
etme. Her düşüş `Ayiklama.duzeltmeler` ile geri döner ve reasoning trace'e yazılır.

GUNCELLEMELER
- 8 Agu 2026 BUG #268 fix: modul olusturuldu (LLM-008'in kalan yarisi). `save_insight`
  tool semasi artik BURADAN URETILIR (elle yazili ikinci liste degil), oncelik etiketi
  `sort_priority` merdivenine baglandi ve yazma yolu savepoint ile izole edildi.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from app.tr_text import normalize as _tr_normalize

# ============================================================
# ÖNEM MERDİVENİ — enjeksiyon sıralamasının TEK ÖLÇEĞİ
# ============================================================
#
# `coach_insights` çıkarıcıları zaten bu ölçeği kullanıyor (ERL_DOMINANT_PRIORITY=15,
# ERL_K2_PRIORITY=12, MC_REFERENCE/QT_WARNING=10, ARP/ST_COMPOUND=9, CAP=8, BT/ST=7,
# QT_HEALTHY=5, düşürülmüş=1). Koçun `save_insight`'ı bu ölçeğe HİÇ yazmıyordu.
#
# Yerleştirme gerekçesi (ADR-050):
#   15  deterministik kırmızı-çizgi çıkarımı  — kullanıcının sözü + veri temelli
#   14  KULLANICI BEYANI: critical            — kullanıcının sözü, LLM sınıflandırması
#   12  kırmızı-çizgi K2 (zayıf kanıt)
#   11  KULLANICI BEYANI: high                — beyan, tüm desen gözlemlerinin ÜSTÜNDE
#   10..7  çıkarıcı desen gözlemleri
#    5  KULLANICI BEYANI: normal              — bugünkü varsayılan (davranış değişmez)
#
# İlke: kullanıcının kendi ağzından çıkan gerçek, hakkında ÇIKARILAN desenden önce gelir;
# deterministik çıkarım ise aynı kanıt seviyesindeki LLM sınıflandırmasından önce gelir.
# Sıra ilişkisi `tests/test_icgoru_kapisi.py`'de GERÇEK sabitlerden türetilerek kilitlenir.
ONEM_MERDIVENI: Dict[str, int] = {
    "critical": 14,
    "high": 11,
    "normal": 5,
}

ONCELIKLER: Tuple[str, ...] = tuple(ONEM_MERDIVENI)          # critical | high | normal
VARSAYILAN_ONCELIK = "normal"

# `category` DAVRANIŞA ETKİ ETMEZ (ölçüldü: `CoachInsight.category` okuyan hiçbir karar yolu
# yok — yalnız kayıt/teşhis alanı). Bu yüzden bilinmeyen değer kaydı düşürmez; belgeli
# kümeye çekilir. Küme tool açıklamasına BURADAN yazılır, elle ikinci kez yazılmaz.
KATEGORILER: Tuple[str, ...] = ("preference", "event", "pattern", "goal", "general")
VARSAYILAN_KATEGORI = "general"

# Enjeksiyon bütçesi 1500 token / en fazla 5 kayıt. Tek bir içgörü bu bütçeyi yiyip
# diğerlerini tahliye edemesin diye içerik sınırlanır (~200 token TR).
ICERIK_AZAMI = 600
DEDUP_ANAHTAR_AZAMI = 80

_SLUG_DISI = re.compile(r"[^a-z0-9]+")


class IcgoruGecersiz(ValueError):
    """Kaydedilemez içgörü. Koç akışı bunu kullanıcıya GÖRÜNÜR bir notla söyler —
    sessiz kalırsa koçun 'Not aldım.' cümlesi ekranda kalır ve hafıza boş olur."""


class Ayiklama:
    """Doğrulanmış argümanlar + uygulanan düşüşlerin listesi.

    `duzeltmeler` boş değilse bir şey beyan edildiği gibi kaydedilmedi; çağıran bunu
    trace'e yazar (sessiz düşüş = ölçülemeyen davranış)."""

    __slots__ = ("content", "category", "priority", "dedup_key", "expires_at",
                 "sort_priority", "duzeltmeler")

    def __init__(self, content: str, category: str, priority: str, dedup_key: str,
                 expires_at: Optional[str], sort_priority: int, duzeltmeler: List[str]):
        self.content = content
        self.category = category
        self.priority = priority
        self.dedup_key = dedup_key
        self.expires_at = expires_at
        self.sort_priority = sort_priority
        self.duzeltmeler = duzeltmeler

    def __repr__(self) -> str:  # teşhis
        return (f"Ayiklama(dedup_key={self.dedup_key!r}, priority={self.priority!r}, "
                f"sort_priority={self.sort_priority}, duzeltmeler={self.duzeltmeler})")


def slugla(metin: str) -> str:
    """'Fon Satışı — Seyahat' → 'fon_satisi_seyahat' (Türkçe katlama tek kaynaktan)."""
    return _SLUG_DISI.sub("_", _tr_normalize(metin)).strip("_")[:DEDUP_ANAHTAR_AZAMI]


def ayikla(inp) -> Ayiklama:
    """`save_insight` tool argümanını sözleşmeye göre çözer.

    Yalnız İÇERİK yoksa/metne dönüşmüyorsa `IcgoruGecersiz` fırlatır; metadata sorunları
    belgeli varsayılana düşürülür ve `duzeltmeler`de raporlanır (modül docstring'i:
    başarısızlık yönü).
    """
    if not isinstance(inp, dict):
        raise IcgoruGecersiz(
            f"ICGORU_GECERSIZ: tool argumani nesne olmali, {type(inp).__name__} geldi")

    duzeltmeler: List[str] = []

    ham = inp.get("content")
    if ham is None:
        raise IcgoruGecersiz("ICGORU_GECERSIZ: 'content' yok — kaydedilecek bir gercek yok")
    if not isinstance(ham, str):
        # Ölçümde bu satır TÜM koç isteğini çökertiyordu (dict → SQLite bind hatası →
        # zehirli session). Artık onay sınırında, yazma denenmeden reddedilir.
        raise IcgoruGecersiz(
            f"ICGORU_GECERSIZ: 'content' metin olmali, {type(ham).__name__} geldi")
    content = ham.strip()
    if not content:
        raise IcgoruGecersiz("ICGORU_GECERSIZ: 'content' bos")
    if len(content) > ICERIK_AZAMI:
        raise IcgoruGecersiz(
            f"ICGORU_GECERSIZ: 'content' {len(content)} karakter — azami {ICERIK_AZAMI} "
            f"(tek icgoru paylasilan hafiza butcesini yiyemez)")

    kategori = inp.get("category")
    if not isinstance(kategori, str) or kategori not in KATEGORILER:
        if kategori is not None:
            duzeltmeler.append(f"category={kategori!r} taninmadi → {VARSAYILAN_KATEGORI}")
        kategori = VARSAYILAN_KATEGORI

    oncelik = inp.get("priority")
    if not isinstance(oncelik, str) or oncelik not in ONCELIKLER:
        if oncelik is not None:
            # Aşağı yönde düşülür: tanınmayan bir etiket "critical" sayılamaz.
            duzeltmeler.append(f"priority={oncelik!r} taninmadi → {VARSAYILAN_ONCELIK}")
        oncelik = VARSAYILAN_ONCELIK

    anahtar = inp.get("dedup_key")
    anahtar = slugla(anahtar) if isinstance(anahtar, str) else ""
    if not anahtar:
        # Boş anahtar UNIQUE(user_id, dedup_key) indeksini ikinci kayitta patlatıyordu →
        # içerikten türet: aynı gerçek aynı anahtara düşer, dedup amacı korunur.
        anahtar = slugla(content) or "icgoru"
        duzeltmeler.append(f"dedup_key yoktu → icerikten turetildi ({anahtar})")

    bitis = inp.get("expires_at")
    if bitis is not None:
        try:
            date.fromisoformat(str(bitis))
            bitis = str(bitis)
        except ValueError:
            duzeltmeler.append(f"expires_at={bitis!r} tarih degil → suresiz kaydedildi")
            bitis = None

    return Ayiklama(
        content=content, category=kategori, priority=oncelik, dedup_key=anahtar,
        expires_at=bitis, sort_priority=ONEM_MERDIVENI[oncelik], duzeltmeler=duzeltmeler,
    )


# ============================================================
# TOOL ŞEMASI — sözleşmeden ÜRETİLİR (elle yazılan ikinci liste değil, L27)
# ============================================================

def tool_semasi() -> dict:
    """`save_insight` tool tanımı. İzin verilen değer kümeleri ve sınırlar bu modüldeki
    sözleşmeden gelir — prompt ile doğrulama arasında drift olamaz."""
    return {
        "name": "save_insight",
        "description": (
            "Kullanıcının söylediği önemli bir gerçeği, planı, tercihi veya davranış "
            "kalıbını kalıcı hafızaya kaydet. UZUN VADELİ HAFIZA listesinde ZATEN VARSA "
            "ÇAĞIRMA — dedup_key aynı kalıp olmalı. Tarihli olaylar için expires_at ver."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "maxLength": ICERIK_AZAMI,
                    "description": (
                        f"Tek Türkçe cümle: ne hatırlanmalı. En fazla {ICERIK_AZAMI} karakter."
                    ),
                },
                "category": {
                    "type": "string",
                    "enum": list(KATEGORILER),
                    "description": ("preference: tercih/red. event: tarihli olay. "
                                    "pattern: davranış kalıbı. goal: plan/hedef. "
                                    "general: diğer."),
                },
                "priority": {
                    "type": "string",
                    "enum": list(ONCELIKLER),
                    "description": (
                        "critical: kullanıcının 'asla/kesinlikle' diye beyan ettiği sınır — "
                        "hafızada tüm desen gözlemlerinin ÜSTÜNDE tutulur. "
                        "high: stratejik. normal: genel bağlam."
                    ),
                },
                "dedup_key": {
                    "type": "string",
                    "maxLength": DEDUP_ANAHTAR_AZAMI,
                    "description": (
                        "Kısa snake_case slug: konu+zaman+kategori özetle. Örn: "
                        "fon_satisi_seyahat, haftalik_market. Aynı gerçek için daima aynı key."
                    ),
                },
                "expires_at": {
                    "type": "string",
                    "description": "YYYY-MM-DD — tarihli olaylar için (seyahat, ödeme). Opsiyonel.",
                },
            },
            "required": ["content", "dedup_key"],
        },
    }
