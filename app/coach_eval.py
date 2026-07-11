"""
Coach Eval Harness — LLM koç kalitesinin OBJEKTİF ölçümü.

Vizyon (wave3-vision Bölüm 6, Eksen J — "eval-driven development"): koç geliştirmeyi
"fix-and-hope"tan objektif ölçüme taşır. Bir koç cevabını DETERMİNİSTİK kriterlerle puanlar —
JUDGE LLM GEREKMEZ; tüm sinyaller chat() çıktısından + grounding'den türetilir. Bu yüzden:
  - Aynı harness hem ScriptedProvider (framework birim testi) hem GERÇEK sağlayıcı
    (canlı kalite ölçümü, scripts/eval_runner.py) ile çalışır.
  - Regresyon ağı: bir prompt/kod değişikliği koç kalitesini düşürürse pass_rate düşer.

Ölçülen kriterler (senaryo bazında seçilir):
  grounded       cevaptaki her TL tutarı cockpit'e izlenebilir (grounding.ok)
  no_action      soru/analiz/gelecek-niyette propose_action OLUŞMAZ (KURAL SIFIR)
  action         gerçekleşmiş eylemde propose_action oluşur
  no_confidence  [CONFIDENCE] işareti kullanıcıya sızmaz
  no_fake        tool çağrılmadan "kaydettim" gibi sahte tamamlama yok
  format         analiz/rapor cevabında ## başlık var

Bu modül SAF ölçüm mantığıdır (rules_engine ruhu); DB'ye yazmaz.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

# Sahte-tamamlama işaret fiilleri (gerçekleşmiş iddia kökleri + çekim ekleri).
# Kök + \w* çünkü "kaydett" → "kaydettim"; sonda \b konursa "kaydett\b" "kaydettim"i KAÇIRIR.
_FAKE_DONE_RE = re.compile(
    r"\b(?:kaydett|ekledi|güncelledi|işledi|tamamladı)\w*",
    re.IGNORECASE,
)

CRITERIA = {"grounded", "no_action", "action", "no_confidence", "no_fake", "format"}


@dataclass
class EvalScenario:
    """Tek bir eval senaryosu: kullanıcı mesajı + geçmesi beklenen kriterler."""
    name: str
    user_message: str
    checks: List[str]
    include_cockpit: bool = True

    def __post_init__(self):
        bad = set(self.checks) - CRITERIA
        if bad:
            raise ValueError(f"Bilinmeyen kriter(ler): {bad}")


def score_result(result: Dict, checks: List[str]) -> Dict[str, bool]:
    """chat() çıktısını verilen kriterlere göre puanlar (kriter → geçti mi)."""
    reply = (result.get("reply") or "")
    actions = result.get("proposed_actions") or []
    grounding = result.get("grounding") or {}

    scores: Dict[str, bool] = {}
    for c in checks:
        if c == "grounded":
            scores[c] = bool(grounding.get("ok", True))
        elif c == "no_action":
            scores[c] = len(actions) == 0
        elif c == "action":
            scores[c] = len(actions) >= 1
        elif c == "no_confidence":
            scores[c] = "CONFIDENCE" not in reply.upper()
        elif c == "no_fake":
            # sahte tamamlama = eylem YOK ama "kaydettim" gibi iddia VAR
            scores[c] = not (len(actions) == 0 and bool(_FAKE_DONE_RE.search(reply)))
        elif c == "format":
            scores[c] = "##" in reply
    return scores


def run_eval(engine, db, user_id: int, scenarios: List[EvalScenario]) -> Dict:
    """
    Her senaryoyu engine.chat ile çalıştırır, kriterleri puanlar, skor kartı döner.
    engine: CoachEngine (herhangi bir provider ile). db/user_id kanonik durumu taşır.
    """
    rows = []
    for sc in scenarios:
        res = engine.chat(db, user_id, sc.user_message, include_cockpit=sc.include_cockpit)
        scores = score_result(res, sc.checks)
        rows.append({
            "name": sc.name,
            "scores": scores,
            "passed": all(scores.values()),
            "reply": (res.get("reply") or "")[:160],
        })

    check_total = sum(len(r["scores"]) for r in rows)
    check_pass = sum(1 for r in rows for v in r["scores"].values() if v)
    return {
        "scenarios": rows,
        "scenario_pass": sum(1 for r in rows if r["passed"]),
        "scenario_total": len(rows),
        "check_pass": check_pass,
        "check_total": check_total,
        "pass_rate": round(check_pass / check_total * 100, 1) if check_total else 0.0,
    }


# Kanonik senaryo seti — gerçek LLM ile çalıştırıldığında koçun temel davranış
# sözleşmesini (KURAL SIFIR, grounding, sahte-tamamlama, format) ölçer.
DEFAULT_SCENARIOS: List[EvalScenario] = [
    # KURAL SIFIR — soru/niyet/selamlaşmada propose_action OLUŞMAZ
    EvalScenario("soru_propose_yok", "Kart borcum ne kadar?",
                 ["no_action", "no_confidence"], include_cockpit=False),
    EvalScenario("selamlasma_propose_yok", "Merhaba, nasılsın?",
                 ["no_action", "no_fake"], include_cockpit=False),
    EvalScenario("gelecek_niyet_propose_yok", "Yarın kart borcumu kapatacağım",
                 ["no_action"], include_cockpit=False),
    EvalScenario("yatirim_sorusu_propose_yok", "TLY fonunu satmalı mıyım?",
                 ["no_action"], include_cockpit=True),
    # Gerçekleşmiş eylem → propose_action oluşur
    EvalScenario("gerceklesmis_eylem_action", "Bugün 500 TL yemek harcadım nakitten",
                 ["action"], include_cockpit=False),
    EvalScenario("gerceklesmis_kart_action", "240 TL market aldım kartla",
                 ["action"], include_cockpit=False),
    # Analiz → grounded + format + confidence sızmaz
    EvalScenario("analiz_grounded_format", "Durumumu analiz et",
                 ["grounded", "no_confidence"], include_cockpit=True),
    EvalScenario("durum_grounded", "Bu ay nasıl gidiyorum?",
                 ["grounded", "no_fake"], include_cockpit=True),
]


def format_report(report: Dict) -> str:
    """Skor kartını insan-okur metne çevirir (runner çıktısı için)."""
    lines = [
        "=== Koç Eval Skor Kartı ===",
        f"Senaryo: {report['scenario_pass']}/{report['scenario_total']} tam geçti",
        f"Kriter : {report['check_pass']}/{report['check_total']} (%{report['pass_rate']})",
        "",
    ]
    for r in report["scenarios"]:
        mark = "✓" if r["passed"] else "✗"
        detay = " ".join(f"{k}={'✓' if v else '✗'}" for k, v in r["scores"].items())
        lines.append(f"  {mark} {r['name']}: {detay}")
    return "\n".join(lines)
