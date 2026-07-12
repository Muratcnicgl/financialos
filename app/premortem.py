"""
Premortem Engine — Wave-2 H2G3
Klein 1989 prospective hindsight + LLM-tabanli senaryo uretimi.

Murat'in onaylamak uzere oldugu bir aksiyon icin 5 basarisizlik senaryosu uretir.
Her senaryo: gerekce + olasilik etiketi + TL etki + mitigation aksiyonu.

ADR-001 ilkesi: Premortem KARAR VERMEZ, sadece korluk noktalarini acar.
Son karar her zaman Murat'in.

Mimari:
- LLM provider: build_provider() (Groq -> Cerebras -> Gemini -> OpenRouter fallback)
- Output: structured JSON, Pydantic V2 validate
- Parse fail -> 1 retry (strict reminder), sonra hata fail-loud
- Persist: DecisionJournal.premortem_scenarios (JSON Text), premortem_run_at (datetime)

Referanslar:
- Klein, G. (2007) "Performing a Project Premortem", HBR
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coach import LLMProvider, build_provider
from app.models import DecisionJournal, PendingAction

logger = logging.getLogger(__name__)


# ============================================================
# PYDANTIC V2 MODELLER
# ============================================================

ProbabilityLabel = Literal["dusuk", "orta", "yuksek"]


class PremortemScenario(BaseModel):
    """Tek bir basarisizlik senaryosu."""

    id: str = Field(description="Stabil ID: S1..S5")
    title: str = Field(min_length=8, max_length=120)
    probability_label: ProbabilityLabel
    impact_tl: float = Field(
        description="Tahmini TL etki (negatif = zarar, 0.0 = belirsiz)"
    )
    narrative: str = Field(
        min_length=40, max_length=600,
        description="Klein gramer: gecmis kip, 'basarisiz oldu. Sebebi su idi:'",
    )
    mitigation: str = Field(min_length=20, max_length=400)

    @field_validator("narrative")
    @classmethod
    def _check_narrative(cls, v: str) -> str:
        # Yumusak kontrol: gecmis kip prompt seviyesinde zorlanir.
        return v


class PremortemResult(BaseModel):
    """Bir aksiyon icin tam premortem ciktisi."""
    model_config = ConfigDict(protected_namespaces=())

    action_id: int
    scenarios: List[PremortemScenario] = Field(min_length=3, max_length=5)
    provider_used: Optional[str] = None
    model_name: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================
# EXCEPTIONS
# ============================================================


class PremortemError(Exception):
    """Premortem engine bazli hata."""


class PremortemValidationError(PremortemError):
    """LLM ciktisi Pydantic schema'sina uymadi."""


# ============================================================
# PROMPTS
# ============================================================

_SYSTEM_PROMPT = """Sen bir finansal karar destek aracinin Premortem motorusun.

Gorevin: Kullanicinin onaylamak uzere oldugu bir aksiyonun **6 ay sonra basarisiz**
oldugunu HAYAL ET ve neden basarisiz oldugunu ANLATAN 5 senaryo uret.

KRITIK GRAMER KURALI (Klein 1989 prospective hindsight):
- "Bu aksiyon basarisiz OLABILIR" DEME — kosullu kip yasak.
- "Bu aksiyon basarisiz OLDU. Sebebi su idi:" DE — gecmis kip zorunlu.

KURALLAR:
1. 5 senaryo uret. ID'ler: S1, S2, S3, S4, S5.
2. Senaryolar BIRBIRINDEN FARKLI sebeplerle. (Hepsi "kur dustu" olmamali.)
3. Her senaryoda somut TL etki tahmin et. Bilinmiyorsa 0.0 yaz.
4. Her senaryoya BU SENARYOYA OZEL bir mitigation bagla. Genel tavsiye degil.
5. probability_label: "dusuk" / "orta" / "yuksek" — sadece bu uc secenekten biri.
6. Turkce, samimi ama profesyonel ton. Dalkavukluk yok, panik de yok.

ZORUNLU CIKTI FORMATI — sadece JSON, baska hicbir sey yok:
{
  "scenarios": [
    {
      "id": "S1",
      "title": "Kisa baslik",
      "probability_label": "orta",
      "impact_tl": -1500.0,
      "narrative": "Bu aksiyon basarisiz oldu. Sebebi su idi: ...",
      "mitigation": "Bunu onlemek icin ..."
    }
  ]
}"""


