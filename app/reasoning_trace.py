"""
TraceRecorder - Wave-2 H1G3 ReAct reasoning trace yazimi.

CoachEngine.chat() icinde her ReAct step'inin (rule_check / llm_call /
execute_tool / observation / final_answer) reasoning_traces tablosuna
yazilmasini saglar. Patern: OpenTelemetry start_as_current_span +
LangSmith RunTree sentezi. Lokal SQLite icin async/distributed degil.

Kullanim:
    recorder = TraceRecorder(db, user_id=1)
    try:
        with recorder.step(OperationName.RULE_CHECK, intent="MC4 kontrolu") as s:
            result = check_rule()
            s.observation = f"MC4 tetiklendi: {result}"
            s.inference = "LLM'e baglam ver"

        # Nested step
        first_llm_id = None
        with recorder.step(OperationName.LLM_CALL, intent="Yanit uretimi") as s:
            response = llm.generate(...)
            s.provider_system = "groq"
            s.model_name = "llama-3.3-70b-versatile"
            first_llm_id = s.step_db_id  # nested icin parent referansi

        # Retry ornek (parent = first_llm_id)
        with recorder.step(OperationName.LLM_CALL, parent_step_id=first_llm_id,
                          intent="Retry: tool call zorla") as s:
            response2 = llm.generate(retry_prompt)

        # STEP 6 sonrasi - coach_memory_id backfill
        recorder.set_coach_memory_id(coach_memory.id)
    finally:
        recorder.close()
"""

from __future__ import annotations

import json
import time
import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy.orm import Session

from app.models import OperationName, ReasoningTrace
from app.error_tracking import temizle  # BUG #258: kalici iz maskeli


class _StepProxy:
    """
    with recorder.step(...) as s: bloku icinde yazilan alanlar.

    Block exit'te bu degerler ReasoningTrace record'una kopyalanir.
    Kullanici sadece atama yapar - DB'ye yazim recorder tarafindan halledilir.
    """

    __slots__ = (
        "step_db_id",  # commit sonrasi DB'den gelen id (nested step'te parent referansi icin)
        "observation",
        "inference",
        "action_input_json",
        "confidence_score",
        "provider_system",
        "model_name",
        "usage_input_tokens",
        "usage_output_tokens",
    )

    def __init__(self):
        self.step_db_id = None
        self.observation = None
        self.inference = None
        self.action_input_json = None
        self.confidence_score = None
        self.provider_system = None
        self.model_name = None
        self.usage_input_tokens = None
        self.usage_output_tokens = None

    def set_action_input(self, value: dict):
        """Yardimci: dict -> JSON string (mc_rules_applied paterni)."""
        self.action_input_json = json.dumps(value, ensure_ascii=False, default=float)


class TraceRecorder:
    """
    Bir CoachEngine.chat() cagrisi icin reasoning trace yazimini yonetir.

    Her chat() basinda yeni bir TraceRecorder uretilir, trace_id otomatik
    olusturulur. Her step block'u ReasoningTrace satiri yazar. STEP 6
    sonrasi set_coach_memory_id() ile NULL coach_memory_id'ler backfill
    edilir.
    """

    def __init__(self, db: Session, user_id: int, coach_memory_id: Optional[int] = None):
        """
        Args:
            db: SQLAlchemy session (chat() ile ayni session paylasilir).
            user_id: Trace sahibinin user_id'si.
            coach_memory_id: STEP 6'da yazildiktan sonra set_coach_memory_id()
                ile backfill edilir. Baslangicta None.
        """
        self.db = db
        self.user_id = user_id
        self.coach_memory_id = coach_memory_id
        self.trace_id = str(uuid.uuid4())
        self._step_index = 0
        self._step_ids: list[int] = []  # backfill icin: bu trace'in tum satir id'leri

    @contextmanager
    def step(
        self,
        operation: OperationName,
        intent: Optional[str] = None,
        parent_step_id: Optional[int] = None,
    ) -> Iterator[_StepProxy]:
        """
        Bir reasoning step'ini wrap'leyen context manager.

        with bloku icinde:
        - latency otomatik olculur (perf_counter)
        - exception yakalanirsa error kolonu doldurulur, sonra raise
        - block sonunda DB'ye yazilir, proxy.step_db_id set edilir

        Args:
            operation: OperationName enum (rule_check / llm_call / vs.)
            intent: Bu step'in niyeti (TEXT, opsiyonel).
            parent_step_id: Nested step icin ebeveyn satir id'si. None ise
                en son yazilan step parent olur (otomatik nesting).

        Yields:
            _StepProxy: with bloku icinde alanlar yazilabilir.
        """
        proxy = _StepProxy()
        record = ReasoningTrace(
            user_id=self.user_id,
            trace_id=self.trace_id,
            step_index=self._step_index,
            parent_step_id=parent_step_id,
            coach_memory_id=self.coach_memory_id,
            operation_name=operation,
            intent=intent,
        )
        self._step_index += 1
        start = time.perf_counter()

        try:
            yield proxy
        except Exception as exc:
            # BUG #258: iz kaydi KALICI — istisna metni sir/PII tasiyabilir, maskeden gecer.
            record.error = temizle(f"{type(exc).__name__}: {exc}", max_uzunluk=500)
            raise
        finally:
            record.latency_ms = int((time.perf_counter() - start) * 1000)
            # Proxy alanlari kopyala
            for field in (
                "observation",
                "inference",
                "action_input_json",
                "confidence_score",
                "provider_system",
                "model_name",
                "usage_input_tokens",
                "usage_output_tokens",
            ):
                value = getattr(proxy, field, None)
                if value is not None:
                    setattr(record, field, value)
            self.db.add(record)
            self.db.commit()
            self.db.refresh(record)
            proxy.step_db_id = record.id
            self._step_ids.append(record.id)

    def set_coach_memory_id(self, coach_memory_id: int) -> None:
        """
        STEP 6'da CoachMemory yazildigindan sonra cagrilir.

        Bu trace'in tum NULL coach_memory_id satirlarini backfill eder.
        Idempotent - tekrar cagrilirsa zaten dolu olanlari es gecer.
        """
        if not self._step_ids:
            return
        self.db.query(ReasoningTrace).filter(  # scope-exempt: yalnız BU trace örneğinin kendi yazdığı satır id'leri
            ReasoningTrace.id.in_(self._step_ids),
            ReasoningTrace.coach_memory_id.is_(None),
        ).update(
            {ReasoningTrace.coach_memory_id: coach_memory_id},
            synchronize_session=False,
        )
        self.db.commit()
        self.coach_memory_id = coach_memory_id

    def close(self) -> None:
        """Recorder'i temizle. Su an no-op (db session disardan yonetiliyor)."""
        pass
