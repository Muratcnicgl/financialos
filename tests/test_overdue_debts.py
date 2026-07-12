"""
BUG #120 — vadesi geçmiş borç/alacak gecikme uyarısı (_collect_overdue_debts).
Hatırlatmalar sadece 0-7 gün İLERİ bakar; vade geçince kalem sessizce kaybolurdu.
Gecikmiş yükümlülük (kritik) / tahsil edilmemiş alacak (uyarı) artık alert olur.
Deterministik — izole in-memory DB.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.models import PersonalDebt, DebtDirection
from app.rules_engine import _collect_overdue_debts


def _debt(db, user_id, *, direction, counterparty="X", amount=1000.0,
          overdue_days=5, is_paid=False, today=date(2026, 5, 20)):
    d = PersonalDebt(
        user_id=user_id, counterparty=counterparty, direction=direction,
        amount=amount, is_paid=is_paid, due_date=today - timedelta(days=overdue_days),
    )
    db.add(d); db.commit(); db.refresh(d)
    return d


def test_120_gecikmis_borc_kritik_alert(db_session, test_user):
    today = date(2026, 5, 20)
    _debt(db_session, test_user.id, direction=DebtDirection.payable,
          counterparty="Kirveci", amount=2500.0, overdue_days=3, today=today)

    alerts = _collect_overdue_debts(test_user.id, today, db_session)

    assert len(alerts) == 1
    assert alerts[0]["seviye"] == "kritik"
    assert "Kirveci" in alerts[0]["baslik"]
    assert "3 gün gecikti" in alerts[0]["mesaj"]
    assert "öde" in alerts[0]["mesaj"]


def test_120_gecikmis_alacak_uyari_alert(db_session, test_user):
    today = date(2026, 5, 20)
    _debt(db_session, test_user.id, direction=DebtDirection.receivable,
          counterparty="Efe", amount=4000.0, overdue_days=7, today=today)

    alerts = _collect_overdue_debts(test_user.id, today, db_session)

    assert len(alerts) == 1
    assert alerts[0]["seviye"] == "uyari"
    assert "Efe" in alerts[0]["baslik"]
    assert "7 gün gecikti" in alerts[0]["mesaj"]
    assert "tahsil" in alerts[0]["mesaj"]


def test_120_odenmis_ve_gelecek_vadeli_haric(db_session, test_user):
    today = date(2026, 5, 20)
    # ödenmiş geçmiş vade → hariç
    _debt(db_session, test_user.id, direction=DebtDirection.payable,
          is_paid=True, overdue_days=10, today=today)
    # gelecek vade (negatif overdue = ileri tarih) → hariç
    _debt(db_session, test_user.id, direction=DebtDirection.receivable,
          overdue_days=-5, today=today)   # due_date = today + 5

    assert _collect_overdue_debts(test_user.id, today, db_session) == []


def test_120_en_cok_geciken_once(db_session, test_user):
    today = date(2026, 5, 20)
    _debt(db_session, test_user.id, direction=DebtDirection.payable,
          counterparty="Yeni", overdue_days=2, today=today)
    _debt(db_session, test_user.id, direction=DebtDirection.payable,
          counterparty="Eski", overdue_days=30, today=today)

    alerts = _collect_overdue_debts(test_user.id, today, db_session)
    assert [a["baslik"] for a in alerts] == ["Gecikmiş borç: Eski", "Gecikmiş borç: Yeni"]


def test_120_generate_cockpit_alerts_e_dusuyor(db_session, test_user):
    """Uçtan uca: gecikmiş kalem generate_cockpit çıktısının alerts listesine düşmeli."""
    from app.rules_engine import generate_cockpit
    today = date(2026, 5, 20)
    _debt(db_session, test_user.id, direction=DebtDirection.payable,
          counterparty="Kirveci", overdue_days=4, today=today)

    cockpit = generate_cockpit(test_user.id, today, db_session)
    kritikler = [a for a in cockpit["alerts"] if a["seviye"] == "kritik"]
    assert any("Kirveci" in a.get("baslik", "") for a in kritikler)
    # kritik gecikme listenin başına alınır
    assert cockpit["alerts"][0]["baslik"].startswith("Gecikmiş borç")


def test_120_gecikme_tutari_grounding_dogrulanir(db_session, test_user):
    """
    Regresyon guard'ı: koç gecikmiş tutarı doğru yazınca grounding onu DOĞRULANMIŞ saymalı.
    Tutar yalnızca mesaj string'inde kalsaydı (numerik 'tutar' alanı olmasaydı) grounding
    tutarı 'izlenemeyen' sanıp confidence'ı düşürürdü — bu regresyonu kilitliyoruz.
    """
    from app.rules_engine import generate_cockpit
    from app.grounding import check_grounding
    today = date(2026, 5, 20)
    # Gecikmiş Efe 4.000 + ikinci (gelecek vadeli) 1.500 alacak → alacaklar_toplami=5.500.
    # Böylece 4.000 tutarı SADECE overdue alert'in numerik 'tutar' alanı üzerinden grounding'e
    # girer (toplam 5.500 üstünden değil) — fix'in gerçekten iş yaptığını kanıtlar.
    _debt(db_session, test_user.id, direction=DebtDirection.receivable,
          counterparty="Efe", amount=4000.0, overdue_days=7, today=today)
    _debt(db_session, test_user.id, direction=DebtDirection.receivable,
          counterparty="Selim", amount=1500.0, overdue_days=-10, today=today)  # gelecek vade

    cockpit = generate_cockpit(test_user.id, today, db_session)
    reply = "Efe'den 4.000 TL alacağın 7 gün gecikti, tahsil etmelisin."
    g = check_grounding(reply, cockpit)
    assert g["ok"] is True, f"gecikmiş tutar grounding'de izlenemedi: {g['unverified']}"