def _user_prompt(action_context: dict, cockpit_snapshot: Optional[dict] = None) -> str:
    lines = [
        "AKSIYON BAGLAMI:",
        f"  Tip: {action_context.get('action_type', 'bilinmiyor')}",
        f"  Aciklama: {action_context.get('description', '-')}",
        f"  Tutar: {action_context.get('amount_tl', 0.0)} TL",
        f"  Hedef: {action_context.get('target', '-')}",
    ]
    if action_context.get("rationale"):
        lines.append(f"  Murat'in gerekcesi: {action_context['rationale']}")

    if cockpit_snapshot:
        lines += [
            "",
            "COCKPIT OZETI (mevcut finansal durum):",
            f"  Net deger: {cockpit_snapshot.get('net_worth_tl', 0.0)} TL",
            f"  30g net akis: {cockpit_snapshot.get('cashflow_30d_tl', 0.0)} TL",
            f"  60g net akis: {cockpit_snapshot.get('cashflow_60d_tl', 0.0)} TL",
            # BUG #065 fix (CS-001): yanlış anahtar 'crunch_day' HER ZAMAN '-' döndürüyordu;
            # build_cockpit_snapshot 'lowest_balance_date/tl' + 'crunch_count' üretiyor. Dosyanın
            # en kritik verisi (nakit ne zaman tükenir) LLM'e hiç ulaşmıyordu.
            f"  En dusuk bakiye tarihi: {cockpit_snapshot.get('lowest_balance_date', '-')}",
            f"  En dusuk bakiye: {cockpit_snapshot.get('lowest_balance_tl', 0.0)} TL",
            f"  Nakit kriz gunu sayisi (30g): {cockpit_snapshot.get('crunch_count', 0)}",
        ]

    lines += [
        "",
        "GOREVIN: Bu aksiyonun 6 ay sonra basarisiz oldugunu hayal et.",
        "5 farkli sebep uret. Sadece JSON ile cevap ver.",
    ]
    return "\n".join(lines)


_RETRY_REMINDER = (
    "ONCEKI CEVABIN JSON FORMATINA UYMADI. "
    "Sadece JSON dondur: ```json fence yok, aciklama yok. "
    "Schema'ya tam uy: id, title, probability_label, impact_tl, narrative, mitigation."
)


# ============================================================
# JSON PARSE + VALIDATE
# ============================================================


def _parse_and_validate(raw_text: str) -> List[PremortemScenario]:
    """LLM serbest metnini JSON'a cevirip Pydantic ile validate eder."""
    text = raw_text.strip()
    # Bazi modeller ```json ... ``` blogu donduruyor; fence'i soy.
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:] if lines[0].startswith("```") else lines
        lines = lines[:-1] if lines and lines[-1].startswith("```") else lines
        text = "\n".join(lines).strip()

    payload = json.loads(text)  # JSONDecodeError -> caller yakalar
    raw_list = payload.get("scenarios")
    if not isinstance(raw_list, list):
        raise PremortemValidationError(
            f"'scenarios' alani list degil: {type(raw_list)}"
        )

    scenarios = [PremortemScenario.model_validate(s) for s in raw_list]
    if not (3 <= len(scenarios) <= 5):
        raise PremortemValidationError(
            f"{len(scenarios)} senaryo uretildi; 3-5 olmali."
        )
    return scenarios


# ============================================================
# ANA FONKSİYON
# ============================================================


