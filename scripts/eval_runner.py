"""
Koç Eval Runner — CANLI LLM koç kalitesini objektif ölçer.

Vizyon: wave3-vision Bölüm 6 "eval-driven development" — koç kalitesini görünür/ölçülebilir
kılar. Bir prompt/model/kod değişikliği kaliteyi düşürürse pass_rate düşer (regresyon ağı).

Kullanım:
    python -m scripts.eval_runner                          # .env'deki LLM_PROVIDER ile
    python -m scripts.eval_runner --altin                  # ALTIN SENARYO SETİ (G1-G6)
    LLM_PROVIDER=groq python -m scripts.eval_runner
    python -m scripts.eval_runner --saglayicilar gemini,groq,ollama   # YAN YANA
    python -m scripts.eval_runner --judge                   # + öznel boyut (LLM-as-judge)
    python -m scripts.eval_runner --judge-saglayici gemini  # judge'ı ayrı sağlayıcıya ver
    python -m scripts.eval_runner --kaydet                  # skoru data/eval_runs.jsonl'e yaz
    python -m scripts.eval_runner --gecmis                  # saklanan koşumları listele

İZOLE in-memory kanonik durum kullanır (Murat'ın tipik manzarası) → GERÇEK DB'ye DOKUNMAZ.
Deterministik kriterler (grounding, KURAL SIFIR, sahte-tamamlama, üslup, format) judge
GEREKTİRMEZ; `--judge` yalnız desenle ölçülemeyen boyutu (muhakeme/çerçeve/risk) ekler ve
CI kapısı DEĞİLDİR (bkz. app/coach_judge.py).

GUNCELLEMELER
- 10 Agu 2026 BUG #278 (LLM-005): yan yana saglayici kosumu + judge + skor saklama eklendi.
  Onceki hal tek saglayiciyi kosup ekrana basiyor ve unutuyordu.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine                     # noqa: E402
from sqlalchemy.orm import sessionmaker                  # noqa: E402

from app.models import Base, User, Account, AccountType  # noqa: E402
from app.coach import CoachEngine, build_provider        # noqa: E402
from scripts.coach_altin import ALTIN_SENARYOLAR, altin_db  # noqa: E402
from app.coach_eval import DEFAULT_SCENARIOS, run_eval, format_report  # noqa: E402
from app.coach_judge import (JudgeSonucu, degerlendir,   # noqa: E402
                             oz_degerlendirme_mi, rapor_satirlari)
from app.eval_store import (VARSAYILAN_YOL, dusus_raporu, kaydet,  # noqa: E402
                            kayit_olustur, oku)


def _canonical_db():
    """
    Kontrollü MİNİMAL manzara — izole, tekrarlanabilir (gerçek DB'ye dokunmaz).

    NEDEN minimal (12 Tem gözlemi): eval DETERMİNİSTİK KOÇ DAVRANIŞ regresyonunu ölçer
    (KURAL SIFIR, action-proposing, sahte-tamamlama, format) — Murat'ın tam verisini
    simüle etmek DEĞİL. DB'yi zenginleştirmek (5 kredi + alacaklar) koç context'ini
    ~8000+ token'a şişirip Groq+Cerebras free-tier TPM'ini AŞTIRIYOR → ikisi de circuit
    breaker'la atlanıp ZAYIF sağlayıcıya düşülüyor → action senaryoları provider-boyut
    gürültüsüyle bozuluyor (6/8 → 4/8). Minimal DB davranışı sağlayıcı-boyutundan İZOLE
    ölçer. Grounding-analiz senaryoları sağlayıcı-halüsinasyonuna duyarlıdır (kaçınılmaz;
    grounding uydurmayı DOĞRU yakalar → confidence düşer). Bkz. memory reference_groq_tpm_limiti.
    """
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    s = sessionmaker(bind=eng)()
    s.add(User(id=1, name="Murat"))
    s.add(Account(user_id=1, name="Enpara", account_type=AccountType.cash, balance=4276.0))
    s.add(Account(user_id=1, name="Ziraat", account_type=AccountType.credit_card,
                  balance=11976.0, credit_limit=12000.0, statement_day=2, payment_day=12))
    s.commit()
    return s


def _saglayici_kur(ad: Optional[str]):
    """Adı verilen sağlayıcıyı kurar (ad yoksa .env'deki). Kuramazsa (None, hata) döner."""
    onceki = os.environ.get("LLM_PROVIDER")
    try:
        if ad:
            os.environ["LLM_PROVIDER"] = ad
        return build_provider(), None
    except Exception as e:
        return None, str(e)
    finally:
        if ad:
            if onceki is None:
                os.environ.pop("LLM_PROVIDER", None)
            else:
                os.environ["LLM_PROVIDER"] = onceki


def _judge_kosumu(judge_provider, cevaplar: List[Tuple[str, str, str]],
                  olculen_saglayici: str) -> Tuple[Dict, List[str]]:
    """Her senaryo cevabını judge'a puanlatır; özet + rapor satırlarını döner."""
    sonuclar: List[Tuple[str, JudgeSonucu]] = []
    for ad, mesaj, cevap in cevaplar:
        sonuclar.append((ad, degerlendir(judge_provider, mesaj, cevap)))

    gecerliler = [s for _, s in sonuclar if s.gecerli and s.oran is not None]
    ozet = {
        "saglayici": getattr(judge_provider, "NAME", type(judge_provider).__name__),
        "model": getattr(judge_provider, "model", None),
        # Bilinmeyen, sıfır DEĞİLDİR (L45): hiç geçerli puan yoksa oran None kalır.
        "oran": round(sum(s.oran for s in gecerliler) / len(gecerliler), 1) if gecerliler else None,
        "olculen": len(gecerliler),
        "gecersiz": len(sonuclar) - len(gecerliler),
    }
    ozet["oz_degerlendirme"] = oz_degerlendirme_mi(ozet["saglayici"], olculen_saglayici)
    return ozet, rapor_satirlari(sonuclar)


def _tek_kosum(saglayici_adi: Optional[str], judge_provider, args) -> Optional[Dict]:
    provider, hata = _saglayici_kur(saglayici_adi)
    if provider is None:
        print(f"[ATLANDI] {saglayici_adi or '(.env)'}: sağlayıcı kurulamadı — {hata}")
        return None
    ad = getattr(provider, "NAME", type(provider).__name__)
    print(f"\n=== Sağlayıcı: {ad} ({getattr(provider, 'model', '?')}) ===")

    engine = CoachEngine(provider=provider)
    # Altın set KENDİ manzarasını ister: `_canonical_db` kasten minimaldir (davranış ölçümünü
    # sağlayıcı gürültüsünden yalıtmak için), altın set ise zorunlu olarak zengindir.
    senaryolar = ALTIN_SENARYOLAR if args.altin else DEFAULT_SCENARIOS
    db = altin_db() if args.altin else _canonical_db()
    try:
        if args.altin:
            print("  [altin] G1-G6 — koçun MUHAKEMESİ ölçülüyor (davranış sözleşmesi değil).")
        rapor = run_eval(engine, db, 1, senaryolar)
        print(format_report(rapor))

        judge_ozet = None
        if judge_provider is not None:
            # Judge, DETERMİNİSTİK KOŞUMUN TAM cevaplarını puanlar (ikinci bir geçiş
            # koşmak başka cevapları puanlardı — ölçüm ile not ayrışırdı).
            mesajlar = {sc.name: sc.user_message for sc in senaryolar}
            cevaplar = [(r["name"], mesajlar.get(r["name"], ""), r.get("reply_tam", ""))
                        for r in rapor["scenarios"]]
            judge_ozet, satirlar = _judge_kosumu(judge_provider, cevaplar, ad)
            print("\n--- Judge (öznel boyut — CI kapısı DEĞİL) ---")
            oran = judge_ozet["oran"]
            print(f"  Judge: {judge_ozet['saglayici']} · ortalama: "
                  f"{'ÖLÇÜLEMEDİ' if oran is None else f'%{oran}'} "
                  f"({judge_ozet['olculen']} ölçüldü, {judge_ozet['gecersiz']} skor yok)")
            if judge_ozet["oz_degerlendirme"]:
                print("  !! ÖZ-DEĞERLENDİRME: judge, ölçülen sağlayıcının kendisi — "
                      "skor yanlı olabilir.")
            print("\n".join(satirlar))
    finally:
        db.close()

    # İki set AYNI dosyaya yazılır ama AYNI ŞEYİ ölçmez. Etiket olmadan geçmiş listesinde
    # davranış oranı ile muhakeme oranı yan yana durur ve düşüş raporu ikisini kıyaslar —
    # yani birbirine karışan iki ölçüm sahte bir "regresyon" üretir.
    kayit = kayit_olustur(rapor, ad, getattr(provider, "model", None), judge_ozet,
                          senaryo_seti="altin" if args.altin else "varsayilan")
    if args.kaydet:
        onceki = onceki_ayni_setten(ad, kayit["set"])
        dusus = dusus_raporu(kayit, onceki[-1] if onceki else None)
        yol = kaydet(kayit)
        print(f"\n  [kayıt] {yol}")
        if dusus:
            print("  !! ÖNCEKİ KOŞUMA GÖRE DÜŞÜŞ:")
            for satir in dusus:
                print(f"     - {satir}")
    return kayit


def onceki_ayni_setten(saglayici: str, senaryo_seti: str) -> List[Dict]:
    """
    Düşüş karşılaştırması için AYNI SETİN önceki koşumları.

    Filtre olmadan `dusus_raporu` davranış setinin oranıyla altın setin oranını kıyaslar;
    ikisi farklı soruları ölçtüğü için her set değişiminde SAHTE bir "düşüş" basılır — ve
    sahte alarm veren bir gösterge kısa sürede hiç okunmaz hâle gelir.
    Etiketsiz eski kayıtlar davranış seti sayılır (o tarihte altın set yoktu).
    """
    return [k for k in oku(saglayici=saglayici)
            if k.get("set", "varsayilan") == senaryo_seti]


def _gecmis_yazdir() -> None:
    kayitlar = oku()
    if not kayitlar:
        print(f"Kayıt yok ({VARSAYILAN_YOL}).")
        return
    print(f"{'zaman':26s} {'set':10s} {'saglayici':14s} {'pass_rate':>9s} "
          f"{'senaryo':>9s} {'judge':>7s}")
    for k in kayitlar:
        judge = (k.get("judge") or {}).get("oran")
        gecerli = "" if k.get("gecerli", True) else "  (GECERSIZ)"
        print(f"{k['zaman'][:25]:26s} {str(k.get('set', 'varsayilan'))[:10]:10s} "
              f"{str(k['saglayici'])[:14]:14s} "
              f"{k['pass_rate']:>8.1f}% {k['senaryo_pass']:>4d}/{k['senaryo_total']:<4d} "
              f"{'-' if judge is None else f'{judge:>6.1f}%'}{gecerli}")


def main() -> None:
    ayristirici = argparse.ArgumentParser(description="Koç kalite eval koşumu")
    ayristirici.add_argument("--saglayicilar", default=None,
                             help="virgülle ayrılmış liste (yan yana koşum), ör. gemini,groq")
    ayristirici.add_argument("--judge", action="store_true",
                             help="öznel boyutu da ölç (LLM-as-judge)")
    ayristirici.add_argument("--judge-saglayici", default=None,
                             help="judge için ayrı sağlayıcı (öz-değerlendirme yanlılığını azaltır)")
    ayristirici.add_argument("--kaydet", action="store_true",
                             help="skoru data/eval_runs.jsonl'e ekle ve önceki koşumla karşılaştır")
    ayristirici.add_argument("--gecmis", action="store_true", help="saklanan koşumları listele")
    ayristirici.add_argument("--altin", action="store_true",
                             help="ALTIN SENARYO SETİ (G1-G6): koçun muhakemesini ölçer "
                                  "(1 Eyl 2026 gerçek manzarası; bkz. scripts/coach_altin.py)")
    args = ayristirici.parse_args()

    if args.gecmis:
        _gecmis_yazdir()
        return

    judge_provider = None
    if args.judge or args.judge_saglayici:
        judge_provider, hata = _saglayici_kur(args.judge_saglayici)
        if judge_provider is None:
            print(f"Judge sağlayıcısı kurulamadı: {hata}")
            print("İpucu: --judge-saglayici gemini (ya da .env'de LLM_PROVIDER).")
            raise SystemExit(1)

    adlar = [a.strip() for a in args.saglayicilar.split(",")] if args.saglayicilar else [None]
    kayitlar = [k for k in (_tek_kosum(ad, judge_provider, args) for ad in adlar) if k]

    if len(kayitlar) > 1:
        print("\n=== YAN YANA ===")
        print(f"{'saglayici':16s} {'pass_rate':>9s} {'senaryo':>9s} {'judge':>8s}  durum")
        for k in kayitlar:
            judge = (k.get("judge") or {}).get("oran")
            print(f"{str(k['saglayici'])[:16]:16s} {k['pass_rate']:>8.1f}% "
                  f"{k['senaryo_pass']:>4d}/{k['senaryo_total']:<4d} "
                  f"{'-' if judge is None else f'{judge:>7.1f}%'}  "
                  f"{'gecerli' if k['gecerli'] else 'GECERSIZ (saglayici cevap vermedi)'}")

    if not kayitlar:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
