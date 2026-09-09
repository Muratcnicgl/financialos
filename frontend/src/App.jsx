import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  Sun, Moon, WifiOff, AlertTriangle, LogOut,
} from 'lucide-react';
import { healthApi, authApi, coachApi, consumeOAuthRedirect, getResetTokenFromUrl, getJoinTokenFromUrl,
  workspaceApi, getActiveWorkspaceId, setActiveWorkspaceId } from './api.js';
import Login from './panels/Login.jsx';
import Workspace, { WorkspaceJoin } from './panels/Workspace.jsx';
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
import Hesap from './panels/Hesap.jsx';  // P4.4 (BUG #215/#216): KVKK haklari arayuzde
import FeedbackWidget from './components/FeedbackWidget.jsx';  // FEAT-033
// Öğretici sistem: içerik `lib/ogretici.js`'te tek kaynak, bu üç bileşen yalnız çizer.
import Ipucu from './components/Ipucu.jsx';
import OgreticiSihirbaz from './components/OgreticiSihirbaz.jsx';
import YardimKosesi from './components/YardimKosesi.jsx';
import { onboardingApi } from './api.js';
// Sekme listesi burada DEĞİL: üç yerde ayrı yazılıydı ve ayrışmıştı (lib/sekmeler.js).
import { gorunurSekmeler, sekmeEtiketi, kisayolSirasi } from './lib/sekmeler.js';
import { useGorunumModu } from './hooks/useGorunumModu.js';
import GorunumSecici from './components/GorunumSecici.jsx';

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
  // FE-012 (5 Eyl 2026): BAŞLANGIÇ DEĞERİ ARTIK `null`, 0 DEĞİL.
  // `setUsagePct` hiçbir yerde çağrılmıyordu: state 0'da doğuyor ve orada kalıyordu.
  // Sonuç, başlıkta HER KULLANICIYA kalıcı olarak "0%" gösteren bir rozet — canlı bir
  // ölçüm gibi duran, aslında sabit bir sayı. Renk mantığı (>%80 kırmızı, >%50 sarı)
  // hiçbir zaman tetiklenemiyordu. `null` bilinçli: ölçüm YOKSA rozet HİÇ çizilmez,
  // çünkü bilinmeyen sıfır değildir (L45) ve sıfır göstermek uydurmaktır.
  const [usagePct, setUsagePct] = useState(null);

  useEffect(() => {
    let active = true;
    let interval;
    let kullanimAralik;

    const check = async () => {
      try {
        await healthApi.check();
        if (active) setStatus('online');
      } catch {
        if (active) setStatus('offline');
      }
    };

    // FE-012: rozetin verisi ZATEN VARDI ve bağlanmamıştı. `/api/coach/usage` ucu
    // `today_count` / `daily_limit` / `percentage` döner ve kendi docstring'i
    // "Cockpit panelinin üst köşesindeki 'API kullanım: %42' rozetini bundan çekecek"
    // diyor — yani sözleşme yazılıydı, çağıran yoktu.
    // Kota YAVAŞ değişir: sağlık 5 sn'de bir yoklanır, bu 60 sn'de bir. Hata olursa
    // SESSİZ kalınır ve son bilinen değer korunur; rozeti "0%"a düşürmek, kesintiyi
    // "kullanım yok" diye göstermek olurdu.
    const kullanimOku = async () => {
      try {
        const u = await coachApi.usage();
        if (active && typeof u?.percentage === 'number') {
          setUsagePct(Math.round(u.percentage));
        }
      } catch {
        /* sessiz: rozet son bilinen değeri korur, uydurmaz */
      }
    };

    // PERF-008 (5 Eyl 2026): yoklama SEKME GÖRÜNÜRKEN yapılır.
    // Eskiden koşulsuz `setInterval(check, 5000)` vardı: arka plana atılmış bir sekme
    // saatte 720 istek üretiyordu ve o isteklerin hiçbirinin bakan bir gözü yoktu.
    // Mobil/PWA hedefi olan bir üründe bu doğrudan pil ve veri demek. Aralık DEĞİŞMEDİ
    // (görünürken hâlâ 5 sn — tepkiselliği düşürmek ayrı bir karar); yalnız görünmezken
    // duruyor ve sekme geri geldiğinde ANINDA bir ölçüm yapılıyor, böylece kullanıcı
    // bayat bir "çevrimdışı" rozetiyle karşılaşmıyor.
    const gorunur = () =>
      typeof document === 'undefined' || document.visibilityState !== 'hidden';

    const basla = () => {
      if (interval) return;
      interval = setInterval(check, 5000);
      kullanimAralik = setInterval(kullanimOku, 60000);
    };
    const dur = () => {
      clearInterval(interval);
      clearInterval(kullanimAralik);
      interval = null;
      kullanimAralik = null;
    };

    const gorunurlukDegisti = () => {
      if (gorunur()) {
        check();          // sekme geri geldi: bekletmeden ölç
        kullanimOku();
        basla();
      } else {
        dur();
      }
    };

    check();
    kullanimOku();
    if (gorunur()) basla();
    document.addEventListener('visibilitychange', gorunurlukDegisti);

    return () => {
      active = false;
      document.removeEventListener('visibilitychange', gorunurlukDegisti);
      dur();
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
  const [phase, setPhase] = useState('checking'); // checking | login | app | join
  const [oauthError, setOauthError] = useState(null);
  const [resetToken, setResetToken] = useState(null); // M18: şifre sıfırlama linki
  const [joinToken, setJoinToken] = useState(null);   // M42: workspace davet linki

  const check = useCallback(async () => {
    // M42: workspace davet linki (/workspaces/join?token=..) → kabul ekranı
    const jt = getJoinTokenFromUrl();
    if (jt) { setJoinToken(jt); setPhase('join'); return; }
    // M18: şifre-sıfırlama linki (/auth/reset?token=..) → Login reset modunda açılır
    const rt = getResetTokenFromUrl();
    if (rt) { setResetToken(rt); setPhase('login'); return; }
    // M17: OAuth callback redirect'ini yakala.
    // BUG #179 (P2): URL artık token değil tek-kullanımlık kod taşır → takas async.
    const oauth = await consumeOAuthRedirect();
    if (oauth.status === 'success') { setPhase('app'); return; }
    if (oauth.status === 'error') { setOauthError(oauth.error); setPhase('login'); return; }
    try {
      const h = await healthApi.get();
      if (h?.auth_enabled && !authApi.isLoggedIn()) { setPhase('login'); return; }
    } catch { /* backend erişilemezse yine app'i göster (health banner uyarır) */ }
    setPhase('app');
  }, []);

  useEffect(() => { check(); }, [check]);

  // M61 (BUG #158): api.js oturumu kurtaramazsa 'fos:auth-expired' yayar → Login'e düş
  // (ölü token uygulamayı beyaz ekranda/hata döngüsünde bırakmasın).
  useEffect(() => {
    const onExpired = () => { setResetToken(null); setJoinToken(null); setPhase('login'); };
    window.addEventListener('fos:auth-expired', onExpired);
    return () => window.removeEventListener('fos:auth-expired', onExpired);
  }, []);

  if (phase === 'checking') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 text-zinc-500 dark:text-zinc-400 text-sm">
        Yükleniyor…
      </div>
    );
  }
  if (phase === 'join') return (
    <WorkspaceJoin token={joinToken} onDone={() => {
      try { window.history.replaceState({}, '', '/'); } catch { /* */ }
      setJoinToken(null); setPhase('checking'); check();
    }} />
  );
  if (phase === 'login') return (
    <Login onAuthed={() => setPhase('app')} initialError={oauthError}
      initialMode={resetToken ? 'reset' : 'login'} resetToken={resetToken} />
  );
  return <AppContent onLogout={async () => { await authApi.logout(); setPhase('login'); }} />;
}

