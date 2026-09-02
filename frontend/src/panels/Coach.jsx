import { useState, useEffect, useRef, useCallback, Component } from 'react';
import {
  Send, Loader2, RotateCcw, MessageSquare, AlertTriangle, User, Sparkles, RefreshCw,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { coachApi, cockpitApi, userApi } from '../api.js';
import { useToast } from '../components/Toast.jsx';
import PendingActions from '../components/PendingActions.jsx';
import EmptyState from '../components/EmptyState.jsx';
import TracePanel from '../components/TracePanel.jsx';

// Llama'nın köşeli parantez başlık formatını Markdown'a çevirir
// [1. STRATEJİK ANALİZ] → ## 1. STRATEJİK ANALİZ
// [A. Seçenek] → ### A. Seçenek
function preprocessMarkdown(text) {
  if (!text) return text;
  return text
    // Köşeli parantez formatları (Llama eski alışkanlığı)
    .replace(/\[(\d+\.\s[^\]]+)\]/g, '## $1')
    .replace(/\[([A-Z]\.\s[^\]]+)\]/g, '### $1')
    // BUG #050: Llama kural 13'ü tam benimsemediğinde fallback regex
    // "A. Seçenek:" veya "A. Seçenek (" → ### A. Seçenek...
    .replace(/^([A-Z])\.\s+Seçenek([:\s(])/gm, '### $1. Seçenek$2')
    // "1. STRATEJİK ANALİZ" gibi tüm büyük harf başlıklar (min 3 büyük harf) → ##
    .replace(/^(\d+)\.\s+([A-ZÇĞİÖŞÜ][A-ZÇĞİÖŞÜ\s]{2,})$/gm, '## $1. $2');
}

// Tailwind utility tabanlı markdown bileşenleri (@tailwindcss/typography gerektirmez)
const mdComponents = {
  h1: ({ children }) => <h1 className="text-base font-bold mt-3 mb-1">{children}</h1>,
  h2: ({ children }) => <h2 className="text-sm font-semibold mt-3 mb-1 text-brand-700 dark:text-brand-300 border-b border-zinc-200 dark:border-zinc-700 pb-0.5">{children}</h2>,
  h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-0.5">{children}</h3>,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  em: ({ children }) => <em className="italic">{children}</em>,
  ul: ({ children }) => <ul className="list-disc pl-4 space-y-0.5 my-1">{children}</ul>,
  ol: ({ children }) => <ol className="list-decimal pl-4 space-y-0.5 my-1">{children}</ol>,
  li: ({ children }) => <li className="text-sm leading-snug">{children}</li>,
  p: ({ children }) => <p className="text-sm leading-relaxed mb-1 last:mb-0">{children}</p>,
  code: ({ children }) => <code className="bg-zinc-200 dark:bg-zinc-700 rounded px-1 text-xs font-mono">{children}</code>,
};

/**
 * Coach — Koc ile sohbet paneli.
 *
 * BUG #010 fix (2 May 2026):
 *   - handleActionResolved try-catch ile saritildi (3 ayri korumali blok)
 *   - ErrorBoundary ile sayfa kilitlenmesi engellendi
 *   - onActionResolved callback'i guvenli hale getirildi (parent hatasi Coach'u dusurmez)
 *   - summary parametresi tipinden bagimsiz hale getirildi
 *
 * BUG #018 fix (2 May 2026):
 *   - Backend artik akilli placeholder donduruyor ("(bos cevap)" yerine
 *     "Onayinizi bekliyorum" gibi). Frontend fallback'i da nazik metin oldu.
 *
 * BUG #017 fix (2 May 2026):
 *   - PendingActions component'i a.id ?? a.action_id ile iki kaynak destekler.
 *     Bu dosya bu konuda dogrudan rol almıyor, ama gecmis kayitlardaki
 *     action.action_id'yi temizleme isleminde dogru aksiyon id'sini bulur.
 */

// ============================================================
// ERROR BOUNDARY — siyah ekrani onler
// ============================================================

class CoachErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    // eslint-disable-next-line no-console
    console.error('[Coach ErrorBoundary]', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex-1 flex flex-col items-center justify-center px-6 animate-fade-in">
          <div className="w-12 h-12 rounded-xl bg-negative-100 dark:bg-negative-900/30 flex items-center justify-center mb-4">
            <AlertTriangle className="w-6 h-6 text-negative-600 dark:text-negative-400" />
          </div>
          <h3 className="font-semibold text-lg mb-2">Koç paneli geçici bir hata yaşadı</h3>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 max-w-md text-center mb-4">
            Sayfa kilitlendi ama veriniz güvende. Aşağıdaki butona basarak paneli yenileyebilirsiniz.
          </p>
          {this.state.error && (
            <pre className="text-xs text-zinc-500 max-w-md text-center mb-4 font-mono break-all">
              {String(this.state.error?.message || this.state.error)}
            </pre>
          )}
          <button
            onClick={this.handleReset}
            className="btn btn-primary"
          >
            <RefreshCw className="w-4 h-4" />
            Paneli yenile
          </button>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-3">
            Tarayıcıyı F5 ile de yenileyebilirsiniz, veriler kaybolmaz.
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}

// ============================================================
// HELPERS
// ============================================================

/**
 * BUG #011 fix: Backend bazen 'created_at', bazen 'timestamp' donduruyordu.
 * Esnek okuma + gecersiz tarihte null donus (Invalid Date sorununu kokunden cozer).
 */
function parseHistoryDate(item) {
  const raw = item?.created_at ?? item?.timestamp;
  if (!raw) return null;
  try {
    // FE-017: backend UTC-naive datetime ('Z'/offset suffix'siz) gönderirse `new Date` bunu
    // LOCAL sanıp Türkiye'de 3 saat kaydırır. Suffix yoksa 'Z' ekle (UTC olarak yorumla) —
    // frontend/PROJE.md'nin uyardığı bug sınıfı; tz'li string'e dokunmaz.
    const s = String(raw);
    const hasTz = s.endsWith('Z') || /[+-]\d{2}:?\d{2}$/.test(s);
    const d = new Date(hasTz ? s : s + 'Z');
    if (isNaN(d.getTime())) return null;
    return d;
  } catch {
    return null;
  }
}

// ============================================================
// COACH (icerik) — ErrorBoundary ile saritlanir
// ============================================================

