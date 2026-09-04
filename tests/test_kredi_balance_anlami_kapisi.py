"""
BUG #327 KAPISI — `balance`IN ANLAMI: BELGE İLE MOTOR BİRBİRİNİ TUTMUYORDU.

`app/models.py`'deki BUG #318 yorumu şunu söylüyordu:
    "`balance` = KALAN TAKSİT TOPLAMI (gelecek faizi icerir)"
Oysa `app/debt_strategy.py:182` her ay şunu yapıyor:
    interest = bal * (d.interest_rate_monthly / 100.0)
Yani `balance`ı FAİZLENDİRİYOR. Zaten gelecek faizi içeren bir sayıyı faizlendirmek,
faizi iki kez saymaktır.

ÖLÇÜLDÜ (4 Eylül 2026, Garanti'nin kendi verisiyle — iki gerçek kredi):

    Kredi 1: erken kapama 14.916,25 · taksit 4.109,90 × 4  · taksit toplami 16.439,65
    Kredi 2: erken kapama 34.688,87 · taksit 2.747,22 × 23 · taksit toplami 63.186,20

    balance = ERKEN KAPAMA        -> 4/23 ay sonra bakiye  0,00        ✅
    balance = KALAN TAKSIT TOPL.  -> 1.782,60 / 102.266,40 KALIYOR     ❌

İkinci satırdaki 102.266,40, 34.500 TL'lik bir kredinin borcunu ÜÇ KATINA çıkarır.
Bu tam olarak `financialos-veri-modeli-tuzaklari` hafızasındaki "kredi matematiksel
olarak asla bitmiyor" defektidir ve bugün canlı veride hâlâ duruyordu (u1 profili).

KARAR: **motor doğru, yorum yanlış.** `balance` = bugün kapatırsan ödeyeceğin tutar
(erken kapama). Yorum düzeltildi; bu kapı ikisinin bir daha ayrışmamasını sağlar.

ÜÇÜNCÜ BİR SAYI DA VAR VE ÜRÜN ONU MODELLEMİYOR (ödeme planından, açık bulgu):
    kalan taksit toplamı 63.186,20 · **kalan ANAPARA 32.604,08** · erken kapama 34.688,87
Erken kapama = kalan anapara + son taksitten bu yana işlemiş faiz. Ayrıca planda
`fon` + `vergi` (KKDF+BSMV) sütunları var ve toplamları **faizin %30'u** — yani nominal
faiz, gerçek aylık yükü tek başına anlatmıyor.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.debt_strategy import DebtItem, calc_avalanche

KOK = Path(__file__).resolve().parent.parent


def _kapanis_bakiyesi(balance: float, oran: float, taksit: float, ay: int) -> float:
    """Motorun yaptığı aritmetiğin aynısı (debt_strategy:182 ile aynı formül)."""
    for _ in range(ay):
        balance = balance * (1 + oran / 100.0) - taksit
    return balance


#: TOLERANS GEREKÇELİ: oran veritabanında 3 ondalıkla saklanıyor (%5,713). Ölçülen
#: kalıntı 23 ayda −0,17 TL ve +2,92 TL — yani bakiyenin **%0,008**'i. Bu bir modelleme
#: hatası değil, saklama hassasiyetidir; mutlak 1 TL'lik bir eşik DOĞRU cevabı düşürürdü
#: (BUG #316'nın dersi: bir ölçüt, kabul ettiği yazım/hassasiyet kadar iyidir).
#: Ölçüt bu yüzden ORANSAL: kalıntı, borcun binde birinden küçük olmalı.
_KALINTI_PAYI = 0.001


def test_ERKEN_KAPAMA_yorumu_krediyi_KAPATIR():
    """Garanti Kredi 1 ve 2'nin gerçek sayıları — bankanın planıyla birebir."""
    assert abs(_kapanis_bakiyesi(14916.25, 4.006, 4109.90, 4)) < 14916.25 * _KALINTI_PAYI
    assert abs(_kapanis_bakiyesi(34688.87, 5.713, 2747.22, 23)) < 34688.87 * _KALINTI_PAYI


