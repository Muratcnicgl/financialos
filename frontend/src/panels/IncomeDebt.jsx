import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  TrendingUp, TrendingDown, Plus, Pencil, Trash2, X,
  Loader2, AlertTriangle, RefreshCw, CheckCircle, Clock,
  Calendar, ArrowDownToLine, ArrowUpToLine, Filter,
  Power, CreditCard, Receipt,
} from 'lucide-react';
import {
  incomesApi, expensesApi, debtsApi, accountsApi,
  formatTL, formatDate, todayLocalISO, currentYearMonthLocal, parseTRNumber,
} from '../api.js';
import { useToast } from '../components/Toast.jsx';

const CURRENT_YEAR_MONTH = currentYearMonthLocal(); // "2026-05" — LOCAL (gece vardiyası TZ güvenliği)
const EXPENSE_CATEGORIES = ['abonelik', 'fatura', 'kira', 'sigorta', 'internet', 'telefon', 'diger'];

/**
 * IncomeDebt paneli — Iki sutunlu yonetim:
 *  - Sol: Periyodik gelirler (Maas, vs.)
 *  - Sag: Borc/Alacak (PersonalDebt — kisisel alacaklar + diger)
 *
 * Ozellikler:
 *  - CRUD her iki tablo icin
 *  - Borc/Alacak filtresi (alacak/borc, odendi/bekleyen)
 *  - 'Odendi olarak isaretle' tek tikla
 *  - Toplam ozet (aylik gelir / bekleyen alacak / bekleyen borc)
 */
