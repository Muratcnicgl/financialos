"""
setup_data.py — Murat'in GERCEK Mayis 2026 finansal manzarasi.

Calistirma:
    python -m scripts.setup_data

Davranis:
    - DB'yi tamamen sifirlar (drop_all + create_all)
    - Tum tablolari yeniden olusturur
    - Murat'in 1 Mayis 2026 itibariyle gercek verilerini yukler

ICERIK (1 Mayis 2026):
    - 1 kullanici (Murat)
    - 8 hesap (1 nakit + 1 kart + 5 kredi + 1 yatirim) — emanet artik YOK
    - 1 periyodik gelir (Maas)
    - 13 alacak (Efe takvimi, 13 ay yayili)
    - 7 master checkpoint (MC1 silindi cunku emanet artik yok, MC2-MC8 korundu)

NOT: Emanet kavrami sistemde kaliyor (Account.is_emanet alani, action_executor
korumalari, coach prompt). Sadece Murat'in DB'sinde kullanilmiyor cunku 1 May'da
annesi 1 lot TLY emaneti hediye etti, artik kisisel hesabin icinde.
"""

from datetime import date, datetime
from app.database import Base, engine, SessionLocal
from app.models import (
    User, Account, AccountType,
    RecurringIncome, RecurringExpense,
    PersonalDebt, DebtDirection,
    MasterCheckpoint, CheckpointType,
)


