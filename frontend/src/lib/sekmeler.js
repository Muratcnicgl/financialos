/**
 * SEKMELER — panel listesinin TEK KAYNAĞI.
 *
 * Neden tek kaynak: liste üç yerde ayrı ayrı yazılıydı — `App.jsx` (TABS),
 * `CommandPalette.jsx` (COMMANDS) ve `hooks/useKeyboardShortcuts.js` (TAB_IDS).
 * Üçü zaten ayrışmıştı: palette'te "Aile" ve "Hesap" HİÇ YOKTU, yani o iki panele
 * Cmd+K ile ulaşılamıyordu. Bir listeyi üç kez yazmak, üçünün de eksik olmasıyla
 * biter; ayrıca görünüm modu bu listeyi kısaltacağı için dördüncü bir kopya daha
 * doğacaktı.
 *
 * `temel` alanı: basit görünümde çizilen çekirdek sekmeler. Seçim ölçütü "az olsun"
 * değil, GÜNLÜK KARAR için gereken şey: bugün ne kadar harcayabilirim (özet),
 * param nerede (hesaplar), ne harcadım (işlemler), soru sorabileceğim biri (koç),
 * ayarlarım (hesap). Kalan sekmeler yok olmaz — detaylı görünümde ve her iki modda
 * komut paletinde durur.
 */
import {
  Activity, MessageSquare, Wallet, Receipt, TrendingUp, ShieldAlert,
  BarChart3, Waves, CreditCard, Target, PiggyBank, Users, UserCog,
} from 'lucide-react';

export const SEKMELER = [
  // basitEtiket: "Cockpit" havacılık terimidir; finansa yeni birine hiçbir şey
  // anlatmaz. Basit görünümde panelin adı ne yaptığıdır.
  { id: 'cockpit',      label: 'Cockpit',          basitEtiket: 'Özet', icon: Activity,      temel: true,  komut: 'Cockpit\'e geç' },
  { id: 'coach',        label: 'Koç',              icon: MessageSquare, temel: true,  komut: 'Koç\'a geç' },
  { id: 'accounts',     label: 'Hesaplar',         icon: Wallet,        temel: true,  komut: 'Hesaplar\'a geç' },
  { id: 'transactions', label: 'İşlemler',         icon: Receipt,       temel: true,  komut: 'İşlemler\'e geç' },
  { id: 'incomedebt',   label: 'Gelir & Borç',     icon: TrendingUp,    temel: false, komut: 'Gelir & Borç\'a geç' },
  { id: 'redlines',     label: 'Kırmızı Çizgiler', icon: ShieldAlert,   temel: false, komut: 'Kırmızı Çizgiler\'e geç' },
  { id: 'reports',      label: 'Raporlar',         icon: BarChart3,     temel: false, komut: 'Raporlar\'a geç' },
  { id: 'cashflow',     label: 'Akış',             icon: Waves,         temel: false, komut: 'Nakit Akışı\'na geç' },
  { id: 'debtstrategy', label: 'Borç Stratejisi',  icon: CreditCard,    temel: false, komut: 'Borç Stratejisi\'ne geç' },
  { id: 'goals',        label: 'Hedefler',         icon: Target,        temel: false, komut: 'Hedefler\'e geç' },
  { id: 'budget',       label: 'Bütçe',            icon: PiggyBank,     temel: false, komut: 'Bütçe\'ye geç' },
  { id: 'workspace',    label: 'Aile',             icon: Users,         temel: false, komut: 'Aile\'ye geç' },
  { id: 'hesap',        label: 'Hesap',            icon: UserCog,       temel: true,  komut: 'Hesap\'a geç' },
];

/** Sekme çubuğunda çizilecekler. Basit modda yalnız çekirdek. */
export function gorunurSekmeler(basit) {
  return basit ? SEKMELER.filter((s) => s.temel) : SEKMELER;
}

/** Moda göre sekme adı — basit modda daha anlaşılır bir ad varsa o kullanılır. */
export function sekmeEtiketi(sekme, basit) {
  return basit && sekme.basitEtiket ? sekme.basitEtiket : sekme.label;
}

/**
 * Belge başlığı (BUG #392 / A11Y-017, WCAG 2.4.2): sekme değişince `document.title` de
 * değişir — ekran okuyucu ve tarayıcı geçmişi "hangi paneldeyim"i buradan okur. Tek
 * kaynak yine SEKMELER; bilinmeyen id'de yalnız ürün adı.
 */
export const URUN_ADI = 'FinancialOS';
export function sayfaBasligi(sekmeId, basit) {
  const sekme = SEKMELER.find((s) => s.id === sekmeId);
  return sekme ? `${sekmeEtiketi(sekme, basit)} · ${URUN_ADI}` : URUN_ADI;
}

/**
 * Cmd/Ctrl+1..9 sırası. Basit modda kısayol GÖRÜNEN sekmelere bağlanır: kullanıcıyı
 * çubukta olmayan bir panele ışınlayan kısayol, aktif sekmesi görünmeyen bir arayüz
 * bırakır.
 */
export function kisayolSirasi(basit) {
  return gorunurSekmeler(basit).map((s) => s.id);
}