function CoachInner({ onActionResolved }) {
  const toast = useToast();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [usage, setUsage] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState(null);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  // BUG #231 (D10): koça giden verinin gerçek kapsamı rıza metninde eksik beyan edilmişti.
  // Sürüm v3'e çıktı; ESKİ sürüme onay vermiş kullanıcı yeni kapsamı onaylamış sayılmaz.
  const [kvkkDurum, setKvkkDurum] = useState(null);
  const [kvkkOnaylaniyor, setKvkkOnaylaniyor] = useState(false);

  const scrollRef = useRef(null);
  const textareaRef = useRef(null);

  // ============================================================
  // GECMISI YUKLE (sayfa acilisi)
  // ============================================================

  // BUG #231: rıza sürümü durumu — hata olursa panel çalışmaya devam eder (banner çıkmaz).
  useEffect(() => {
    let mounted = true;
    userApi.kvkkDurum()
      .then((d) => { if (mounted) setKvkkDurum(d); })
      .catch(() => {});
    return () => { mounted = false; };
  }, []);

  useEffect(() => {
    let mounted = true;
    Promise.all([coachApi.history(50), cockpitApi.get().catch(() => null)])
      .then(([items, cockpit]) => {
        if (!mounted) return;
        const accounts = cockpit?.accounts || [];
        const msgs = (items || []).map((h) => ({
          role: h.role === 'user' ? 'user' : 'coach',
          text: h.content,
          ts: parseHistoryDate(h),
          actions: h.actions || [],  // BUG #046: history'deki pending aksiyonlar
          accounts,                  // hesap adı çevirisi için
          coachMemoryId: h.id ?? null,
        }));
        setMessages(msgs);
        setHistoryLoaded(true);
      })
      .catch(() => {
        if (mounted) setHistoryLoaded(true);
      });

    coachApi.usage().then((u) => { if (mounted) setUsage(u); }).catch(() => {});

    return () => { mounted = false; };
  }, []);

  // ============================================================
  // OTOMATIK SCROLL
  // ============================================================

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, sending]);

  // ============================================================
  // MESAJ GONDER
  // ============================================================

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg = { role: 'user', text, ts: new Date(), actions: [] };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setSending(true);
    setError(null);

    try {
      const res = await coachApi.chat(text);
      const coachMsg = {
        role: 'coach',
        // BUG #018 fix: Backend artik akilli placeholder donduruyor.
        // Yine de guvenlik icin nazik bir fallback (eski "(bos cevap)" idi).
        text: res.reply || 'Koç cevap vermedi.',
        actions: res.proposed_actions || [],
        accounts: res.cockpit_snapshot?.accounts || [],
        ts: new Date(),
        coachMemoryId: res.coach_memory_id ?? null,
      };
      setMessages((prev) => [...prev, coachMsg]);
      if (res.usage) setUsage(res.usage);

      // Aksiyon onerildiyse toast info — koruma altinda
      if (res.proposed_actions && res.proposed_actions.length > 0) {
        try {
          toast.info(
            `${res.proposed_actions.length} aksiyon önerildi`,
            { detail: 'Onayınız bekleniyor.' }
          );
        } catch (toastErr) {
          // eslint-disable-next-line no-console
          console.warn('[Coach] Toast info hatasi (gormezden geliniyor):', toastErr);
        }
      }
    } catch (e) {
      const msg = e?.message || 'Koç yanıt vermedi';
      setError(msg);
      try {
        toast.error('Koç yanıt vermedi', { detail: msg });
      } catch (toastErr) {
        // eslint-disable-next-line no-console
        console.warn('[Coach] Toast error hatasi (gormezden geliniyor):', toastErr);
      }
    } finally {
      setSending(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  }, [input, sending, toast]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ============================================================
  // SOHBETI SIFIRLA
  // ============================================================

  const handleReset = async () => {
    const ok = window.confirm('Tüm sohbet geçmişi silinecek. Devam edilsin mi?');
    if (!ok) return;
    setResetting(true);
    try {
      await coachApi.reset();
      setMessages([]);
      setError(null);
      try {
        toast.success('Sohbet sıfırlandı');
      } catch (toastErr) {
        // eslint-disable-next-line no-console
        console.warn('[Coach] Toast hatasi (gormezden geliniyor):', toastErr);
      }
    } catch (e) {
      const msg = e?.message || 'Sıfırlama başarısız';
      setError(msg);
      try {
        toast.error('Sıfırlama başarısız', { detail: msg });
      } catch (toastErr) {
        // eslint-disable-next-line no-console
        console.warn('[Coach] Toast hatasi (gormezden geliniyor):', toastErr);
      }
    } finally {
      setResetting(false);
    }
  };

  // ============================================================
  // AKSIYON ONAY/RED — BUG #010 FIX
  //
  // 3 katmanli koruma:
  //   (1) State guncelleme - try-catch
  //   (2) Toast cagrisi - try-catch
  //   (3) Parent callback - try-catch
  //
  // Herhangi bir katman patlasa diger katmanlar calisir, panel kilitlenmez.
  // ============================================================

  const handleActionResolved = (actionId, status, summary) => {
    // (1) State guncelleme: bu action'i mesajlardan temizle
    // BUG #017 ile uyumlu: hem a.id hem a.action_id kontrolu yapiliyor
    try {
      setMessages((prev) => prev.map((m) => ({
        ...m,
        actions: (m.actions || []).filter((a) => {
          const aid = a?.id ?? a?.action_id;
          return aid !== actionId;
        }),
      })));
    } catch (stateErr) {
      // eslint-disable-next-line no-console
      console.error('[Coach] handleActionResolved state guncelleme hatasi:', stateErr);
    }

    // (2) Toast bildirim — summary tipini stringe normalize et
    let summaryText = '';
    try {
      if (typeof summary === 'string') {
        summaryText = summary;
      } else if (summary && typeof summary === 'object') {
        summaryText = summary.message || summary.detail || JSON.stringify(summary);
      } else if (summary != null) {
        summaryText = String(summary);
      }
    } catch {
      summaryText = '';
    }

    try {
      if (status === 'approved' || status === 'executed') {
        toast.success('Aksiyon uygulandı', {
          detail: summaryText || `Aksiyon #${actionId} onaylandı ve uygulandı.`,
        });
      } else if (status === 'rejected') {
        toast.info('Aksiyon reddedildi', {
          detail: summaryText || `Aksiyon #${actionId} iptal edildi.`,
        });
      } else if (status === 'failed' || status === 'error') {
        toast.error('Aksiyon başarısız', {
          detail: summaryText || `Aksiyon #${actionId} uygulanamadı.`,
        });
      }
    } catch (toastErr) {
      // eslint-disable-next-line no-console
      console.warn('[Coach] Toast cagri hatasi (gormezden geliniyor):', toastErr);
    }

    // (3) Parent callback — Cockpit refresh tetikler, hata Coach'u dusurmez
    try {
      onActionResolved?.(actionId, status);
    } catch (parentErr) {
      // eslint-disable-next-line no-console
      console.error('[Coach] Parent onActionResolved hatasi (panel acik kaliyor):', parentErr);
    }
  };

  // ============================================================
  // RENDER
  // ============================================================

  const usageWarn = usage && usage.percentage >= 80;
  const usageBlock = usage && usage.block;

  // KISA VIEWPORT (telefon landscape): panel yuksekligi 236px'e duser ve ipucu seridi +
  // baslik + yazi alani hepsini yer; mesaj listesi 32px'e COKUYORDU (olculdu:
  // mobil-landscape tanisi). Kisa viewport'ta panel butunuyle kaydirilir, birincil icerik
  // ezilmez; ayrica liste bir tabanin (8rem) altina inemez, yazi alani da tavanlanir.
  return (
    <div className="flex-1 flex flex-col overflow-hidden [@media(max-height:500px)]:overflow-y-auto animate-fade-in">
      {/* ===== UST: BASLIK + RESET ===== */}
      <div className="flex items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-9 h-9 rounded-lg bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center flex-shrink-0">
            <Sparkles className="w-5 h-5 text-brand-600 dark:text-brand-400" />
          </div>
          <div className="min-w-0">
            <h2 className="font-semibold">Stratejist Koç</h2>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Cockpit'i biliyor · MC kurallarına saygılı · Saf Türkçe
            </p>
          </div>
        </div>
        <button
          onClick={handleReset}
          disabled={resetting || messages.length === 0}
          className="btn btn-ghost !text-xs flex-shrink-0"
          title="Yeni sohbet (geçmişi sıfırla)"
        >
          {resetting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">Yeni sohbet</span>
        </button>
      </div>

      {/* ===== RIZA TAZELEME BANTI (BUG #231 / D10) =====
          Rıza metninin KAPSAMI değişti (koça giden verinin gerçek listesi). Eski sürüme
          verilmiş onay yeni kapsamı kapsamaz; sürümü yükseltip susmak "belgede düzelttik"
          olurdu (L8). Kullanıcı okumadan onaylamak zorunda değil — koç yine çalışır,
          bant kalır. */}
      {kvkkDurum?.yeniden_onay_gerekli && (
        <div className="card p-3 mb-3 border-warn-300 dark:border-warn-700/50 bg-warn-50 dark:bg-warn-950/30">
          <div className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 text-warn-600 dark:text-warn-400 flex-shrink-0" />
            <span className="text-warn-700 dark:text-warn-300 flex-1">
              Gizlilik metni güncellendi: koça <strong>hangi verinin</strong> gittiği artık
              tam olarak yazıyor (işlem açıklamaların ve kişi adları dahil).{' '}
              <a href="/api/legal/kvkk" target="_blank" rel="noreferrer" className="underline">
                Metni oku
              </a>
            </span>
            <button
              type="button"
              disabled={kvkkOnaylaniyor}
              onClick={async () => {
                setKvkkOnaylaniyor(true);
                try {
                  const d = await userApi.kvkkTazele();
                  setKvkkDurum({ ...kvkkDurum, ...d });
                } catch {
                  setKvkkOnaylaniyor(false);
                }
              }}
              className="btn-secondary text-xs min-h-[44px] sm:min-h-0 sm:py-1.5 px-3 whitespace-nowrap"
            >
              {kvkkOnaylaniyor ? 'Kaydediliyor…' : 'Okudum, onaylıyorum'}
            </button>
          </div>
        </div>
      )}

      {/* ===== USAGE UYARI BANTI ===== */}
      {usageBlock && (
        <div className="card p-3 mb-3 border-negative-300 dark:border-negative-700/50 bg-negative-50 dark:bg-negative-950/30">
          <div className="flex items-center gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 text-negative-600 dark:text-negative-400 flex-shrink-0" />
            <span className="text-negative-700 dark:text-negative-300">
              {/* BUG #234 (D14): bu bant artık gerçekten görünebiliyor (sayaç ölçülüyor).
                  Sayı PAYLAŞILAN kapasitedir — kullanıcı kendi kullanımı sanmasın; sağlayıcı
                  adı da yazılmaz (iç yapılandırma son kullanıcıya ifşa edilmez, BUG #188). */}
              Koç bugünlük kapasitesini doldurdu. Yarın tekrar dene — paneller ve hesaplamalar
              çalışmaya devam ediyor.
            </span>
          </div>
        </div>
      )}
      {usageWarn && !usageBlock && (
        <div className="card p-3 mb-3 border-warn-300 dark:border-warn-700/50 bg-warn-50 dark:bg-warn-950/30">
          <div className="flex items-center gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 text-warn-600 dark:text-warn-400 flex-shrink-0" />
            <span className="text-warn-700 dark:text-warn-300">
              Koç kapasitesinin %{usage.percentage.toFixed(0)}'i doldu (paylaşılan günlük
              kapasite). Bugün dikkatli kullan.
            </span>
          </div>
        </div>
      )}

      {/* ===== MESAJ LISTESI ===== */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto card p-4 space-y-4 [@media(max-height:500px)]:min-h-[8rem]"
      >
        {!historyLoaded ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="w-6 h-6 animate-spin text-zinc-500 dark:text-zinc-400" />
          </div>
        ) : messages.length === 0 ? (
          <EmptyState
              fullHeight
              icon={MessageSquare}
              title="Henüz mesaj yok"
              description="Stratejik bir analiz iste, bir aksiyon bildir veya bir soru sor."
            >
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-md">
                {[
                  'Bugün durumumu kapsamlı analiz et',
                  'Kart borcunu nasıl kapatmalıyım?',
                  'Bu ay nakit akışım nasıl gidecek?',
                  'TLY satışım ne kadar getirir?',
                ].map((s) => (
                  <button
                    key={s}
                    onClick={() => setInput(s)}
                    className="text-xs text-left p-3 min-h-[44px] card hover:border-brand-300 dark:hover:border-brand-700 transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </EmptyState>
        ) : (
          <>
            {messages.map((m, i) => (
              <Message
                key={i}
                message={m}
                onActionResolved={handleActionResolved}
              />
            ))}
            {sending && <CoachTypingIndicator />}
          </>
        )}
      </div>

      {/* ===== HATA BANT ===== */}
      {error && (
        <div className="card p-3 mt-3 border-negative-300 dark:border-negative-700/50 bg-negative-50 dark:bg-negative-950/30">
          <div className="flex items-center gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 text-negative-600 dark:text-negative-400 flex-shrink-0" />
            <span className="text-negative-700 dark:text-negative-300">{error}</span>
          </div>
        </div>
      )}

      {/* ===== INPUT ===== */}
      <div className="mt-3 flex items-end gap-2 flex-shrink-0 sticky bottom-0 pb-[env(safe-area-inset-bottom)]">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Bir şey sor veya bir aksiyon bildir... (Enter: gönder · Shift+Enter: satır)"
          rows={2}
          disabled={sending || usageBlock}
          className="input resize-none font-sans [@media(max-height:500px)]:max-h-16"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || sending || usageBlock}
          className="btn btn-primary !py-3 flex-shrink-0"
          title="Gönder (Enter)"
        >
          {sending ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
        </button>
      </div>
      {/* P4 (H13): "yatırım tavsiyesi değildir" uyarısı yalnız sözleşmede değil, koçun
          KULLANILDIĞI yerde görünür olmalı — kullanıcı metni orada okur. */}
      <p className="mt-2 text-[11px] leading-snug text-zinc-500">
        Koç yatırım/finans tavsiyesi vermez; ürettiği metin hatalı olabilir. Sayısal
        hesaplar kural motorundan gelir, kararların sorumluluğu sana aittir.{' '}
        <a href="/api/legal/kullanim-sartlari" target="_blank" rel="noreferrer"
          className="underline hover:text-zinc-500 dark:hover:text-zinc-400">Kullanım şartları</a>
      </p>
      {/* BUG #231 (D10): aktarımın KAPSAMI, aktarımın YAPILDIĞI yerde yazmalı — kullanıcı
          rıza metnini kayıtta bir kez okur, mesajı burada yazar. */}
      <p className="mt-1 text-[11px] leading-snug text-zinc-500">
        Mesaj gönderdiğinde hesap adların, <strong>son işlemlerin (yazdığın açıklamalar
        dahil)</strong> ve alacak/borç kayıtlarındaki <strong>kişi adları</strong> yapay
        zekâ sağlayıcısına gider (yurt dışı olabilir).{' '}
        <a href="/api/legal/veri-isleyenler" target="_blank" rel="noreferrer"
          className="underline hover:text-zinc-500 dark:hover:text-zinc-400">Neler gönderiliyor?</a>
      </p>
    </div>
  );
}

// ============================================================
// ANA EXPORT — ErrorBoundary ile sarit
// ============================================================

export default function Coach({ onActionResolved }) {
  return (
    <CoachErrorBoundary>
      <CoachInner onActionResolved={onActionResolved} />
    </CoachErrorBoundary>
  );
}

// ============================================================
// MESSAGE — bir mesaj balonu
// ============================================================

function Message({ message, onActionResolved }) {
  const isUser = message.role === 'user';
  const ts = message.ts;
  const time = (ts instanceof Date && !isNaN(ts.getTime()))
    ? ts.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} animate-slide-up`}>
      {/* Avatar */}
      <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${
        isUser
          ? 'bg-zinc-200 dark:bg-zinc-700'
          : 'bg-brand-100 dark:bg-brand-900/30'
      }`}>
        {isUser
          ? <User className="w-4 h-4 text-zinc-600 dark:text-zinc-300" />
          : <Sparkles className="w-4 h-4 text-brand-600 dark:text-brand-400" />
        }
      </div>

      {/* Mesaj icerigi */}
      <div className={`flex-1 min-w-0 ${isUser ? 'flex flex-col items-end' : ''}`}>
        <div className={`max-w-[90%] rounded-xl px-4 py-3 ${
          isUser
            ? 'bg-brand-600 text-white'
            : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100'
        }`}>
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap leading-relaxed break-words">
              {message.text}
            </p>
          ) : (
            <div className="text-sm space-y-0.5 break-words">
              <ReactMarkdown components={mdComponents}>
                {preprocessMarkdown(message.text)}
              </ReactMarkdown>
            </div>
          )}
        </div>
        {time && (
          <p className="text-[10px] text-zinc-500 dark:text-zinc-400 mt-1 px-1">{time}</p>
        )}

        {/* Propose actions */}
        {!isUser && message.actions && message.actions.length > 0 && (
          <div className="mt-3 w-full sm:max-w-[90%]">
            <PendingActions
              actions={message.actions}
              onResolved={onActionResolved}
              accounts={message.accounts}
            />
          </div>
        )}

        {/* Reasoning trace — lazy, collapsed by default */}
        {!isUser && message.coachMemoryId != null && (
          <TracePanel
            memoryId={message.coachMemoryId}
            fetchTrace={coachApi.trace}
          />
        )}
      </div>
    </div>
  );
}

// ============================================================
// COACH TYPING INDICATOR
// ============================================================

function CoachTypingIndicator() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="w-8 h-8 rounded-full bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center flex-shrink-0">
        <Sparkles className="w-4 h-4 text-brand-600 dark:text-brand-400" />
      </div>
      <div className="bg-zinc-100 dark:bg-zinc-800 rounded-xl px-4 py-3 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-500 animate-pulse" style={{ animationDelay: '0ms' }} />
        <span className="w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-500 animate-pulse" style={{ animationDelay: '150ms' }} />
        <span className="w-2 h-2 rounded-full bg-zinc-400 dark:bg-zinc-500 animate-pulse" style={{ animationDelay: '300ms' }} />
      </div>
    </div>
  );
}