def main():
    # BUG #076 fix (SSD-001): drop_all TÜM veriyi siler. Yanlışlıkla Murat'ın gerçek
    # verisini yok etmeyi önlemek için açık onay (interaktif) veya --force/env flag gerekir,
    # ve hedef DATABASE_URL kullanıcıya gösterilir.
    import os as _os
    import sys as _sys
    _db_url = _os.getenv("DATABASE_URL", "sqlite:///./data/financialos.db")
    _force = ("--force" in _sys.argv) or (_os.getenv("SETUP_DATA_FORCE") == "1")
    print(f"UYARI: Bu script hedef veritabanındaki TÜM veriyi siler (drop_all).")
    print(f"       Hedef: {_db_url}")
    if not _force:
        _resp = input("Devam edilsin mi? Tüm mevcut veri KALICI SİLİNECEK (evet/hayir): ").strip().lower()
        if _resp not in ("evet", "e", "yes", "y"):
            print("İptal edildi. (Onaysız çalıştırmak için: --force veya SETUP_DATA_FORCE=1)")
            return
    print("DB sifirlaniyor (drop_all + create_all)...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("  -> Tum tablolar yeniden olusturuldu (11 tablo).\n")

    db = SessionLocal()
    try:
        # ============================================================
        # 1. KULLANICI
        # ============================================================
        print("=== Murat verisi yukleniyor (1 Mayis 2026 manzarasi) ===\n")

        murat = User(
            name="Murat",
            created_at=datetime.utcnow(),
        )
        db.add(murat)
        db.flush()
        print(f"Kullanici olusturuldu: {murat.name} (id={murat.id})\n")

        # ============================================================
        # 2. HESAPLAR (8 adet — emanet yok)
        # ============================================================
        print("Hesaplar:")

        # --- 2.1 NAKIT — Enpara
        enpara = Account(
            user_id=murat.id,
            name="Enpara Nakit",
            account_type=AccountType.cash,
            balance=6190.78,
            is_emanet=False,
        )
        db.add(enpara)

        # --- 2.2 KREDI KARTI — Ziraat
        ziraat = Account(
            user_id=murat.id,
            name="Ziraat Kredi Karti",
            account_type=AccountType.credit_card,
            balance=4342.98,             # Mevcut borc
            credit_limit=4349.63,        # Toplam limit (borc + kullanilabilir 6.65)
            statement_day=2,             # Kesim gunu
            payment_day=12,              # Son odeme tarihi
            is_emanet=False,
        )
        db.add(ziraat)

        # --- 2.3 GARANTI KREDI 1 (30K, paylasimli, Mayis sonrasi tamamen Murat'in)
        kredi_1 = Account(
            user_id=murat.id,
            name="Garanti Kredi 1 (30K)",
            account_type=AccountType.loan,
            balance=32879.25,
            monthly_payment=4109.90,
            remaining_installments=8,
            next_payment_date=date(2026, 5, 11),
            is_emanet=False,
        )
        db.add(kredi_1)

        # --- 2.4 GARANTI KREDI 2 (30K, paylasimli, Mayis sonrasi tamamen Murat'in)
        kredi_2 = Account(
            user_id=murat.id,
            name="Garanti Kredi 2 (30K)",
            account_type=AccountType.loan,
            balance=30760.61,
            monthly_payment=4394.36,
            remaining_installments=7,
            next_payment_date=date(2026, 5, 15),
            is_emanet=False,
        )
        db.add(kredi_2)

        # --- 2.5 GARANTI KREDI 3 (9K, tamamen Efe)
        kredi_3 = Account(
            user_id=murat.id,
            name="Garanti Kredi 3 (9K - Efe)",
            account_type=AccountType.loan,
            balance=7983.60,
            monthly_payment=2661.19,
            remaining_installments=3,
            next_payment_date=date(2026, 5, 15),
            is_emanet=False,
        )
        db.add(kredi_3)

        # --- 2.6 GARANTI KREDI 4 (7.5K, tamamen Efe)
        kredi_4 = Account(
            user_id=murat.id,
            name="Garanti Kredi 4 (7.5K - Efe)",
            account_type=AccountType.loan,
            balance=6517.43,
            monthly_payment=2172.47,
            remaining_installments=3,
            next_payment_date=date(2026, 5, 25),
            is_emanet=False,
        )
        db.add(kredi_4)

        # --- 2.7 GARANTI KREDI 5 (6K, tamamen Efe)
        kredi_5 = Account(
            user_id=murat.id,
            name="Garanti Kredi 5 (6K - Efe)",
            account_type=AccountType.loan,
            balance=7616.55,
            monthly_payment=846.29,
            remaining_installments=9,
            next_payment_date=date(2026, 5, 5),
            is_emanet=False,
        )
        db.add(kredi_5)

        # --- 2.8 TLY (Midas, 6 lot)
        tly = Account(
            user_id=murat.id,
            name="TLY Fonu (Midas)",
            account_type=AccountType.investment,
            balance=31342.82,            # 6 * 5223.81 = 31342.86 ama Midas 31342.82 gosteriyor
            lot_count=6,
            cost_per_lot=4125.2333,
            current_price=5223.81,
            fund_code="TLY",
            last_price_update=datetime.utcnow(),
            is_emanet=False,
        )
        db.add(tly)

        db.flush()

        for acc in [enpara, ziraat, kredi_1, kredi_2, kredi_3, kredi_4, kredi_5, tly]:
            print(f"  Hesap olusturuldu: {acc.name} (id={acc.id})")
        print()

        # ============================================================
        # 3. PERIYODIK GELIR — Maas
        # ============================================================
        print("Periyodik gelirler:")
        maas = RecurringIncome(
            user_id=murat.id,
            name="Maas",
            amount=8300.0,                # Bu ay 8300 yatti (genelde ~8400)
            day_of_month=1,
            is_active=True,
        )
        db.add(maas)
        print(f"  Gelir olusturuldu: {maas.name} ({maas.amount} TL/ay, ayin {maas.day_of_month}'i)")
        kyk = RecurringIncome(
            user_id=murat.id,
            name="KYK Bursu",
            amount=4000.0,
            day_of_month=8,
            is_active=True,
        )
        db.add(kyk)
        print(f"  Gelir olusturuldu: {kyk.name} ({kyk.amount} TL/ay, ayin {kyk.day_of_month}'i)\n")

        # ============================================================
        # 3b. PERIYODIK GIDER — Abonelikler ve faturalar (A3)
        # ============================================================
        print("Periyodik giderler:")
        recurring_expenses = [
            RecurringExpense(user_id=murat.id, name="Netflix",    amount=149.0,  account_id=ziraat.id,
                             category="abonelik",  day_of_month=1,  is_active=True),
            RecurringExpense(user_id=murat.id, name="Spotify",    amount=49.0,   account_id=ziraat.id,
                             category="abonelik",  day_of_month=1,  is_active=True),
            RecurringExpense(user_id=murat.id, name="Internet",   amount=299.0,  account_id=ziraat.id,
                             category="fatura",    day_of_month=10, is_active=True),
        ]
        for exp in recurring_expenses:
            db.add(exp)
            print(f"  Gider olusturuldu: {exp.name} ({exp.amount} TL/ay, ayin {exp.day_of_month}'i)")
        print()

        # ============================================================
        # 4. EFE ALACAK TAKVIMI (15 kayit, toplam 29.635 TL)
        # ============================================================
        print("Efe alacak takvimi (15 odeme, toplam 29.635 TL):")

        efe_takvim = [
            # Mayis 2026
            (date(2026, 5, 5),  10215.00, "Ortak krediler son pay (Mayis sonrasi 30K krediler tamamen Murat'a kaliyor)"),
            (date(2026, 5, 5),    850.00, "Kredi #5 (6K) payi 1/9"),
            (date(2026, 5, 25),  2150.00, "Kredi #4 (7.5K) payi 1/3"),

            # Haziran 2026
            (date(2026, 6, 5),   2660.00, "Kredi #3 (9K) payi 1/3"),
            (date(2026, 6, 5),    850.00, "Kredi #5 (6K) payi 2/9"),
            (date(2026, 6, 25),  2150.00, "Kredi #4 (7.5K) payi 2/3"),

            # Temmuz 2026
            (date(2026, 7, 5),   2660.00, "Kredi #3 (9K) son taksit 3/3"),
            (date(2026, 7, 5),    850.00, "Kredi #5 (6K) payi 3/9"),
            (date(2026, 7, 25),  2150.00, "Kredi #4 (7.5K) son taksit 3/3"),

            # Agustos 2026 - Ocak 2027 (Kredi #5 son 6 taksit)
            (date(2026, 8, 5),    850.00, "Kredi #5 (6K) payi 4/9"),
            (date(2026, 9, 5),    850.00, "Kredi #5 (6K) payi 5/9"),
            (date(2026, 10, 5),   850.00, "Kredi #5 (6K) payi 6/9"),
            (date(2026, 11, 5),   850.00, "Kredi #5 (6K) payi 7/9"),
            (date(2026, 12, 5),   850.00, "Kredi #5 (6K) payi 8/9"),
            (date(2027, 1, 5),    850.00, "Kredi #5 (6K) son taksit 9/9"),
        ]

        toplam = 0
        for tarih, tutar, aciklama in efe_takvim:
            alacak = PersonalDebt(
                user_id=murat.id,
                counterparty="Efe",
                direction=DebtDirection.receivable,    # Murat alacakli (Efe -> Murat)
                amount=tutar,
                due_date=tarih,
                description=aciklama,
                is_paid=False,
            )
            db.add(alacak)
            toplam += tutar
            print(f"  Alacak: {tarih.isoformat()} {tutar:>9.2f} TL - {aciklama}")
        print(f"  TOPLAM: {toplam:.2f} TL\n")

        # ============================================================
        # 5. MASTER CHECKPOINTS (7 adet, MC1 silindi numara korunur)
        # ============================================================
        print("Master Checkpoints (MC1 silindi cunku emanet artik yok):")

        checkpoints = [
            # MC1 SILINDI - Anne 1 Mayis'ta TLY emanetini Murat'a hediye etti.
            (
                "MC2 - TLY Kaldirac Stratejisi",
                CheckpointType.strategy,
                2,
                "TLY fonu Garanti kredilerine karsi kalkan gorevi gorur. "
                "TLY satislari Murat'in onayiyla, belirli kosullarda yapilir "
                "(likidite ihtiyaci + reel butce baskisi). MC8 (Hayatta Kalma > Yatirim) "
                "ile birlikte degerlendirilir."
            ),
            (
                "MC3 - Ziraat Kart Dongusu",
                CheckpointType.strategy,
                2,
                "Ziraat Kredi Karti her ayin 2'sinde ekstre kesim, ayin 12'sinde "
                "son odeme. Kesim sonrasi 35-40 gunluk vade avantaji saglayarak "
                "stratejik bir nakit yonetim araci olarak kullanilir. Kullanim orani "
                "%95 uzerinde kritik uyari verir. Kart korkulacak nesne degil, "
                "stratejik bir aractir."
            ),
            (
                "MC4 - Golge Muhasebe Kurali",
                CheckpointType.rule,
                1,
                "Reel butce hesaplamasinda kart borcu HARCANMIS para olarak kabul "
                "edilir. Yani: reel_butce = nakit + beklenen_gelir - kart_borcu. "
                "Bu kural koc'un 'gercek harcanabilir para'yi dogru raporlamasini saglar."
            ),
            (
                "MC5 - Dalkavukluk Yasak",
                CheckpointType.rule,
                1,
                "Koc Murat'a guzel sozler soylemez, asilmaz, motivasyon konusmasi "
                "yapmaz. Direkt, dogru, stratejist konusur. Hata olmusa hata der. "
                "Risk varsa risk der. KESINLIKLE kalir."
            ),
            (
                "MC6 - Varsayim Yasagi",
                CheckpointType.rule,
                1,
                "Koc hayali rakam uretmez, varsayim yapmaz. Sadece DB'deki gercek "
                "veriyi kullanir. Bilmedigi bir bilgi varsa Murat'a sorar. Tahmin "
                "yerine 'bilmiyorum' der."
            ),
            (
                "MC7 - Efe Kredi Payi Takvimi",
                CheckpointType.context,
                2,
                "Efe Garanti kredilerinin BAZILARINI paylasti. 30K iki kredi (Kredi 1+2) "
                "Mayis'a kadar paylasimli, Mayis sonrasi tamamen Murat'a. 9K (Kredi 3), "
                "7.5K (Kredi 4), 6K (Kredi 5) tamamen Efe'ye ait, Efe nakit gonderir Murat oder. "
                "Toplam Efe alacagi 29.635 TL, 13 ay yayilmis. 5 May'da 11.065 TL ilk buyuk giris "
                "(10.215 + 850), sonra her ayin 5'i 850 TL Kredi #5 icin (9 ay), 25'i 2.150 TL "
                "Kredi #4 icin (Mayis-Temmuz), Haziran-Temmuz 5'leri 2.660 TL Kredi #3 icin."
            ),
            (
                "MC8 - Hayatta Kalma > Yatirim",
                CheckpointType.rule,
                1,
                "Likidite her zaman yatirimdan once gelir. Nakit darbogazinda agresif "
                "yatirim onerilmez. Kart kapama veya kredi taksiti gibi onceliklerin "
                "altinda yatirim alimi gibi 'olsa guzel' hamleler reddedilir."
            ),
        ]

        for title, cp_type, priority, description in checkpoints:
            cp = MasterCheckpoint(
                user_id=murat.id,
                title=title,
                checkpoint_type=cp_type,
                priority=priority,
                description=description,
                is_active=True,
            )
            db.add(cp)
            print(f"  MC olusturuldu: {title}")
        print()

        # ============================================================
        # COMMIT
        # ============================================================
        db.commit()

        # ============================================================
        # OZET
        # ============================================================
        print("=== OZET ===")
        print(f"Kullanici    : Murat (id={murat.id})")
        print(f"Hesap        : 8 (1 nakit + 1 kart + 5 kredi + 1 yatirim, emanet YOK)")
        print(f"Gelir        : 1 (Maas 8300 TL/ay, ayin 1'i)")
        print(f"Alacak       : 15 (Efe takvimi, toplam {toplam:.2f} TL)")
        print(f"Checkpoint   : 7 (MC1 silindi, MC2-MC8 korundu)")
        print()
        print("Hesaplanan net deger:")
        nakit = 6190.78
        yatirim = 31342.82
        alacak = 29635.00
        kart = 4342.98
        krediler = 32879.25 + 30760.61 + 7983.60 + 6517.43 + 7616.55
        net = nakit + yatirim + alacak - kart - krediler
        print(f"  Nakit (Enpara)         : {nakit:>10.2f} TL")
        print(f"  Yatirim (TLY 6 lot)    : {yatirim:>10.2f} TL")
        print(f"  Alacaklar (Efe 15)     : {alacak:>10.2f} TL")
        print(f"  Kart borcu (Ziraat)    : {-kart:>10.2f} TL")
        print(f"  Kredi borcu (5 kredi)  : {-krediler:>10.2f} TL")
        print(f"  ----------------------------------")
        print(f"  NET DEGER              : {net:>10.2f} TL")
        print()
        print("Kurulum tamam. Backend ayakta ise GET /api/cockpit ile dogrulayabilirsin.")
        print("Tarayicida localhost:5173 acik ise sayfayi F5 ile yenile, gercek manzaran gozukecek.")

    except Exception as e:
        db.rollback()
        print(f"\nHATA: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()