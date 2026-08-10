"""
Koç kalite skorlarının ZAMAN İÇİNDE saklanması (LLM-005'in (c) ayağı).

NEDEN:
  `scripts/eval_runner.py` bugüne kadar skoru EKRANA basıp unutuyordu. "Bir prompt/model
  değişikliği kaliteyi düşürürse pass_rate düşer" cümlesi ancak ÖNCEKİ pass_rate bir yerde
  duruyorsa anlamlıdır — yoksa düşüşü görmek operatörün eski terminal çıktısını hatırlamasına
  bağlıdır. #275/#276/#277 üçlemesi harness'ın kendi ölçütlerini düzeltti; bu modül o
  ölçümü KARŞILAŞTIRILABİLİR kılar.

NEDEN DB DEĞİL, JSONL:
  Kayıt operatör aracına aittir (kullanıcı verisi değil), şema göçü gerektirmez, DB
  sıfırlansa da yaşar ve diff'lenebilir. Tablo açmak burada ek kalite getirmezdi
  (KURAL 12: kalitede eşitse basit olan seçilir).

GİZLİLİK (kod seviyesinde, iyi niyete bırakılmaz):
  Dosyaya YALNIZ kod, sayı ve oran yazılır. Koç cevabı, kullanıcı mesajı, judge gerekçesi
  ve herhangi bir PARA TUTARI buraya ASLA girmez (`tests/test_eval_kayit_kapisi.py`
  bunu kilitler) — `scripts/beta_metrics.py` ile aynı çizgi.

GUNCELLEMELER
- 10 Agu 2026 BUG #278 (LLM-005): modul olusturuldu.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

VARSAYILAN_YOL = Path(__file__).resolve().parent.parent / "data" / "eval_runs.jsonl"

# Kayda giren alanlar SABİTTİR: yeni bir alan eklemek, gizlilik kapısından geçmelidir.
IZINLI_ALANLAR = {"zaman", "saglayici", "model", "gecerli", "llm_olu_cagri", "pass_rate",
                  "senaryo_pass", "senaryo_total", "kriterler", "judge"}
IZINLI_JUDGE_ALANLARI = {"saglayici", "model", "oran", "olculen", "gecersiz",
                         "oz_degerlendirme"}


def kayit_olustur(rapor: Dict, saglayici: str, model: Optional[str] = None,
                  judge: Optional[Dict] = None, zaman: Optional[datetime] = None) -> Dict:
    """`coach_eval.run_eval` raporundan saklanabilir (metinsiz) kayıt üretir."""
    kriterler: Dict[str, Dict[str, int]] = {}
    for satir in rapor.get("scenarios", []):
        for kod, gecti in satir.get("scores", {}).items():
            hucre = kriterler.setdefault(kod, {"gecti": 0, "toplam": 0})
            hucre["toplam"] += 1
            hucre["gecti"] += 1 if gecti else 0
    kayit = {
        "zaman": (zaman or datetime.now(timezone.utc)).isoformat(),
        "saglayici": saglayici,
        "model": model,
        "gecerli": bool(rapor.get("gecerli", True)),
        "llm_olu_cagri": int(rapor.get("llm_olu_cagri", 0)),
        "pass_rate": float(rapor.get("pass_rate", 0.0)),
        "senaryo_pass": int(rapor.get("scenario_pass", 0)),
        "senaryo_total": int(rapor.get("scenario_total", 0)),
        "kriterler": kriterler,
        "judge": {k: v for k, v in (judge or {}).items() if k in IZINLI_JUDGE_ALANLARI}
        if judge else None,
    }
    return {k: v for k, v in kayit.items() if k in IZINLI_ALANLAR}


def kaydet(kayit: Dict, yol: Optional[Path] = None) -> Path:
    hedef = Path(yol) if yol else VARSAYILAN_YOL
    hedef.parent.mkdir(parents=True, exist_ok=True)
    with hedef.open("a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    return hedef


def oku(yol: Optional[Path] = None, saglayici: Optional[str] = None,
        n: Optional[int] = None) -> List[Dict]:
    """Kayıtları eskiden yeniye döner. Bozuk satır ATLANIR (dosya elle düzenlenebilir)."""
    hedef = Path(yol) if yol else VARSAYILAN_YOL
    if not hedef.exists():
        return []
    kayitlar = []
    for satir in hedef.read_text(encoding="utf-8").splitlines():
        satir = satir.strip()
        if not satir:
            continue
        try:
            k = json.loads(satir)
        except json.JSONDecodeError:
            continue
        if saglayici and k.get("saglayici") != saglayici:
            continue
        kayitlar.append(k)
    return kayitlar[-n:] if n else kayitlar


def dusus_raporu(yeni: Dict, onceki: Optional[Dict]) -> List[str]:
    """İki koşumu karşılaştırır; DÜŞEN kriterleri satır satır döner (yoksa boş liste).

    GEÇERSİZ koşum (sağlayıcı hiç cevap veremedi) karşılaştırmaya girmez — ölü koçun
    düşük skoru "kalite düştü" demek değildir, "ölçüm yapılamadı" demektir (L47/BUG #276).
    """
    if onceki is None:
        return []
    if not yeni.get("gecerli", True) or not onceki.get("gecerli", True):
        return ["karşılaştırma yapılmadı: koşumlardan biri GEÇERSİZ (sağlayıcı cevap vermedi)"]

    satirlar: List[str] = []
    if yeni.get("pass_rate", 0) < onceki.get("pass_rate", 0):
        satirlar.append(
            f"pass_rate {onceki['pass_rate']} -> {yeni['pass_rate']} (DÜŞTÜ)")
    for kod, hucre in sorted(yeni.get("kriterler", {}).items()):
        eski = (onceki.get("kriterler") or {}).get(kod)
        if not eski or not eski.get("toplam") or not hucre.get("toplam"):
            continue
        y = hucre["gecti"] / hucre["toplam"]
        e = eski["gecti"] / eski["toplam"]
        if y < e:
            satirlar.append(
                f"{kod}: {eski['gecti']}/{eski['toplam']} -> {hucre['gecti']}/{hucre['toplam']} (DÜŞTÜ)")
    # Judge oranı bilinmiyorsa (None) karşılaştırılmaz — bilinmeyen, düşüş değildir (L45).
    y_j = (yeni.get("judge") or {}).get("oran")
    e_j = (onceki.get("judge") or {}).get("oran")
    if y_j is not None and e_j is not None and y_j < e_j:
        satirlar.append(f"judge: %{e_j} -> %{y_j} (DÜŞTÜ)")
    return satirlar
