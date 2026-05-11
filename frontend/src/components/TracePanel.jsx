import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Shield,
  Sparkles,
  Wrench,
  Eye,
  MessageSquare,
  AlertCircle,
  Loader2,
} from 'lucide-react';

/**
 * "Coach'ın muhakemesi" paneli — bir asistan mesajının altına eklenen
 * collapsible reasoning trace.
 *
 * Tasarım kararları (sektör araştırması):
 * - Default collapsed (asistan arayuzu Extended Thinking + assistant-ui patterni)
 * - Operation type ayrımı: ikon + Türkçe etiket (LangSmith emoji+label
 *   patterni). Renk vurgusu yok — minimal/muted (assistant-ui patterni).
 *   final_answer + error özel durumlar.
 * - Confidence skoru göreceli sinyal olarak gösterilir, mutlak değil
 *   (LandingAI ADE patterni: "ranking and triage signal").
 * - Lazy fetch: panel açılana kadar /trace çağrılmaz; bandwidth + LLM
 *   ortamında defaulted aşırı yük olmasın.
 *
 * Props:
 *   memoryId    — CoachMemory.id, /api/coach/trace/{memoryId} için anahtar
 *   fetchTrace  — (memoryId) => Promise<TraceResponse>, dependency injection
 *                 ile test edilebilirlik (genelde coachApi.trace)
 */
