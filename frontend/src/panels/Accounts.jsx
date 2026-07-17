import { useState, useEffect, useCallback } from 'react';
import {
  Wallet, CreditCard, Building2, TrendingUp, Lock,
  Plus, Pencil, Trash2, RefreshCw, Loader2, AlertTriangle,
  X, ExternalLink, Clock,
} from 'lucide-react';
import {
  accountsApi, fundPriceApi,
  formatTL, formatTLSuffix, formatDate, signClass, parseTRNumber,
} from '../api.js';
import EmptyState from '../components/EmptyState.jsx';
import { useToast } from '../components/Toast.jsx';

/**
 * Accounts paneli — 8 hesabin tam yonetimi.
 *
 * Ozellikler:
 *  - Tum hesaplar grid (4 tip rengi: cash/credit_card/loan/investment)
 *  - Yeni hesap ekle (modal, tipe gore dinamik form alanlari)
 *  - Duzenle (modal)
 *  - Sil (onay)
 *  - Yatirim hesabinda 'Fiyat guncelle' butonu (TEFAS link + manuel deger)
 *  - Yenile butonu
 */
export default function Accounts() {
  const toast = useToast();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const [editingAccount, setEditingAccount] = useState(null);  // null | account obj | 'new'
  const [priceUpdateAccount, setPriceUpdateAccount] = useState(null);
  const [confirmingDelete, setConfirmingDelete] = useState(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const data = await accountsApi.list();
      setAccounts(data || []);
    } catch (e) {
      setError(e.message || 'Hesaplar yuklenemedi');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = () => { setRefreshing(true); load(); };

  // FE-005: mutasyon handler'ları try/catch — API/ağ hatası sessizce düşmesin.
  const handleSave = async (formData, isNew) => {
    try {
      if (isNew) {
        await accountsApi.create(formData);
      } else {
        await accountsApi.update(editingAccount.id, formData);
      }
      setEditingAccount(null);
      handleRefresh();
    } catch (e) { toast.error(`Hesap kaydedilemedi: ${e.message}`); }
  };

  const handleDelete = async (id) => {
    try {
      await accountsApi.delete(id);
      setConfirmingDelete(null);
      handleRefresh();
    } catch (e) { toast.error(`Hesap silinemedi: ${e.message}`); }
  };

  // ============================================================
  // RENDER
  // ============================================================

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6 border-negative-300 dark:border-negative-700 bg-negative-50 dark:bg-negative-950/30">
        <div className="flex items-start gap-3">
          <AlertTriangle className="w-6 h-6 text-negative-600 dark:text-negative-400 flex-shrink-0" />
          <div>
            <h3 className="font-semibold text-negative-700 dark:text-negative-300">
              Hesaplar yüklenemedi
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

  // Tipe gore grupla
  const grouped = {
    cash: accounts.filter(a => a.account_type === 'cash'),
    credit_card: accounts.filter(a => a.account_type === 'credit_card'),
    loan: accounts.filter(a => a.account_type === 'loan'),
    investment: accounts.filter(a => a.account_type === 'investment'),
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold mb-1">Hesaplar</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {accounts.length} hesap · {grouped.cash.length} nakit, {grouped.credit_card.length} kart,
            {' '}{grouped.loan.length} kredi, {grouped.investment.length} yatırım
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button type="button" onClick={handleRefresh} disabled={refreshing} className="btn btn-secondary !text-xs">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Yenile</span>
          </button>
          <button type="button" onClick={() => setEditingAccount('new')} className="btn btn-primary !text-xs">
            <Plus className="w-3.5 h-3.5" />
            Yeni hesap
          </button>
        </div>
      </div>

      {/* Gruplar halinde liste */}
      {[
        { key: 'cash', label: 'Nakit', icon: Wallet, color: 'positive' },
        { key: 'credit_card', label: 'Kredi Kartları', icon: CreditCard, color: 'negative' },
        { key: 'loan', label: 'Krediler', icon: Building2, color: 'warn' },
        { key: 'investment', label: 'Yatırımlar', icon: TrendingUp, color: 'brand' },
      ].map(({ key, label, icon: Icon, color }) => {
        const items = grouped[key];
        if (items.length === 0) return null;
        return (
          <section key={key}>
            <div className="flex items-center gap-2 mb-3">
              <Icon className={`w-5 h-5 text-${color}-600 dark:text-${color}-400`} />
              <h3 className="font-semibold">{label} ({items.length})</h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {items.map((acc) => (
                <AccountRow
                  key={acc.id}
                  account={acc}
                  onEdit={() => setEditingAccount(acc)}
                  onDelete={() => setConfirmingDelete(acc)}
                  onPriceUpdate={() => setPriceUpdateAccount(acc)}
                />
              ))}
            </div>
          </section>
        );
      })}

      {accounts.length === 0 && (
        <EmptyState
          icon={Wallet}
          title="Henüz hesap yok"
          description="Banka hesabı, kredi kartı veya nakit hesabı ekle."
          ctaLabel="Yeni Hesap"
          onCta={() => setEditingAccount('new')}
        />
      )}

      {/* Modallar */}
      {editingAccount && (
        <AccountFormModal
          account={editingAccount === 'new' ? null : editingAccount}
          onClose={() => setEditingAccount(null)}
          onSave={handleSave}
        />
      )}

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

      {confirmingDelete && (
        <ConfirmDeleteModal
          account={confirmingDelete}
          onClose={() => setConfirmingDelete(null)}
          onConfirm={() => handleDelete(confirmingDelete.id)}
        />
      )}
    </div>
  );
}

// ============================================================
// ACCOUNT ROW — tek hesap satiri
// ============================================================

function AccountRow({ account, onEdit, onDelete, onPriceUpdate }) {
  const a = account;

  // Backend AccountOut: {id, name, account_type, balance, ...} ile geliyor
  // Cockpit'tekinden farkli olarak burada 'ad/tip/bakiye' Turkce alias yok
  const balance = a.balance;
  const utilizationPct = a.account_type === 'credit_card' && a.credit_limit
    ? (a.balance / a.credit_limit) * 100
    : null;

  return (
    <div className={`card p-4 ${a.is_emanet ? 'border-warn-300 dark:border-warn-700/50' : ''}`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0 flex-1">
          <h4 className="font-semibold text-sm truncate">{a.name}</h4>
          {a.is_emanet && (
            <span className="chip chip-warn text-[10px] mt-1">
              <Lock className="w-3 h-3" /> EMANET
            </span>
          )}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button type="button" onClick={onEdit} className="btn btn-ghost btn-icon !p-1.5" title="Düzenle">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button type="button" onClick={onDelete} className="btn btn-ghost btn-icon !p-1.5 hover:!text-negative-600" title="Sil">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <p className="font-numeric text-xl font-bold mb-2">
        {formatTL(balance)} <span className="text-xs font-normal text-zinc-500">TL</span>
      </p>

      {/* Tipe ozel detay */}
      {a.account_type === 'credit_card' && a.credit_limit && (
        <div className="space-y-1 text-xs">
          <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
            <span>Limit</span>
            <span className="font-numeric">{formatTL(a.credit_limit)} TL</span>
          </div>
          <div className="flex justify-between text-zinc-600 dark:text-zinc-400">
            <span>Kesim / Ödeme</span>
            <span className="font-numeric">{a.statement_day || '-'} / {a.payment_day || '-'}</span>
          </div>
          {utilizationPct !== null && (
            <div>
              <div className="flex justify-between mb-1">
                <span className="text-zinc-600 dark:text-zinc-400">Kullanım</span>
                <span className={`font-numeric font-semibold ${utilizationPct > 95 ? 'text-negative-600' : utilizationPct > 75 ? 'text-warn-600' : 'text-zinc-700 dark:text-zinc-300'}`}>
                  %{utilizationPct.toFixed(1)}
                </span>
              </div>
              <div className="h-1.5 bg-zinc-200 dark:bg-zinc-800 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${utilizationPct > 95 ? 'bg-negative-500' : utilizationPct > 75 ? 'bg-warn-500' : 'bg-positive-500'}`}
                  style={{ width: `${Math.min(100, utilizationPct)}%` }}
                />
              </div>
            </div>
          )}
        </div>
      )}

      {a.account_type === 'loan' && (
        <div className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          {a.monthly_payment && (
            <div className="flex justify-between">
              <span>Aylık taksit</span>
              <span className="font-numeric font-semibold text-zinc-800 dark:text-zinc-200">
                {formatTL(a.monthly_payment)} TL
              </span>
            </div>
          )}
          {a.remaining_installments != null && (
            <div className="flex justify-between">
              <span>Kalan taksit</span>
              <span className="font-numeric">{a.remaining_installments}</span>
            </div>
          )}
          {a.next_payment_date && (
            <div className="flex justify-between">
              <span>Sonraki</span>
              <span className="font-numeric">{formatDate(a.next_payment_date)}</span>
            </div>
          )}
        </div>
      )}

      {a.account_type === 'investment' && (
        <div className="space-y-1 text-xs text-zinc-600 dark:text-zinc-400">
          {a.fund_code && (
            <div className="flex justify-between">
              <span>Fon kodu</span>
              <span className="font-numeric font-semibold">{a.fund_code}</span>
            </div>
          )}
          {a.lot_count != null && (
            <div className="flex justify-between">
              <span>Lot</span>
              <span className="font-numeric">{a.lot_count}</span>
            </div>
          )}
          {a.current_price != null && (
            <div className="flex justify-between">
              <span>Güncel fiyat</span>
              <span className="font-numeric">{formatTL(a.current_price)} TL</span>
            </div>
          )}
          {a.cost_per_lot != null && (
            <div className="flex justify-between">
              <span>Maliyet/lot</span>
              <span className="font-numeric">{formatTL(a.cost_per_lot)} TL</span>
            </div>
          )}
          {!a.is_emanet && (
            <button type="button" onClick={onPriceUpdate} className="mt-2 w-full btn btn-secondary !py-1.5 !text-xs">
              <Clock className="w-3 h-3" /> Fiyat güncelle
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ============================================================
// ACCOUNT FORM MODAL — yeni / duzenle
// ============================================================

function AccountFormModal({ account, onClose, onSave }) {
  const isNew = !account;
  const [type, setType] = useState(account?.account_type || 'cash');
  const [name, setName] = useState(account?.name || '');
  const [balance, setBalance] = useState(account?.balance?.toString() || '0');
  const [creditLimit, setCreditLimit] = useState(account?.credit_limit?.toString() || '');
  const [statementDay, setStatementDay] = useState(account?.statement_day?.toString() || '');
  const [paymentDay, setPaymentDay] = useState(account?.payment_day?.toString() || '');
  const [monthlyPayment, setMonthlyPayment] = useState(account?.monthly_payment?.toString() || '');
  const [remainingInstallments, setRemainingInstallments] = useState(account?.remaining_installments?.toString() || '');
  const [nextPaymentDate, setNextPaymentDate] = useState(account?.next_payment_date || '');
  const [fundCode, setFundCode] = useState(account?.fund_code || '');
  const [lotCount, setLotCount] = useState(account?.lot_count?.toString() || '');
  const [costPerLot, setCostPerLot] = useState(account?.cost_per_lot?.toString() || '');
  const [currentPrice, setCurrentPrice] = useState(account?.current_price?.toString() || '');
  const [isEmanet, setIsEmanet] = useState(account?.is_emanet || false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const parseNum = (v) => {
    if (!v || v === '') return null;
    const n = parseTRNumber(v); // W3-001: TR binlik/ondalık güvenli parse
    return isNaN(n) ? null : n;
  };
  const parseInt2 = (v) => {
    if (!v || v === '') return null;
    const n = parseInt(v, 10);
    return isNaN(n) ? null : n;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Hesap adı boş olamaz');
      return;
    }
    setBusy(true);
    setError(null);

    const data = {
      name: name.trim(),
      account_type: type,
      balance: parseNum(balance) ?? 0,
      is_emanet: isEmanet,
    };

    if (type === 'credit_card') {
      data.credit_limit = parseNum(creditLimit);
      data.statement_day = parseInt2(statementDay);
      data.payment_day = parseInt2(paymentDay);
    } else if (type === 'loan') {
      data.monthly_payment = parseNum(monthlyPayment);
      data.remaining_installments = parseInt2(remainingInstallments);
      data.next_payment_date = nextPaymentDate || null;
    } else if (type === 'investment') {
      data.fund_code = fundCode || null;
      data.lot_count = parseNum(lotCount);
      data.cost_per_lot = parseNum(costPerLot);
      data.current_price = parseNum(currentPrice);
    }

    try {
      await onSave(data, isNew);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isNew ? 'Yeni hesap' : `Düzenle — ${account.name}`} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Tip */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tip</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="input"
            disabled={!isNew}
          >
            <option value="cash">Nakit</option>
            <option value="credit_card">Kredi Kartı</option>
            <option value="loan">Kredi</option>
            <option value="investment">Yatırım</option>
          </select>
        </div>

        {/* Ad */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Ad</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input"
            placeholder="Enpara, Ziraat Kart vb."
            autoFocus
          />
        </div>

        {/* Bakiye */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">
            Bakiye {type === 'credit_card' || type === 'loan' ? '(borç)' : ''}
          </label>
          <input
            type="text"
            value={balance}
            onChange={(e) => setBalance(e.target.value)}
            className="input font-numeric"
            placeholder="0"
          />
        </div>

        {/* Kredi karti */}
        {type === 'credit_card' && (
          <>
            <div>
              <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Limit</label>
              <input type="text" value={creditLimit} onChange={(e) => setCreditLimit(e.target.value)} className="input font-numeric" placeholder="50000" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Kesim günü</label>
                <input type="text" value={statementDay} onChange={(e) => setStatementDay(e.target.value)} className="input font-numeric" placeholder="2" />
              </div>
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Ödeme günü</label>
                <input type="text" value={paymentDay} onChange={(e) => setPaymentDay(e.target.value)} className="input font-numeric" placeholder="12" />
              </div>
            </div>
          </>
        )}

        {/* Kredi */}
        {type === 'loan' && (
          <>
            <div>
              <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Aylık taksit</label>
              <input type="text" value={monthlyPayment} onChange={(e) => setMonthlyPayment(e.target.value)} className="input font-numeric" placeholder="4109.90" />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Kalan taksit</label>
                <input type="text" value={remainingInstallments} onChange={(e) => setRemainingInstallments(e.target.value)} className="input font-numeric" placeholder="8" />
              </div>
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Sonraki tarih</label>
                <input type="date" value={nextPaymentDate} onChange={(e) => setNextPaymentDate(e.target.value)} className="input" />
              </div>
            </div>
          </>
        )}

        {/* Yatirim */}
        {type === 'investment' && (
          <>
            <div>
              <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Fon kodu</label>
              <input type="text" value={fundCode} onChange={(e) => setFundCode(e.target.value.toUpperCase())} className="input font-numeric" placeholder="TLY" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Lot</label>
                <input type="text" value={lotCount} onChange={(e) => setLotCount(e.target.value)} className="input font-numeric" placeholder="6" />
              </div>
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Maliyet/lot</label>
                <input type="text" value={costPerLot} onChange={(e) => setCostPerLot(e.target.value)} className="input font-numeric" placeholder="4125" />
              </div>
              <div>
                <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Güncel fiyat</label>
                <input type="text" value={currentPrice} onChange={(e) => setCurrentPrice(e.target.value)} className="input font-numeric" placeholder="5223" />
              </div>
            </div>
            <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
              <input type="checkbox" checked={isEmanet} onChange={(e) => setIsEmanet(e.target.checked)} className="w-4 h-4 rounded" />
              Emanet (dokunulmaz)
            </label>
          </>
        )}

        {error && <p className="text-xs text-negative-600 dark:text-negative-400">{error}</p>}

        <div className="flex gap-2 pt-2">
          <button type="submit" disabled={busy} className="btn btn-primary flex-1">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : (isNew ? 'Oluştur' : 'Kaydet')}
          </button>
          <button type="button" onClick={onClose} className="btn btn-secondary">İptal</button>
        </div>
      </form>
    </Modal>
  );
}

// ============================================================
// PRICE UPDATE MODAL
// ============================================================

function PriceUpdateModal({ account, onClose, onUpdated }) {
  const [newPrice, setNewPrice] = useState(account.current_price?.toString() || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const price = parseTRNumber(newPrice); // W3-001
    if (!price || price <= 0) { setErr('Geçerli bir fiyat girin'); return; }
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
    <Modal title="Fiyat güncelle" onClose={onClose}>
      <p className="text-sm text-zinc-600 dark:text-zinc-400 mb-4">
        {account.name} · {account.fund_code}
      </p>
      <a href={tefasUrl} target="_blank" rel="noopener noreferrer" className="btn btn-secondary !text-xs w-full mb-4">
        <ExternalLink className="w-3 h-3" /> TEFAS'ta aç
      </a>
      <form onSubmit={handleSubmit}>
        <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Yeni fiyat (TL)</label>
        <input type="text" value={newPrice} onChange={(e) => setNewPrice(e.target.value)} className="input font-numeric" placeholder="5223.81" autoFocus />
        {err && <p className="text-xs text-negative-600 dark:text-negative-400 mt-2">{err}</p>}
        <div className="flex gap-2 mt-4">
          <button type="submit" disabled={busy} className="btn btn-primary flex-1">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Kaydet'}
          </button>
          <button type="button" onClick={onClose} className="btn btn-secondary">İptal</button>
        </div>
      </form>
    </Modal>
  );
}

// ============================================================
// CONFIRM DELETE MODAL
// ============================================================

function ConfirmDeleteModal({ account, onClose, onConfirm }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const handleDelete = async () => {
    setBusy(true);
    setErr(null);
    try {
      await onConfirm();
    } catch (e) {
      setErr(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title="Hesabı sil" onClose={onClose}>
      <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-negative-50 dark:bg-negative-950/30 border border-negative-200 dark:border-negative-800">
        <AlertTriangle className="w-5 h-5 text-negative-600 dark:text-negative-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold text-negative-700 dark:text-negative-300 mb-1">
            {account.name}
          </p>
          <p className="text-zinc-700 dark:text-zinc-300">
            Bu hesap ve bağlı işlemler silinecek. Bu işlem geri alınamaz.
          </p>
        </div>
      </div>
      {err && <p className="text-xs text-negative-600 dark:text-negative-400 mb-2">{err}</p>}
      <div className="flex gap-2">
        <button type="button" onClick={handleDelete} disabled={busy} className="btn btn-negative flex-1">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Evet, sil'}
        </button>
        <button type="button" onClick={onClose} className="btn btn-secondary">İptal</button>
      </div>
    </Modal>
  );
}

// ============================================================
// GENEL MODAL WRAPPER
// ============================================================

function Modal({ title, children, onClose }) {
  return (
    <div
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-2 sm:p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="card p-6 w-full sm:max-w-md max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">{title}</h3>
          <button type="button" onClick={onClose} className="btn btn-ghost btn-icon !p-1.5" title="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}