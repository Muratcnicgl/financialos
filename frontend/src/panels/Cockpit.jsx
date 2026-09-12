import { useState, useEffect, useCallback, useId, useRef } from 'react';
import { useDialog } from '../lib/dialog.js';
import {
  Wallet, CreditCard, Building2, TrendingUp, Lock,
  Banknote, Calculator, Scale, AlertTriangle,
  Calendar, Users, RefreshCw, Loader2, Clock, ExternalLink,
  Eye, Telescope, Bell, Waves, ArrowRight, Target, ChevronDown, ChevronRight,
} from 'lucide-react';
import { cockpitApi, fundPriceApi, actionsApi, incomesApi, expensesApi, cashflowApi, reportsApi, formatPercent, formatDate, signClass, parseTRNumber } from '../api.js';
import MetricCard from '../components/MetricCard.jsx';
import MonthlySummary from '../components/MonthlySummary.jsx';
import AylikSeri from '../components/AylikSeri.jsx';
import AccountCard from '../components/AccountCard.jsx';
import PendingActions from '../components/PendingActions.jsx';
import { Skeleton } from '../components/Skeleton.jsx';
import EmptyState from '../components/EmptyState.jsx';
import Onboarding from '../components/Onboarding.jsx';  // H20: ilk kullanım rehberi + demo veri
// Sadeleştirme: ikincil bölümler katlanır — özet başlıkta kalır, bilgi eksilmez.
import KatlanirBolum from '../components/KatlanirBolum.jsx';
import AkisSparkline from '../components/AkisSparkline.jsx';
import ButceSeridi from '../components/ButceSeridi.jsx';
import BuAyCikacak from '../components/BuAyCikacak.jsx';
import { formatPara, formatSayi, paraEtiketi } from '../lib/money.js';
// Sade / detaylı görünüm: bu panel ikisinin de yükünü taşır (bkz. lib/gorunumModu.js).
import { useGorunumModu } from '../hooks/useGorunumModu.js';

/**
 * FEAT-030 (UX açıklanabilirlik): Günlük limitin AÇIK dökümü.
 * Kullanıcı "66 TL / 208 TL nereden geliyor?" sorusunu tek bakışta görür; "kredi bakiyesinin
 * tamamını mı düşüyor?" şüphesi kalkar. Sayılar backend `butce_dokum`'dan (rules_engine tek
 * kaynak — ADR-001: engine hesaplar, UI gösterir); JS'te YENİDEN hesap YOK (drift riski yok).
 */
