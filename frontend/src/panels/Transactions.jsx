import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  Receipt, Plus, Loader2, AlertTriangle, RefreshCw,
  Search, Trash2, Pencil, X, Filter, ArrowUp, ArrowDown,
  Wallet, CreditCard,
} from 'lucide-react';
import {
  transactionsApi, accountsApi,
  formatTL, formatDate, signClass, todayLocalISO,
} from '../api.js';
import EmptyState from '../components/EmptyState.jsx';

/**
 * Transactions paneli — islem listesi + hizli giris.
 *
 * Ozellikler:
 *  - Ust kisimda QuickEntry cubugu: "320 borc" gibi tek satir ile gider ekle
 *  - Yapilandirilmis form modali (tip/tutar/kategori/aciklama/hesap)
 *  - Tablo: tarih, tip, tutar, kategori, hesap, aciklama, sil/duzenle
 *  - Filtreler: kategori, tip, tarih araligi, arama metni
 *  - Toplam toplama (gelirler + / giderler -)
 */

// Yaygin kategori listesi (UI hint icin, backend zorunlu kilmaz)
const COMMON_CATEGORIES = [
  'yemek', 'ulasim', 'fatura', 'eglence', 'sigara',
  'alisveris', 'saglik', 'borc_geri_odeme', 'diger',
];