// M43: header workspace seçici — değiştirince aktif workspace kaydedilir + sayfa yenilenir
// (tüm paneller yeni X-Workspace-Id header'ıyla yeniden yükler). M64: test için export.
export function WorkspaceSwitcher() {
  const [list, setList] = useState([]);
  const [active, setActive] = useState(getActiveWorkspaceId());

  useEffect(() => {
    let alive = true;
    workspaceApi.list().then((ws) => {
      if (!alive) return;
      setList(ws);
      if (!getActiveWorkspaceId() && ws.length) {
        const personal = ws.find((w) => w.is_personal) || ws[0];
        setActiveWorkspaceId(personal.id);
        setActive(String(personal.id));
      }
    }).catch(() => { /* auth kapalı / tek-kullanıcı: seçiciyi gösterme */ });
    return () => { alive = false; };
  }, []);

  if (list.length <= 1) return null;  // tek workspace varsa seçici gereksiz

  const onChange = (e) => {
    const id = e.target.value;
    setActiveWorkspaceId(id);
    window.location.reload();  // panellerin yeni workspace ile yeniden yüklenmesi
  };

  return (
    <select value={active || ''} onChange={onChange}
      title="Aktif workspace"
      className="chip bg-transparent border border-zinc-300 dark:border-zinc-700 rounded-lg px-2 py-1 text-xs max-w-[100px] sm:max-w-[140px]">
      {list.map((w) => (
        <option key={w.id} value={w.id}>
          {w.is_personal ? '👤 ' : '👥 '}{w.name}
        </option>
      ))}
    </select>
  );
}

