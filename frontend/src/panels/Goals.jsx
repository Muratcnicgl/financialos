import React, { useState, useEffect } from 'react';
import { goalsApi } from '../api';
import { formatTL, formatTLSuffix, formatDate, parseTRNumber } from '../api';
import { useToast } from '../components/Toast.jsx';
import { Loader2, Target, Plus, X, RefreshCw } from 'lucide-react';

function getGoalIcon(goalType) {
  return goalType === 'debt_freedom' ? '💰' : '🎯';
}

function getStatusColor(status) {
  const colors = {
    active:    'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
    achieved:  'bg-blue-500/20 text-blue-300 border-blue-500/30',
    paused:    'bg-zinc-500/20 text-zinc-300 border-zinc-500/30',
    abandoned: 'bg-rose-500/20 text-rose-300 border-rose-500/30',
  };
  return colors[status] || colors.active;
}

export default function Goals() {
  const toast = useToast();
  const [goals, setGoals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedGoal, setSelectedGoal] = useState(null);
  const [showCreateWizard, setShowCreateWizard] = useState(false);

  const fetchGoals = async () => {
    try {
      setLoading(true);
      const res = await goalsApi.list();
      setGoals(res);
    } catch (e) {
      toast.error(`Hedefler yüklenemedi: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchGoals(); }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-400">
        <Loader2 className="w-6 h-6 animate-spin mr-2" /> Yükleniyor...
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-zinc-100 flex items-center gap-2">
            <Target className="w-6 h-6 text-brand-400" />
            Hedefler
          </h2>
          <p className="text-sm text-zinc-400 mt-1">
            Tasarruf ve borç ödeme hedeflerini yönet. {goals.length} hedef.
          </p>
        </div>
        <button
          onClick={() => setShowCreateWizard(true)}
          className="btn btn-primary !text-xs flex items-center gap-1"
        >
          <Plus className="w-4 h-4" /> Yeni Hedef
        </button>
      </div>

      {/* Grid */}
      {goals.length === 0 ? (
        <div className="card p-8 text-center">
          <Target className="w-10 h-10 mx-auto text-zinc-500 mb-3" />
          <h3 className="text-lg text-zinc-200 mb-1">Hedef yok</h3>
          <p className="text-sm text-zinc-400 mb-4">İlk hedefinizi oluşturmaya başlayın.</p>
          <button
            onClick={() => setShowCreateWizard(true)}
            className="btn btn-secondary !text-xs"
          >
            <Plus className="w-4 h-4 mr-1" /> Hedef Oluştur
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {goals.map((goal) => (
            <GoalCard
              key={goal.id}
              goal={goal}
              onSelect={() => setSelectedGoal(goal)}
            />
          ))}
        </div>
      )}

      {selectedGoal && (
        <GoalDetailModal
          goal={selectedGoal}
          onClose={() => { setSelectedGoal(null); fetchGoals(); }}
        />
      )}

      {showCreateWizard && (
        <GoalCreateWizard
          onClose={() => {
            setShowCreateWizard(false);
            fetchGoals();
          }}
        />
      )}
    </div>
  );
}

// ============================================================
// GOAL CARD
// ============================================================

function GoalCard({ goal, onSelect }) {
  const progressPercent = parseFloat(goal.progress_percent) || 0;
  const statusText = {
    active:    'Aktif',
    achieved:  'Tamamlandı',
    paused:    'Duraklatıldı',
    abandoned: 'Vazgeçildi',
  }[goal.status] || 'Bilinmiyor';

  const color = goal.goal_type === 'debt_freedom'
    ? 'from-amber-500 to-amber-600'
    : 'from-emerald-500 to-emerald-600';

  return (
    <button
      onClick={onSelect}
      className="card p-5 text-left hover:border-brand-500/50 transition-colors cursor-pointer"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{getGoalIcon(goal.goal_type)}</span>
          <div>
            <h3 className="font-semibold text-zinc-100">{goal.title}</h3>
            <p className="text-xs text-zinc-400 mt-0.5">
              {goal.goal_type === 'debt_freedom' ? 'Borç Ödeme' : 'Tasarruf'}
            </p>
          </div>
        </div>
        <span className={`text-xs px-2 py-1 rounded border ${getStatusColor(goal.status)}`}>
          {statusText}
        </span>
      </div>

      {/* Progress bar — track + fill */}
      <div className="mb-4 h-2 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full bg-gradient-to-r ${color} rounded-full transition-all`}
          style={{ width: `${Math.min(progressPercent, 100)}%` }}
        />
      </div>
      <p className="text-xs text-zinc-500 mb-3">%{progressPercent.toFixed(1)}</p>

      <div className="grid grid-cols-3 gap-2 text-center text-sm">
        <div>
          <p className="text-zinc-400 text-xs">Mevcut</p>
          <p className="font-semibold text-zinc-100">{formatTL(goal.current_amount)}</p>
        </div>
        <div>
          <p className="text-zinc-400 text-xs">Hedef</p>
          <p className="font-semibold text-zinc-100">{formatTL(goal.target_amount)}</p>
        </div>
        <div>
          <p className="text-zinc-400 text-xs">Tahmini Bitiş</p>
          <p className="font-semibold text-zinc-100">
            {goal.projected_completion_date ? formatDate(goal.projected_completion_date) : '—'}
          </p>
        </div>
      </div>

      {/* FEAT-003: sinking fund — target_date'li birikim hedefinde aylık gereken katkı */}
      {goal.sinking_fund && !goal.sinking_fund.tamamlandi && (
        <div className={`mt-2 text-xs flex items-center justify-center gap-1.5 ${goal.sinking_fund.gecikmis ? 'text-negative-400' : 'text-zinc-400'}`}>
          <span>💧</span>
          {goal.sinking_fund.gecikmis
            ? `Vade geçti — kalan ${formatTL(goal.sinking_fund.aylik_gereken)} TL gerekli`
            : `Aylık gereken: ${formatTL(goal.sinking_fund.aylik_gereken)} TL/ay · ${goal.sinking_fund.kalan_ay} ay kaldı`}
        </div>
      )}
    </button>
  );
}

// ============================================================
// GOAL DETAIL MODAL
// ============================================================

function GoalDetailModal({ goal, onClose }) {
  const toast = useToast();
  const [tab, setTab] = useState('allocations');
  const [allocations, setAllocations] = useState([]);
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadDetail = async () => {
    try {
      const [allocs, rls] = await Promise.all([
        goalsApi.allocations.list(goal.id),
        goalsApi.rules.list(goal.id),
      ]);
      setAllocations(allocs);
      setRules(rls);
    } catch (e) {
      toast.error(`Detay yükleme hatası: ${e.message}`);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadDetail(); }, [goal.id]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      await goalsApi.refresh(goal.id);
      toast.success('Progress güncellendi');
      onClose(); // parent fetchGoals çağırır
    } catch (e) {
      toast.error(`Yenileme hatası: ${e.message}`);
    } finally {
      setRefreshing(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-700/50 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal header */}
        <div className="border-b border-zinc-700/50 p-5 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-xl flex-shrink-0">{getGoalIcon(goal.goal_type)}</span>
            <h3 className="text-lg font-semibold text-zinc-100 truncate">{goal.title}</h3>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="btn btn-ghost !text-xs flex items-center gap-1"
              title="Progress'i yeniden hesapla"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
              Yenile
            </button>
            <button type="button" onClick={onClose} className="text-zinc-400 hover:text-zinc-200">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Tab bar */}
        <div className="border-b border-zinc-700/50 flex">
          {['allocations', 'rules'].map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex-1 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                tab === t
                  ? 'text-brand-400 border-brand-400'
                  : 'text-zinc-400 border-transparent hover:text-zinc-200'
              }`}
            >
              {t === 'allocations' ? 'Allocations' : 'Kurallar'}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="flex-1 overflow-y-auto p-5">
          {loading ? (
            <div className="flex items-center justify-center h-32 text-zinc-400">
              <Loader2 className="w-5 h-5 animate-spin mr-2" /> Yükleniyor...
            </div>
          ) : tab === 'allocations' ? (
            <AllocationsTab allocations={allocations} goalId={goal.id} onRefresh={loadDetail} />
          ) : (
            <RulesTab rules={rules} goalId={goal.id} onRefresh={loadDetail} />
          )}
        </div>
      </div>
    </div>
  );
}

function AllocationsTab({ allocations, onRefresh }) {
  const toast = useToast();

  const handleDelete = async (id) => {
    try {
      await goalsApi.allocations.delete(id);
      toast.success('Allocation silindi');
      onRefresh();
    } catch (e) {
      toast.error(`Silinemedi: ${e.message}`);
    }
  };

  return (
    <div className="space-y-3">
      {allocations.length === 0 ? (
        <p className="text-sm text-zinc-400 text-center py-6">Henüz allocation yok.</p>
      ) : (
        allocations.map((a) => (
          <div key={a.id} className="bg-zinc-800/50 p-3 rounded text-sm flex items-center justify-between gap-2">
            <div className="text-zinc-300">
              <span className={a.amount >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                {a.amount >= 0 ? '+' : ''}{formatTLSuffix(a.amount)}
              </span>
              <span className="text-zinc-500 ml-2 text-xs">
                {a.source === 'rule' ? '• Kural' : '• Manuel'} · TX#{a.transaction_id}
              </span>
            </div>
            <button
              onClick={() => handleDelete(a.id)}
              className="text-zinc-500 hover:text-rose-400 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))
      )}
    </div>
  );
}

function RulesTab({ rules, goalId, onRefresh }) {
  const toast = useToast();

  const handleDelete = async (id) => {
    try {
      await goalsApi.rules.delete(id);
      toast.success('Kural silindi');
      onRefresh();
    } catch (e) {
      toast.error(`Silinemedi: ${e.message}`);
    }
  };

  const allocationLabel = (r) => {
    if (r.allocation_type === 'percent') return `%${r.allocation_value}`;
    if (r.allocation_type === 'fixed') return formatTLSuffix(r.allocation_value);
    return 'Tamamı';
  };

  return (
    <div className="space-y-3">
      {rules.length === 0 ? (
        <p className="text-sm text-zinc-400 text-center py-6">Henüz kural yok.</p>
      ) : (
        rules.map((r) => (
          <div key={r.id} className="bg-zinc-800/50 p-3 rounded flex items-start justify-between gap-2">
            <div className="text-sm">
              <p className="text-zinc-200 font-medium">{r.name}</p>
              <p className="text-zinc-500 text-xs mt-0.5">
                {JSON.stringify(r.criteria)} → {allocationLabel(r)}
                {!r.is_active && <span className="ml-2 text-zinc-600">(kapalı)</span>}
              </p>
            </div>
            <button
              onClick={() => handleDelete(r.id)}
              className="text-zinc-500 hover:text-rose-400 transition-colors flex-shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))
      )}
    </div>
  );
}

// ============================================================
// GOAL CREATE WIZARD
// ============================================================

function GoalCreateWizard({ onClose }) {
  const toast = useToast();
  const [step, setStep] = useState(1); // 1=tip, 2=detay
  const [goalType, setGoalType] = useState(null);
  const [form, setForm] = useState({ title: '', target_amount: '', target_date: '' });
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.title.trim() || !form.target_amount) return;

    setSaving(true);
    try {
      await goalsApi.create({
        goal_type: goalType,
        title: form.title.trim(),
        target_amount: parseTRNumber(form.target_amount), // W3-001
        target_date: form.target_date || null,
      });
      toast.success('Hedef oluşturuldu');
      onClose();
    } catch (e) {
      toast.error(`Oluşturulamadı: ${e.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-zinc-900 border border-zinc-700/50 rounded-lg w-full max-w-md"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="border-b border-zinc-700/50 p-5 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-zinc-100">
            {step === 1 ? 'Hedef Türü Seç' : 'Hedef Detayları'}
          </h3>
          <button type="button" onClick={onClose} className="text-zinc-400 hover:text-zinc-200">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5">
          {/* ADIM 1 — Tip Seçimi */}
          {step === 1 && (
            <div className="space-y-3">
              <p className="text-sm text-zinc-400 mb-4">
                Ne tür bir hedef oluşturmak istiyorsunuz?
              </p>
              <button
                onClick={() => { setGoalType('cash_target'); setStep(2); }}
                className="w-full p-4 rounded-lg border border-zinc-700 hover:border-emerald-500/50 hover:bg-emerald-500/5 transition-all text-left"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">🎯</span>
                  <div>
                    <p className="font-semibold text-zinc-100">Tasarruf Hedefi</p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Belirli bir miktar biriktirmek (acil fon, tatil vb.)
                    </p>
                  </div>
                </div>
              </button>
              <button
                onClick={() => { setGoalType('debt_freedom'); setStep(2); }}
                className="w-full p-4 rounded-lg border border-zinc-700 hover:border-amber-500/50 hover:bg-amber-500/5 transition-all text-left"
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl">💰</span>
                  <div>
                    <p className="font-semibold text-zinc-100">Borç Ödeme Hedefi</p>
                    <p className="text-xs text-zinc-400 mt-0.5">
                      Tüm kredi ve borçları kapatmak
                    </p>
                  </div>
                </div>
              </button>
            </div>
          )}

          {/* ADIM 2 — Detaylar */}
          {step === 2 && (
            <form onSubmit={handleSubmit} className="space-y-4">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                ← Geri
              </button>

              <div>
                <label className="block text-sm text-zinc-300 mb-1">Hedef Adı *</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder={goalType === 'debt_freedom' ? 'Borçsuz 2027' : 'Acil Fon 50k'}
                  className="input w-full"
                  required
                  autoFocus
                />
              </div>

              <div>
                <label className="block text-sm text-zinc-300 mb-1">Hedef Tutar (TL) *</label>
                <input
                  type="number"
                  value={form.target_amount}
                  onChange={(e) => setForm({ ...form, target_amount: e.target.value })}
                  placeholder="50000"
                  min="1"
                  step="0.01"
                  className="input w-full"
                  required
                />
              </div>

              <div>
                <label className="block text-sm text-zinc-300 mb-1">
                  Hedef Tarih <span className="text-zinc-500">(opsiyonel)</span>
                </label>
                <input
                  type="date"
                  value={form.target_date}
                  onChange={(e) => setForm({ ...form, target_date: e.target.value })}
                  className="input w-full"
                />
              </div>

              {goalType === 'debt_freedom' && (
                <p className="text-xs text-zinc-500 bg-zinc-800/50 rounded p-3">
                  💡 Borç ödeme hedefinde mevcut toplam kredi + kart bakiyeniz otomatik olarak
                  başlangıç noktası alınır.
                </p>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="btn btn-ghost flex-1"
                >
                  İptal
                </button>
                <button
                  type="submit"
                  disabled={saving || !form.title.trim() || !form.target_amount}
                  className="btn btn-primary flex-1 flex items-center justify-center gap-2"
                >
                  {saving && <Loader2 className="w-4 h-4 animate-spin" />}
                  Oluştur
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