export default function TracePanel({ memoryId, fetchTrace }) {
  const [isOpen, setIsOpen] = useState(false);
  const [trace, setTrace] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleToggle() {
    const next = !isOpen;
    setIsOpen(next);

    // Lazy fetch: sadece ilk acilis sırasında.
    if (next && !trace && !loading) {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchTrace(memoryId);
        setTrace(data);
      } catch (err) {
        // 404 (trace yok / yetkisiz) ya da ag hatasi
        if (err?.status === 404) {
          setError('Bu mesaj için kayıtlı muhakeme yok.');
        } else {
          setError('Muhakeme yüklenemedi. Daha sonra tekrar deneyin.');
        }
      } finally {
        setLoading(false);
      }
    }
  }

  return (
    <div className="mt-2 border-t border-zinc-200 dark:border-zinc-700 pt-2">
      <button
        type="button"
        onClick={handleToggle}
        className="flex items-center gap-1.5 text-xs text-zinc-500 dark:text-zinc-400 hover:text-zinc-700 dark:hover:text-zinc-200 transition-colors"
        aria-expanded={isOpen}
        aria-controls={`trace-panel-${memoryId}`}
        title="Koçun bu cevaba nasıl ulaştığını gör"
      >
        {isOpen ? (
          <ChevronDown className="w-3.5 h-3.5" />
        ) : (
          <ChevronRight className="w-3.5 h-3.5" />
        )}
        <span>Coach'ın muhakemesi</span>
      </button>

      {isOpen && (
        <div
          id={`trace-panel-${memoryId}`}
          className="mt-2 space-y-1.5"
        >
          {loading && (
            <div className="flex items-center gap-2 text-xs text-zinc-500 dark:text-zinc-400 py-2">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>Yükleniyor…</span>
            </div>
          )}

          {error && (
            <div className="text-xs text-zinc-500 dark:text-zinc-400 italic py-1">
              {error}
            </div>
          )}

          {trace && trace.steps.length === 0 && (
            <div className="text-xs text-zinc-500 dark:text-zinc-400 italic py-1">
              Bu mesaj için kayıtlı adım yok.
            </div>
          )}

          {trace && trace.steps.length > 0 && (
            <>
              {trace.steps.map((step) => (
                <TraceStep key={step.id} step={step} />
              ))}
              <div className="text-[10px] text-zinc-400 dark:text-zinc-500 pt-1 font-mono">
                trace_id: {trace.trace_id}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}


// ----- Private sub-components -----

const OPERATION_META = {
  rule_check:    { label: 'Kural kontrolü',   Icon: Shield },
  llm_call:      { label: 'LLM çağrısı',      Icon: Sparkles },
  execute_tool:  { label: 'Araç çalıştırma',  Icon: Wrench },
  observation:   { label: 'Gözlem',           Icon: Eye },
  final_answer:  { label: 'Nihai cevap',      Icon: MessageSquare },
};

function TraceStep({ step }) {
  const hasError = Boolean(step.error);
  const meta = OPERATION_META[step.operation_name] || {
    label: step.operation_name,
    Icon: MessageSquare,
  };
  const Icon = hasError ? AlertCircle : meta.Icon;
  const isFinal = step.operation_name === 'final_answer';

  // Vurgu kuralları: error -> negative, final_answer -> brand, diğerleri muted
  const iconColor = hasError
    ? 'text-negative-500 dark:text-negative-400'
    : isFinal
    ? 'text-brand-500 dark:text-brand-400'
    : 'text-zinc-500 dark:text-zinc-400';

  const labelColor = hasError
    ? 'text-negative-700 dark:text-negative-300'
    : 'text-zinc-700 dark:text-zinc-200';

  const detailsRows = [];
  if (step.intent) detailsRows.push(['Niyet', step.intent]);
  if (step.observation) detailsRows.push(['Gözlem', step.observation]);
  if (step.inference) detailsRows.push(['Çıkarım', step.inference]);
  if (step.error) detailsRows.push(['Hata', step.error]);
  if (step.action_input_json) detailsRows.push(['Araç girdisi', step.action_input_json]);

  const hasDetails = detailsRows.length > 0;
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-md bg-zinc-50 dark:bg-zinc-800/50 px-2 py-1.5 text-xs">
      <button
        type="button"
        onClick={() => hasDetails && setExpanded((v) => !v)}
        className={`w-full flex items-center gap-2 ${hasDetails ? 'cursor-pointer' : 'cursor-default'}`}
        disabled={!hasDetails}
        aria-expanded={hasDetails ? expanded : undefined}
      >
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${iconColor}`} />
        <span className={`font-medium ${labelColor}`}>{meta.label}</span>

        <span className="flex-1" />

        {step.confidence_score != null && isFinal && (
          <ConfidenceBadge score={step.confidence_score} />
        )}

        {step.latency_ms != null && (
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 font-mono">
            {step.latency_ms}ms
          </span>
        )}

        {(step.usage_input_tokens != null || step.usage_output_tokens != null) && (
          <span
            className="text-[10px] text-zinc-400 dark:text-zinc-500 font-mono"
            title="Girdi + çıktı token sayısı"
          >
            {(step.usage_input_tokens || 0) + (step.usage_output_tokens || 0)}t
          </span>
        )}

        {hasDetails && (
          expanded ? (
            <ChevronDown className="w-3 h-3 text-zinc-400" />
          ) : (
            <ChevronRight className="w-3 h-3 text-zinc-400" />
          )
        )}
      </button>

      {hasDetails && expanded && (
        <div className="mt-1.5 ml-5 space-y-0.5">
          {detailsRows.map(([label, value]) => (
            <div key={label} className="text-zinc-600 dark:text-zinc-300">
              <span className="text-zinc-500 dark:text-zinc-400 font-medium">
                {label}:
              </span>{' '}
              <span className="whitespace-pre-wrap break-words">{value}</span>
            </div>
          ))}
          {(step.provider_system || step.model_name) && (
            <div className="text-[10px] text-zinc-400 dark:text-zinc-500 font-mono pt-1">
              {step.provider_system && <span>{step.provider_system}</span>}
              {step.provider_system && step.model_name && <span> · </span>}
              {step.model_name && <span>{step.model_name}</span>}
            </div>
          )}
        </div>
      )}
    </div>
  );
}


function ConfidenceBadge({ score }) {
  // Eşikler: AI Confidence Visualization sektör konvansiyonu
  // (>=0.80 yüksek, 0.50-0.79 orta, <0.50 düşük).
  // Mevcut Tailwind palette token'ları: positive/warn/negative.
  let bg, text, label;
  if (score >= 0.80) {
    bg = 'bg-positive-100 dark:bg-positive-900/30';
    text = 'text-positive-700 dark:text-positive-300';
    label = 'Yüksek';
  } else if (score >= 0.50) {
    bg = 'bg-warn-100 dark:bg-warn-900/30';
    text = 'text-warn-700 dark:text-warn-300';
    label = 'Orta';
  } else {
    bg = 'bg-negative-100 dark:bg-negative-900/30';
    text = 'text-negative-700 dark:text-negative-300';
    label = 'Düşük';
  }

  return (
    <span
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${bg} ${text}`}
      title="Coach'ın kendi kendine verdiği güven skoru. Mutlak güvenilirlik değil, göreceli sinyal — 0.85, 0.60'tan daha güvenli demektir ama %85 doğru anlamına gelmez. Önemli kararlarda destekleyici bilgiyi kontrol et."
    >
      <span>{score.toFixed(2)}</span>
      <span>·</span>
      <span>{label}</span>
    </span>
  );
}