function AppContent({ onLogout }) {
  const [theme, toggleTheme] = useTheme();
  const [activeTab, setActiveTab] = useState('cockpit');
  const { status, usagePct } = useBackendHealth();
  const [showHelp, setShowHelp] = useState(false);
  const [showPalette, setShowPalette] = useState(false);
  const [showSihirbaz, setShowSihirbaz] = useState(false);
  // Geri bildirim kutusunu dışarıdan açmak için: key değişimi widget'ı `acik` başlatır.
  const [gbAcSayaci, setGbAcSayaci] = useState(0);

  // Sade / detaylı görünüm. `secildi` false ise tercih HİÇ sorulmadı — bir kez sorulur.
  const { basit, secildi, degistir, BASIT, DETAYLI } = useGorunumModu();
  const sekmeler = useMemo(() => gorunurSekmeler(basit), [basit]);
  // Kısayol sırası memolanır: her render'da yeni bir dizi üretmek, klavye dinleyicisini
  // her render'da söküp yeniden takardı.
  const sekmeIdleri = useMemo(() => kisayolSirasi(basit), [basit]);

  // Detaylıdan sadeye geçen kullanıcı, çubukta artık olmayan bir panelde kalabilir
  // (ör. Raporlar). O hâlde aktif sekme HİÇBİR hapla eşleşmez: içerik görünür ama
  // kullanıcı nerede olduğunu göremez ve geri dönemez. Görünmeyen sekme → Cockpit.
  useEffect(() => {
    if (!sekmeler.some((s) => s.id === activeTab)) setActiveTab('cockpit');
  }, [sekmeler, activeTab]);

  // Sekme şeridi: detaylı görünümde 13 sekme dar ekrana sığmaz ve yatay kayar.
  // Kaydırmanın ÜÇ yolu da açık olmalı — çubuk (ince ama görünür, index.css),
  // fare tekerleği ve klavye. İlk sürümde yalnız klavye çalışıyordu: çubuk gizliydi,
  // dikey tekerlek de yatay konteyneri kaydırmaz. Ulaşılamayan sekme, olmayan sekmedir.
  const seritRef = useRef(null);

  useEffect(() => {
    const serit = seritRef.current;
    if (!serit) return undefined;
    const tekerlek = (e) => {
      // Dokunmatik yüzeylerin YATAY jestini tarayıcı zaten çeviriyor; yalnız dikey
      // tekerleği devralıyoruz ve ancak kayacak yer VARSA — yoksa sayfanın dikey
      // kaydırmasını çalmış oluruz.
      if (e.deltaY === 0 || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      if (serit.scrollWidth <= serit.clientWidth) return;
      e.preventDefault();
      serit.scrollLeft += e.deltaY;
    };
    serit.addEventListener('wheel', tekerlek, { passive: false });
    return () => serit.removeEventListener('wheel', tekerlek);
  }, [basit]);

  // Aktif sekme şeridin dışında kalmasın (klavye kısayolu ya da mod değişimi sonrası
  // kullanıcı "hangi sekmedeyim" sorusunu kaydırarak aramamalı). `scrollIntoView`
  // yerine elle hesap: o çağrı sayfanın DİKEY konumunu da oynatabiliyor.
  useEffect(() => {
    const serit = seritRef.current;
    const dugme = serit?.querySelector('[data-aktif="1"]');
    if (!serit || !dugme) return;
    const solTasma = dugme.offsetLeft - serit.scrollLeft;
    const sagTasma = solTasma + dugme.offsetWidth - serit.clientWidth;
    if (solTasma < 0) serit.scrollLeft += solTasma - 8;
    else if (sagTasma > 0) serit.scrollLeft += sagTasma + 8;
  }, [activeTab, basit]);

  useKeyboardShortcuts({
    setActiveTab,
    sekmeIdleri,
    onHelp: () => setShowHelp(h => !h),
    onPalette: () => setShowPalette(p => !p),
  });

  // Sihirbaz İLK girişte bir kez kendiliğinden açılır: yalnız hiçbir adım tamamlanmamışsa
  // ve kullanıcı rehberi daha önce kapatmamışsa. Sonraki açılışlarda çıkmaz — davet
  // edilmemiş bir modal, ikinci gösterimde engeldir. Yardım köşesinden her an açılır.
  useEffect(() => {
    let iptal = false;
    const OTOMATIK_ANAHTAR = 'sihirbaz_otomatik_acildi';
    try {
      if (localStorage.getItem(OTOMATIK_ANAHTAR) === '1') return undefined;
    } catch { /* depolama yoksa yine de bir kez göster */ }

    onboardingApi.rehber()
      .then((r) => {
        if (iptal || !r?.gorunur || (r.tamamlanan ?? 0) > 0) return;
        setShowSihirbaz(true);
        try { localStorage.setItem(OTOMATIK_ANAHTAR, '1'); } catch { /* önemsiz */ }
      })
      .catch(() => { /* rehber okunamadıysa sihirbaz zorlanmaz */ });

    return () => { iptal = true; };
  }, []);

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
            <WorkspaceSwitcher />
            {/* Bağlantı durumu: HER ŞEY YOLUNDAYKEN yalnız bir nokta.
                Eskiden başlıkta kalıcı yeşil bir "Bağlı" rozeti duruyordu — hiçbir gün
                değişmeyen bir bilgi, her gün yer kaplıyordu. Sorun VARSA rozet konuşur
                (ve altta ayrıca tam genişlikte şerit çıkar). Bilgi eksilmiyor: normal
                hâlin karşılığı `title`/`aria-label`'da yazılı. */}
            {status === 'online' ? (
              <span
                className="w-2.5 h-2.5 rounded-full bg-positive-500 flex-shrink-0"
                title="Backend bağlantısı var"
                aria-label="Backend bağlantısı var"
                role="status"
              />
            ) : status === 'offline' ? (
              <span className="chip chip-negative" role="status">
                <WifiOff className="w-3 h-3" /> <span className="hidden sm:inline">Backend kapalı</span>
              </span>
            ) : (
              <span
                className="w-2.5 h-2.5 rounded-full bg-zinc-400 animate-pulse flex-shrink-0"
                title="Bağlantı kontrol ediliyor"
                aria-label="Bağlantı kontrol ediliyor"
                role="status"
              />
            )}

            {/* FE-012: olcum YOKSA rozet HIC cizilmez — "0%" gostermek uydurmaktir (L45). */}
            {usagePct !== null && (
              <span
                className={`chip font-numeric ${
                  usagePct > 80 ? 'chip-negative' :
                  usagePct > 50 ? 'chip-warn' :
                  ''
                }`}
                title="Bugunku LLM cagri kullanimi (gunluk limitin yuzdesi)"
              >
                {usagePct}%
              </span>
            )}

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

        {/* Sekme çubuğu — hap tasarımı. Sade görünümde 5, detaylıda 13 sekme.
            Şerit yatay kayar: ince ama GÖRÜNÜR çubuk + fare tekerleği + klavye.
            Sağ kenardaki solma maskesi "devamı var" der; maske tıklamayı yemesin diye
            `pointer-events-none` ve çubuğun üstüne binmemesi için alttan pay bırakılır.
            BUG #265: yükseklik ≥44px — `.sekme` sınıfı bunu taşıyor (ADR-010). */}
        <nav className="border-t border-zinc-200/60 dark:border-zinc-800/60" aria-label="Paneller">
          <div className="max-w-6xl mx-auto relative">
            <div ref={seritRef} className="px-2 pt-1.5 pb-1 overflow-x-auto kaydirma-ince">
              {/* Bilerek `role="tab"` DEĞİL, sade <button>.
                  ARIA sekme örüntüsü yalnız rol atamakla tamamlanmaz: ok tuşlarıyla
                  gezinme, roving tabindex ve aria-controls ister. Yarım uygulanmış bir
                  örüntü, ekran okuyucuya çalışmayan bir sözleşme vaat eder — düğme
                  listesi burada hem dürüst hem çalışıyor. Aktif olan `aria-current`
                  ile işaretlenir. */}
              <div className="flex gap-1">
                {sekmeler.map((sekme) => {
                  const Icon = sekme.icon;
                  const aktif = activeTab === sekme.id;
                  return (
                    <button
                      key={sekme.id}
                      onClick={() => setActiveTab(sekme.id)}
                      aria-current={aktif ? 'page' : undefined}
                      data-aktif={aktif ? '1' : undefined}
                      className={`sekme ${aktif ? 'sekme-aktif' : 'sekme-pasif'}`}
                    >
                      <Icon className="w-4 h-4 flex-shrink-0" />
                      {sekmeEtiketi(sekme, basit)}
                    </button>
                  );
                })}
              </div>
            </div>
            {!basit && (
              <div
                aria-hidden="true"
                className="pointer-events-none absolute right-0 top-0 bottom-2 w-8
                           bg-gradient-to-l from-zinc-50 dark:from-zinc-950 to-transparent"
              />
            )}
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
          {/* Panel içi öğretici şerit — ne işe yarar + nasıl kullanılır + örnek.
              İçerik `lib/ogretici.js`, kapatınca hatırlanır, yardım köşesinden geri gelir. */}
          <Ipucu sekme={activeTab} />

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
            {activeTab === 'workspace' && <Workspace />}
            {activeTab === 'hesap' && <Hesap />}
          </ErrorBoundary>
        </div>
      </main>

      <footer className="flex-shrink-0 max-w-6xl mx-auto px-4 py-3 text-center text-xs text-zinc-500">
        FinancialOS · v0.1.0
        {' · '}
        {/* Görünüm modunun ikinci kapısı. Asıl anahtar Hesap panelinde; buradaki satır
            onun VAR OLDUĞUNU söyler — kimsenin bilmediği bir ayar, olmayan ayardır. */}
        <span>Görünüm: {basit ? 'Sade' : 'Detaylı'}</span>
        {' · '}
        {/* BUG #216: duz <a href> Authorization basligi TASIMAZ -> giris acikken 401
            indiriyordu. Indirme artik yetkili istekle Hesap panelinde yapiliyor. */}
        <button type="button" onClick={() => setActiveTab('hesap')}
           className="underline hover:text-zinc-700 dark:hover:text-zinc-300">
          Hesap, görünüm & verilerim
        </button>
      </footer>

      {showPalette && (
        <CommandPalette
          onClose={() => setShowPalette(false)}
          setActiveTab={setActiveTab}
          basit={basit}
          onModDegistir={() => degistir(basit ? DETAYLI : BASIT)}
        />
      )}

      {/* Tercih HİÇ sorulmamışsa bir kez sorulur. Kapatan kişi sade ile devam eder ve
          soru bir daha çıkmaz (Hesap panelinden her an değiştirilebilir). */}
      {!secildi && <GorunumSecici onSec={(m) => degistir(m)} />}
      {showHelp && (
        <HelpModal onClose={() => setShowHelp(false)} />
      )}

      {showSihirbaz && (
        <OgreticiSihirbaz
          onKapat={() => setShowSihirbaz(false)}
          setActiveTab={setActiveTab}
        />
      )}

      {/* Her panelde duran yardım düğmesi: bu ekran ne işe yarar + sihirbazı yeniden başlat */}
      <YardimKosesi
        sekme={activeTab}
        onSihirbaz={() => setShowSihirbaz(true)}
        onKisayollar={() => setShowHelp(true)}
        onGeriBildirim={() => setGbAcSayaci((n) => n + 1)}
      />

      {/* FEAT-033: her ekranda geri bildirim (aktif sekme bağlam olarak geçer).
          key: yardım köşesinden "Sorun bildir" seçilince widget açık başlar. */}
      <FeedbackWidget key={gbAcSayaci} page={activeTab} acik={gbAcSayaci > 0} />
    </div>
  );
}