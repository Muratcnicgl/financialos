import { useState, useEffect, useCallback } from 'react';
import {
  Activity, MessageSquare, Wallet, Receipt, TrendingUp, ShieldAlert,
  Sun, Moon, Wifi, WifiOff, AlertTriangle, BarChart3, Waves, CreditCard, Target, PiggyBank, LogOut,
} from 'lucide-react';
import { healthApi, authApi } from './api.js';
import Login from './panels/Login.jsx';
import { ToastProvider } from './components/Toast.jsx';
import { useKeyboardShortcuts } from './hooks/useKeyboardShortcuts.js';
import CommandPalette from './components/CommandPalette.jsx';
import HelpModal from './components/HelpModal.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import Cockpit from './panels/Cockpit.jsx';
import Coach from './panels/Coach.jsx';
import Accounts from './panels/Accounts.jsx';
import Transactions from './panels/Transactions.jsx';
import IncomeDebt from './panels/IncomeDebt.jsx';
import RedLines from './panels/RedLines.jsx';
import Reports from './panels/Reports.jsx';
import Cashflow from './panels/Cashflow.jsx';
import DebtStrategy from './panels/DebtStrategy.jsx';
import Goals from './panels/Goals.jsx';
import Budget from './panels/Budget.jsx';

const TABS = [
  { id: 'cockpit',     label: 'Cockpit',         icon: Activity      },
  { id: 'coach',       label: 'Koç',             icon: MessageSquare },
  { id: 'accounts',    label: 'Hesaplar',        icon: Wallet        },
  { id: 'transactions',label: 'İşlemler',        icon: Receipt       },
  { id: 'incomedebt',  label: 'Gelir & Borç',    icon: TrendingUp    },
  { id: 'redlines',    label: 'Kırmızı Çizgiler', icon: ShieldAlert  },
  { id: 'reports',     label: 'Raporlar',         icon: BarChart3    },
  { id: 'cashflow',    label: 'Akış',             icon: Waves        },
  { id: 'debtstrategy', label: 'Borç Stratejisi', icon: CreditCard  },
  { id: 'goals',        label: 'Hedefler',        icon: Target      },
  { id: 'budget',       label: 'Bütçe',           icon: PiggyBank   },
];