def test_TAKSIT_TOPLAMI_yorumu_krediyi_ASLA_KAPATMAZ():
    """Ölçülen felaket: 34.500 TL'lik kredi 102 bin TL borç olarak kalıyor."""
    assert _kapanis_bakiyesi(16439.65, 4.006, 4109.90, 4) > 1500
    assert _kapanis_bakiyesi(63186.20, 5.713, 2747.22, 23) > 100000


def test_MOTOR_balance_i_FAIZLENDIRIYOR_bu_sozlesmedir():
    """
    Kapının çekirdeği: motor `balance`ı faizlendirdiği sürece `balance` ANAPARA olmalıdır.
    Motor bir gün faizi başka bir alandan hesaplamaya başlarsa bu test kırılır ve
    `models.py`'deki tanımın da güncellenmesi gerektiğini söyler.
    """
    kaynak = (KOK / "app" / "debt_strategy.py").read_text(encoding="utf-8")
    assert re.search(r"interest\s*=\s*bal\s*\*\s*\(\s*d\.interest_rate_monthly", kaynak), \
        "motor artık balance'ı faizlendirmiyor — models.py'deki `balance` tanımı gözden geçirilmeli"


def test_SOZLESME_MAKINE_OKUR_ve_MOTORLA_AYNI():
    """
    BUG #327: alanın anlamı iki yerde YAZILIYSA ve ayrışırsa veri sessizce bozulur —
    bugün canlı veride iki profil iki AYRI konvansiyondaydı.

    İlk yazımda bu kapı `models.py` METNİNDE "kalan taksit toplamı" ifadesini arıyordu ve
    **düzeltmenin kendi ölçüm tablosu** o ifadeyi içerdiği için kırmızı verdi. L67'nin
    aynısı: bir kapı, kendisini açıklayan belge yüzünden kırılamaz. Sözleşme bu yüzden
    düz yazıdan çıkarılıp tek bir DEĞERE taşındı; değiştirmek bilinçli bir edim olur.
    """
    from app.models import KREDI_BALANCE_ANLAMI
    assert KREDI_BALANCE_ANLAMI == "erken_kapama", (
        "Kredi `balance` anlamı değiştirilmiş. Motor (debt_strategy:182) balance'ı "
        "faizlendirdiği sürece bu değer 'erken_kapama' olmalıdır; değiştirilecekse "
        "faiz tabanı da değişmeli ve bu kapı gerekçesiyle güncellenmelidir.")


def test_simulasyon_gercek_kredilerle_makul_sure_veriyor():
    """Uçtan uca: iki gerçek krediyi motora verdiğimizde plan süresine yakın çıkmalı."""
    borclar = [
        DebtItem(account_id=1, name="K1", account_type="loan", balance=14916.25,
                 interest_rate_monthly=4.006, min_payment=4109.90),
        DebtItem(account_id=2, name="K2", account_type="loan", balance=34688.87,
                 interest_rate_monthly=5.713, min_payment=2747.22),
    ]
    sonuc = calc_avalanche(borclar, extra_monthly=0.0)
    assert sonuc.months_to_freedom <= 26, sonuc.months_to_freedom


def test_KALINTI_ESIGI_GEVSETILEMEZ():
    """
    Mutasyon bunu yazdırdı: `_KALINTI_PAYI`'yi %1000'e çekmek hiçbir testi düşürmüyordu —
    yani ölçüt sessizce vakumsal yeşile çevrilebiliyordu ("her kalıntı kabul").

    Eşik ÖLÇÜLEREK seçildi: oran 3 ondalıkla saklandığı için 23 ayda −0,17 / +2,92 TL
    kalıntı doğar (bakiyenin %0,008'i). Binde bir, bunun on katı kadar pay bırakır ve
    hâlâ gerçek bir modelleme hatasını (1.782,60 / 102.266,40) yakalar.
    """
    assert _KALINTI_PAYI <= 0.001, (
        "Kalıntı eşiği gevşetilmiş. Gevşetmeden önce MEŞRULUK SINAMASI yap: bu gevşetme, "
        "korumaya çalıştığı defekti (balance=taksit toplamı) kaçırır mı?")
