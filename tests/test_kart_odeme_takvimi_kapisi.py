"""
KART SON ÖDEMESİ TAKVİMDE KAPISI — parçalı takvimin son parçası.

NEDEN VAR (ölçülen defekt, 10 Eyl 2026, gerçek banka verisiyle): cockpit'in 60 günlük
"Yaklaşan ödemeler" listesi (`upcoming_payments`) yalnız KREDİ TAKSİTLERİNİ taşıyordu —
üreteci `_collect_upcoming_loan_payments` adıyla bile bunu söylüyordu. Kullanıcı ekranda
iki kredi taksitini (4.109,90 ve 2.747,22) gördü, 10.020,75 TL'lik kart son ödemesini
göremedi ve bildirdi: listenin EN BÜYÜK kalemi listede yoktu.

Aynı olay üç ayrı yerde üç ayrı şekilde türetiliyordu (0-7 günlük hatırlatmalar, ay sonu
nakit takvimi, 60 günlük ödeme listesi) — ilk ikisi kendi kopyasını yazmış, üçüncüsü hiç
yazmamıştı. Bu yüzden tarih+tutar tek kaynağa alındı: `kart_son_odeme`.

İKİNCİ DEFEKT — TUTAR: son ödeme gününde ödenecek olan EKSTREDEN KALAN borçtur, güncel
borç değil. Kesimden sonraki harcamalar GELECEK dönemin ekstresine yazılıdır; onları bu
ayın nakit çıkışına koymak olmayan bir açık üretir (BUG #331 ailesi). Ölçüldü: güncel borç
10.020,75 · ekstreden kalan 6.576,90 · dönem içi 3.443,85 → 14 Eylül'de ödenecek 6.576,90.

KİLİTLENEN DEĞİŞMEZLER:
  1. Kart son ödemesi 60 günlük `upcoming_payments` listesinde YER ALIR (tip=kart_odeme).
  2. Tutar `statement_balance`tan gelir; NULL ise (bilinmiyor) `balance`e düşülür ve bu
     durum `ekstre_biliniyor` bayrağıyla SÖYLENİR (varsayım gizlenmez).
  3. Borcu olmayan kart takvime girmez (ödenecek şey yoksa satır da yok).
  4. Üç tüketici de AYNI tarihi ve AYNI tutarı görür (kopya türetme geri gelmesin).
"""
from __future__ import annotations

from datetime import date

from app.models import Account, AccountType
from app.rules_engine import (
    _collect_upcoming_card_payments,
    _collect_upcoming_reminders,
    calculate_nakit_takvimi,
    kart_son_odeme,
)

BUGUN = date(2026, 9, 10)


def _kart(db, user_id, *, balance, statement_balance=None, payment_day=12,
          credit_limit=12000.0, name="Kart A"):
    a = Account(user_id=user_id, name=name, account_type=AccountType.credit_card,
                balance=balance, statement_balance=statement_balance,
                payment_day=payment_day, statement_day=2, credit_limit=credit_limit)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def test_kart_son_odemesi_60_gunluk_listede_YER_ALIR(db_session, test_user):
    """Bildirilen defektin ta kendisi: kart, yaklaşan ödemelerde hiç görünmüyordu."""
    _kart(db_session, test_user.id, balance=10020.75, statement_balance=6576.90)
    kalemler = _collect_upcoming_card_payments(test_user.id, BUGUN, db_session)
    assert len(kalemler) == 1, "kart son ödemesi takvimde yok"
    k = kalemler[0]
    assert k["tip"] == "kart_odeme"
    assert k["tarih"] == "2026-09-12"
    assert k["tutar"] == 6576.90


def test_tutar_EKSTREDEN_KALAN_borctur_guncel_borc_degil(db_session, test_user):
    """Kesimden sonraki 3.443,85 gelecek ekstreye yazılı — bu ayın çıkışı değil."""
    kart = _kart(db_session, test_user.id, balance=10020.75, statement_balance=6576.90)
    son = kart_son_odeme(kart, BUGUN)
    assert son["tutar"] == 6576.90
    assert son["tutar"] != 10020.75
    assert son["ekstre_biliniyor"] is True


def test_ekstre_bilinmiyorsa_guncel_borca_dusulur_ve_SOYLENIR(db_session, test_user):
    """NULL = bilinmiyor → eski davranış (balance). Ama bu bir varsayım; bayrakla söylenir."""
    kart = _kart(db_session, test_user.id, balance=10020.75, statement_balance=None)
    son = kart_son_odeme(kart, BUGUN)
    assert son["tutar"] == 10020.75
    assert son["ekstre_biliniyor"] is False


def test_ekstre_SIFIR_bilinmiyor_DEGILDIR(db_session, test_user):
    """0 geçerli bir değerdir ('ekstre kapandı') — balance'e DÜŞÜLMEZ, satır hiç olmaz."""
    kart = _kart(db_session, test_user.id, balance=3443.85, statement_balance=0.0)
    assert kart_son_odeme(kart, BUGUN) is None
    assert _collect_upcoming_card_payments(test_user.id, BUGUN, db_session) == []


def test_borcu_olmayan_kart_takvime_girmez(db_session, test_user):
    _kart(db_session, test_user.id, balance=0.0)
    assert _collect_upcoming_card_payments(test_user.id, BUGUN, db_session) == []


def test_UC_tuketici_de_ayni_tarih_ve_tutari_gorur(db_session, test_user):
    """Kopya türetme geri gelirse burası kırılır: hatırlatma / nakit takvimi / 60 gün."""
    kart = _kart(db_session, test_user.id, balance=10020.75, statement_balance=6576.90)

    liste = _collect_upcoming_card_payments(test_user.id, BUGUN, db_session)[0]
    hatirlatma = [
        r for r in _collect_upcoming_reminders(
            test_user.id, BUGUN, db_session, [kart], kart_borcu=10020.75)
        if r["type"] == "card_payment"
    ][0]
    takvim = [
        k for k in calculate_nakit_takvimi(test_user.id, db_session, BUGUN)["kalemler"]
        if k["tip"] == "kart_odeme"
    ][0]

    assert liste["tarih"] == hatirlatma["due_date"] == takvim["tarih"]
    assert float(liste["tutar"]) == float(hatirlatma["amount"]) == float(takvim["tutar"]) == 6576.90
