"""
Beta KULLANIM METRİKLERİ (P7/P8, BUG #214) — operatör aracı, gizliliğe saygılı.

SORUN: P8'in çıkış ölçütü "gerçek kullanıcı davranışıyla sınanmış operasyon". Ama
operatörün betanın KULLANILIP kullanılmadığını görebileceği hiçbir yol yoktu:
`beta_triage` yalnız şikâyet edeni gösterir — sessizce vazgeçen kullanıcı hiç görünmez.
Beta'nın en olası başarısızlığı gürültülü çöküş değil, SESSİZ terktir: 8 kişi davet
edilir, 6'sı kayıt olur, 5'i ilk ekranda takılır, kimse şikâyet etmez, panelde her şey
yeşil görünür. Bu araç o kör noktayı kapatır.

GİZLİLİK TASARIMI (kod seviyesinde, iyi niyete bırakılmaz):
- Yalnız SAYI ve ORAN basılır. E-posta, isim, işlem açıklaması, PARA TUTARI, koç mesajı
  ve serbest metin bu araçtan ASLA çıkmaz (`tests/test_beta_metrics.py` bunu kilitler).
- Veri makineden ÇIKMAZ: dış analitik servisi (GA/Mixpanel/Sentry) yoktur, sorgular
  kendi DB'mize gider. Hata izlemede verilen kararla aynı çizgi (BUG #195).
- "Kim ne yaptı" sorusu bu aracın konusu değildir; o, kullanıcının kendi talebiyle
  (destek) `beta_triage` üzerinden ve maskeli yürür.

AKTİFLİK TANIMI: bir kullanıcı, bir günde şu izlerden en az birini bıraktıysa o gün
aktiftir — işlem yazımı, koç çağrısı, koç mesajı. Ayrı bir "son giriş" sütunu EKLENMEDİ:
şema değişikliği gerektirir ve giriş yapıp hiçbir şey yapmamak zaten "kullanım" değildir.

Kullanım (sunucuda):
    python -m scripts.beta_metrics                # son 30 gün
    python -m scripts.beta_metrics --gun 7
    python -m scripts.beta_metrics --json         # makine okunur (izleme/cron)
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Set

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Account,
    ApiCallLog,
    ApiCallStatus,
    CoachMemory,
    ErrorLog,
    Feedback,
    Goal,
    MasterCheckpoint,
    Transaction,
    User,
)


def _gun_kumeleri(db, esik: datetime) -> Dict[int, Set[str]]:
    """{user_id: {"2026-08-05", ...}} — aktif GÜN kümesi (üç sinyalin birleşimi).

    Aynı gün hem işlem hem koç kullanan kullanıcı BİR kez sayılır; aksi halde tek
    kişinin yoğun bir günü "çok kullanıcı" gibi görünür (metrik kendini kandırır).
    """
    gunler: Dict[int, Set[str]] = {}

    def _ekle(satirlar) -> None:
        for uid, zaman in satirlar:
            if uid is None or zaman is None:
                continue
            gunler.setdefault(uid, set()).add(zaman.strftime("%Y-%m-%d"))

    _ekle(db.query(Transaction.user_id, Transaction.created_at)
          .filter(Transaction.created_at >= esik).all())
    _ekle(db.query(ApiCallLog.user_id, ApiCallLog.called_at)
          .filter(ApiCallLog.called_at >= esik).all())
    _ekle(db.query(CoachMemory.user_id, CoachMemory.timestamp)
          .filter(CoachMemory.timestamp >= esik).all())
    return gunler


def _huni(db) -> Dict[str, int]:
    """Onboarding hunisi — kaç kullanıcı hangi adımda takıldı (sayı, kimlik değil).

    P3.5'in ("sistem tek kişinin OS'u olmaktan çıkıp ürün oldu") tek gerçek ölçüsü:
    yeni kullanıcı KENDİ verisini kurabiliyor mu, yoksa boş ekranda mı kalıyor?
    """
    def _ayri(model, alan="user_id") -> int:
        return db.query(func.count(func.distinct(getattr(model, alan)))).scalar() or 0

    return {
        "kayitli": db.query(func.count(User.id)).scalar() or 0,
        "eposta_dogrulanmis": db.query(func.count(User.id))
                                .filter(User.email_verified_at.isnot(None)).scalar() or 0,
        "hesap_ekleyen": _ayri(Account),
        "islem_giren": _ayri(Transaction),
        "koc_kullanan": _ayri(CoachMemory),
        "hedef_koyan": _ayri(Goal),
        "kendi_kuralini_yazan": _ayri(MasterCheckpoint),
    }


def _tutunma(db, gunler: Dict[int, Set[str]]) -> Dict[str, int]:
    """Kayıttan SONRAKİ bir günde geri dönen kullanıcı sayısı.

    Tek oturumluk merak ile gerçek kullanımı ayıran ölçü budur. Kayıt gününde yapılan
    her şey "ilk oturum" sayılır; tutunma ancak BAŞKA bir günde iz varsa sayılır.
    """
    donen = 0
    tek_gun = 0
    for u in db.query(User.id, User.created_at).all():
        uid, kayit = u[0], u[1]
        u_gunler = gunler.get(uid, set())
        if not u_gunler:
            continue
        kayit_gunu = kayit.strftime("%Y-%m-%d") if kayit else None
        diger = {g for g in u_gunler if g != kayit_gunu}
        if diger:
            donen += 1
        else:
            tek_gun += 1
    return {"geri_donen": donen, "tek_gun_kalan": tek_gun}


def _koc(db, esik: datetime) -> Dict[str, float]:
    toplam = db.query(func.count(ApiCallLog.id)).filter(ApiCallLog.called_at >= esik).scalar() or 0
    basarisiz = (db.query(func.count(ApiCallLog.id))
                 .filter(ApiCallLog.called_at >= esik,
                         ApiCallLog.status == ApiCallStatus.failed).scalar() or 0)
    ortalama = (db.query(func.avg(ApiCallLog.duration_ms))
                .filter(ApiCallLog.called_at >= esik,
                        ApiCallLog.status == ApiCallStatus.success).scalar())
    return {
        "cagri": toplam,
        "basarisiz": basarisiz,
        "hata_orani_yuzde": round(100.0 * basarisiz / toplam, 1) if toplam else 0.0,
        "ortalama_sure_ms": int(ortalama) if ortalama else 0,
    }


def _maliyet(db, esik: datetime) -> Dict[str, object]:
    """BUG #274 (LLM-006/OBS-005): koç ne tutuyor — ve neyi HESAPLAYAMIYORUZ.

    İki "eksik" birbirinden ayrı raporlanır, çünkü sebepleri ayrı:
    - `fiyati_bilinmeyen`: token biliniyor ama (sağlayıcı, model) fiyat tablosunda yok
      → yeni bir model eklenmiş, `app/llm_cost.FIYATLAR` güncellenmeli.
    - `tokeni_bilinmeyen`: sağlayıcı usage döndürmedi (çöken istek, yerel model)
      → o çağrının parası hesaplanamaz; sıfır SAYILMAZ.
    Toplam bu iki kümeyi dışarıda bırakır — yani ALT SINIRDIR, gerçek harcama ≥ bu sayı.
    """
    satirlar = (db.query(ApiCallLog.amac, ApiCallLog.est_cost_usd,
                         ApiCallLog.tokens_in, ApiCallLog.tokens_out)
                .filter(ApiCallLog.called_at >= esik).all())

    amac_usd: Dict[str, Decimal] = {}
    toplam_usd = Decimal("0")
    tokeni_bilinmeyen = fiyati_bilinmeyen = 0
    giris = cikis = 0
    for amac, usd, t_in, t_out in satirlar:
        giris += t_in or 0
        cikis += t_out or 0
        if usd is None:
            if t_in is None and t_out is None:
                tokeni_bilinmeyen += 1
            else:
                fiyati_bilinmeyen += 1
            continue
        d = Decimal(usd)
        toplam_usd += d
        anahtar = amac or "?"
        amac_usd[anahtar] = amac_usd.get(anahtar, Decimal("0")) + d

    return {
        "tahmini_usd": float(toplam_usd),
        "amac_bazinda_usd": {k: float(v) for k, v in sorted(amac_usd.items())},
        "giris_token": giris,
        "cikis_token": cikis,
        "fiyati_bilinmeyen_cagri": fiyati_bilinmeyen,
        "tokeni_bilinmeyen_cagri": tokeni_bilinmeyen,
    }


def topla(db, gun: int = 30) -> dict:
    """Tüm metrikleri tek sözlükte döndürür (yalnız sayı/oran — PII yok)."""
    esik = datetime.utcnow() - timedelta(days=gun)
    gunler = _gun_kumeleri(db, esik)

    bugun = datetime.utcnow().strftime("%Y-%m-%d")
    hafta = {(datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)}

    huni = _huni(db)
    aktif_hic = sum(1 for g in gunler.values() if g)
    return {
        "pencere_gun": gun,
        "huni": huni,
        "hic_iz_birakmayan": max(0, huni["kayitli"] - aktif_hic),
        "aktif": {
            "bugun": sum(1 for g in gunler.values() if bugun in g),
            "son_7_gun": sum(1 for g in gunler.values() if g & hafta),
            f"son_{gun}_gun": aktif_hic,
        },
        "tutunma": _tutunma(db, gunler),
        "koc": _koc(db, esik),
        "maliyet": _maliyet(db, esik),
        "saglik": {
            "acik_geri_bildirim": db.query(func.count(Feedback.id))
                                    .filter(Feedback.status == "new").scalar() or 0,
            "hata_grubu": db.query(func.count(ErrorLog.id))
                            .filter(ErrorLog.last_seen_at >= esik).scalar() or 0,
            "hata_tekrari": db.query(func.coalesce(func.sum(ErrorLog.occurrence_count), 0))
                              .filter(ErrorLog.last_seen_at >= esik).scalar() or 0,
        },
    }


def _yuzde(pay: int, payda: int) -> str:
    return f"{100.0 * pay / payda:5.1f}%" if payda else "    —"


def yazdir(m: dict) -> None:
    h = m["huni"]
    kayitli = h["kayitli"]
    print(f"\n=== BETA KULLANIM METRİKLERİ (son {m['pencere_gun']} gün) ===")
    print("    (yalnız toplam sayılar — kişi/e-posta/tutar bu çıktıda yoktur)")

    print("\n-- ONBOARDING HUNİSİ --")
    for etiket, anahtar in (
        ("kayıtlı kullanıcı", "kayitli"),
        ("e-postası doğrulanmış", "eposta_dogrulanmis"),
        ("hesap ekleyen", "hesap_ekleyen"),
        ("işlem giren", "islem_giren"),
        ("koçu kullanan", "koc_kullanan"),
        ("hedef koyan", "hedef_koyan"),
        ("kendi kuralını yazan", "kendi_kuralini_yazan"),
    ):
        print(f"  {etiket:<24} {h[anahtar]:>5}  {_yuzde(h[anahtar], kayitli)}")
    print(f"  {'hiç iz bırakmayan':<24} {m['hic_iz_birakmayan']:>5}  "
          f"{_yuzde(m['hic_iz_birakmayan'], kayitli)}   <- sessiz terk")

    a = m["aktif"]
    print("\n-- AKTİFLİK (işlem / koç çağrısı / koç mesajı olan gün) --")
    for k, v in a.items():
        print(f"  {k:<24} {v:>5}")

    t = m["tutunma"]
    print("\n-- TUTUNMA --")
    print(f"  {'başka bir gün dönen':<24} {t['geri_donen']:>5}  {_yuzde(t['geri_donen'], kayitli)}")
    print(f"  {'yalnız ilk gün':<24} {t['tek_gun_kalan']:>5}  <- merak edip bırakan")

    k = m["koc"]
    print("\n-- KOÇ --")
    print(f"  {'çağrı':<24} {k['cagri']:>5}")
    print(f"  {'başarısız':<24} {k['basarisiz']:>5}  (%{k['hata_orani_yuzde']})")
    print(f"  {'ortalama süre':<24} {k['ortalama_sure_ms']:>5} ms")

    mal = m["maliyet"]
    print("\n-- LLM MALİYETİ (liste fiyatına göre TAHMİN) --")
    print(f"  {'tahmini tutar':<24} ${mal['tahmini_usd']:.4f}")
    for amac, usd in mal["amac_bazinda_usd"].items():
        print(f"    {amac:<22} ${usd:.4f}")
    print(f"  {'girdi / çıktı token':<24} {mal['giris_token']} / {mal['cikis_token']}")
    if mal["fiyati_bilinmeyen_cagri"]:
        print(f"  {'FİYATI BİLİNMEYEN çağrı':<24} {mal['fiyati_bilinmeyen_cagri']:>5}"
              "   <- app/llm_cost.FIYATLAR güncellenmeli")
    if mal["tokeni_bilinmeyen_cagri"]:
        print(f"  {'token döndürmeyen çağrı':<24} {mal['tokeni_bilinmeyen_cagri']:>5}"
              "   <- çöken istek / yerel model / BUG #274 öncesi eski satır")
    print("  (ücretsiz katmanda gerçek fatura 0'dır; tavan zaten çağrı sayısıdır)")

    s = m["saglik"]
    print("\n-- SAĞLIK --")
    print(f"  {'açık geri bildirim':<24} {s['acik_geri_bildirim']:>5}")
    print(f"  {'hata grubu':<24} {s['hata_grubu']:>5}  (toplam {s['hata_tekrari']} tekrar)")
    print("\nDetay/triyaj: python -m scripts.beta_triage")


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Beta kullanım metrikleri (gizliliğe saygılı)")
    ap.add_argument("--gun", type=int, default=30, help="Pencere (varsayılan 30)")
    ap.add_argument("--json", action="store_true", help="Makine okunur çıktı")
    args = ap.parse_args(argv)

    db = SessionLocal()
    try:
        m = topla(db, args.gun)
        if args.json:
            print(json.dumps(m, ensure_ascii=False, indent=2))
        else:
            yazdir(m)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