def generate_premortem(
    action_id: int,
    action_context: dict,
    cockpit_snapshot: Optional[dict] = None,
    provider: Optional[LLMProvider] = None,
) -> PremortemResult:
    """
    Bir aksiyon icin premortem senaryolari uretir.

    Args:
        action_id       : PendingAction.id
        action_context  : {action_type, description, amount_tl, target, rationale?}
        cockpit_snapshot: Opsiyonel finansal durum ozeti (cashflow + net_worth)
        provider        : DI icin; None ise build_provider() cagrilir

    Returns:
        PremortemResult — 3-5 senaryo + provider metadata

    Raises:
        PremortemError  : 2 deneme sonrasi da basarisiz
    """
    if provider is None:
        provider = build_provider()

    base_prompt = _user_prompt(action_context, cockpit_snapshot)
    messages = [{"role": "user", "content": base_prompt}]
    last_error: Optional[Exception] = None

    for attempt in range(2):
        try:
            response = provider.chat(
                system_prompt=_SYSTEM_PROMPT,
                messages=messages,
                tools=[],
            )
            if not response.text or not response.text.strip():
                last_error = PremortemError("LLM bos cevap dondurdu.")
                logger.warning("premortem: bos cevap attempt=%d provider=%s",
                               attempt, response.provider_used)
                continue

            scenarios = _parse_and_validate(response.text)
            return PremortemResult(
                action_id=action_id,
                scenarios=scenarios,
                provider_used=response.provider_used,
                model_name=response.model_name,
            )

        except (json.JSONDecodeError, ValidationError, PremortemValidationError) as e:
            last_error = e
            logger.warning("premortem: parse/validate hatasi attempt=%d hata=%s",
                           attempt, str(e)[:200])
            messages = [
                {"role": "user", "content": base_prompt},
                {"role": "user", "content": _RETRY_REMINDER},
            ]

        except Exception as e:
            last_error = e
            logger.exception("premortem: beklenmedik hata attempt=%d", attempt)

    raise PremortemError(
        f"Premortem 2 denemede basarisiz. "
        f"Son hata: {type(last_error).__name__}: {last_error}"
    )


# ============================================================
# PERSISTENCE — DecisionJournal entegrasyonu
# ============================================================


def persist_premortem(
    session: Session,
    action: PendingAction,
    user_id: int,
    result: PremortemResult,
    snapshot_hash: str = "",
) -> DecisionJournal:
    """
    Premortem sonuclarini DecisionJournal'a yazar.

    Ayni action_id icin tekrar cagrilirsa mevcut kaydi gunceller (idempotent).
    """
    sentinel = f"PendingAction#{action.id}"
    existing = session.execute(
        select(DecisionJournal).where(
            DecisionJournal.user_id == user_id,
            DecisionJournal.decision_text == sentinel,
        )
    ).scalar_one_or_none()

    scenarios_json = json.dumps([s.model_dump() for s in result.scenarios], ensure_ascii=False, default=float)
    now = datetime.now(timezone.utc)

    if existing:
        existing.premortem_scenarios = scenarios_json
        existing.premortem_run_at = now
        existing.cockpit_snapshot_hash = snapshot_hash
        dj = existing
    else:
        dj = DecisionJournal(
            user_id=user_id,
            decision_text=sentinel,
            decision_type=action.action_type,
            predicted_outcome=action.summary or "",
            confidence_at_decision=None,
            mc_rules_applied=json.dumps([]),
            cockpit_snapshot_hash=snapshot_hash,
            premortem_scenarios=scenarios_json,
            premortem_run_at=now,
        )
        session.add(dj)

    session.commit()
    session.refresh(dj)
    return dj


def link_premortem_outcome(
    session: Session,
    pending_action_id: int,
    action_history_id: int,
    success: bool,
    message: str,
    net_worth_delta: Optional[float] = None,
) -> Optional[DecisionJournal]:
    """
    Aksiyon yurutuldukten sonra premortem DJ kaydina outcome yazar.

    Args:
        pending_action_id : Yurutulen PendingAction.id
        action_history_id : Yeni olusan ActionHistory.id — DJ.related_action_id'ye yazilir
        success           : execute_pending_action sonucu
        message           : Handler'in dondurdugu Turkce ozet
        net_worth_delta   : Karar oncesi/sonrasi net deger farki (opsiyonel)

    Returns:
        Guncellenen DJ; premortem cagirilmamis aksiyon icin None.

    Sessiz gec — premortem zorunlu degil (kullanici karar verir, AI aciklar).
    """
    sentinel = f"PendingAction#{pending_action_id}"
    dj = session.execute(
        select(DecisionJournal).where(DecisionJournal.decision_text == sentinel)
    ).scalar_one_or_none()

    if dj is None:
        return None

    now = datetime.now(timezone.utc)
    dj.related_action_id = action_history_id
    dj.actual_outcome = message
    dj.outcome_evaluated_at = now
    dj.outcome_score = 1 if success else -1

    session.commit()
    session.refresh(dj)
    return dj
