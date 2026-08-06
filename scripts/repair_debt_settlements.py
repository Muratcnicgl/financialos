"""
BUG #241 onarımı — fix ÖNCESİ panelden "ödendi" işaretlenmiş borç/alacakların nakit ayağını uygular.

Panel yolu (`PUT /api/debts/{id}`) kapanışın nakit ayağını hiç uygulamıyordu: alacak tahsil
işaretlenince listeden düşüyor ama nakit artmıyordu (Tam Net Değer sessizce eriyordu). Fix
sonrası yeni işaretlemeler doğru; ama **eski kayıtlar** için para hâlâ eksik. Bu script o
kayıtları bulur ve ayağı TEK KAYNAKTAN (`app/services/debt_settlement`) uygular — yani
kullanıcının "geri al + tekrar işaretle" yapmasıyla bit-bit aynı sonucu üretir.

ÇİFT-SAYIM KORUMASI: koç yolundan (`mark_debt_paid` aksiyonu) kapatılan kayıtlarda nakit
ZATEN hareket etmişti (BUG #113). Bu kayıtlar `settlement_account_id` NULL görünür (kolon
o zaman yoktu) ama ayakları uygulanmıştır → executed `mark_debt_paid` aksiyonu olan borçlar
ATLANIR. Karar veri ile alınır, tahminle değil.

Kullanım (varsayılan KURU ÇALIŞMA — hiçbir şey yazmaz):
    .\\venv\\Scripts\\python.exe -m scripts.repair_debt_settlements
    .\\venv\\Scripts\\python.exe -m scripts.repair_debt_settlements --uygula

Önce `python -m scripts.backup` çalıştır (script bunu hatırlatır, yerine geçmez).
"""
from __future__ import annotations

import argparse
import json

from app.database import SessionLocal
from app.models import PersonalDebt, PendingAction, ActionStatus
from app.services.debt_settlement import KapanisDurumu, senkronize_nakit
from app.action_executor import _yazma_workspace_id


def _koc_yolundan_kapatilanlar(db) -> set[int]:
    """Executed `mark_debt_paid` aksiyonlarının dokunduğu debt_id'ler (nakdi zaten hareket etti)."""
    idler: set[int] = set()
    for a in (db.query(PendingAction)
                .filter(PendingAction.action_type == "mark_debt_paid",
                        PendingAction.status == ActionStatus.executed)
                .all()):
        try:
            debt_id = json.loads(a.payload or "{}").get("debt_id")
        except (ValueError, TypeError):
            continue
        if debt_id is not None:
            idler.add(int(debt_id))
    return idler


def onar(db, uygula: bool = False) -> list[str]:
    """Eksik nakit ayaklarını bulur (ve `uygula` ise yazar). Döner: rapor satırları.

    Session dışarıdan verilir → test edilebilir (canlı DB'ye dokunmadan).
    """
    koc = _koc_yolundan_kapatilanlar(db)
    adaylar = (db.query(PersonalDebt)
                 .filter(PersonalDebt.is_paid.is_(True),
                         PersonalDebt.settlement_account_id.is_(None))
                 .order_by(PersonalDebt.id.asc())
                 .all())

    if not adaylar:
        return ["Nakit ayağı eksik kalmış kapanış YOK — onarılacak bir şey yok."]

    rapor = [f"{len(adaylar)} kapanışın nakit ayağı eksik görünüyor "
             f"({len(koc)} kayıt koç yolundan kapatıldığı için atlanacak):", ""]
    uygulanan = 0
    for d in adaylar:
        etiket = (f"  #{d.id} {d.direction.value} {float(d.amount):,.2f} TL "
                  f"(ödenme: {d.paid_date})")
        if d.id in koc:
            rapor.append(f"{etiket} -> ATLANDI (koç yolundan kapatılmış, nakit zaten hareket etti)")
            continue

        if not uygula:
            rapor.append(f"{etiket} -> uygulanacak (kuru çalışma)")
            uygulanan += 1
            continue

        onceki = KapanisDurumu(is_paid=False, amount=d.amount,
                               direction=d.direction.value, settlement_account_id=None)
        sonuc = senkronize_nakit(db, d.user_id, d, onceki,
                                 workspace_id=_yazma_workspace_id(db, d.user_id))
        if sonuc["applied"]:
            rapor.append(f"{etiket} -> {sonuc['cash_account']}: {float(sonuc['cash_effect']):+,.2f} TL")
            uygulanan += 1
        else:
            rapor.append(f"{etiket} -> ATLANDI (uygun nakit hesap yok)")

    if uygula:
        db.commit()
        rapor += ["", f"TAMAM: {uygulanan} kapanışın nakit ayağı uygulandı."]
    else:
        rapor += ["", f"KURU ÇALIŞMA: {uygulanan} kapanış uygulanacaktı. "
                      "Yazmak için: --uygula (önce `python -m scripts.backup`)."]
    return rapor


def main() -> int:
    ap = argparse.ArgumentParser(description="BUG #241: eksik kalan nakit ayaklarını uygular")
    ap.add_argument("--uygula", action="store_true",
                    help="Gerçekten yaz (varsayılan: yalnız rapor)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        for satir in onar(db, uygula=args.uygula):
            print(satir)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
