"""
NAKİT TAKVİMİ KAPISI (Wave-K / altın senaryo G3) — YÖN, KOÇUN ÇIKARIMINA BIRAKILMAZ.

ÖLÇÜLEN DEFEKT (2 Eyl 2026): koça "8 Eylül'de 4.000 TL KYK ödemem gelecek. Eylül boyunca
zorunlu ödemelerimi karşılayabilir miyim?" soruldu. Koç şunu yazdı:

    "Eylül zorunlu ödemelerin toplamı 10.857 TL:
       - 8 Eylül KYK: 4.000 TL          ← GELEN parayı ÇIKIŞ listesine koydu
       - 11 Eylül Garanti Kredi 1: 4.109,90
       - 15 Eylül Garanti Kredi 2: 2.747,22"

İki hata birden: (a) kullanıcıya GELEN 4.000 TL gider sayıldı, (b) ayın en büyük tek çıkışı
olan 8.221,13 TL kart ödemesi hiç sayılmadı. Doğru çıkış toplamı 15.078,25 TL.

KÖK NEDEN, PROMPT DEĞİLDİ: cockpit takvimi PARÇALI veriyordu — `upcoming_payments` yalnız
kredi taksitleri, `upcoming_receivables` yalnız alacaklar; **kart ödemesi hiçbir tarihli
listede yoktu** ve hiçbir kalem yönünü söylemiyordu. Koç takvimi kendisi kurmak zorundaydı.
Bu aritmetik mimarinin kendi ilkesine göre kural motorunun işidir.

BU KAPININ TUTTUĞU SÖZLEŞME:
  1. Tek, tarihe göre sıralı liste; kart ödemesi DAHİL.
  2. Her kalem yönünü İKİ KEZ söyler: `yon` kelimesi + işaretli `etki`. Fazlalık kasıtlı —
     ölçülen defekt tam olarak işaretin yanlış okunmasıydı.
  3. `tutar` DAİMA pozitif büyüklüktür; işaret yalnız `etki`dedir.
  4. Açık, ay sonu bakiyesine değil EN DÜŞÜK noktaya bakar.
  5. Bu ay zaten nakde geçmiş yinelenen kalem İKİNCİ KEZ sayılmaz (BUG #086).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (Account, AccountType, Base, DebtDirection, PersonalDebt,
                        RecurringExpense, RecurringIncome, User)
from app.rules_engine import calculate_nakit_takvimi

BUGUN = date(2026, 9, 2)


def _db(*, nakit=2663.59, gelir=None, gider=None, kart=None, kredi=None, alacak=None):
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="T"))
    kasa = Account(id=1, user_id=1, name="Kasa", account_type=AccountType.cash, balance=nakit)
    s.add(kasa)
    s.flush()   # RecurringExpense.account_id NOT NULL — hesabın id'si gerekiyor
    if gelir:
        s.add(RecurringIncome(user_id=1, name=gelir[0], amount=gelir[1],
                              day_of_month=gelir[2], is_active=True,
                              last_triggered_year_month=gelir[3] if len(gelir) > 3 else None))
    if gider:
        s.add(RecurringExpense(user_id=1, name=gider[0], amount=gider[1],
                               account_id=kasa.id, day_of_month=gider[2], is_active=True))
    if kart:
        s.add(Account(user_id=1, name="Kart", account_type=AccountType.credit_card,
                      balance=kart[0], credit_limit=12000.0, statement_day=2,
                      payment_day=kart[1]))
    if kredi:
        s.add(Account(user_id=1, name="Kredi", account_type=AccountType.loan,
                      balance=16439.65, monthly_payment=kredi[0],
                      next_payment_date=kredi[1]))
    if alacak:
        s.add(PersonalDebt(user_id=1, counterparty=alacak[0], amount=alacak[1],
                           direction=DebtDirection.receivable, is_paid=False,
                           due_date=alacak[2]))
    s.commit()
    return s


def _kalem(r, ad):
    return next(k for k in r["kalemler"] if k["ad"] == ad)


# ---- 1) YÖN: ölçülen defektin ta kendisi --------------------------------------

def test_gelen_para_GIRIS_gider_CIKIS_olarak_isaretlenir():
    """G3'ün hatası buydu: gelen 4.000 TL çıkış listesine kondu."""
    db = _db(gelir=("KYK", 4000.0, 8), gider=("Kira", 1500.0, 5))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert _kalem(r, "KYK")["yon"] == "giris"
    assert float(_kalem(r, "KYK")["etki"]) == 4000.0
    assert _kalem(r, "Kira")["yon"] == "cikis"
    assert float(_kalem(r, "Kira")["etki"]) == -1500.0


def test_tutar_DAIMA_pozitif_isaret_yalniz_etkide():
    """`tutar` büyüklüktür. İşareti oraya da koymak çift-negatif okumaya kapı açar."""
    db = _db(gider=("Kira", 1500.0, 5))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    for k in r["kalemler"]:
        assert float(k["tutar"]) > 0, f"{k['ad']}: tutar işaretli"
        assert (float(k["etki"]) < 0) == (k["yon"] == "cikis")


