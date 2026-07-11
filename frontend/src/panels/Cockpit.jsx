import { useState, useEffect, useCallback } from 'react';
import {
  Wallet, CreditCard, Building2, TrendingUp, Lock,
  Banknote, Calculator, Scale, ScaleIcon, AlertTriangle,
  Calendar, Users, RefreshCw, Loader2, Clock, ExternalLink,
  Eye, Telescope, Bell, Waves, ArrowRight,
} from 'lucide-react';
import {
  cockpitApi, fundPriceApi, actionsApi, incomesApi, expensesApi,
  cashflowApi, formatTL, formatTLSuffix, formatPercent, formatDate, signClass,
} from '../api.js';
import MetricCard from '../components/MetricCard.jsx';
import MonthlySummary from '../components/MonthlySummary.jsx';
import AccountCard from '../components/AccountCard.jsx';
import PendingActions from '../components/PendingActions.jsx';
import { Skeleton } from '../components/Skeleton.jsx';
import EmptyState from '../components/EmptyState.jsx';

/**
 * Cockpit — Ana finansal kontrol paneli.
 * Tek bir GET /api/cockpit cagrisi ile tum manzarayi getirir.
 *
 * BUG #006 fix (2 May 2026): Iki net deger metrigi
 * - Gorulen Net Deger (operasyonel, alacaksiz)
 * - Tam Net Deger (stratejik, sozlesmeli alacaklar dahil)
 *
 * Layout iki grupta:
 * - Ust grup: Operasyonel (Nakit, Kart, Kredi, Yatirim) - 4 kart
 * - Alt grup: Strateji (Emanet, Gelir, Reel Butce, Gorulen Net, Tam Net) - 5 kart
 */