function useTheme() {
  const [theme, setTheme] = useState(() => {
    if (typeof window === 'undefined') return 'dark';
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') return saved;
    return 'dark';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') root.classList.add('dark');
    else root.classList.remove('dark');
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggle = () => setTheme(t => (t === 'dark' ? 'light' : 'dark'));
  return [theme, toggle];
}

function useBackendHealth() {
  const [status, setStatus] = useState('checking');
  const [usagePct, setUsagePct] = useState(0);

  useEffect(() => {
    let active = true;
    let interval;

    const check = async () => {
      try {
        await healthApi.check();
        if (active) setStatus('online');
      } catch {
        if (active) setStatus('offline');
      }
    };

    check();
    interval = setInterval(check, 5000);

    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  return { status, usagePct };
}

function formatTodayTR() {
  const d = new Date();
  const months = ['Ocak','Şubat','Mart','Nisan','Mayıs','Haziran','Temmuz','Ağustos','Eylül','Ekim','Kasım','Aralık'];
  const days = ['Pazar','Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi'];
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()} ${days[d.getDay()]}`;
}

export default function App() {
  return (
    <ToastProvider>
      <AuthGate />
    </ToastProvider>
  );
}

// M11 (ADR-033): AUTH_ENABLED açık + token yoksa Login göster; aksi halde uygulama.
function AuthGate() {
  const [phase, setPhase] = useState('checking'); // checking | login | app

  const check = useCallback(async () => {
    try {
      const h = await healthApi.get();
      if (h?.auth_enabled && !authApi.isLoggedIn()) { setPhase('login'); return; }
    } catch { /* backend erişilemezse yine app'i göster (health banner uyarır) */ }
    setPhase('app');
  }, []);

  useEffect(() => { check(); }, [check]);

  if (phase === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-400 text-sm">
        Yükleniyor…
      </div>
    );
  }
  if (phase === 'login') return <Login onAuthed={() => setPhase('app')} />;
  return <AppContent onLogout={async () => { await authApi.logout(); setPhase('login'); }} />;
}

function AppContent({ onLogout }) {
  const [theme, toggleTheme] = useTheme();
  const [activeTab, setActiveTab] = useState('cockpit');
  const { status, usagePct } = useBackendHealth();
  const [showHelp, setShowHelp] = useState(false);
  const [showPalette, setShowPalette] = useState(false);

  useKeyboardShortcuts({
    setActiveTab,
    onHelp: () => setShowHelp(h => !h),
    onPalette: () => setShowPalette(p => !p),
  });

  return (
    <div className="h-dvh flex flex-col overflow-hidden bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100">
      <header className="flex-shrink-0 sticky top-0 z-30 border-b border-zinc-200 dark:border-zinc-800 bg-zinc-50/85 dark:bg-zinc-950/85 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-3">
          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-400 to-brand-600 flex items-center justify-center text-white font-bold shadow-glow-brand">
              ₺
            </div>
            <div className="hidden sm:block">
              <h1 className="font-bold text-base leading-tight">FinancialOS</h1>
              <p className="text-[11px] text-zinc-500 leading-tight">{formatTodayTR()}</p>
            </div>
          </div>

          <div className="flex-1" />

          <div className="flex items-center gap-2 flex-shrink-0">
            <div className="flex items-center gap-1.5">
              {status === 'online' ? (
                <span className="chip chip-positive">
                  <Wifi className="w-3 h-3" /> <span className="hidden sm:inline">Bağlı</span>
                </span>
              ) : status === 'offline' ? (
                <span className="chip chip-negative">
                  <WifiOff className="w-3 h-3" /> <span className="hidden sm:inline">Backend kapalı</span>
                </span>
              ) : (
                <span className="chip">
                  <span className="w-2 h-2 rounded-full bg-zinc-400 animate-pulse" />
                  <span className="hidden sm:inline">Kontrol...</span>
                </span>
              )}
            </div>

            <span className={`chip font-numeric ${
              usagePct > 80 ? 'chip-negative' :
              usagePct > 50 ? 'chip-warn' :
              ''
            }`}>
              {usagePct}%
            </span>

            <button
              onClick={toggleTheme}
              className="btn btn-ghost btn-icon !p-2"
              title={theme === 'dark' ? 'Açık tema' : 'Koyu tema'}
            >
              {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            {onLogout && authApi.isLoggedIn() && (
              <button
                onClick={onLogout}
                className="btn btn-ghost btn-icon !p-2"
                title="Çıkış yap"
              >
                <LogOut className="w-4 h-4" />
              </button>
            )}
          </div>
        </div>

        <nav className="border-t border-zinc-200/60 dark:border-zinc-800/60">
          <div className="max-w-6xl mx-auto px-2 overflow-x-auto">
            <div className="flex gap-1">
              {TABS.map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id)}
                  className={`flex items-center gap-1.5 px-3 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                    activeTab === id
                      ? 'text-brand-600 dark:text-brand-400 border-brand-500'
                      : 'text-zinc-600 dark:text-zinc-400 border-transparent hover:text-zinc-900 dark:hover:text-zinc-200'
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </button>
              ))}
            </div>
          </div>
        </nav>
      </header>

      {status === 'offline' && (
        <div className="flex-shrink-0 bg-negative-50 dark:bg-negative-950/30 border-b border-negative-200 dark:border-negative-900">
          <div className="max-w-6xl mx-auto px-4 py-2 flex items-center gap-2 text-sm">
            <AlertTriangle className="w-4 h-4 text-negative-600 dark:text-negative-400 flex-shrink-0" />
            <span className="text-negative-700 dark:text-negative-300">
              Backend ile bağlantı yok. <code className="font-numeric text-xs px-1.5 py-0.5 rounded bg-negative-100 dark:bg-negative-950 ml-1">uvicorn app.main:app --reload --port 8000</code> komutunu kontrol et.
            </span>
          </div>
        </div>
      )}

      <main className="flex-1 overflow-y-auto overflow-x-hidden">
        <div className={`max-w-6xl mx-auto px-4 ${
          activeTab === 'coach' ? 'h-full flex flex-col pt-4' : 'py-6'
        }`}>
          {/* FE-003: her panel hata sınırıyla sarılı — biri çökerse tüm uygulama beyaz ekrana
              düşmesin. resetKey=activeTab → sekme değişince sınır sıfırlanır. */}
          <ErrorBoundary resetKey={activeTab}>
            {activeTab === 'cockpit' && <Cockpit setActiveTab={setActiveTab} />}
            {activeTab === 'coach' && <Coach />}
            {activeTab === 'accounts' && <Accounts />}
            {activeTab === 'transactions' && <Transactions />}
            {activeTab === 'incomedebt' && <IncomeDebt />}
            {activeTab === 'redlines' && <RedLines />}
            {activeTab === 'reports' && <Reports />}
            {activeTab === 'cashflow' && <Cashflow />}
            {activeTab === 'debtstrategy' && <DebtStrategy />}
            {activeTab === 'goals' && <Goals />}
            {activeTab === 'budget' && <Budget />}
          </ErrorBoundary>
        </div>
      </main>

      <footer className="flex-shrink-0 max-w-6xl mx-auto px-4 py-3 text-center text-xs text-zinc-500">
        FinancialOS · 160 IQ stratejist finansal koç · v0.1.0
        {' · '}
        <a href="/api/user/export" download="financialos-verim.json"
           className="underline hover:text-zinc-700 dark:hover:text-zinc-300">
          Verimi indir
        </a>
      </footer>

      {showPalette && (
        <CommandPalette onClose={() => setShowPalette(false)} setActiveTab={setActiveTab} />
      )}
      {showHelp && (
        <HelpModal onClose={() => setShowHelp(false)} />
      )}
    </div>
  );
}