export default function Transactions() {
  const [transactions, setTransactions] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Modal state
  const [editing, setEditing] = useState(null);  // null | 'new' | transaction obj
  const [confirmingDelete, setConfirmingDelete] = useState(null);

  // Filtreler
  const [searchText, setSearchText] = useState('');
  const [filterType, setFilterType] = useState('all');  // all | income | expense | transfer
  const [filterCategory, setFilterCategory] = useState('all');
  const [filterAccount, setFilterAccount] = useState('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  const isFiltered = searchText || filterType !== 'all' || filterCategory !== 'all'
    || filterAccount !== 'all' || filterDateFrom || filterDateTo;

  const resetFilters = () => {
    setSearchText(''); setFilterType('all'); setFilterCategory('all');
    setFilterAccount('all'); setFilterDateFrom(''); setFilterDateTo('');
  };

  const load = useCallback(async () => {
    try {
      setError(null);
      const [txns, accs] = await Promise.all([
        transactionsApi.list(),
        accountsApi.list(),
      ]);
      setTransactions(txns || []);
      setAccounts(accs || []);
    } catch (e) {
      setError(e.message || 'İşlemler yüklenemedi');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = () => { setRefreshing(true); load(); };

  // Account id -> account map (lookup icin)
  const accountMap = useMemo(() => {
    const m = {};
    accounts.forEach(a => { m[a.id] = a; });
    return m;
  }, [accounts]);

  // Filtrelenmis ve siralanmis islemler
  const filtered = useMemo(() => {
    let list = transactions;

    if (filterType !== 'all') {
      list = list.filter(t => t.transaction_type === filterType);
    }
    if (filterCategory !== 'all') {
      list = list.filter(t => t.category === filterCategory);
    }
    if (filterAccount !== 'all') {
      list = list.filter(t => String(t.account_id) === filterAccount);
    }
    if (filterDateFrom) {
      list = list.filter(t => (t.transaction_date || '') >= filterDateFrom);
    }
    if (filterDateTo) {
      list = list.filter(t => (t.transaction_date || '') <= filterDateTo);
    }
    if (searchText.trim()) {
      const q = searchText.toLowerCase();
      list = list.filter(t =>
        (t.description || '').toLowerCase().includes(q) ||
        (t.category || '').toLowerCase().includes(q) ||
        (t.notes || '').toLowerCase().includes(q)
      );
    }
    // En yeni once (transaction_date sonra created_at)
    return [...list].sort((a, b) => {
      const dA = a.transaction_date || '';
      const dB = b.transaction_date || '';
      if (dA !== dB) return dB.localeCompare(dA);
      return (b.id || 0) - (a.id || 0);
    });
  }, [transactions, filterType, filterCategory, filterAccount, filterDateFrom, filterDateTo, searchText]);

  // Toplam
  const totals = useMemo(() => {
    let income = 0, expense = 0;
    filtered.forEach(t => {
      if (t.transaction_type === 'income') income += t.amount;
      else if (t.transaction_type === 'expense') expense += t.amount;
    });
    return { income, expense, net: income - expense };
  }, [filtered]);

  // Mevcut kategoriler (filter dropdown icin)
  const allCategories = useMemo(() => {
    const set = new Set();
    transactions.forEach(t => { if (t.category) set.add(t.category); });
    return Array.from(set).sort();
  }, [transactions]);

  const handleDelete = async (id) => {
    await transactionsApi.delete(id);
    setConfirmingDelete(null);
    handleRefresh();
  };

  const handleSave = async (formData, isNew, txnId) => {
    if (isNew) {
      await transactionsApi.create(formData);
    } else {
      await transactionsApi.update(txnId, formData);
    }
    setEditing(null);
    handleRefresh();
  };

  // QuickEntry submit
  const handleQuickSubmit = async (text) => {
    // Backend hizli giris destekliyor: { quick_text: '320 borc', auto_update_balance: true, account_id: <default cash> }
    // Default hesap: ilk cash hesap
    const defaultCash = accounts.find(a => a.account_type === 'cash');
    const payload = {
      quick_text: text,
      auto_update_balance: true,
    };
    if (defaultCash) payload.account_id = defaultCash.id;

    await transactionsApi.create(payload);
    handleRefresh();
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
              İşlemler yüklenemedi
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

  return (
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold mb-1">İşlemler</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Toplam {transactions.length} işlem
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button onClick={handleRefresh} disabled={refreshing} className="btn btn-secondary !text-xs">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Yenile</span>
          </button>
          <button onClick={() => setEditing('new')} className="btn btn-primary !text-xs">
            <Plus className="w-3.5 h-3.5" />
            Yeni işlem
          </button>
        </div>
      </div>

      {/* QuickEntry */}
      <QuickEntry onSubmit={handleQuickSubmit} accounts={accounts} />

      {/* Toplam ozet */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
        <div className="card p-3 text-center">
          <div className="flex items-center justify-center gap-1 text-xs text-zinc-500 mb-1">
            <ArrowUp className="w-3 h-3 text-positive-600" />
            <span>Gelir</span>
          </div>
          <p className="font-numeric text-base font-bold text-positive-600 dark:text-positive-400">
            +{formatTL(totals.income)}
          </p>
        </div>
        <div className="card p-3 text-center">
          <div className="flex items-center justify-center gap-1 text-xs text-zinc-500 mb-1">
            <ArrowDown className="w-3 h-3 text-negative-600" />
            <span>Gider</span>
          </div>
          <p className="font-numeric text-base font-bold text-negative-600 dark:text-negative-400">
            −{formatTL(totals.expense)}
          </p>
        </div>
        <div className="card p-3 text-center">
          <div className="text-xs text-zinc-500 mb-1">Net</div>
          <p className={`font-numeric text-base font-bold ${signClass(totals.net)}`}>
            {totals.net >= 0 ? '+' : '−'}{formatTL(Math.abs(totals.net))}
          </p>
        </div>
      </div>

      {/* Filtreler */}
      <div className="card p-3">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-zinc-500" />
            <span className="text-xs font-semibold text-zinc-600 dark:text-zinc-400">Filtreler</span>
            {isFiltered && (
              <span className="chip chip-neutral text-[10px]">
                {transactions.length} işlemden {filtered.length}'i gösteriliyor
              </span>
            )}
          </div>
          {isFiltered && (
            <button onClick={resetFilters} className="btn btn-ghost !text-xs !py-1 !px-2">
              <X className="w-3 h-3" /> Sıfırla
            </button>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
          {/* Arama */}
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-zinc-400" />
            <input type="text" value={searchText}
              onChange={e => setSearchText(e.target.value)}
              placeholder="Açıklama, kategori, not..." className="input !pl-8 !text-xs" />
          </div>
          {/* Tip */}
          <select value={filterType} onChange={e => setFilterType(e.target.value)} className="input !text-xs">
            <option value="all">Tüm tipler</option>
            <option value="income">Gelir</option>
            <option value="expense">Gider</option>
            <option value="transfer">Transfer</option>
          </select>
          {/* Kategori */}
          <select value={filterCategory} onChange={e => setFilterCategory(e.target.value)} className="input !text-xs">
            <option value="all">Tüm kategoriler</option>
            {allCategories.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
          {/* Hesap */}
          <select value={filterAccount} onChange={e => setFilterAccount(e.target.value)} className="input !text-xs">
            <option value="all">Tüm hesaplar</option>
            {accounts.map(a => <option key={a.id} value={String(a.id)}>{a.name}</option>)}
          </select>
          {/* Tarih başlangıç */}
          <input type="date" value={filterDateFrom}
            onChange={e => setFilterDateFrom(e.target.value)}
            className="input !text-xs" title="Başlangıç tarihi" />
          {/* Tarih bitiş */}
          <input type="date" value={filterDateTo}
            onChange={e => setFilterDateTo(e.target.value)}
            className="input !text-xs" title="Bitiş tarihi" />
        </div>
      </div>

      {/* Liste */}
      {filtered.length === 0 ? (
        transactions.length === 0 ? (
          <EmptyState
            icon={Receipt}
            title="Henüz işlem yok"
            description='Hızlı giriş çubuğu ile veya "Yeni işlem" butonu ile başla.'
            ctaLabel="Yeni İşlem"
            onCta={() => setEditing('new')}
          />
        ) : (
          <EmptyState
            icon={Filter}
            title="Bu filtreyle eşleşen işlem yok"
            description="Filtreyi temizle veya kriterleri değiştir."
            ctaLabel="Filtreyi Temizle"
            onCta={resetFilters}
          />
        )
      ) : (
        <div className="space-y-1.5">
          {filtered.map(t => (
            <TransactionRow
              key={t.id}
              txn={t}
              account={accountMap[t.account_id]}
              onEdit={() => setEditing(t)}
              onDelete={() => setConfirmingDelete(t)}
            />
          ))}
        </div>
      )}

      {/* Modallar */}
      {editing && (
        <TransactionFormModal
          txn={editing === 'new' ? null : editing}
          accounts={accounts}
          onClose={() => setEditing(null)}
          onSave={handleSave}
        />
      )}

      {confirmingDelete && (
        <ConfirmDeleteModal
          txn={confirmingDelete}
          onClose={() => setConfirmingDelete(null)}
          onConfirm={() => handleDelete(confirmingDelete.id)}
        />
      )}
    </div>
  );
}

// ============================================================
// QUICK ENTRY — "320 borc" gibi tek satir hizli giris
// ============================================================

function QuickEntry({ onSubmit, accounts }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState(null);  // {ok, msg}

  const defaultCash = accounts.find(a => a.account_type === 'cash');

  const handleSubmit = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    setBusy(true);
    setFeedback(null);
    try {
      await onSubmit(t);
      setText('');
      setFeedback({ ok: true, msg: 'Kaydedildi' });
      setTimeout(() => setFeedback(null), 2500);
    } catch (e) {
      setFeedback({ ok: false, msg: e.message || 'Hata oluştu' });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="card p-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <span className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-400 font-numeric text-sm select-none">
            ⚡
          </span>
          <input
            type="text"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder='Hızlı giriş: "320 borc" veya "230 yemek"'
            className="input !pl-9"
            disabled={busy}
          />
        </div>
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="btn btn-primary"
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Ekle'}
        </button>
      </form>
      <div className="flex items-center justify-between mt-2 text-[11px] text-zinc-500">
        <span>
          Format: tutar + kategori (Enter ile gönder)
          {defaultCash && <> · Hesap: <strong>{defaultCash.name}</strong></>}
        </span>
        {feedback && (
          <span className={feedback.ok ? 'text-positive-600' : 'text-negative-600'}>
            {feedback.msg}
          </span>
        )}
      </div>
    </div>
  );
}

// ============================================================
// TRANSACTION ROW — tek islem satiri
// ============================================================

function TransactionRow({ txn, account, onEdit, onDelete }) {
  const isIncome = txn.transaction_type === 'income';
  const sign = isIncome ? '+' : '−';
  const colorClass = isIncome ? 'text-positive-600 dark:text-positive-400' : 'text-negative-600 dark:text-negative-400';

  return (
    <div className="card p-3 hover:border-zinc-300 dark:hover:border-zinc-700 transition-colors">
      <div className="flex items-center gap-3">
        {/* Tip ikonu */}
        <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${
          isIncome
            ? 'bg-positive-100 dark:bg-positive-950/30 text-positive-600 dark:text-positive-400'
            : 'bg-negative-100 dark:bg-negative-950/30 text-negative-600 dark:text-negative-400'
        }`}>
          {isIncome ? <ArrowUp className="w-4 h-4" /> : <ArrowDown className="w-4 h-4" />}
        </div>

        {/* Orta — kategori + aciklama */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <span className="font-semibold text-sm">{txn.category || '—'}</span>
            {txn.is_card_expense && (
              <span className="chip chip-warn !text-[10px]">
                <CreditCard className="w-2.5 h-2.5" /> Kart
              </span>
            )}
          </div>
          {txn.description && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 truncate mt-0.5">
              {txn.description}
            </p>
          )}
          <div className="flex items-center gap-2 text-[11px] text-zinc-500 mt-0.5">
            <span>{formatDate(txn.transaction_date)}</span>
            {account && (
              <>
                <span>·</span>
                <span>{account.name}</span>
              </>
            )}
          </div>
        </div>

        {/* Sag — tutar + butonlar */}
        <div className="text-right flex-shrink-0">
          <p className={`font-numeric font-bold text-base ${colorClass}`}>
            {sign}{formatTL(txn.amount)}
          </p>
          <div className="flex items-center justify-end gap-1 mt-1">
            <button onClick={onEdit} className="btn btn-ghost btn-icon !p-1" title="Düzenle">
              <Pencil className="w-3 h-3" />
            </button>
            <button onClick={onDelete} className="btn btn-ghost btn-icon !p-1 hover:!text-negative-600" title="Sil">
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// TRANSACTION FORM MODAL — yeni / duzenle
// ============================================================

function TransactionFormModal({ txn, accounts, onClose, onSave }) {
  const isNew = !txn;
  const [type, setType] = useState(txn?.transaction_type || 'expense');
  const [amount, setAmount] = useState(txn?.amount?.toString() || '');
  const [category, setCategory] = useState(txn?.category || '');
  const [description, setDescription] = useState(txn?.description || '');
  const [accountId, setAccountId] = useState(txn?.account_id?.toString() || '');
  const [transactionDate, setTransactionDate] = useState(
    txn?.transaction_date || todayLocalISO()
  );
  const [isCardExpense, setIsCardExpense] = useState(txn?.is_card_expense || false);

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Default account: ilk cash
  useEffect(() => {
    if (!accountId && accounts.length > 0) {
      const cash = accounts.find(a => a.account_type === 'cash');
      if (cash) setAccountId(cash.id.toString());
      else setAccountId(accounts[0].id.toString());
    }
  }, [accounts, accountId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    const amt = parseFloat(amount.replace(',', '.'));
    if (!amt || amt <= 0) { setError('Geçerli tutar girin'); return; }

    setBusy(true);
    setError(null);

    const data = {
      transaction_type: type,
      amount: amt,
      category: category.trim() || null,
      description: description.trim() || null,
      transaction_date: transactionDate,
      account_id: accountId ? parseInt(accountId) : null,
      is_card_expense: isCardExpense,
      auto_update_balance: true,
    };

    try {
      await onSave(data, isNew, txn?.id);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isNew ? 'Yeni işlem' : 'İşlemi düzenle'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Tip */}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setType('expense')}
            className={`btn !text-xs ${type === 'expense' ? 'btn-negative' : 'btn-secondary'}`}
          >
            <ArrowDown className="w-3.5 h-3.5" /> Gider
          </button>
          <button
            type="button"
            onClick={() => setType('income')}
            className={`btn !text-xs ${type === 'income' ? 'btn-positive' : 'btn-secondary'}`}
          >
            <ArrowUp className="w-3.5 h-3.5" /> Gelir
          </button>
        </div>

        {/* Tutar */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tutar (TL)</label>
          <input
            type="text"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="input font-numeric !text-base !font-semibold"
            placeholder="0.00"
            autoFocus
          />
        </div>

        {/* Kategori */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Kategori</label>
          <input
            type="text"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="input"
            placeholder="yemek, ulasim, fatura..."
            list="category-list"
          />
          <datalist id="category-list">
            {COMMON_CATEGORIES.map(c => <option key={c} value={c} />)}
          </datalist>
        </div>

        {/* Aciklama */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Açıklama (opsiyonel)</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input"
            placeholder="Kısa not..."
          />
        </div>

        {/* Hesap + Tarih */}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Hesap</label>
            <select
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
              className="input"
            >
              <option value="">— seç —</option>
              {accounts.map(a => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tarih</label>
            <input
              type="date"
              value={transactionDate}
              onChange={(e) => setTransactionDate(e.target.value)}
              className="input"
            />
          </div>
        </div>

        {/* Kart harcamasi mi */}
        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={isCardExpense}
            onChange={(e) => setIsCardExpense(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          Bu kart harcaması (gölge muhasebe için)
        </label>

        {error && <p className="text-xs text-negative-600 dark:text-negative-400">{error}</p>}

        <div className="flex gap-2 pt-2">
          <button type="submit" disabled={busy} className="btn btn-primary flex-1">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : (isNew ? 'Ekle' : 'Kaydet')}
          </button>
          <button type="button" onClick={onClose} className="btn btn-secondary">İptal</button>
        </div>
      </form>
    </Modal>
  );
}

// ============================================================
// CONFIRM DELETE
// ============================================================

function ConfirmDeleteModal({ txn, onClose, onConfirm }) {
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
    <Modal title="İşlemi sil" onClose={onClose}>
      <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-negative-50 dark:bg-negative-950/30 border border-negative-200 dark:border-negative-800">
        <AlertTriangle className="w-5 h-5 text-negative-600 dark:text-negative-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold text-negative-700 dark:text-negative-300 mb-1">
            {txn.category || '(kategorisiz)'} · {formatTL(txn.amount)} TL
          </p>
          <p className="text-zinc-700 dark:text-zinc-300">
            Bu işlem silinecek ve hesap bakiyesi otomatik güncellenecek. Geri alınamaz.
          </p>
        </div>
      </div>
      {err && <p className="text-xs text-negative-600 dark:text-negative-400 mb-2">{err}</p>}
      <div className="flex gap-2">
        <button onClick={handleDelete} disabled={busy} className="btn btn-negative flex-1">
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Evet, sil'}
        </button>
        <button onClick={onClose} className="btn btn-secondary">İptal</button>
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
      className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4 animate-fade-in"
      onClick={onClose}
    >
      <div
        className="card p-6 w-full max-w-md max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold">{title}</h3>
          <button onClick={onClose} className="btn btn-ghost btn-icon !p-1.5" title="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}