export default function Cockpit({ setActiveTab }) {
  const [data, setData] = useState(null);
  const [pendingActions, setPendingActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [priceUpdateAccount, setPriceUpdateAccount] = useState(null);
  const [flowSummary, setFlowSummary] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const [cockpit, pending, dueIncome, dueExpense] = await Promise.all([
        cockpitApi.get(),
        actionsApi.pending(),
        incomesApi.triggerDue().catch(() => ({ triggered: [] })),   // A2: sessiz fail
        expensesApi.triggerDue().catch(() => ({ triggered: [] })),  // A3: sessiz fail
      ]);
      setData(cockpit);
      // A2+A3: vadesi gelen gelir ve giderler pending listesine eklenir (dedup backend'de)
      const dueActions = [
        ...(dueIncome?.triggered || []),
        ...(dueExpense?.triggered || []),
      ];
      const existingIds = new Set((pending || []).map(a => a.id));
      const merged = [...(pending || []), ...dueActions.filter(a => !existingIds.has(a.id))];
      setPendingActions(merged);
    } catch (e) {
      setError(e.message || 'Cockpit yuklenemedi');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    // Akış özeti — sessiz fail, cockpit yüklemesini engellemesin
    cashflowApi.getForecast({ days: 30 })
      .then(r => setFlowSummary(r.summary))
      .catch(() => {});
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = () => {
    setRefreshing(true);
    load();
  };

  const handleActionResolved = async () => {
    setRefreshing(true);
    await load();
  };

  if (loading) return <CockpitSkeleton />;

  if (error) {
    return (
      <div className="card p-6 border-negative-300 dark:border-negative-700 bg-negative-50 dark:bg-negative-950/30">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-negative-600 dark:text-negative-400 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-negative-700 dark:text-negative-300">
              Cockpit yüklenemedi
            </h3>
            <p className="text-sm text-zinc-700 dark:text-zinc-300 mt-1">{error}</p>
            <button onClick={handleRefresh} className="btn btn-secondary !text-xs mt-3">
              <RefreshCw className="w-3 h-3" /> Tekrar dene
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!data) return null;

  const investmentPnl = data.investment_pnl?.[0];

  // BUG #006 fix: Yeni alanlar (eski cockpit response'i ile geriye uyumlu olsun diye fallback)
  const netDegerTam = data.net_deger_tam ?? data.net_deger;
  const alacaklarToplami = data.alacaklar_toplami ?? 0;
  const borclarToplami = data.borclar_toplami ?? 0;   // BUG #116: kişisel borç (net_deger_tam'dan −)
  const alacaklarVar = alacaklarToplami > 0;
  // Tam Net Değer alt-yazısı: hem +alacak hem −kişisel-borç şeffaf gösterilir (#116)
  const netTamDetay = [
    alacaklarToplami > 0 ? `+${formatTL(alacaklarToplami)} TL alacak` : null,
    borclarToplami > 0 ? `−${formatTL(borclarToplami)} TL kişisel borç` : null,
  ].filter(Boolean).join(', ');

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Statu + Yenile */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-lg sm:text-xl font-bold mb-1">Bugünkü manzara</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">{data.statu}</p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="btn btn-secondary !text-xs flex-shrink-0"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Yenile</span>
        </button>
      </div>

      {/* Bekleyen aksiyonlar */}
      {pendingActions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 text-brand-600 dark:text-brand-400">
            Onay bekleyen aksiyonlar ({pendingActions.length})
          </h3>
          <PendingActions actions={pendingActions} onResolved={handleActionResolved} accounts={data?.accounts} />
        </div>
      )}

      {/* ===== USTGRUP: OPERASYONEL ===== */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Eye className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
          <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
            Operasyonel manzara
          </h3>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <MetricCard title="Nakit" value={data.nakit_kasa} variant="positive" icon={Wallet} />
          <MetricCard title="Kart Borcu" value={data.kart_borcu} variant="negative" icon={CreditCard} />
          <MetricCard title="Kredi Borcu" value={data.kredi_borcu} variant="negative" icon={Building2} />
          <MetricCard title="Yatırım" value={data.yatirim_deger} variant="brand" icon={TrendingUp} />
        </div>
      </div>

      {/* ===== ALT GRUP: STRATEJIK ===== */}
      <div>
        <div className="flex items-center gap-2 mb-2">
          <Telescope className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
          <h3 className="text-xs font-semibold text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
            Stratejik manzara
          </h3>
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
          <MetricCard
            title="Emanet"
            value={data.emanet_kasa}
            variant="warn"
            icon={Lock}
            isEmanet
            subtitle="Net değere dahil değil"
          />
          <MetricCard
            title="Beklenen Gelir"
            value={data.beklenen_gelir}
            variant="positive"
            icon={Banknote}
            subtitle="Bu ay sonuna kadar"
          />
          <MetricCard
            title="Reel Bütçe"
            value={data.reel_butce}
            variant={data.reel_butce >= 0 ? 'positive' : 'negative'}
            icon={Calculator}
            subtitle="Gölge muhasebe sonrası"
          />
          {/* Gorulen Net Deger - operasyonel rakam, cuzdan acildiginda gorunen */}
          <MetricCard
            title="Görülen Net Değer"
            value={data.net_deger}
            variant={data.net_deger >= 0 ? 'positive' : 'negative'}
            icon={Scale}
            subtitle="Alacaksız (operasyonel)"
          />
          {/* Tam Net Deger - stratejik rakam, sozlesmeli alacaklar dahil */}
          <MetricCard
            title="Tam Net Değer"
            value={netDegerTam}
            variant={netDegerTam >= 0 ? 'positive' : 'negative'}
            icon={Telescope}
            subtitle={netTamDetay
              ? `${netTamDetay} dahil`
              : 'Alacak/borç yok, görülen ile aynı'}
          />
        </div>
      </div>

      {/* Günlük limit kutusu */}
      <div className="card p-5 border-brand-200 dark:border-brand-800/50 bg-brand-50/50 dark:bg-brand-950/20">
        <div>
          <h3 className="text-xs font-medium text-zinc-600 dark:text-zinc-400 mb-1">
            Bugünkü harcama hedefi
          </h3>
          <p className="font-numeric text-3xl sm:text-4xl font-bold text-brand-700 dark:text-brand-400">
            {formatTLSuffix(data.today_target)}
          </p>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1">
            Ay sonuna {data.days_remaining} gün · Günlük limit {formatTL(data.daily_limit)} TL
            {data.carried_forward !== 0 && (
              <span className={signClass(data.carried_forward)}>
                {' '}· Devreden {data.carried_forward > 0 ? '+' : ''}{formatTL(data.carried_forward)} TL
              </span>
            )}
          </p>
          {/* Zikzak projeksiyonu — kurucu "biriken güç": bugün harcamazsan yarınki limit yükselir */}
          {data.yarin_limit_harcamasiz > data.daily_limit && (
            <p className="text-xs text-positive-600 dark:text-positive-400 mt-1.5 flex items-center gap-1">
              <Waves className="w-3.5 h-3.5 shrink-0" />
              Bugün harcamazsan yarın limitin {formatTL(data.yarin_limit_harcamasiz)} TL/gün'e çıkar
            </p>
          )}
          {/* FEAT-009: ileriye-dönük güvenli harcama tabanı — lumpy yükümlülükleri hesaba katar (kart hariç) */}
          {data.guvenli_harcama !== undefined && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5 flex items-center gap-1">
              <Lock className="w-3.5 h-3.5 shrink-0" />
              Güvenli harcama (90g öngörü, kart borcu düşülmüş):{' '}
              <span className={`font-numeric font-semibold ${data.guvenli_harcama > 0 ? 'text-zinc-700 dark:text-zinc-200' : 'text-negative-600 dark:text-negative-400'}`}>
                {formatTL(data.guvenli_harcama)} TL
              </span>
            </p>
          )}
          {/* FEAT-010: nakit runway — gelirsiz mevcut nakit kaç gün yeter */}
          {data.nakit_runway_gun !== undefined && data.nakit_runway_gun !== null && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5 shrink-0" />
              Nakit runway:{' '}
              <span className={`font-numeric font-semibold ${data.nakit_runway_gun >= 30 ? 'text-zinc-700 dark:text-zinc-200' : 'text-negative-600 dark:text-negative-400'}`}>
                {data.nakit_runway_gun} gün
              </span>
              <span className="text-zinc-400 dark:text-zinc-500"> (gelirsiz, 30g harcama hızıyla)</span>
            </p>
          )}
        </div>
      </div>

      {/* A3: Aylık özet — kurucu "durum raporu" */}
      <MonthlySummary />

      {/* FEAT-006: toplam abonelik yükü — glanceable (Rocket Money headline) */}
      {data.abonelik_yuku?.adet > 0 && (
        <div className="card p-3 flex items-center gap-2 text-sm">
          <RefreshCw className="w-4 h-4 text-zinc-500 dark:text-zinc-400 shrink-0" />
          <span className="text-zinc-600 dark:text-zinc-300">
            {data.abonelik_yuku.adet} abonelik ·{' '}
            <span className="font-numeric font-semibold">{formatTL(data.abonelik_yuku.aylik)} TL</span>/ay
            <span className="text-zinc-400 dark:text-zinc-500"> ({formatTL(data.abonelik_yuku.yillik)} TL/yıl)</span>
          </span>
        </div>
      )}

      {/* Uyarılar */}
      {data.alerts && data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((alert, i) => (
            <div
              key={i}
              className={`card p-4 ${
                alert.seviye === 'kritik'
                  ? 'border-negative-300 dark:border-negative-700/50 bg-negative-50/50 dark:bg-negative-950/20'
                  : 'border-warn-300 dark:border-warn-700/50 bg-warn-50/50 dark:bg-warn-950/20'
              }`}
            >
              <div className="flex items-start gap-3">
                <AlertTriangle
                  className={`w-5 h-5 flex-shrink-0 mt-0.5 ${
                    alert.seviye === 'kritik'
                      ? 'text-negative-600 dark:text-negative-400'
                      : 'text-warn-600 dark:text-warn-400'
                  }`}
                />
                <div className="min-w-0">
                  <h4
                    className={`font-semibold text-sm ${
                      alert.seviye === 'kritik'
                        ? 'text-negative-700 dark:text-negative-300'
                        : 'text-warn-700 dark:text-warn-300'
                    }`}
                  >
                    {alert.baslik}
                  </h4>
                  <p className="text-xs text-zinc-700 dark:text-zinc-300 mt-1">
                    {alert.mesaj}
                  </p>
                </div>
              </div>
            </div>
          ))}
          {/* #126: sığmayan uyarılar — alert yorgunluğu için gizlenenlerin sayısı */}
          {data.gizli_uyari_sayisi > 0 && (
            <p className="text-xs text-zinc-400 dark:text-zinc-500 text-center pt-1">
              +{data.gizli_uyari_sayisi} düşük öncelikli uyarı daha
            </p>
          )}
        </div>
      )}

      {/* Hesaplar grid */}
      <div>
        <h3 className="text-sm font-semibold mb-3 text-zinc-700 dark:text-zinc-300">
          Hesaplar ({data.accounts?.length || 0})
        </h3>
        {data.accounts?.length === 0 ? (
          <EmptyState
            icon={Wallet}
            title="Henüz hesap yok"
            description="Hesaplar panelinden ilk hesabını ekleyerek başla."
          />
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {data.accounts.map((acc) => (
              <AccountCard
                key={acc.id}
                account={acc}
                onPriceUpdateClick={(a) => setPriceUpdateAccount(a)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Yatırım K/Z */}
      {investmentPnl && (
        <div className="card p-5">
          <div className="flex items-center gap-2 mb-3">
            <TrendingUp className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <h3 className="font-semibold">Yatırım Kâr/Zarar</h3>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Toplam maliyet</p>
              <p className="font-numeric font-semibold">{formatTLSuffix(investmentPnl.toplam_maliyet)}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Güncel değer</p>
              <p className="font-numeric font-semibold">{formatTLSuffix(investmentPnl.guncel_deger)}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Brüt kâr</p>
              <p className={`font-numeric font-semibold ${signClass(investmentPnl.brut_kar)}`}>
                {investmentPnl.brut_kar > 0 ? '+' : ''}
                {formatTLSuffix(investmentPnl.brut_kar)}
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Getiri</p>
              <p className={`font-numeric font-semibold ${signClass(investmentPnl.getiri_yuzde)}`}>
                {formatPercent(investmentPnl.getiri_yuzde)}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Akış Özeti — cashflow forecast özeti (30 gün) */}
      {flowSummary && (
        <div className="card p-4 border-brand-200/60 dark:border-brand-800/40 bg-brand-50/30 dark:bg-brand-950/10">
          <div className="flex items-center justify-between gap-2 mb-3">
            <div className="flex items-center gap-2">
              <Waves className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <h3 className="font-semibold text-sm">Akış Özeti (30 gün)</h3>
            </div>
            {setActiveTab && (
              <button
                onClick={() => setActiveTab('cashflow')}
                className="flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 hover:underline"
              >
                Detay <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-0.5">En Düşük Bakiye</p>
              <p className={`font-numeric font-semibold text-sm ${flowSummary.lowest_balance >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                {formatTL(flowSummary.lowest_balance)} TL
              </p>
              <p className="text-[10px] text-zinc-400 dark:text-zinc-500">{formatDate(flowSummary.lowest_date)}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-0.5">Net Akış</p>
              <p className={`font-numeric font-semibold text-sm ${flowSummary.net_flow >= 0 ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                {flowSummary.net_flow > 0 ? '+' : ''}{formatTL(flowSummary.net_flow)} TL
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-0.5">Sıkışma Günü</p>
              <p className={`font-numeric font-semibold text-sm ${flowSummary.crunch_count > 0 ? 'text-negative-600 dark:text-negative-400' : 'text-zinc-400 dark:text-zinc-500'}`}>
                {flowSummary.crunch_count}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* A1: Yaklaşan Vadeler (0-7 gün) */}
      {data.upcoming_reminders?.length > 0 && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Bell className="w-4 h-4 text-brand-600 dark:text-brand-400" />
            <h3 className="font-semibold text-sm">Yaklaşan vadeler</h3>
            <span className="chip chip-neutral text-[10px] ml-auto">
              {data.upcoming_reminders.length} kalem
            </span>
          </div>
          <div className="space-y-2">
            {data.upcoming_reminders.map((r, i) => {
              const dayLabel = r.days_until === 0 ? 'Bugün'
                : r.days_until === 1 ? 'Yarın'
                : `${r.days_until} gün sonra`;
              // BUG #119: alacak (receivable) da gelir gibi bir NAKİT GİRİŞİ — + ve yeşil.
              const isInflow = r.type === 'income' || r.type === 'receivable';
              const sign = isInflow ? '+' : '−';
              const colorClass = isInflow
                ? 'text-positive-600 dark:text-positive-400'
                : 'text-negative-600 dark:text-negative-400';
              const typeLabel = { income: 'Gelir', receivable: 'Tahsilat',
                debt: 'Borç', expense: 'Gider', card_payment: 'Son ödeme' }[r.type] || r.type;
              return (
                <div key={i}
                  className="flex items-center justify-between text-sm py-1.5 border-b border-zinc-100 dark:border-zinc-800 last:border-0 gap-2">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                      <p className="font-medium truncate">{r.name}</p>
                      {r.type === 'card_payment' ? (
                        <span className="chip chip-negative text-[9px] flex-shrink-0">💳 Son ödeme</span>
                      ) : r.card_risk ? (
                        <span className="chip chip-negative text-[9px] flex-shrink-0">Kart riski</span>
                      ) : null}
                    </div>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {dayLabel} · {r.account_name || typeLabel}
                    </p>
                  </div>
                  <span className={`font-numeric font-semibold flex-shrink-0 ${colorClass}`}>
                    {sign}{formatTL(r.amount)} TL
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Takvim 2 sütun */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {data.upcoming_payments?.length > 0 && (
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Calendar className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
              <h3 className="font-semibold text-sm">Yaklaşan ödemeler</h3>
            </div>
            <div className="space-y-2">
              {data.upcoming_payments.map((p, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm py-1.5 border-b border-zinc-100 dark:border-zinc-800 last:border-0"
                >
                  <div className="min-w-0">
                    <p className="font-medium truncate">{p.ad}</p>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400">
                      {formatDate(p.tarih)} ·{' '}
                      {p.tip === 'gelir'
                        ? 'Gelir'
                        : p.tip === 'kredi_taksit'
                        ? 'Kredi taksiti'
                        : p.tip}
                    </p>
                  </div>
                  <span
                    className={`font-numeric font-semibold flex-shrink-0 ${
                      p.tip === 'gelir'
                        ? 'text-positive-600 dark:text-positive-400'
                        : 'text-negative-600 dark:text-negative-400'
                    }`}
                  >
                    {p.tip === 'gelir' ? '+' : '−'}
                    {formatTL(p.tutar)} TL
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.upcoming_receivables?.length > 0 && (
          <div className="card p-4">
            <div className="flex items-center gap-2 mb-3">
              <Users className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
              <h3 className="font-semibold text-sm">Yaklaşan tahsilatlar</h3>
            </div>
            <div className="space-y-2">
              {data.upcoming_receivables.map((r, i) => (
                <div
                  key={i}
                  className="flex items-start justify-between text-sm py-1.5 border-b border-zinc-100 dark:border-zinc-800 last:border-0 gap-2"
                >
                  <div className="min-w-0">
                    <p className="font-medium">{r.kim}</p>
                    <p
                      className="text-xs text-zinc-500 dark:text-zinc-400 truncate"
                      title={r.aciklama}
                    >
                      {formatDate(r.tarih)} · {r.aciklama}
                    </p>
                  </div>
                  <span className="font-numeric font-semibold text-positive-600 dark:text-positive-400 flex-shrink-0">
                    +{formatTL(r.tutar)} TL
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Fiyat tazeliği */}
      {data.price_freshness?.items?.length > 0 && (
        <div className="card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Clock className="w-4 h-4 text-zinc-600 dark:text-zinc-400" />
            <h3 className="font-semibold text-sm">Fiyat tazeliği</h3>
            {data.price_freshness.stale_count > 0 && (
              <span className="chip chip-warn text-[10px]">
                {data.price_freshness.stale_count} eski
              </span>
            )}
          </div>
          <div className="space-y-1.5">
            {data.price_freshness.items.map((item) => (
              <div key={item.account_id} className="flex items-center justify-between text-xs">
                <span className="text-zinc-700 dark:text-zinc-300">
                  {item.name}
                  {item.is_emanet && (
                    <Lock className="inline w-3 h-3 ml-1 text-warn-500" />
                  )}
                </span>
                <span
                  className={`font-numeric ${
                    item.is_stale
                      ? 'text-warn-600 dark:text-warn-400'
                      : 'text-zinc-500 dark:text-zinc-400'
                  }`}
                >
                  {item.age_text}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Manuel fiyat güncelleme modal */}
      {priceUpdateAccount && (
        <PriceUpdateModal
          account={priceUpdateAccount}
          onClose={() => setPriceUpdateAccount(null)}
          onUpdated={() => {
            setPriceUpdateAccount(null);
            handleRefresh();
          }}
        />
      )}
    </div>
  );
}

// ============================================================
// COCKPIT SKELETON — loading state, gerçek layout'u yansıtır
// ============================================================

function CockpitSkeleton() {
  return (
    <div className="space-y-6">
      {/* Başlık */}
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2 min-w-0">
          <Skeleton className="h-7 w-44" />
          <Skeleton className="h-4 w-64" />
        </div>
        <Skeleton className="h-9 w-20 flex-shrink-0 rounded-lg" />
      </div>

      {/* Operasyonel — 4 MetricCard */}
      <div>
        <Skeleton className="h-3 w-36 mb-3" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-7 w-28" />
              <Skeleton className="h-2 w-20" />
            </div>
          ))}
        </div>
      </div>

      {/* Stratejik — 5 MetricCard */}
      <div>
        <Skeleton className="h-3 w-32 mb-3" />
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 sm:gap-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="card p-4 space-y-2">
              <Skeleton className="h-3 w-16" />
              <Skeleton className="h-7 w-24" />
              <Skeleton className="h-2 w-20" />
            </div>
          ))}
        </div>
      </div>

      {/* Günlük limit kutusu */}
      <div className="card p-5 space-y-3">
        <Skeleton className="h-3 w-36" />
        <Skeleton className="h-11 w-40" />
        <Skeleton className="h-3 w-72" />
      </div>

      {/* Hesaplar grid */}
      <div>
        <Skeleton className="h-4 w-28 mb-3" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card p-4 space-y-3">
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-8 w-1/2" />
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============================================================
// PRICE UPDATE MODAL
// ============================================================

function PriceUpdateModal({ account, onClose, onUpdated }) {
  const [newPrice, setNewPrice] = useState(account.fiyat?.toString() || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const price = parseFloat(newPrice.replace(',', '.'));
    if (!price || price <= 0) {
      setErr('Geçerli bir fiyat girin');
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await fundPriceApi.update(account.id, price);
      onUpdated();
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  };

  const tefasUrl = `https://www.tefas.gov.tr/FonAnaliz.aspx?FonKod=${account.fund_code}`;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div className="card p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-semibold mb-1">Fiyat güncelle</h3>
        <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
          {account.ad} · {account.fund_code}
        </p>

        <a
          href={tefasUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="btn btn-secondary !text-xs w-full mb-4"
        >
          <ExternalLink className="w-3 h-3" />
          TEFAS'ta aç
        </a>

        <form onSubmit={handleSubmit}>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">
            Yeni fiyat (TL)
          </label>
          <input
            type="text"
            value={newPrice}
            onChange={(e) => setNewPrice(e.target.value)}
            className="input"
            placeholder="4929.56"
            autoFocus
          />
          {err && (
            <p className="text-xs text-negative-600 dark:text-negative-400 mt-2">{err}</p>
          )}
          <div className="flex gap-2 mt-4">
            <button type="submit" disabled={busy} className="btn btn-primary flex-1">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Kaydet'}
            </button>
            <button type="button" onClick={onClose} className="btn btn-secondary">
              İptal
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}