export default function IncomeDebt() {
  const toast = useToast();
  const [incomes, setIncomes] = useState([]);
  const [expenses, setExpenses] = useState([]);
  const [debts, setDebts] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  // Aktif sekme
  const [activeTab, setActiveTab] = useState('income'); // income | expense | debt

  // Modallar
  const [editingIncome, setEditingIncome] = useState(null);
  const [editingExpense, setEditingExpense] = useState(null);
  const [editingDebt, setEditingDebt] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);  // {kind: 'income'|'expense'|'debt', item}

  // Filtre — borç/alacak listesi
  const [filterDirection, setFilterDirection] = useState('all');
  const [filterPaid, setFilterPaid] = useState('pending');

  const load = useCallback(async () => {
    try {
      setError(null);
      const [inc, exp, dbt, accs] = await Promise.all([
        incomesApi.list(),
        expensesApi.list(),
        debtsApi.list(),
        accountsApi.list(),
      ]);
      setIncomes(inc || []);
      setExpenses(exp || []);
      setDebts(dbt || []);
      setAccounts(accs || []);
    } catch (e) {
      setError(e.message || 'Veri yüklenemedi');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = () => { setRefreshing(true); load(); };

  // Filtrelenmis borçlar
  const filteredDebts = useMemo(() => {
    let list = debts;
    if (filterDirection !== 'all') {
      list = list.filter(d => d.direction === filterDirection);
    }
    if (filterPaid === 'pending') {
      list = list.filter(d => !d.is_paid);
    } else if (filterPaid === 'paid') {
      list = list.filter(d => d.is_paid);
    }
    // Sirala: bekleyen + tarihe gore artan, sonra odenen + tarihe gore azalan
    return [...list].sort((a, b) => {
      if (a.is_paid !== b.is_paid) return a.is_paid ? 1 : -1;
      const dA = a.due_date || '';
      const dB = b.due_date || '';
      if (a.is_paid) return dB.localeCompare(dA);
      return dA.localeCompare(dB);
    });
  }, [debts, filterDirection, filterPaid]);

  // Toplam ozet
  const summary = useMemo(() => {
    const monthlyIncome = incomes
      .filter(i => i.is_active)
      .reduce((sum, i) => sum + (i.amount || 0), 0);
    const monthlyExpense = expenses
      .filter(e => e.is_active)
      .reduce((sum, e) => sum + (e.amount || 0), 0);
    const pendingReceivable = debts
      .filter(d => !d.is_paid && d.direction === 'receivable')
      .reduce((sum, d) => sum + (d.amount || 0), 0);
    const pendingPayable = debts
      .filter(d => !d.is_paid && d.direction === 'payable')
      .reduce((sum, d) => sum + (d.amount || 0), 0);
    return { monthlyIncome, monthlyExpense, pendingReceivable, pendingPayable };
  }, [incomes, expenses, debts]);

  // ============================================================
  // ACTION HANDLERS
  // ============================================================

  // FE-005: mutasyon handler'ları try/catch ile — API/ağ hatası SESSİZCE düşmesin (kullanıcı
  // "oldu" sanıp yanılmasın). Hata → toast.error; başarı → refresh. Unhandled rejection yok.
  const handleSaveIncome = async (data, isNew) => {
    try {
      if (isNew) await incomesApi.create(data);
      else await incomesApi.update(editingIncome.id, data);
      setEditingIncome(null);
      handleRefresh();
    } catch (e) { toast.error(`Gelir kaydedilemedi: ${e.message}`); }
  };

  const handleToggleIncome = async (inc) => {
    try {
      await incomesApi.update(inc.id, { is_active: !inc.is_active });
      handleRefresh();
    } catch (e) { toast.error(`Gelir durumu değiştirilemedi: ${e.message}`); }
  };

  const handleSaveExpense = async (data, isNew) => {
    try {
      if (isNew) await expensesApi.create(data);
      else await expensesApi.update(editingExpense.id, data);
      setEditingExpense(null);
      handleRefresh();
    } catch (e) { toast.error(`Gider kaydedilemedi: ${e.message}`); }
  };

  const handleToggleExpense = async (exp) => {
    try {
      await expensesApi.update(exp.id, { is_active: !exp.is_active });
      handleRefresh();
    } catch (e) { toast.error(`Gider durumu değiştirilemedi: ${e.message}`); }
  };

  const handleSaveDebt = async (data, isNew) => {
    try {
      if (isNew) await debtsApi.create(data);
      else await debtsApi.update(editingDebt.id, data);
      setEditingDebt(null);
      handleRefresh();
    } catch (e) { toast.error(`Kayıt yapılamadı: ${e.message}`); }
  };

  const handleMarkPaid = async (debt) => {
    try {
      await debtsApi.update(debt.id, { is_paid: true, paid_date: todayLocalISO() });
      handleRefresh();
    } catch (e) { toast.error(`Ödendi işaretlenemedi: ${e.message}`); }
  };

  const handleDelete = async () => {
    try {
      if (confirmDelete.kind === 'income') {
        await incomesApi.delete(confirmDelete.item.id);
      } else if (confirmDelete.kind === 'expense') {
        await expensesApi.delete(confirmDelete.item.id);
      } else {
        await debtsApi.delete(confirmDelete.item.id);
      }
      setConfirmDelete(null);
      handleRefresh();
    } catch (e) { toast.error(`Silinemedi: ${e.message}`); }
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
              Veri yüklenemedi
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

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold mb-1">Gelir & Borç</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            {incomes.length} gelir · {expenses.length} gider · {debts.length} borç/alacak
          </p>
        </div>
        <button type="button" onClick={handleRefresh} disabled={refreshing} className="btn btn-secondary !text-xs">
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          <span className="hidden sm:inline">Yenile</span>
        </button>
      </div>

      {/* Ozet — 4 kart */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        <div className="card p-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-500 mb-1">
            <TrendingUp className="w-3 h-3 text-positive-600" />
            <span>Aylık gelir</span>
          </div>
          <p className="font-numeric text-base font-bold text-positive-600 dark:text-positive-400">
            +{formatTL(summary.monthlyIncome)} <span className="text-[10px] font-normal">TL</span>
          </p>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-500 mb-1">
            <Receipt className="w-3 h-3 text-negative-600" />
            <span>Aylık gider</span>
          </div>
          <p className="font-numeric text-base font-bold text-negative-600 dark:text-negative-400">
            −{formatTL(summary.monthlyExpense)} <span className="text-[10px] font-normal">TL</span>
          </p>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-500 mb-1">
            <ArrowDownToLine className="w-3 h-3 text-positive-600" />
            <span>Bekleyen alacak</span>
          </div>
          <p className="font-numeric text-base font-bold text-positive-600 dark:text-positive-400">
            +{formatTL(summary.pendingReceivable)} <span className="text-[10px] font-normal">TL</span>
          </p>
        </div>
        <div className="card p-3">
          <div className="flex items-center gap-1.5 text-xs text-zinc-500 mb-1">
            <ArrowUpToLine className="w-3 h-3 text-negative-600" />
            <span>Bekleyen borç</span>
          </div>
          <p className="font-numeric text-base font-bold text-negative-600 dark:text-negative-400">
            −{formatTL(summary.pendingPayable)} <span className="text-[10px] font-normal">TL</span>
          </p>
        </div>
      </div>

      {/* Sekmeler — MC2 (Wave-8): overflow-x-auto, 390px'de 3. sekme kırpılmasın (main overflow-x-hidden). */}
      <div className="flex gap-1 border-b border-zinc-200 dark:border-zinc-700 overflow-x-auto">
        {[
          { id: 'income',  label: `Gelirler (${incomes.length})`,  icon: TrendingUp },
          { id: 'expense', label: `Giderler (${expenses.length})`, icon: Receipt },
          { id: 'debt',    label: `Borç/Alacak (${debts.length})`, icon: ArrowDownToLine },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
              activeTab === id
                ? 'text-brand-600 dark:text-brand-400 border-brand-500'
                : 'text-zinc-500 border-transparent hover:text-zinc-800 dark:hover:text-zinc-200'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            {label}
          </button>
        ))}
      </div>

      {/* ============ GELIRLER SEKMESI ============ */}
      {activeTab === 'income' && (
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-positive-600 dark:text-positive-400" />
            <h3 className="font-semibold">Düzenli Gelirler</h3>
          </div>
          <button type="button" onClick={() => setEditingIncome('new')} className="btn btn-primary !text-xs">
            <Plus className="w-3.5 h-3.5" /> Yeni
          </button>
        </div>
        {incomes.length === 0 ? (
          <div className="card p-6 text-center">
            <p className="text-sm text-zinc-500">Henüz gelir kaydı yok</p>
          </div>
        ) : (
          <div className="space-y-2">
            {incomes.map(inc => (
              <IncomeRow
                key={inc.id}
                income={inc}
                onToggle={() => handleToggleIncome(inc)}
                onEdit={() => setEditingIncome(inc)}
                onDelete={() => setConfirmDelete({ kind: 'income', item: inc })}
              />
            ))}
          </div>
        )}
      </section>
      )}

      {/* ============ GIDERLER SEKMESI ============ */}
      {activeTab === 'expense' && (
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Receipt className="w-5 h-5 text-negative-600 dark:text-negative-400" />
            <h3 className="font-semibold">Düzenli Giderler</h3>
          </div>
          <button type="button" onClick={() => setEditingExpense('new')} className="btn btn-primary !text-xs">
            <Plus className="w-3.5 h-3.5" /> Yeni
          </button>
        </div>
        {expenses.length === 0 ? (
          <div className="card p-6 text-center">
            <p className="text-sm text-zinc-500">Henüz gider kaydı yok</p>
          </div>
        ) : (
          <div className="space-y-2">
            {expenses.map(exp => (
              <ExpenseRow
                key={exp.id}
                expense={exp}
                accounts={accounts}
                onToggle={() => handleToggleExpense(exp)}
                onEdit={() => setEditingExpense(exp)}
                onDelete={() => setConfirmDelete({ kind: 'expense', item: exp })}
              />
            ))}
          </div>
        )}
      </section>
      )}

      {/* ============ BORC/ALACAK SEKMESI ============ */}
      {activeTab === 'debt' && (
      <section>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <ArrowDownToLine className="w-5 h-5 text-brand-600 dark:text-brand-400" />
            <h3 className="font-semibold">Borç / Alacak ({debts.length})</h3>
          </div>
          <button type="button" onClick={() => setEditingDebt('new')} className="btn btn-primary !text-xs">
            <Plus className="w-3.5 h-3.5" /> Yeni
          </button>
        </div>

          {/* Filtreler */}
          <div className="card p-2 mb-3">
            <div className="grid grid-cols-2 gap-2">
              <select
                value={filterDirection}
                onChange={(e) => setFilterDirection(e.target.value)}
                className="input !text-xs !py-1.5"
              >
                <option value="all">Hepsi</option>
                <option value="receivable">Alacak (bana gelecek)</option>
                <option value="payable">Borç (ben vereceğim)</option>
              </select>
              <select
                value={filterPaid}
                onChange={(e) => setFilterPaid(e.target.value)}
                className="input !text-xs !py-1.5"
              >
                <option value="pending">Bekleyen</option>
                <option value="paid">Ödenmiş</option>
                <option value="all">Hepsi</option>
              </select>
            </div>
          </div>

          {filteredDebts.length === 0 ? (
            <div className="card p-6 text-center">
              <p className="text-sm text-zinc-500">
                {debts.length === 0 ? 'Henüz borç/alacak kaydı yok' : 'Filtreyle eşleşen kayıt yok'}
              </p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[600px] overflow-y-auto pr-1">
              {filteredDebts.map(d => (
                <DebtRow
                  key={d.id}
                  debt={d}
                  onEdit={() => setEditingDebt(d)}
                  onDelete={() => setConfirmDelete({ kind: 'debt', item: d })}
                  onMarkPaid={() => handleMarkPaid(d)}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Modallar */}
      {editingIncome && (
        <IncomeFormModal
          income={editingIncome === 'new' ? null : editingIncome}
          onClose={() => setEditingIncome(null)}
          onSave={handleSaveIncome}
        />
      )}

      {editingExpense && (
        <ExpenseFormModal
          expense={editingExpense === 'new' ? null : editingExpense}
          accounts={accounts}
          onClose={() => setEditingExpense(null)}
          onSave={handleSaveExpense}
        />
      )}

      {editingDebt && (
        <DebtFormModal
          debt={editingDebt === 'new' ? null : editingDebt}
          onClose={() => setEditingDebt(null)}
          onSave={handleSaveDebt}
        />
      )}

      {confirmDelete && (
        <ConfirmDeleteModal
          item={confirmDelete}
          onClose={() => setConfirmDelete(null)}
          onConfirm={handleDelete}
        />
      )}
    </div>
  );
}

// ============================================================
// INCOME ROW
// ============================================================

function IncomeRow({ income, onToggle, onEdit, onDelete }) {
  const triggeredThisMonth = income.last_triggered_year_month === CURRENT_YEAR_MONTH;
  return (
    <div className={`card p-3 transition-opacity ${!income.is_active ? 'opacity-50' : ''}`}>
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-positive-100 dark:bg-positive-950/30 text-positive-600 dark:text-positive-400 flex items-center justify-center flex-shrink-0">
          <TrendingUp className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-sm">{income.name}</h4>
            {!income.is_active && <span className="chip !text-[10px]">Pasif</span>}
            {income.is_active && triggeredThisMonth && (
              <span className="chip chip-neutral !text-[10px]">✓ Bu ay</span>
            )}
          </div>
          <div className="flex items-center gap-2 text-[11px] text-zinc-500 mt-0.5">
            <Calendar className="w-3 h-3" />
            <span>Her ayın {income.day_of_month}'i</span>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="font-numeric font-bold text-base text-positive-600 dark:text-positive-400">
            +{formatTL(income.amount)}
          </p>
          <div className="flex items-center justify-end gap-1 mt-1">
            <button type="button" onClick={onToggle} className="btn btn-ghost btn-icon !p-1" title={income.is_active ? 'Pasifleştir' : 'Aktive et'}>
              <Power className={`w-3 h-3 ${income.is_active ? 'text-positive-500' : 'text-zinc-400'}`} />
            </button>
            <button type="button" onClick={onEdit} className="btn btn-ghost btn-icon !p-1" title="Düzenle">
              <Pencil className="w-3 h-3" />
            </button>
            <button type="button" onClick={onDelete} className="btn btn-ghost btn-icon !p-1 hover:!text-negative-600" title="Sil">
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// EXPENSE ROW
// ============================================================

function ExpenseRow({ expense, accounts, onToggle, onEdit, onDelete }) {
  const triggeredThisMonth = expense.last_triggered_year_month === CURRENT_YEAR_MONTH;
  const accName = accounts.find(a => a.id === expense.account_id)?.name || `Hesap #${expense.account_id}`;
  return (
    <div className={`card p-3 transition-opacity ${!expense.is_active ? 'opacity-50' : ''}`}>
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-negative-100 dark:bg-negative-950/30 text-negative-600 dark:text-negative-400 flex items-center justify-center flex-shrink-0">
          <Receipt className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h4 className="font-semibold text-sm">{expense.name}</h4>
            {expense.category && <span className="chip chip-neutral !text-[10px]">{expense.category}</span>}
            {!expense.is_active && <span className="chip !text-[10px]">Pasif</span>}
            {expense.is_active && triggeredThisMonth && (
              <span className="chip chip-neutral !text-[10px]">✓ Bu ay</span>
            )}
          </div>
          <div className="flex items-center gap-3 text-[11px] text-zinc-500 mt-0.5">
            <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />Her ayın {expense.day_of_month}'i</span>
            <span className="flex items-center gap-1"><CreditCard className="w-3 h-3" />{accName}</span>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="font-numeric font-bold text-base text-negative-600 dark:text-negative-400">
            −{formatTL(expense.amount)}
          </p>
          <div className="flex items-center justify-end gap-1 mt-1">
            <button type="button" onClick={onToggle} className="btn btn-ghost btn-icon !p-1" title={expense.is_active ? 'Pasifleştir' : 'Aktive et'}>
              <Power className={`w-3 h-3 ${expense.is_active ? 'text-positive-500' : 'text-zinc-400'}`} />
            </button>
            <button type="button" onClick={onEdit} className="btn btn-ghost btn-icon !p-1" title="Düzenle">
              <Pencil className="w-3 h-3" />
            </button>
            <button type="button" onClick={onDelete} className="btn btn-ghost btn-icon !p-1 hover:!text-negative-600" title="Sil">
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// DEBT ROW
// ============================================================

function DebtRow({ debt, onEdit, onDelete, onMarkPaid }) {
  const isReceivable = debt.direction === 'receivable';
  const sign = isReceivable ? '+' : '−';
  const colorClass = isReceivable
    ? 'text-positive-600 dark:text-positive-400'
    : 'text-negative-600 dark:text-negative-400';
  const bgClass = isReceivable
    ? 'bg-positive-100 dark:bg-positive-950/30 text-positive-600 dark:text-positive-400'
    : 'bg-negative-100 dark:bg-negative-950/30 text-negative-600 dark:text-negative-400';

  // Bugune kalan gun sayisi
  const daysRemaining = useMemo(() => {
    if (!debt.due_date || debt.is_paid) return null;
    const today = new Date();
    today.setHours(0,0,0,0);
    const due = new Date(debt.due_date);
    return Math.round((due - today) / (1000 * 60 * 60 * 24));
  }, [debt.due_date, debt.is_paid]);

  return (
    <div className={`card p-3 ${debt.is_paid ? 'opacity-60' : ''}`}>
      <div className="flex items-start gap-3">
        <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 ${bgClass}`}>
          {isReceivable ? <ArrowDownToLine className="w-4 h-4" /> : <ArrowUpToLine className="w-4 h-4" />}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap">
            <h4 className="font-semibold text-sm">{debt.counterparty}</h4>
            {debt.is_paid && (
              <span className="chip chip-positive !text-[10px]">
                <CheckCircle className="w-2.5 h-2.5" /> Ödendi
              </span>
            )}
          </div>
          {debt.description && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5 line-clamp-2">
              {debt.description}
            </p>
          )}
          <div className="flex items-center gap-2 text-[11px] text-zinc-500 mt-1 flex-wrap">
            {debt.due_date && (
              <span className="flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatDate(debt.due_date)}
              </span>
            )}
            {daysRemaining !== null && (
              <span className={`font-numeric ${
                daysRemaining < 0 ? 'text-negative-600 font-semibold' :
                daysRemaining <= 3 ? 'text-warn-600 font-semibold' :
                'text-zinc-500'
              }`}>
                {daysRemaining < 0 ? `${-daysRemaining} gün gecikti` :
                 daysRemaining === 0 ? 'Bugün' :
                 daysRemaining === 1 ? 'Yarın' :
                 `${daysRemaining} gün kaldı`}
              </span>
            )}
            {debt.is_paid && debt.paid_date && (
              <span>Ödenme: {formatDate(debt.paid_date)}</span>
            )}
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className={`font-numeric font-bold text-base ${colorClass}`}>
            {sign}{formatTL(debt.amount)}
          </p>
          <div className="flex items-center justify-end gap-1 mt-1">
            {!debt.is_paid && (
              <button
                onClick={onMarkPaid}
                className="btn btn-ghost btn-icon !p-1 hover:!text-positive-600"
                title="Ödendi olarak işaretle"
              >
                <CheckCircle className="w-3.5 h-3.5" />
              </button>
            )}
            <button type="button" onClick={onEdit} className="btn btn-ghost btn-icon !p-1" title="Düzenle">
              <Pencil className="w-3 h-3" />
            </button>
            <button type="button" onClick={onDelete} className="btn btn-ghost btn-icon !p-1 hover:!text-negative-600" title="Sil">
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// INCOME FORM MODAL
// ============================================================

function IncomeFormModal({ income, onClose, onSave }) {
  const isNew = !income;
  const [name, setName] = useState(income?.name || '');
  const [amount, setAmount] = useState(income?.amount?.toString() || '');
  const [dayOfMonth, setDayOfMonth] = useState(income?.day_of_month?.toString() || '1');
  const [isActive, setIsActive] = useState(income?.is_active !== false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) { setError('Ad boş olamaz'); return; }
    const amt = parseTRNumber(amount); // W3-001
    if (!amt || amt <= 0) { setError('Geçerli tutar girin'); return; }
    const day = parseInt(dayOfMonth);
    if (!day || day < 1 || day > 31) { setError('Gün 1-31 arasında olmalı'); return; }

    setBusy(true);
    setError(null);

    try {
      await onSave({
        name: name.trim(),
        amount: amt,
        day_of_month: day,
        is_active: isActive,
      }, isNew);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isNew ? 'Yeni periyodik gelir' : 'Geliri düzenle'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Ad</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="input"
            placeholder="Maaş, Burs, Kira..."
            autoFocus
          />
        </div>

        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tutar (TL)</label>
          <input
            type="text"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="input font-numeric !text-base !font-semibold"
            placeholder="8300"
          />
        </div>

        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">
            Ayın hangi günü? (1-31)
          </label>
          <input
            type="number"
            min="1"
            max="31"
            value={dayOfMonth}
            onChange={(e) => setDayOfMonth(e.target.value)}
            className="input font-numeric"
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          Aktif (Cockpit hesaplamasına dahil)
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
// EXPENSE FORM MODAL
// ============================================================

function ExpenseFormModal({ expense, accounts, onClose, onSave }) {
  const isNew = !expense;
  const [name, setName] = useState(expense?.name || '');
  const [amount, setAmount] = useState(expense?.amount?.toString() || '');
  const [accountId, setAccountId] = useState(expense?.account_id?.toString() || '');
  const [dayOfMonth, setDayOfMonth] = useState(expense?.day_of_month?.toString() || '1');
  const [category, setCategory] = useState(
    expense?.category
      ? (EXPENSE_CATEGORIES.includes(expense.category) ? expense.category : 'diger')
      : 'abonelik'
  );
  const [customCategory, setCustomCategory] = useState(
    expense?.category && !EXPENSE_CATEGORIES.includes(expense.category) ? expense.category : ''
  );
  const [isActive, setIsActive] = useState(expense?.is_active !== false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) { setError('Ad boş olamaz'); return; }
    const amt = parseTRNumber(amount); // W3-001
    if (!amt || amt <= 0) { setError('Geçerli tutar girin'); return; }
    const day = parseInt(dayOfMonth);
    if (!day || day < 1 || day > 31) { setError('Gün 1-31 arasında olmalı'); return; }
    if (!accountId) { setError('Hesap seçmelisiniz'); return; }
    const finalCategory = category === 'diger' ? (customCategory.trim() || 'diger') : category;

    setBusy(true);
    setError(null);
    try {
      await onSave({
        name: name.trim(),
        amount: amt,
        account_id: parseInt(accountId),
        category: finalCategory,
        day_of_month: day,
        is_active: isActive,
      }, isNew);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isNew ? 'Yeni düzenli gider' : 'Gideri düzenle'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Ad</label>
          <input type="text" value={name} onChange={e => setName(e.target.value)}
            className="input" placeholder="Netflix, Kira, İnternet..." autoFocus />
        </div>
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tutar (TL)</label>
          <input type="text" value={amount} onChange={e => setAmount(e.target.value)}
            className="input font-numeric !text-base !font-semibold" placeholder="149" />
        </div>
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Hesap</label>
          <select value={accountId} onChange={e => setAccountId(e.target.value)} className="input">
            <option value="">Hesap seçin...</option>
            {accounts.map(a => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Kategori</label>
          <select value={category} onChange={e => setCategory(e.target.value)} className="input">
            {EXPENSE_CATEGORIES.map(c => (
              <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
            ))}
          </select>
        </div>
        {category === 'diger' && (
          <div>
            <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Özel kategori</label>
            <input type="text" value={customCategory} onChange={e => setCustomCategory(e.target.value)}
              className="input" placeholder="spor, aidat..." />
          </div>
        )}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Ayın hangi günü? (1-31)</label>
          <input type="number" min="1" max="31" value={dayOfMonth}
            onChange={e => setDayOfMonth(e.target.value)} className="input font-numeric" />
        </div>
        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} className="w-4 h-4 rounded" />
          Aktif (otomatik tetiklenir)
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
// DEBT FORM MODAL
// ============================================================

function DebtFormModal({ debt, onClose, onSave }) {
  const isNew = !debt;
  const [counterparty, setCounterparty] = useState(debt?.counterparty || '');
  const [direction, setDirection] = useState(debt?.direction || 'receivable');
  const [amount, setAmount] = useState(debt?.amount?.toString() || '');
  const [description, setDescription] = useState(debt?.description || '');
  const [dueDate, setDueDate] = useState(debt?.due_date || '');
  const [isPaid, setIsPaid] = useState(debt?.is_paid || false);
  const [paidDate, setPaidDate] = useState(debt?.paid_date || '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!counterparty.trim()) { setError('Karşı taraf boş olamaz'); return; }
    const amt = parseTRNumber(amount); // W3-001
    if (!amt || amt <= 0) { setError('Geçerli tutar girin'); return; }

    setBusy(true);
    setError(null);

    try {
      await onSave({
        counterparty: counterparty.trim(),
        direction,
        amount: amt,
        description: description.trim() || null,
        due_date: dueDate || null,
        is_paid: isPaid,
        paid_date: isPaid ? (paidDate || todayLocalISO()) : null,
      }, isNew);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isNew ? 'Yeni borç/alacak' : 'Kaydı düzenle'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Yön */}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setDirection('receivable')}
            className={`btn !text-xs ${direction === 'receivable' ? 'btn-positive' : 'btn-secondary'}`}
          >
            <ArrowDownToLine className="w-3.5 h-3.5" /> Alacak
          </button>
          <button
            type="button"
            onClick={() => setDirection('payable')}
            className={`btn !text-xs ${direction === 'payable' ? 'btn-negative' : 'btn-secondary'}`}
          >
            <ArrowUpToLine className="w-3.5 h-3.5" /> Borç
          </button>
        </div>

        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">
            {direction === 'receivable' ? 'Bana gelecek (kim)' : 'Vereceğim (kime)'}
          </label>
          <input
            type="text"
            value={counterparty}
            onChange={(e) => setCounterparty(e.target.value)}
            className="input"
            placeholder="Ali, Anne, Kardeşim..."
            autoFocus
          />
        </div>

        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tutar (TL)</label>
          <input
            type="text"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="input font-numeric !text-base !font-semibold"
            placeholder="850"
          />
        </div>

        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Vade tarihi</label>
          <input
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
            className="input"
          />
        </div>

        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Açıklama (opsiyonel)</label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input"
            placeholder="Kredi #5 payı 4/9 vb."
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={isPaid}
            onChange={(e) => setIsPaid(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          Ödendi olarak işaretle
        </label>

        {isPaid && (
          <div>
            <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Ödeme tarihi</label>
            <input
              type="date"
              value={paidDate || todayLocalISO()}
              onChange={(e) => setPaidDate(e.target.value)}
              className="input"
            />
          </div>
        )}

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

function ConfirmDeleteModal({ item, onClose, onConfirm }) {
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

  const data = item.item;
  const label = item.kind === 'income' || item.kind === 'expense'
    ? `${data.name} (${formatTL(data.amount)} TL/ay)`
    : `${data.counterparty} · ${formatTL(data.amount)} TL`;

  return (
    <Modal title={item.kind === 'income' ? 'Geliri sil' : item.kind === 'expense' ? 'Gideri sil' : 'Kaydı sil'} onClose={onClose}>
      <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-negative-50 dark:bg-negative-950/30 border border-negative-200 dark:border-negative-800">
        <AlertTriangle className="w-5 h-5 text-negative-600 dark:text-negative-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold text-negative-700 dark:text-negative-300 mb-1">{label}</p>
          <p className="text-zinc-700 dark:text-zinc-300">
            Bu kayıt silinecek. Geri alınamaz.
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
// MODAL WRAPPER
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
          <button type="button" onClick={onClose} className="btn btn-ghost btn-icon !p-1.5" title="Kapat">
            <X className="w-4 h-4" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}