def test_yon_hem_kelime_hem_isaret_tasir():
    """Fazlalık KASITLI: tek bir eksi yanlış okunabilir, bir kelime okunamaz."""
    db = _db(gelir=("Maas", 9000.0, 15), gider=("Kira", 1500.0, 5))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    for k in r["kalemler"]:
        assert k["yon"] in ("giris", "cikis")
        assert "etki" in k and "tutar" in k


# ---- 2) KART ÖDEMESİ: hiçbir tarihli listede yoktu ----------------------------

def test_kart_odemesi_takvime_GIRIYOR():
    """G3'ün ikinci hatası: 8.221,13 TL hiç sayılmadı çünkü hiçbir listede yoktu."""
    db = _db(kart=(8221.13, 14))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    kart = _kalem(r, "Kart")
    assert kart["tip"] == "kart_odeme" and kart["yon"] == "cikis"
    assert float(kart["tutar"]) == 8221.13
    assert kart["tarih"] == "2026-09-14"


def test_borcu_olmayan_kart_takvime_girmez():
    db = _db(kart=(0.0, 14))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert not any(k["tip"] == "kart_odeme" for k in r["kalemler"])


# ---- 3) 1 EYLÜL MANZARASI: insanın elle bulduğu sayıyı üretiyor mu -------------

def test_altin_manzarada_cikis_toplami_15078_25():
    """
    Çıta, 1 Eyl 2026'da elle yapılan analiz: Eylül zorunlu çıkışı 15.078,25 TL
    (4.109,90 + 8.221,13 + 2.747,22). Koç 10.857 demişti.
    """
    from scripts.coach_altin import EYLUL_ZORUNLU_CIKIS, altin_db
    db = altin_db()
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert float(r["toplam_cikis"]) == EYLUL_ZORUNLU_CIKIS
    assert [k["tarih"] for k in r["kalemler"]] == ["2026-09-11", "2026-09-14", "2026-09-15"]


# ---- 4) AÇIK: ay sonuna değil EN DÜŞÜK noktaya bakar ---------------------------

def test_acik_ay_ortasindaki_dip_noktaya_gore_belirlenir():
    """
    Ay sonu artıda kapanan bir plan, ayın ortasında ödeme kaçırıyorsa yine de açıktır.
    Sıra: 5'inde 1.500 çıkar (dip), 25'inde 5.000 girer (ay sonu artıda kapanır).
    """
    db = _db(nakit=1000.0, gider=("Kira", 1500.0, 5), gelir=("Maas", 5000.0, 25))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert float(r["ay_sonu_bakiye"]) > 0, "kurgu bozuk: ay sonu artıda olmalıydı"
    assert float(r["en_dusuk_bakiye"]) == -500.0
    assert r["en_dusuk_tarih"] == "2026-09-05"
    assert r["acik_var"] is True


def test_acik_yoksa_bayrak_dusmez():
    db = _db(nakit=50000.0, gider=("Kira", 1500.0, 5))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert r["acik_var"] is False


# ---- 5) ÇİFT SAYIM: bu ay nakde geçmiş kalem tekrar sayılmaz -------------------

def test_bu_ay_tetiklenmis_gelir_ikinci_kez_sayilmaz():
    """BUG #086'nın dersi: nakde geçen gelir hem nakitte hem beklenende görünürdü."""
    db = _db(gelir=("Maas", 9000.0, 15, "2026-09"))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert not any(k["ad"] == "Maas" for k in r["kalemler"])


def test_gecmis_tarihli_kalem_takvime_girmez():
    """Bugünden önceki gün geçmiştir; takvim ileriye bakar."""
    db = _db(gider=("Gecmis", 500.0, 1))   # ayın 1'i, bugün 2'si
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert not any(k["ad"] == "Gecmis" for k in r["kalemler"])


def test_alacak_giris_olarak_girer():
    db = _db(alacak=("Ahmet", 2000.0, date(2026, 9, 20)))
    try:
        r = calculate_nakit_takvimi(1, db, BUGUN)
    finally:
        db.close()
    assert _kalem(r, "Ahmet")["yon"] == "giris"


# ---- 6) KOÇ BAĞLAMI: hesap doğru ama taşınmıyorsa boşuna ----------------------

def test_takvim_kocun_baglamina_giriyor():
    from app.coach import _build_context_message
    from scripts.coach_altin import altin_db
    db = altin_db()
    try:
        ctx, cockpit = _build_context_message(db, 1)
    finally:
        db.close()
    assert "nakit_takvimi" in cockpit
    assert "NAKİT TAKVİMİ" in ctx
    # Yönün KELİMESİ bağlamda görünmeli — ölçülen defekt işaretin yanlış okunmasıydı.
    assert "ÇIKIŞ" in ctx
    assert "15.078,25" in ctx, "çıkış toplamı bağlamda yok"
    assert "EN DÜŞÜK" in ctx