function BudgetBreakdown({ dokum }) {
  const [open, setOpen] = useState(false);
  if (!dokum) return null;
  const Row = ({ label, value, sign, muted }) => (
    <div className="flex items-center justify-between py-0.5">
      <span className={muted ? 'text-zinc-500' : 'text-zinc-600 dark:text-zinc-300'}>
        {label}
      </span>
      <span className={`font-numeric ${muted ? 'text-zinc-500' : 'text-zinc-700 dark:text-zinc-200'}`}>
        {sign}{formatPara(Math.abs(value))}
      </span>
    </div>
  );
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="text-xs text-zinc-500 dark:text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 flex items-center gap-1 min-h-[44px]"
      >
        {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
        Günlük limit nasıl hesaplandı?
      </button>
      {open && (
        <div className="mt-1.5 text-xs rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white/60 dark:bg-zinc-900/40 px-3 py-2">
          <Row label="Nakit" value={dokum.nakit} sign="" />
          <Row label="Beklenen gelir (bu ay kalan)" value={dokum.beklenen_gelir} sign="+" />
          <Row label="Kart borcu (tamamı)" value={dokum.kart_borcu} sign="−" />
          <Row label="Bu ayki kredi taksiti" value={dokum.bu_ayki_taksit} sign="−" />
          <div className="border-t border-zinc-200 dark:border-zinc-700 mt-1 pt-1 flex items-center justify-between font-semibold">
            <span className="text-zinc-700 dark:text-zinc-200">= Reel bütçe</span>
            <span className={`font-numeric ${dokum.reel_butce >= 0 ? 'text-zinc-800 dark:text-zinc-100' : 'text-negative-600 dark:text-negative-400'}`}>
              {formatPara(dokum.reel_butce)}
            </span>
          </div>
          <div className="flex items-center justify-between text-zinc-500 dark:text-zinc-400 mt-0.5">
            <span>÷ {dokum.days_remaining} gün</span>
            <span className="font-numeric font-semibold text-brand-600 dark:text-brand-400">
              = {formatPara(dokum.daily_limit)}/gün
            </span>
          </div>
          {dokum.alacak_haric > 0 && (
            <p className="mt-1.5 text-zinc-500 leading-snug">
              Not: Alacaklar ({formatPara(dokum.alacak_haric)}) bütçeye dahil DEĞİL — tahsilat
              muhatabın kontrolünde. Kredinin yalnız <b>bu ayki taksiti</b> düşülür; bakiyenin
              tamamı değil.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * AYNI GERÇEĞİ İKİ KEZ YAZMA KURALI.
 *
 * Ölçülen sorun (10 Eyl 2026, gerçek veriyle): ekranda "Kart kullanımı %80
 * (9.600/12.000)" adanmış kartı ile "Kart kullanım oranı yüksek — Kart 80.0% dolu"
 * uyarısı yan yana duruyordu; asgari-ödeme tuzağı da aynı şekilde iki kez. Dört kutu,
 * iki bilgi. Adanmış kart zengin (çubuk + hedef borç + gerekçe), uyarı yalnız düzyazı.
 *
 * Kural: adanmış kart GERÇEKTEN ÇİZİLİYORSA aynı konunun uyarısı bastırılır.
 * "Çiziliyorsa" şartı önemli — sade görünümde o kartlar gizli ve o zaman uyarı TEK
 * kaynaktır, bastırılmaz. Risk taşıyan bir sinyali, onu gösteren tek yer kapalıyken
 * susturmak, sadeleştirme değil bilgi kaybıdır.
 *
 * Eşleştirme `kod` iledir, başlık dizesiyle DEĞİL: başlık bir yazım düzeltmesiyle bile
 * değişir ve kural sessizce çalışmayı bırakırdı. Kodların varlığını, benzersizliğini ve
 * buradaki listenin ölü olmadığını `tests/test_uyari_kodu_kapisi.py` ölçer.
 */
const KART_KARTI_OLAN_UYARILAR = {
  kart_kullanim: ['kart_kullanim_kritik', 'kart_kullanim_yuksek'],
  kart_asgari:   ['kart_asgari_tuzak', 'kart_asgari_sarmal'],
};

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
// BUG #427 (UX-023): kritik-dışı uyarılardan kaçı katlanmadan görünür
const KATLANMADAN_GORUNEN = 2;

export default function Cockpit({ setActiveTab }) {
  const [uyarilarAcik, setUyarilarAcik] = useState(false);
  // Sade görünümde ANALİZ bölümleri gizlenir; risk taşıyanlar (kritik uyarılar, onay
  // bekleyen aksiyonlar, atlanan düzenli kayıtlar, ilk adım) HER İKİ modda da durur.
  const { basit, degistir, DETAYLI } = useGorunumModu();
  const [data, setData] = useState(null);
  const [pendingActions, setPendingActions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [priceUpdateAccount, setPriceUpdateAccount] = useState(null);
  // Akış tahmini: eskiden yalnız `summary` saklanıyordu ve günlük seri ATILIYORDU.
  // Aynı yanıtın içinde 30 günün `closing_balance` + `crunch` verisi var; üç sayı
  // yerine şekli göstermek için tamamı tutuluyor (ek istek YOK).
  const [flow, setFlow] = useState(null);
  const flowSummary = flow?.summary || null;
  // Net değer geçmişi. ÖLÇÜLDÜ (10 Eyl 2026): yeni kullanıcıda `items` BOŞ döner —
  // seriyi gece işi (NetWorthSnapshot) biriktirir. Bu yüzden kart "veri yoksa hiç
  // çizilmez": tek noktadan eğilim çizmek uydurmadır, iki nokta gerekir.
  const [netTrend, setNetTrend] = useState(null);
  // BUG #273: vadesi gelip de ÖNERİYE DÖNÜŞEMEYEN düzenli gelir/gider. Eskiden bu durum
  // yalnız sunucu log'una düşüyordu; kullanıcı kirasının önerilmediğini ay sonunda,
  // bakiyesi tutmayınca fark ederdi.
  const [atlananlar, setAtlananlar] = useState([]);

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
      // BUG #273: atlanan kayıtlar sessiz kalmaz
      setAtlananlar([...(dueIncome?.atlanan || []), ...(dueExpense?.atlanan || [])]);
    } catch (e) {
      setError(e.message || 'Cockpit yuklenemedi');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
    // YAN ÇAĞRILAR — cockpit yüklemesini asla devirmemeli.
    // `Promise.resolve().then(...)` sarmalı bilerek: `.catch()` yalnız DÖNEN sözü
    // yakalar, çağrının KENDİSİ senkron patlarsa (ör. uç tanımsız) hata sarmalanmadan
    // yükselir ve `load()`'un sözünü reddeder — panel sessizce yarım kalır. Ölçüldü
    // (10 Eyl 2026): testte sahte `reportsApi`de `netWorthTrend` yoktu ve 243 testin
    // hepsi geçtiği hâlde vitest 12 yakalanmamış hatayla kırmızı çıktı. Bir yan
    // çağrının hata yolu, ana akışın hata yolundan daha dayanıklı olmalı.
    const yanCagri = (fn, uygula) =>
      Promise.resolve().then(fn).then(uygula).catch(() => {});

    yanCagri(() => cashflowApi.getForecast({ days: 30 }), (r) => setFlow(r));
    yanCagri(() => reportsApi.netWorthTrend(30), (r) => setNetTrend(r?.items || []));
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
            <button type="button" onClick={handleRefresh} className="btn btn-secondary !text-xs mt-3">
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
  // Tam Net Değer alt-yazısı: hem +alacak hem −kişisel-borç şeffaf gösterilir (#116)
  const netTamDetay = [
    alacaklarToplami > 0 ? `+${formatPara(alacaklarToplami)} alacak` : null,
    borclarToplami > 0 ? `−${formatPara(borclarToplami)} kişisel borç` : null,
  ].filter(Boolean).join(', ');

  // BOŞ VE TEKRAR EDEN GÖSTERGE BASTIRILIR.
  // Ölçülen sorun (9 Eyl 2026, gerçek veriyle): detaylı görünümde beş stratejik
  // kartın İKİSİ sıfır (Emanet, Beklenen Gelir), ÜÇÜ aynı sayıyı gösteriyordu
  // (Reel Bütçe / Görülen Net Değer / Tam Net Değer — hepsi 5.630,00). Bilgi
  // taşımayan bir kart, bilgi taşıyan kartla AYNI görsel ağırlığı kaplayınca ekran
  // "çok şey var ama hiçbiri öne çıkmıyor" hissi veriyor. Ekranı yoran şey bilginin
  // çokluğu değil, boşluğun bilgi gibi durmasıydı.
  //
  // Kural: bir gösterge ancak BİR ŞEY SÖYLÜYORSA çizilir.
  //  - Sıfır bazen anlamlıdır ("kart borcun yok"), bazen gürültü ("hiç kartın yok").
  //    Ayrım hesabın VARLIĞINA bakılarak yapılır, sayıya değil.
  //  - İki net değer eşitse tek kart çizilir; ayrım ancak FARK varken bir şey anlatır.
  // Izgara sütun sayısı KART SAYISINA uyar. Sabit 4 sütun, iki kart kaldığında
  // sağ yarıyı boş bırakıyor ve ekran "bitmemiş" duruyordu (ölçüldü: boş/tekrar eden
  // kartlar bastırılınca 9 kart 4'e indi). Tailwind dinamik sınıf üretmez, bu yüzden
  // eşleme literal dizelerle yapılır.
  const gridSinif = (n) => ({
    1: 'grid-cols-1',
    2: 'grid-cols-2',
    3: 'grid-cols-2 lg:grid-cols-3',
    4: 'grid-cols-2 lg:grid-cols-4',
    5: 'grid-cols-2 lg:grid-cols-5',
  }[Math.min(n, 5)] || 'grid-cols-2 lg:grid-cols-4');

  const hesapTuru = (t) => (data.accounts || []).some((a) => a.account_type === t);
  const netAyrimVar = netDegerTam !== data.net_deger;
  // BUG #429 (DVIZ-005): kart altına "ay başından beri" farkı. Baz yoksa (ilk gün) hiç
  // çizilmez — sıfır fark uydurulmaz. Etiket bazın gerçek tarihini söyler.
  const dd = data.donem_degisimi;
  const degisim = (alan, azalmaIyi = false) => (dd && Number.isFinite(dd[alan])
    ? { tutar: dd[alan], azalmaIyi,
        etiket: dd.ay_basi ? 'ay başından beri' : `${formatDate(dd.baz_tarih)}'den beri` }
    : undefined);

  const operasyonel = [
    { anahtar: 'nakit', goster: true,
      alan: { title: 'Nakit', value: data.nakit_kasa, variant: 'positive', icon: Wallet,
              degisim: degisim('nakit_kasa') } },
    { anahtar: 'kart', goster: data.kart_borcu !== 0 || hesapTuru('credit_card'),
      alan: { title: 'Kart Borcu', value: data.kart_borcu, variant: 'negative', icon: CreditCard,
              degisim: degisim('kart_borcu', true) } },
    { anahtar: 'kredi', goster: data.kredi_borcu !== 0 || hesapTuru('loan'),
      alan: { title: 'Kredi Borcu', value: data.kredi_borcu, variant: 'negative', icon: Building2,
              degisim: degisim('kredi_borcu', true) } },
    { anahtar: 'yatirim', goster: data.yatirim_deger !== 0 || hesapTuru('investment'),
      alan: { title: 'Yatırım', value: data.yatirim_deger, variant: 'brand', icon: TrendingUp,
              degisim: degisim('yatirim_deger') } },
  ].filter((x) => x.goster);

  const stratejik = [
    { anahtar: 'emanet', goster: data.emanet_kasa > 0,
      alan: { title: 'Emanet', value: data.emanet_kasa, variant: 'warn', icon: Lock,
              isEmanet: true, subtitle: 'Net değere dahil değil',
              // BUG #424 (UX-022): taahhüt cihazı — dokunulmazlık kullanıcının KENDİ sözüdür,
              // koç ve yürütücü onu kural olarak uygular (MC1); bağlantı kuralın sayfasına.
              aciklama: 'Kendine söz: bu paraya dokunma. Emanet hesaplar sana ait değil (aile, kira depozitosu, birinin sende duran parası); koç bu hesaplardan harcama önermez, önerilirse yürütücü reddeder.',
              aciklamaBaglanti: setActiveTab ? { metin: 'Kırmızı çizgilerde gör →', onClick: () => setActiveTab('redlines') } : undefined } },
    { anahtar: 'gelir', goster: data.beklenen_gelir > 0,
      alan: { title: 'Beklenen Gelir', value: data.beklenen_gelir, variant: 'positive',
              icon: Banknote, subtitle: 'Bu ay sonuna kadar' } },
    { anahtar: 'butce', goster: true,
      alan: { title: 'Reel Bütçe', value: data.reel_butce, icon: Calculator,
              variant: data.reel_butce >= 0 ? 'positive' : 'negative',
              subtitle: 'Gölge muhasebe sonrası' } },
    { anahtar: 'net', goster: true,
      alan: { title: netAyrimVar ? 'Görülen Net Değer' : 'Net Değer', value: data.net_deger,
              icon: Scale, variant: data.net_deger >= 0 ? 'positive' : 'negative',
              subtitle: netAyrimVar ? 'Alacaksız (operasyonel)' : 'Varlıklar eksi borçlar',
              degisim: degisim('net_deger'),
              // BUG #423 (UX-021): ayrım yalnız detaylı görünümde çizilir; açıklama da orada
              aciklama: netAyrimVar
                ? 'Görülen = bugün cüzdanında ve hesaplarında fiilen olan. Sana borçlu olanların ödeyeceği para buna dahil değil.'
                : undefined } },
    { anahtar: 'nettam', goster: netAyrimVar,
      alan: { title: 'Tam Net Değer', value: netDegerTam, icon: Telescope,
              variant: netDegerTam >= 0 ? 'positive' : 'negative',
              degisim: degisim('net_deger_tam'),
              subtitle: `${netTamDetay} dahil`,
              aciklama: 'Tam = Görülen + sana borçlu olanların ödeyeceği para (alacaklar). Tahsil edilene kadar harcanabilir sayma.' } },
  ].filter((x) => x.goster);

  const tumKartlar = [...operasyonel, ...stratejik];

  // Hangi adanmış kartlar GERÇEKTEN çiziliyor? (sade görünümde ikisi de gizli)
  const kartKullanimCiziliyor = !basit && data.kart_kullanim
    && ['yuksek', 'kritik'].includes(data.kart_kullanim.band);
  const kartAsgariCiziliyor = !basit && data.asgari_tuzagi?.kartlar?.length > 0;
  const bastirilan = new Set([
    ...(kartKullanimCiziliyor ? KART_KARTI_OLAN_UYARILAR.kart_kullanim : []),
    ...(kartAsgariCiziliyor ? KART_KARTI_OLAN_UYARILAR.kart_asgari : []),
  ]);
  const tumUyarilar = data.alerts || [];
  const gorunurUyarilar = tumUyarilar.filter((a) => !bastirilan.has(a.kod));
  const tekrarBastirilan = tumUyarilar.length - gorunurUyarilar.length;
  // BUG #427 (UX-023): bildirim yorgunluğu — kritik olanlar HEP açık; kritik-dışı ilk
  // KATLANMADAN_GORUNEN açık, gerisi "+N uyarı daha" arkasında (kullanıcı açar, kapatır).
  const kritikUyarilar = gorunurUyarilar.filter((a) => a.seviye === 'kritik');
  const digerUyarilar = gorunurUyarilar.filter((a) => a.seviye !== 'kritik');
  const acikDiger = uyarilarAcik ? digerUyarilar : digerUyarilar.slice(0, KATLANMADAN_GORUNEN);
  const katlananSayi = digerUyarilar.length - acikDiger.length;
  const cizilecekUyarilar = [...kritikUyarilar, ...acikDiger];

  // Sade görünümün dört sayısı: param var mı · ne kadar borcum var · neredeyim.
  // Yatırım ve "Görülen/Tam" ayrımı burada yok — ikisi de kavram bilgisi ister.
  const sadeKartlar = [
    ...operasyonel.filter((x) => x.anahtar !== 'yatirim'),
    { anahtar: 'net',
      alan: { title: 'Net Değer', value: data.net_deger, icon: Scale,
              variant: data.net_deger >= 0 ? 'positive' : 'negative',
              subtitle: 'Varlıklar eksi borçlar', degisim: degisim('net_deger') } },
  ];

  // Sade görünümde GİZLENEN analiz bölümlerinin adları. Sayı ELLE yazılmıyor: yalnız
  // verisi olduğu için detaylı görünümde GERÇEKTEN çizilecek bölümler sayılır — yoksa
  // "8 bölüm gizli" yazan ama açınca 3 bölüm gösteren bir arayüz olurdu.
  // Bu liste sade görünümün dürüstlük kapısıdır: gizlemenin ne kadar gizlediğini
  // kullanıcı okur, keşfetmek zorunda kalmaz.
  const gizlenenBolumler = [
    ['Stratejik göstergeler (emanet, beklenen gelir, reel bütçe, tam net değer)', true],
    ['Aylık özet', true],
    ['Abonelik yükü', data.abonelik_yuku?.adet > 0],
    ['Borçsuzluk tarihi', !!data.borc_ozgurluk],
    ['Faiz sızıntısı', data.faiz_sizintisi?.aylik_toplam > 0],
    ['Kart kullanım oranı', ['yuksek', 'kritik'].includes(data.kart_kullanim?.band)],
    ['Alacak yaşlandırma', data.alacak_yaslanma?.gecikmis_adet > 0],
    ['Asgari ödeme tuzağı', data.asgari_tuzagi?.kartlar?.length > 0],
    ['Yatırım kâr/zarar', !!investmentPnl],
    ['30 günlük akış özeti', !!flowSummary],
    ['Ödeme takvimi (60 gün)', data.upcoming_payments?.length > 0],
    ['Tahsilat takvimi', data.upcoming_receivables?.length > 0],
    ['Fiyat tazeliği', data.price_freshness?.items?.length > 0
                       && !(data.price_freshness?.stale_count > 0)],
  ].filter(([, cizilir]) => cizilir).map(([ad]) => ad);


  // H20 (BUG #194): yeni kullanıcı yönlendirilir; verisi olanı rahatsız etmez.
  // BUG #262: "boş mu" ölçütü ARTIK burada değil — rehber 4 adımı backend'de sayar
  // (`/api/onboarding/rehber`) ve hepsi bitene kadar görünür kalır. `setActiveTab`
  // geçilmezse adım düğmeleri ölü bağlantıya döner, bu yüzden zorunlu.
  return (
    <div className="space-y-6 animate-fade-in">
      <Onboarding setActiveTab={setActiveTab} onDegisti={handleRefresh} />

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

      {/* BUGÜN HARCAYABİLECEĞİN — ekranın yıldızı.
          Eskiden bu kutu sayfanın ALTINCI bloğuydu: kullanıcının en sık sorduğu soruya
          ("bugün ne kadar harcayabilirim?") ancak dokuz kartı geçtikten sonra ulaşıyordu.
          Yer değişikliği her iki görünüm için de geçerli — detay isteyen kullanıcı da bu
          sayıyı önce görmek ister, farkı aşağıda ne kadar devam ettiğidir.
          `guvenli_harcama` ve `nakit_runway_gun` satırları yalnız detaylı görünümde:
          ikisi de ileriye dönük PROJEKSİYON, bugünün kararı değil. */}
      <div className="card p-5 sm:p-6 border-brand-200 dark:border-brand-800/50
                      bg-gradient-to-br from-brand-50 via-white to-white
                      dark:from-brand-950/40 dark:via-zinc-900 dark:to-zinc-900">
        <h3 className="bolum-etiket">Bugün harcayabileceğin</h3>
        <p className="para text-4xl sm:text-5xl font-bold leading-none mt-1.5
                      text-brand-700 dark:text-brand-300">
          {formatPara(data.today_target)}
        </p>
        <p className="text-xs text-zinc-600 dark:text-zinc-400 mt-2">
          Ay sonuna {data.days_remaining} gün · Günlük limit {formatPara(data.daily_limit)}
          {data.carried_forward !== 0 && (
            <span className={signClass(data.carried_forward)}>
              {' '}· Devreden {data.carried_forward > 0 ? '+' : ''}{formatPara(data.carried_forward)}
            </span>
          )}
        </p>

        {/* İKİNCİ SAYI (kullanıcı bildirimi, 10 Eyl 2026): üstteki sayı MC4 gereği kart
            borcunun TAMAMINI düşer — bir stok ile bir akışı aynı kefeye koyar. Bu satır
            "bu ay kasandan ne çıkacak"ı söyler. Kurucu kural bozulmadı, bilgi saklanmadı.
            Her iki görünümde de kalır: sadeleştirme, riski gizlemek değildir. */}
        <BuAyCikacak takvim={data.nakit_takvimi} gunKaldi={data.days_remaining} />

        {/* Dökümün GÖRSEL hâli: hangi kalem baskın, tek bakışta. Sayı listesi altta
            katlı duruyor — şerit oranı, liste gerçeği verir. */}
        <ButceSeridi dokum={data.butce_dokum} />

        {/* FEAT-030: günlük limitin açık dökümü. Sade görünümde de KALIR — "bu sayı
            nereden geliyor?" sorusu, finansa yeni olan kullanıcının ilk sorusudur. */}
        <BudgetBreakdown dokum={data.butce_dokum} />

        {/* Zikzak projeksiyonu — bugün harcamazsan yarınki limit yükselir. */}
        {data.yarin_limit_harcamasiz > data.daily_limit && (
          <p className="text-xs text-positive-700 dark:text-positive-400 mt-1.5 flex items-center gap-1">
            <Waves className="w-3.5 h-3.5 shrink-0" />
            Bugün harcamazsan yarın limitin {formatPara(data.yarin_limit_harcamasiz)}/gün'e çıkar
          </p>
        )}

        {!basit && data.guvenli_harcama !== undefined && (
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5 flex items-center gap-1">
            <Lock className="w-3.5 h-3.5 shrink-0" />
            Güvenli harcama (90g öngörü, kart borcu düşülmüş):{' '}
            <span className={`font-numeric font-semibold ${data.guvenli_harcama > 0 ? 'text-zinc-700 dark:text-zinc-200' : 'text-negative-600 dark:text-negative-400'}`}>
              {formatPara(data.guvenli_harcama)}
            </span>
          </p>
        )}
        {!basit && data.nakit_runway_gun !== undefined && data.nakit_runway_gun !== null && (
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5 flex items-center gap-1">
            <Clock className="w-3.5 h-3.5 shrink-0" />
            Nakit runway:{' '}
            <span className={`font-numeric font-semibold ${data.nakit_runway_gun >= 30 ? 'text-zinc-700 dark:text-zinc-200' : 'text-negative-600 dark:text-negative-400'}`}>
              {data.nakit_runway_gun} gün
            </span>
            <span className="text-zinc-500"> (gelirsiz, 30g harcama hızıyla)</span>
          </p>
        )}
      </div>

      {/* FEAT-041: deterministik İLK ADIM — tüm sinyallerin tek en-yüksek-etkili hamlesi */}
      {data.sonraki_eylem && (() => {
        const se = data.sonraki_eylem;
        const style = {
          temerrut: 'border-negative-400 dark:border-negative-600 bg-negative-50 dark:bg-negative-950/40',
          kriz:     'border-negative-400 dark:border-negative-600 bg-negative-50 dark:bg-negative-950/40',
          tahsilat: 'border-warn-400 dark:border-warn-600 bg-warn-50 dark:bg-warn-950/40',
          firsat:   'border-brand-400 dark:border-brand-600 bg-brand-50 dark:bg-brand-950/40',
          stabil:   'border-zinc-300 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-900/40',
        }[se.tip] || 'border-zinc-300 dark:border-zinc-700';
        return (
          <div className={`card p-4 border-2 ${style}`}>
            <div className="flex items-start gap-3">
              <Target className="w-5 h-5 text-brand-600 dark:text-brand-400 shrink-0 mt-0.5" />
              <div className="min-w-0">
                <div className="text-xs font-semibold uppercase tracking-wide text-zinc-500 dark:text-zinc-400 mb-0.5">
                  İlk adım
                </div>
                <div className="font-semibold text-zinc-800 dark:text-zinc-100">{se.eylem}</div>
                <div className="text-sm text-zinc-600 dark:text-zinc-300 mt-0.5">{se.gerekce}</div>
              </div>
            </div>
          </div>
        );
      })()}

      {/* BUG #273: vadesi geldiği hâlde öneriye dönüşemeyen düzenli kayıtlar */}
      {atlananlar.length > 0 && (
        <div
          data-testid="atlanan-duzenli-kayitlar"
          className="card p-4 border-warn-500 dark:border-warn-600 bg-warn-50 dark:bg-warn-950/30"
        >
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-warn-600 dark:text-warn-400 flex-shrink-0" />
            <div className="min-w-0">
              {/* BUG #265 kapısı: her iki temada da ≥3:1 kontrast */}
              <h3 className="font-semibold text-sm text-warn-700 dark:text-warn-300">
                Vadesi gelen {atlananlar.length} düzenli kayıt öneriye dönüşemedi
              </h3>
              <ul className="mt-1 space-y-1 text-sm text-zinc-700 dark:text-zinc-300">
                {atlananlar.map((a, i) => (
                  <li key={a.id ?? `atlanan-${i}`}>
                    {a.ad ? <span className="font-medium">{a.ad}: </span> : null}
                    {a.neden}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Bekleyen aksiyonlar */}
      {pendingActions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold mb-2 text-brand-600 dark:text-brand-400">
            Onay bekleyen aksiyonlar ({pendingActions.length})
          </h3>
          <PendingActions actions={pendingActions} onResolved={handleActionResolved} accounts={data?.accounts} />
        </div>
      )}

      {/* GÖSTERGELER — listeden çizilir; boş/tekrar eden kart hiç doğmaz.
          Grup başlığı da bedava değil: toplam dört karta kadar TEK satır çizilir ve
          "Operasyonel / Stratejik" etiketleri hiç görünmez. İki kartın üstüne başlık
          koymak, sınıflandırdığından daha çok yer kaplar. */}
      {basit ? (
        <div className={`grid gap-3 sm:gap-4 ${gridSinif(sadeKartlar.length)}`}>
          {sadeKartlar.map((x) => <MetricCard key={x.anahtar} {...x.alan} />)}
        </div>
      ) : tumKartlar.length <= 4 ? (
        <div className={`grid gap-3 sm:gap-4 ${gridSinif(tumKartlar.length)}`}>
          {tumKartlar.map((x) => <MetricCard key={x.anahtar} {...x.alan} />)}
        </div>
      ) : (
        <>
          {operasyonel.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Eye className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
                <h3 className="bolum-etiket">Operasyonel manzara</h3>
              </div>
              <div className={`grid gap-3 sm:gap-4 ${gridSinif(operasyonel.length)}`}>
                {operasyonel.map((x) => <MetricCard key={x.anahtar} {...x.alan} />)}
              </div>
            </div>
          )}

          {stratejik.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Telescope className="w-4 h-4 text-zinc-500 dark:text-zinc-400" />
                <h3 className="bolum-etiket">Stratejik manzara</h3>
              </div>
              <div className={`grid gap-3 sm:gap-4 ${gridSinif(stratejik.length)}`}>
                {stratejik.map((x) => <MetricCard key={x.anahtar} {...x.alan} />)}
              </div>
            </div>
          )}
        </>
      )}

      {/* FEAT-022: finansal sağlık skoru — şeffaf composite capstone */}
      {data.saglik_skoru && (() => {
        const sk = data.saglik_skoru;
        const barCls = sk.seviye === 'iyi' ? 'bg-positive-500' : sk.seviye === 'orta' ? 'bg-warn-500' : 'bg-negative-500';
        const txtCls = sk.seviye === 'iyi' ? 'text-positive-600 dark:text-positive-400' : sk.seviye === 'orta' ? 'text-warn-600 dark:text-warn-400' : 'text-negative-600 dark:text-negative-400';
        return (
          <div className="card p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-zinc-600 dark:text-zinc-300">Finansal Sağlık</span>
              <span className={`font-numeric font-bold text-2xl ${txtCls}`}>
                {sk.skor}<span className="text-sm text-zinc-500">/100</span>
              </span>
            </div>
            <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
              <div className={`h-full rounded-full ${barCls}`} style={{ width: `${sk.skor}%` }} />
            </div>
            {/* Bileşenler: gri rozet yığını yerine KATKI ÇUBUĞU.
                Rozetler ("Ödeme gücü 100 · Nakit tamponu 48 · Kart sağlığı 20") hangi
                bileşenin skoru aşağı çektiğini söylemiyordu — üç eşit gri kutu, üç
                farklı gerçek. Çubukta her bileşen kendi puanı kadar dolar; boş kalan
                kısım kaybedilen puandır ve göz doğrudan oraya gider.
                Sade görünümde yine yalnız skor kalır (bileşen dökümü uzman bilgisi). */}
            {!basit && (
              <div className="mt-3 space-y-1.5">
                {sk.bilesenler.map((b) => {
                  const p = Math.max(0, Math.min(100, Number(b.puan) || 0));
                  const renk = p >= 70 ? 'bg-positive-500'
                    : p >= 40 ? 'bg-warn-500' : 'bg-negative-500';
                  return (
                    <div key={b.ad} className="flex items-center gap-2">
                      <span className="text-[11px] text-zinc-600 dark:text-zinc-400
                                       w-28 shrink-0 truncate" title={b.ad}>{b.ad}</span>
                      <span className="flex-1 h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-700
                                       overflow-hidden">
                        <span className={`block h-full rounded-full ${renk}`}
                              style={{ width: `${p}%` }} />
                      </span>
                      <span className="font-numeric text-[11px] w-7 text-right
                                       text-zinc-600 dark:text-zinc-400">{b.puan}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })()}

      {/* A3: Aylık özet — kurucu "durum raporu" */}
      {!basit && <MonthlySummary />}
      {/* BUG #428 (DVIZ-004/FEAT-023): ay-be-ay seri — özetin zaman içindeki hali; sade görünümde yok */}
      {!basit && <AylikSeri months={6} />}

      {/* SİNYALLER — üç tek-satırlık bilgi, ÜÇ AYRI KUTU değil.
          Ölçülen sorun: abonelik yükü, borçsuzluk tarihi ve faiz sızıntısı; her biri
          tek cümlelik bilgi olduğu hâlde tam genişlikte ayrı birer kart kaplıyordu.
          Kutu, içindekinden çok yer tutunca ekran "çok şey var" der ama söylediği şey
          artmaz. Üçü tek kartta satır oldu; içerik ve renkleri aynı kaldı, yalnız
          kutu sayısı 3'ten 1'e indi. Kart kullanım oranı ve asgari tuzağı BU KARTA
          ALINMADI: ikisi de çubuk/liste taşıyor, tek satır değil. */}
      {!basit && (data.abonelik_yuku?.adet > 0 || data.borc_ozgurluk
                  || data.faiz_sizintisi?.aylik_toplam > 0) && (
        <div className="card divide-y divide-zinc-100 dark:divide-zinc-800">
          {data.abonelik_yuku?.adet > 0 && (
            <div className="flex items-center gap-2 px-4 py-2.5 text-sm">
              <RefreshCw className="w-4 h-4 text-zinc-500 dark:text-zinc-400 shrink-0" />
              <span className="text-zinc-600 dark:text-zinc-300">
                {data.abonelik_yuku.adet} abonelik ·{' '}
                <span className="font-numeric font-semibold">{formatPara(data.abonelik_yuku.aylik)}</span>/ay
                <span className="text-zinc-500"> ({formatPara(data.abonelik_yuku.yillik)}/yıl)</span>
              </span>
            </div>
          )}

          {data.borc_ozgurluk && (
            <div className="flex items-center gap-2 px-4 py-2.5 text-sm">
              <Target className="w-4 h-4 text-brand-600 dark:text-brand-400 shrink-0" />
              <span className="text-zinc-600 dark:text-zinc-300">
                {data.borc_ozgurluk.asla_bitmez
                  ? 'Minimum ödemelerle borç makul sürede kapanmıyor — ek ödeme şart.'
                  : <>Borçsuzluk: <span className="font-semibold">{data.borc_ozgurluk.kalan_ay} ay</span>
                      {data.borc_ozgurluk.borcsuz_tarih && <span className="text-zinc-500"> (≈{formatDate(data.borc_ozgurluk.borcsuz_tarih)})</span>}
                      <span className="text-zinc-500"> · kalan faiz {formatPara(data.borc_ozgurluk.toplam_faiz)}</span></>}
              </span>
            </div>
          )}

          {data.faiz_sizintisi?.aylik_toplam > 0 && (
            <div className="flex items-center gap-2 px-4 py-2.5 text-sm">
              <AlertTriangle className="w-4 h-4 text-negative-500 shrink-0" />
              <span className="text-zinc-600 dark:text-zinc-300">
                Faize giden:{' '}
                <span className="font-numeric font-semibold text-negative-600 dark:text-negative-400">{formatPara(data.faiz_sizintisi.aylik_toplam)}</span>/ay
                <span className="text-zinc-500"> ({formatPara(data.faiz_sizintisi.yillik_toplam)}/yıl · günde {formatPara(data.faiz_sizintisi.gunluk)})</span>
              </span>
            </div>
          )}
        </div>
      )}

      {/* FEAT-016: kart kullanım oranı (utilization) + kredi sağlığı — yalnız yüksek/kritik bantta */}
      {!basit && data.kart_kullanim && ['yuksek', 'kritik'].includes(data.kart_kullanim.band) && (() => {
        const ku = data.kart_kullanim;
        const pct = Math.min(100, ku.oran);
        const barColor = ku.band === 'kritik' ? 'bg-negative-500' : 'bg-warn-500';
        const txtColor = ku.band === 'kritik' ? 'text-negative-600 dark:text-negative-400' : 'text-warn-600 dark:text-warn-400';
        const tr = ku.trend;
        return (
          <div className="card p-3 space-y-2 text-sm border-negative-200 dark:border-negative-800/50">
            <div className="flex items-center gap-2">
              <CreditCard className="w-4 h-4 text-zinc-500 dark:text-zinc-400 shrink-0" />
              <span className="text-zinc-600 dark:text-zinc-300">
                Kart kullanımı{' '}
                <span className={`font-numeric font-semibold ${txtColor}`}>%{ku.oran}</span>
                <span className="text-zinc-500"> ({formatSayi(ku.toplam_borc)} / {formatPara(ku.toplam_limit)})</span>
                {/* BUG #425 (UX-003): oranın yanında somut mesafe — "limite ne kadar kaldı" */}
                {Number.isFinite(ku.toplam_limit - ku.toplam_borc) && (
                  <span className={`text-xs ${txtColor}`}> · limite {formatPara(Math.max(0, ku.toplam_limit - ku.toplam_borc))} kaldı</span>
                )}
              </span>
              {tr && (
                <span className={`ml-auto text-xs font-numeric ${tr.iyilesme ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400'}`}>
                  {tr.iyilesme ? '↓' : '↑'} {tr.degisim > 0 ? '+' : ''}{tr.degisim} puan / {tr.gun}g
                </span>
              )}
            </div>
            <div className="h-2 rounded-full bg-zinc-200 dark:bg-zinc-700 overflow-hidden">
              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${pct}%` }} />
            </div>
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              Sağlıklı eşik %30 — borç <span className="font-numeric">{formatPara(ku.saglikli_borc_hedefi)}</span> seviyesine inmeli.
              Kullanım oranı kredi notunda en ağır faktörlerden; her ödenen {paraEtiketi()} doğrudan düşürür.
            </p>
          </div>
        );
      })()}

      {/* FEAT-027: alacak yaşlandırma — gecikmiş alacakları vade-yaşına göre önceliklendir */}
      {!basit && data.alacak_yaslanma?.gecikmis_adet > 0 && (
        <div className="card p-3 flex items-start gap-2 text-sm border-warn-200 dark:border-warn-800/50">
          <Users className="w-4 h-4 text-warn-600 dark:text-warn-500 shrink-0 mt-0.5" />
          <div className="text-zinc-600 dark:text-zinc-300 space-y-0.5">
            <div>
              <span className="font-semibold">{data.alacak_yaslanma.gecikmis_adet} gecikmiş alacak</span>{' '}
              <span className="font-numeric font-semibold text-warn-600 dark:text-warn-400">{formatPara(data.alacak_yaslanma.toplam_gecikmis)}</span>
              <span className="text-zinc-500"> / {data.alacak_yaslanma.adet} alacak</span>
            </div>
            {data.alacak_yaslanma.en_riskli?.length > 0 && (
              <div className="text-zinc-500 text-xs">
                Önce kovala: {data.alacak_yaslanma.en_riskli.map((k) => `${k.kim} ${formatPara(k.tutar)} (${k.gecikme_gun}g)`).join(' · ')}
              </div>
            )}
          </div>
        </div>
      )}

      {/* FEAT-015: kart asgari-ödeme tuzağı — sadece asgari ödeme senaryosu (görünmez maliyet) */}
      {!basit && data.asgari_tuzagi?.kartlar?.length > 0 && (
        <div className="card p-3 flex items-start gap-2 text-sm border-warn-200 dark:border-warn-800/50">
          <AlertTriangle className="w-4 h-4 text-warn-600 dark:text-warn-500 shrink-0 mt-0.5" />
          <div className="text-zinc-600 dark:text-zinc-300 space-y-0.5">
            {data.asgari_tuzagi.kartlar.slice(0, 2).map((k, i) => (
              <div key={i}>
                {k.asla_bitmez
                  ? <><span className="font-semibold">{k.ad}</span>: yalnız asgariyle <span className="font-semibold text-negative-600 dark:text-negative-400">asla kapanmaz</span> (asgari &lt; faiz)</>
                  : <><span className="font-semibold">{k.ad}</span> asgari-ödeme tuzağı: <span className="font-semibold">{k.ay} ay</span> · faiz{' '}
                      <span className="font-numeric font-semibold text-negative-600 dark:text-negative-400">{formatPara(k.toplam_faiz)}</span>
                      {k.payoff_tarih && <span className="text-zinc-500"> (biter ≈{formatDate(k.payoff_tarih)})</span>}</>}
              </div>
            ))}
            <div className="text-zinc-500 text-xs">Asgarinin üstüne her ek ödeme süreyi ve toplam faizi hızla düşürür.</div>
          </div>
        </div>
      )}

      {/* Uyarılar — adanmış kartı çizilen konular BURADA TEKRARLANMAZ (bkz. dosya
          başındaki kural). Bastırılan uyarı sayısı `gizliUyari` ile birlikte sayılır:
          ekrandan bir şey kalkıyorsa kaç tane kalktığı söylenmeli. */}
      {gorunurUyarilar.length > 0 && (
        <div className="space-y-2">
          {cizilecekUyarilar.map((alert, i) => (
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
          {(katlananSayi > 0 || (uyarilarAcik && digerUyarilar.length > KATLANMADAN_GORUNEN)) && (
            <button type="button" onClick={() => setUyarilarAcik((a) => !a)}
                    aria-expanded={uyarilarAcik}
                    className="btn btn-ghost !text-xs w-full justify-center">
              {uyarilarAcik ? 'Daha az uyarı göster' : `+${katlananSayi} uyarı daha`}
            </button>
          )}
          {/* #126: sığmayan uyarılar — alert yorgunluğu için gizlenenlerin sayısı */}
          {(data.gizli_uyari_sayisi > 0 || tekrarBastirilan > 0) && (
            <p className="text-xs text-zinc-500 text-center pt-1">
              {data.gizli_uyari_sayisi > 0 && `+${data.gizli_uyari_sayisi} düşük öncelikli uyarı daha`}
              {data.gizli_uyari_sayisi > 0 && tekrarBastirilan > 0 && ' · '}
              {tekrarBastirilan > 0 && `${tekrarBastirilan} uyarı aşağıdaki kartlarda ayrıntılı gösteriliyor`}
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
      {!basit && investmentPnl && (
        /* Sadeleştirme: dört alt-kalem katlanır ama SONUÇ (brüt kâr + getiri) özet
           olarak başlıkta kalır — kullanıcı açmadan da kârda mı zararda mı bilir. */
        <KatlanirBolum
          ikon={TrendingUp}
          baslik="Yatırım Kâr/Zarar"
          anahtar="cockpit_yatirim_kz"
          ozet={`${investmentPnl.brut_kar > 0 ? '+' : ''}${formatPara(investmentPnl.brut_kar)}`
                + ` · ${formatPercent(investmentPnl.getiri_yuzde)}`}
        >
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Toplam maliyet</p>
              <p className="font-numeric font-semibold">{formatPara(investmentPnl.toplam_maliyet)}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Güncel değer</p>
              <p className="font-numeric font-semibold">{formatPara(investmentPnl.guncel_deger)}</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Brüt kâr</p>
              <p className={`font-numeric font-semibold ${signClass(investmentPnl.brut_kar)}`}>
                {investmentPnl.brut_kar > 0 ? '+' : ''}
                {formatPara(investmentPnl.brut_kar)}
              </p>
            </div>
            <div>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-1">Getiri</p>
              <p className={`font-numeric font-semibold ${signClass(investmentPnl.getiri_yuzde)}`}>
                {formatPercent(investmentPnl.getiri_yuzde)}
              </p>
            </div>
          </div>
        </KatlanirBolum>
      )}

      {/* NET DEĞER SEYRİ — geçmişin şekli.
          Veri `reports/net-worth-trend`'ten gelir ve gece işinin biriktirdiği
          NetWorthSnapshot kayıtlarına dayanır. İKİ noktadan azsa kart HİÇ çizilmez:
          tek ölçümden "eğilim" üretmek, olmayan bir bilgiyi varmış gibi göstermektir.
          Sade görünümde de durur — net değerin yönü analiz değil, temel sinyaldir. */}
      {netTrend && netTrend.length >= 2 && (() => {
        const ilk = Number(netTrend[0].net_worth_seen) || 0;
        const son = Number(netTrend[netTrend.length - 1].net_worth_seen) || 0;
        const fark = son - ilk;
        return (
          <div className="card p-4">
            <div className="flex items-baseline justify-between gap-3 mb-1">
              <h3 className="bolum-etiket">Net değer · son {netTrend.length} ölçüm</h3>
              <span className={`para text-sm font-semibold ${signClass(fark)}`}>
                {fark >= 0 ? '+' : ''}{formatPara(fark)}
              </span>
            </div>
            <AkisSparkline gunler={netTrend} degerAlani="net_worth_seen"
                           renk={fark >= 0 ? 'brand' : 'negative'} yukseklik={52} />
            <p className="mt-1 text-[11px] text-zinc-500 dark:text-zinc-400">
              {formatDate(netTrend[0].date)} → {formatDate(netTrend[netTrend.length - 1].date)}
            </p>
          </div>
        );
      })()}

      {/* AKIŞ — 30 günlük bakiye SEYRİ (üç sayı değil, şekil).
          Veri zaten çekiliyordu; günlük seri atılıyordu (bkz. `flow` state). Üç sayı
          "önümüzdeki ay nasıl geçecek" sorusunu cevaplamıyordu: para ne zaman dibe
          vuruyor, ne zaman toparlıyor — bunu ancak eğri söyler. Sayılar kalktı DEĞİL,
          çizginin altına tek satıra indi. */}
      {!basit && flowSummary && (
        <div className="card p-4">
          <div className="flex items-center justify-between gap-2 mb-2">
            <div className="flex items-center gap-2">
              <Waves className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              <h3 className="font-semibold text-sm">Önümüzdeki 30 gün</h3>
            </div>
            {setActiveTab && (
              <button
                onClick={() => setActiveTab('cashflow')}
                className="flex items-center gap-1 text-xs text-brand-600 dark:text-brand-400 hover:underline min-h-[44px] px-1"
              >
                Detay <ArrowRight className="w-3 h-3" />
              </button>
            )}
          </div>

          <AkisSparkline gunler={flow?.days} yukseklik={64} />

          <div className="flex flex-wrap items-center gap-x-5 gap-y-1 mt-2 text-xs
                          text-zinc-600 dark:text-zinc-300">
            <span>
              En düşük{' '}
              <span className={`font-numeric font-semibold ${flowSummary.lowest_balance >= 0
                ? 'text-zinc-800 dark:text-zinc-100' : 'text-negative-600 dark:text-negative-400'}`}>
                {formatPara(flowSummary.lowest_balance)}
              </span>
              <span className="text-zinc-500"> · {formatDate(flowSummary.lowest_date)}</span>
            </span>
            <span>
              Net akış{' '}
              <span className={`font-numeric font-semibold ${signClass(flowSummary.net_flow)}`}>
                {flowSummary.net_flow > 0 ? '+' : ''}{formatPara(flowSummary.net_flow)}
              </span>
            </span>
            {flowSummary.crunch_count > 0 && (
              <span className="text-negative-600 dark:text-negative-400">
                <span className="font-numeric font-semibold">{flowSummary.crunch_count}</span> sıkışma günü
              </span>
            )}
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
                    {sign}{formatPara(r.amount)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Takvim 2 sütun */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {!basit && data.upcoming_payments?.length > 0 && (
          /* Sadeleştirme: 60 günlük ödeme takvimi PLANLAMA bilgisidir, acil değil —
             katlı gelir. Özet başlıkta kaldığı için bilgi eksilmez (kalem sayısı +
             toplam net etki görünür). */
          <KatlanirBolum
            ikon={Calendar}
            baslik="Yaklaşan ödemeler"
            anahtar="cockpit_odemeler"
            ozet={`${data.upcoming_payments.length} kalem · ${formatPara(
              data.upcoming_payments.reduce(
                (t, p) => t + (p.tip === 'gelir' ? Number(p.tutar) : -Number(p.tutar)), 0))}`}
          >
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
                    {formatPara(p.tutar)}
                  </span>
                </div>
              ))}
            </div>
          </KatlanirBolum>
        )}

        {!basit && data.upcoming_receivables?.length > 0 && (
          <KatlanirBolum
            ikon={Users}
            baslik="Yaklaşan tahsilatlar"
            anahtar="cockpit_tahsilatlar"
            ozet={`${data.upcoming_receivables.length} kalem · +${formatPara(
              data.upcoming_receivables.reduce((t, r) => t + Number(r.tutar), 0))}`}
          >
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
                    +{formatPara(r.tutar)}
                  </span>
                </div>
              ))}
            </div>
          </KatlanirBolum>
        )}
      </div>

      {/* Fiyat tazeliği */}
      {/* Bayat fiyat, ekrandaki yatırım sayılarını YANLIŞ yapar — bu bir veri
          kalitesi riskidir, analiz süsü değil. O yüzden `stale_count > 0` ise bölüm
          sade görünümde de kalır. */}
      {(!basit || data.price_freshness?.stale_count > 0)
        && data.price_freshness?.items?.length > 0 && (
        /* Sadeleştirme: operasyonel bir liste — normalde katlı. AMA bayat fiyat varsa
           `vurgu` rozeti katlıyken de görünür (BUG #239 sınıfı: tazelik sessizce
           kaybolmamalı) ve bölüm kendiliğinden açık gelir. */
        <KatlanirBolum
          ikon={Clock}
          baslik="Fiyat tazeliği"
          anahtar="cockpit_fiyat_tazeligi"
          varsayilanAcik={data.price_freshness.stale_count > 0}
          vurgu={data.price_freshness.stale_count > 0
            ? `${data.price_freshness.stale_count} eski` : null}
          ozet={`${data.price_freshness.items.length} yatırım hesabı`}
        >
          <div className="space-y-1.5">
            {data.price_freshness.items.map((item) => (
              <div key={item.account_id} className="flex items-center justify-between text-xs">
                <span className="text-zinc-700 dark:text-zinc-300">
                  {item.name}
                  {item.is_emanet && (
                    <Lock className="inline w-3 h-3 ml-1 text-warn-600 dark:text-warn-500" />
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
        </KatlanirBolum>
      )}

      {/* SADE GÖRÜNÜMÜN DÜRÜSTLÜK SATIRI.
          Sadeleştirme, gizlediğini söylemediği anda bilgi eksiltmeye döner. Bu kart
          kaç bölümün ve HANGİ bölümlerin gizlendiğini yazar, geçişi de tek tık yapar.
          Sayı elle değil, gerçekten çizilecek bölümler sayılarak üretilir. */}
      {basit && gizlenenBolumler.length > 0 && (
        <div className="card card-interaktif p-4">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">
                Sade görünümdesin — {gizlenenBolumler.length} analiz bölümü gizli
              </h3>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1 leading-relaxed">
                {gizlenenBolumler.join(' · ')}
              </p>
              <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-1.5">
                Uyarılar, onay bekleyen aksiyonlar ve hesap durumun sade görünümde de gizlenmez.
              </p>
            </div>
            <button
              type="button"
              onClick={() => degistir(DETAYLI)}
              className="btn btn-secondary !text-xs flex-shrink-0"
            >
              Detaylı görünüme geç <ArrowRight className="w-3.5 h-3.5" />
            </button>
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
  // BUG #396 (A11Y-001): rol/başlık bağı + odak/Escape/Tab döngüsü tek kaynaktan.
  const baslikId = useId();
  const kutuRef = useRef(null);
  const onCloseRef = useRef(onClose); onCloseRef.current = onClose;
  useDialog(kutuRef, onCloseRef);
  const [newPrice, setNewPrice] = useState(account.fiyat?.toString() || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const price = parseTRNumber(newPrice); // W3-001
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
      <div ref={kutuRef} role="dialog" aria-modal="true" aria-labelledby={baslikId} tabIndex={-1}
        className="card p-6 w-full max-w-md outline-none" onClick={(e) => e.stopPropagation()}>
        <h3 id={baslikId} className="font-semibold mb-1">Fiyat güncelle</h3>
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
            Yeni fiyat ({paraEtiketi()})
          </label>
          <input
            type="text" inputMode="decimal"
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
            <button aria-busy={busy} type="submit" disabled={busy} className="btn btn-primary flex-1">
              {busy && <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />}{'Kaydet'}
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