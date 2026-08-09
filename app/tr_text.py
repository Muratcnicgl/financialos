"""
Türkçe serbest metin normalizasyonu — TEK KAYNAK (BUG #267).

NEDEN AYRI MODÜL:
  Kullanıcı (ve koç) serbest metni bu kod tabanında SEKİZ ayrı yerde elle yazılmış
  regex'lerle eşleştiriliyordu. Her yer diakritik sorununu kendi başına, KISMEN
  çözmüştü: `action_executor._DATE_KEYWORD_RE` üç kelime için `d[uü]n|bugun|gecen`
  yazmış (ayları unutmuş), `coach_insights` desenleri `değil mi|degil mi` gibi çift
  yazım taşımış (`nasil`i yazıp `nasıl`ı unutmuş), `coach.is_question` hiç telafi
  yazmamış. `category_rules.TR_NORM` zaten vardı ama yalnız KATEGORİ adlarına ve
  hesap adlarına uygulanıyordu.

  Ölçüm (7 Ağu 2026, `is_question`/`has_realized_action`/`is_future_or_intent`/
  `QT_OPEN`/`_DATE_KEYWORD_RE` üzerinde token bazlı): **20 token** iki yazımdan
  birinde eşleşmiyordu.

SİNSİLİK KAYNAĞI — `re.IGNORECASE` YARIM İŞ GÖRÜR:
  CPython'un genişletilmiş büyük/küçük katlaması `ı`(U+0131) ↔ `I` ↔ `i` eşitliğini
  KENDİLİĞİNDEN kurar. Yani `\bharcadım\b` deseni "harcadim" yazımını da yakalar ve
  geliştirici "diakritik sorunu yokmuş" sonucuna varır. Oysa `ç/ş/ğ/ö/ü` için aynı
  katlama YOKTUR: `ödedim` deseni "odedim"i yakalamaz. Sonuç, sorunun harf harf
  değişen — yani test edilen örnekte tesadüfen çalışabilen — bir hâli.

SÖZLEŞME:
  Serbest metni desenle eşleştiren HER yer, önce bu modülün `normalize()`'ını
  uygular ve desenini KATLANMIŞ (diakritiksiz, küçük harf) yazar. Böylece
  "iki yazımı da desene elle eklemek" işi ortadan kalkar — unutulacak bir liste
  kalmaz (L26: yasağın gücü kaynağı seçen kod sayısı kadardır).

`normalize()` UZUNLUK KORUR: her karakter tek karaktere gider (`İ` dahil), böylece
normalize edilmiş metin üzerinde bulunan eşleşme ofsetleri HAM metinde de geçerlidir.
Bu, alıntı çıkaran tüketicilerin (`coach_insights._erl_extract_match_text`) ham
metinden kesmesine izin verir.

GUNCELLEMELER
- 8 Agu 2026 BUG #267 fix: modul olusturuldu. Govde `category_rules.normalize`den
  tasindi (davranis birebir ayni; oradaki BUG #026/#167 dersleri buraya geldi),
  `category_rules` artik buradan re-export eder.
"""

from __future__ import annotations

from typing import Optional

# BUG #026: Türkçe karakter normalize.
# BUG #167 fix (P3.5): hedef dizideki 'o' KİRİL 'о' (U+043E) idi → 'ö' harfi ASCII 'o'
# yerine Kiril harfe çevriliyordu. Normalize edilen kategori DB'ye böyle yazıldığından
# ("оgle yemegi"), sonraki kategori eşleşmeleri/gruplamaları sessizce kırılıyordu.
# Artık saf ASCII — bu satırın ASCII'liği teste bağlıdır (bkz. tests/test_niyet_kapisi.py).
TR_NORM = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")

# 'İ'.lower() == 'i' + U+0307 (birleşik nokta). TR_NORM 'İ'yi zaten 'I'ya çevirdiği için
# normal akışta oluşmaz; başka kaynaklardan (kopyala-yapıştır) gelen artıklar temizlenir.
_BIRLESIK_NOKTA = "̇"


def normalize(metin: Optional[str]) -> str:
    """'Eğlence' → 'eglence' · 'Ödedim' → 'odedim' (aksan + büyük harf katlaması).

    BUG #167 fix (P3.5): sıra TERSTİ. `lower()` önce koşunca `'İ'.lower()` birleşik
    noktalı iki karakter üretiyor ve çeviri tablosu bunu yakalayamıyordu → ASCII-dışı
    karakter DB'ye yazılıyordu. Önce çevir, sonra küçült.
    """
    return (metin or "").translate(TR_NORM).lower().replace(_BIRLESIK_NOKTA, "")


def katlanmis_mi(metin: str) -> bool:
    """Metin zaten katlanmış mı? (desen kaynaklarını kilitleyen kapı için — BUG #267)

    Bir desen literali diakritik taşıyorsa, o desen normalize edilmiş metinle ASLA
    eşleşmez ve sessizce ölür. Kapı bunu desen kaynağından TÜRETEREK ölçer (L27).
    """
    return normalize(metin) == (metin or "")
