import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  ShieldAlert, ShieldCheck, Shield, Plus, Pencil, Trash2, X,
  Loader2, AlertTriangle, RefreshCw, CheckCircle, Power,
  Flame, Target, BookOpen, Info,
} from 'lucide-react';
import { checkpointsApi, accountsApi, parseTRNumber } from '../api.js';  // H21: dayatılan kural formu
import { paraEtiketi } from '../lib/money.js';

/**
 * RedLines paneli — Master Checkpoint yonetimi.
 *
 * Ozellikler:
 *  - Tum MC'ler kart halinde, oncelige gore renkli (1=kritik kirmizi, 2=strateji turuncu, 3=normal mavi)
 *  - 4 tip: red_line / strategy / rule / context — her birinin ikonu
 *  - CRUD: ekle, duzenle, sil
 *  - Aktif/pasif toggle (tek tikla)
 *  - Tipe gore filtre + aktif/pasif filtre
 *  - 'Yeni MC' modal (tip + oncelik + baslik + aciklama)
 *
 * GUNCELLEMELER:
 *  - BUG #232 fix: liste `active_only=false` ile cekilir. Backend default'u active_only=True
 *    oldugundan pasiflestirilen (ve soft-delete edilen) kural hicbir sekmede gorunmuyordu.
 */

const TYPE_META = {
  red_line: {
    label: 'Kırmızı Çizgi',
    icon: Flame,
    color: 'negative',
    description: 'Asla geçilmeyecek sınır',
  },
  strategy: {
    label: 'Strateji',
    icon: Target,
    color: 'warn',
    description: 'Stratejik tercih',
  },
  rule: {
    label: 'Kural',
    icon: BookOpen,
    color: 'brand',
    description: 'Genel kural',
  },
  context: {
    label: 'Bağlam',
    icon: Info,
    color: 'positive',
    description: 'Bağlam bilgisi',
  },
};

const PRIORITY_META = {
  1: { label: 'Yüksek', color: 'negative' },
  2: { label: 'Orta', color: 'warn' },
  3: { label: 'Düşük', color: 'positive' },
};

export default function RedLines() {
  const [checkpoints, setCheckpoints] = useState([]);
  const [accounts, setAccounts] = useState([]);   // H21: 'dokunulmaz hesap' kuralı için
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const [editing, setEditing] = useState(null);  // null | 'new' | mc obj
  const [confirmDelete, setConfirmDelete] = useState(null);

  const [filterType, setFilterType] = useState('all');
  const [filterActive, setFilterActive] = useState('active');  // active | inactive | all

  const load = useCallback(async () => {
    try {
      setError(null);
      // BUG #232 fix: backend GET /api/checkpoints `active_only=True` DEFAULT'ludur.
      // Parametresiz çağırıldığında pasif kurallar istemciye HİÇ ulaşmıyordu — bu panelin
      // Aktif/Pasif/Hepsi filtresi istemci-taraflı olduğu için "Pasifleştir" basılan kural
      // her sekmeden kayboluyor, "N pasif" sayacı hep 0 kalıyordu. Pasifleştirme = tarihçeyi
      // koruyarak devre dışı bırakma; kullanıcı kuralı geri açabilmek için GÖREBİLMELİ.
      const data = await checkpointsApi.list({ active_only: false });
      setCheckpoints(data || []);
    } catch (e) {
      setError(e.message || 'Kırmızı çizgiler yüklenemedi');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // H21: 'dokunulmaz hesap' kuralı için hesap listesi (hata olursa kural formu yine açılır —
  // yalnız o seçenek boş kalır; panel çökmez).
  useEffect(() => {
    accountsApi.list().then(setAccounts).catch(() => setAccounts([]));
  }, []);

  const handleRefresh = () => { setRefreshing(true); load(); };

  // Filtreli liste — oncelige sonra olusturulma sirasina gore sirali
  const filtered = useMemo(() => {
    let list = checkpoints;
    if (filterType !== 'all') {
      list = list.filter(c => c.checkpoint_type === filterType);
    }
    if (filterActive === 'active') {
      list = list.filter(c => c.is_active);
    } else if (filterActive === 'inactive') {
      list = list.filter(c => !c.is_active);
    }
    return [...list].sort((a, b) => {
      if (a.is_active !== b.is_active) return a.is_active ? -1 : 1;
      const pA = a.priority || 99;
      const pB = b.priority || 99;
      if (pA !== pB) return pA - pB;
      return (a.id || 0) - (b.id || 0);
    });
  }, [checkpoints, filterType, filterActive]);

  // Tip bazli sayim
  const counts = useMemo(() => {
    const c = { red_line: 0, strategy: 0, rule: 0, context: 0, active: 0, inactive: 0 };
    checkpoints.forEach(cp => {
      if (cp.checkpoint_type) c[cp.checkpoint_type] = (c[cp.checkpoint_type] || 0) + 1;
      if (cp.is_active) c.active++;
      else c.inactive++;
    });
    return c;
  }, [checkpoints]);

  const handleSave = async (data, isNew) => {
    if (isNew) await checkpointsApi.create(data);
    else await checkpointsApi.update(editing.id, data);
    setEditing(null);
    handleRefresh();
  };

  const handleToggleActive = async (cp) => {
    // W3-008: hata yakalanmalı — aksi halde sessiz başarısızlık + unhandled rejection
    try {
      setError(null);
      await checkpointsApi.update(cp.id, { is_active: !cp.is_active });
      handleRefresh();
    } catch (e) {
      setError(e.message || 'Durum değiştirilemedi');
    }
  };

  const handleDelete = async () => {
    try {
      setError(null);
      await checkpointsApi.delete(confirmDelete.id);
      setConfirmDelete(null);
      handleRefresh();
    } catch (e) {
      setError(e.message || 'Silinemedi');
    }
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
              Kırmızı çizgiler yüklenemedi
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
    <div className="space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold mb-1">Kırmızı Çizgiler</h2>
          <p className="text-sm text-zinc-600 dark:text-zinc-400">
            Koç bu kuralları her cevabında dikkate alır · {counts.active} aktif, {counts.inactive} pasif
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button type="button" onClick={handleRefresh} disabled={refreshing} className="btn btn-secondary !text-xs">
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Yenile</span>
          </button>
          <button type="button" onClick={() => setEditing('new')} className="btn btn-primary !text-xs">
            <Plus className="w-3.5 h-3.5" /> Yeni
          </button>
        </div>
      </div>

      {/* Tip ozet — 4 kart */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {Object.entries(TYPE_META).map(([key, meta]) => {
          const Icon = meta.icon;
          const count = counts[key] || 0;
          return (
            <button
              key={key}
              onClick={() => setFilterType(filterType === key ? 'all' : key)}
              className={`card p-3 text-left transition-all ${
                filterType === key
                  ? `ring-2 ring-${meta.color}-500 dark:ring-${meta.color}-600`
                  : 'hover:border-zinc-300 dark:hover:border-zinc-700'
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <Icon className={`w-4 h-4 text-${meta.color}-600 dark:text-${meta.color}-400`} />
                <span className="text-xs font-semibold">{meta.label}</span>
              </div>
              <p className="font-numeric text-xl font-bold">{count}</p>
              <p className="text-[10px] text-zinc-500 mt-0.5">{meta.description}</p>
            </button>
          );
        })}
      </div>

      {/* Aktif/pasif filtre */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-zinc-500">Göster:</span>
        {[
          { id: 'active', label: 'Aktif' },
          { id: 'inactive', label: 'Pasif' },
          { id: 'all', label: 'Hepsi' },
        ].map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setFilterActive(id)}
            className={`btn !text-xs !px-3 ${filterActive === id ? 'btn-positive' : 'btn-secondary'}`}
          >
            {label}
          </button>
        ))}
        {filterType !== 'all' && (
          <button type="button" onClick={() => setFilterType('all')} className="chip ml-auto">
            <X className="w-3 h-3" /> Tip filtresi: {TYPE_META[filterType].label}
          </button>
        )}
      </div>

      {/* MC kartlari */}
      {filtered.length === 0 ? (
        <div className="card p-8 text-center">
          <ShieldAlert className="w-12 h-12 mx-auto text-zinc-400 mb-3" />
          <h3 className="font-semibold mb-2">
            {checkpoints.length === 0 ? 'Henüz kural yok' : 'Filtreyle eşleşen kural yok'}
          </h3>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mb-4">
            {checkpoints.length === 0
              ? 'Koçun davranışını yönlendiren ilk kuralını ekle.'
              : 'Filtreleri değiştirip tekrar dene.'}
          </p>
          {checkpoints.length === 0 && (
            <button type="button" onClick={() => setEditing('new')} className="btn btn-primary !text-xs">
              <Plus className="w-3.5 h-3.5" /> İlk kuralı ekle
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {filtered.map(cp => (
            <CheckpointCard
              key={cp.id}
              checkpoint={cp}
              onEdit={() => setEditing(cp)}
              onDelete={() => setConfirmDelete(cp)}
              onToggleActive={() => handleToggleActive(cp)}
            />
          ))}
        </div>
      )}

      {/* Modallar */}
      {editing && (
        <CheckpointFormModal
          checkpoint={editing === 'new' ? null : editing}
          accounts={accounts}
          onClose={() => setEditing(null)}
          onSave={handleSave}
        />
      )}

      {confirmDelete && (
        <ConfirmDeleteModal
          checkpoint={confirmDelete}
          onClose={() => setConfirmDelete(null)}
          onConfirm={handleDelete}
        />
      )}
    </div>
  );
}

// ============================================================
// CHECKPOINT CARD
// ============================================================

function CheckpointCard({ checkpoint, onEdit, onDelete, onToggleActive }) {
  const cp = checkpoint;
  const typeMeta = TYPE_META[cp.checkpoint_type] || TYPE_META.context;
  const priorityMeta = PRIORITY_META[cp.priority] || PRIORITY_META[2];
  const TypeIcon = typeMeta.icon;
  const [expanded, setExpanded] = useState(false);

  // Kisa aciklama (ilk 150 karakter)
  const description = cp.description || '';
  const isLong = description.length > 150;
  const shortDesc = isLong ? description.slice(0, 150) + '...' : description;

  return (
    <div className={`card p-4 ${!cp.is_active ? 'opacity-60' : ''} ${
      cp.is_active && cp.checkpoint_type === 'red_line' ? 'border-negative-300 dark:border-negative-800' : ''
    }`}>
      <div className="flex items-start gap-3">
        {/* Tip ikonu — sol */}
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 bg-${typeMeta.color}-100 dark:bg-${typeMeta.color}-950/30 text-${typeMeta.color}-600 dark:text-${typeMeta.color}-400`}>
          <TypeIcon className="w-5 h-5" />
        </div>

        {/* Orta — icerik */}
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2 flex-wrap mb-1">
            <h4 className="font-semibold text-sm">{cp.title}</h4>
            <span className={`chip chip-${typeMeta.color} !text-[10px]`}>
              {typeMeta.label}
            </span>
            <span className={`chip chip-${priorityMeta.color} !text-[10px]`}>
              {priorityMeta.label}
            </span>
            {!cp.is_active && (
              <span className="chip !text-[10px]">Pasif</span>
            )}
          </div>
          <p className="text-xs text-zinc-700 dark:text-zinc-300 leading-relaxed whitespace-pre-wrap">
            {expanded || !isLong ? description : shortDesc}
          </p>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="inline-flex items-center py-2 pr-3 text-[11px] text-brand-600 dark:text-brand-400 hover:underline mt-1"
            >
              {expanded ? 'Daha az göster' : 'Devamını oku'}
            </button>
          )}
        </div>

        {/* Sag — butonlar */}
        <div className="flex flex-col items-end gap-1 flex-shrink-0">
          <button
            onClick={onToggleActive}
            className={`btn btn-ghost btn-icon !p-1.5 ${cp.is_active ? 'text-positive-600' : 'text-zinc-400'}`}
            title={cp.is_active ? 'Pasifleştir' : 'Aktifleştir'}
          >
            <Power className="w-3.5 h-3.5" />
          </button>
          <button type="button" onClick={onEdit} className="btn btn-ghost btn-icon !p-1.5" title="Düzenle">
            <Pencil className="w-3.5 h-3.5" />
          </button>
          <button type="button" onClick={onDelete} className="btn btn-ghost btn-icon !p-1.5 hover:!text-negative-600" title="Sil">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================
// CHECKPOINT FORM MODAL
// ============================================================

function CheckpointFormModal({ checkpoint, accounts, onClose, onSave }) {
  const isNew = !checkpoint;
  const [title, setTitle] = useState(checkpoint?.title || '');
  const [description, setDescription] = useState(checkpoint?.description || '');
  const [type, setType] = useState(checkpoint?.checkpoint_type || 'rule');
  const [priority, setPriority] = useState(checkpoint?.priority?.toString() || '2');
  const [isActive, setIsActive] = useState(checkpoint?.is_active !== false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // H21 / BUG #192: DAYATILAN kural. Serbest metin kurallar koça bağlam olarak gider;
  // buradan bir tip seçilirse kural KOD SEVİYESİNDE uygulanır (işlem bloklanır).
  const [ruleType, setRuleType] = useState(checkpoint?.rule_type || '');
  const [ruleAmount, setRuleAmount] = useState(
    checkpoint?.rule_params?.amount != null ? String(checkpoint.rule_params.amount) : ''
  );
  const [ruleAccountId, setRuleAccountId] = useState(
    checkpoint?.rule_params?.account_id != null ? String(checkpoint.rule_params.account_id) : ''
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!title.trim()) { setError('Başlık boş olamaz'); return; }
    if (!description.trim()) { setError('Açıklama boş olamaz'); return; }

    setBusy(true);
    setError(null);

    try {
      // H21: yapılandırılmış kural parametreleri (boşsa gönderilmez → serbest metin kural)
      let rule_params = null;
      if (ruleType === 'account_untouchable') {
        const id = parseInt(ruleAccountId, 10);
        if (!id) { setError('Hesap seçmelisin'); setBusy(false); return; }
        rule_params = { account_id: id };
      } else if (ruleType) {
        const tutar = parseTRNumber(ruleAmount);
        if (!tutar || tutar <= 0) { setError('Geçerli bir tutar gir'); setBusy(false); return; }
        rule_params = { amount: tutar };
      }

      await onSave({
        title: title.trim(),
        description: description.trim(),
        checkpoint_type: type,
        priority: parseInt(priority),
        is_active: isActive,
        rule_type: ruleType || null,
        rule_params,
      }, isNew);
    } catch (e) {
      setError(e.message);
      setBusy(false);
    }
  };

  return (
    <Modal title={isNew ? 'Yeni kural' : 'Kuralı düzenle'} onClose={onClose}>
      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Tip secimi */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Tip</label>
          <div className="grid grid-cols-2 gap-2">
            {Object.entries(TYPE_META).map(([key, meta]) => {
              const Icon = meta.icon;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => setType(key)}
                  className={`btn !text-xs ${type === key ? `btn-${meta.color}` : 'btn-secondary'}`}
                >
                  <Icon className="w-3.5 h-3.5" /> {meta.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Oncelik */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Öncelik</label>
          <div className="grid grid-cols-3 gap-2">
            {Object.entries(PRIORITY_META).map(([key, meta]) => (
              <button
                key={key}
                type="button"
                onClick={() => setPriority(key)}
                className={`btn !text-xs ${priority === key ? `btn-${meta.color}` : 'btn-secondary'}`}
              >
                {key} - {meta.label}
              </button>
            ))}
          </div>
        </div>

        {/* Baslik */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">Başlık</label>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="input"
            placeholder="MC9 - Yeni Kural"
            autoFocus
          />
        </div>

        {/* Aciklama */}
        <div>
          <label className="block text-xs text-zinc-600 dark:text-zinc-400 mb-1">
            Açıklama (koç bunu kullanacak)
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="input min-h-[120px] resize-y"
            placeholder="Detaylı kural metnini buraya yaz. Koç her cevabında bu metni dikkate alır."
          />
          <p className="text-[10px] text-zinc-500 mt-1">
            Net, açık ve koçun anlayacağı şekilde yaz. Örnek: "Kart kullanım oranı %95'i aşarsa kullanıcıya kritik uyarı ver."
          </p>
        </div>

        {/* H21 / BUG #192: DAYATILAN kural — koçun iyi niyetine bırakılmaz, kod uygular */}
        <div className="rounded-lg border border-zinc-200 dark:border-zinc-700 p-3 space-y-2">
          <label className="block text-xs font-medium text-zinc-700 dark:text-zinc-300">
            Bu kural otomatik UYGULANSIN mı? (opsiyonel)
          </label>
          <select
            value={ruleType}
            onChange={(e) => setRuleType(e.target.value)}
            className="input"
          >
            <option value="">Hayır — yalnız koç dikkate alsın (serbest metin)</option>
            <option value="min_cash_floor">Nakdim şu tutarın altına inmesin</option>
            <option value="max_single_expense">Tek seferde şu tutardan fazla harcamayayım</option>
            <option value="account_untouchable">Şu hesaba dokunulmasın</option>
          </select>

          {ruleType && ruleType !== 'account_untouchable' && (
            <div>
              <label className="block text-[11px] text-zinc-600 dark:text-zinc-400 mb-1">Tutar ({paraEtiketi()})</label>
              <input
                type="text" inputMode="decimal"
                value={ruleAmount}
                onChange={(e) => setRuleAmount(e.target.value)}
                className="input" placeholder="örn. 8.000"
              />
            </div>
          )}

          {ruleType === 'account_untouchable' && (
            <div>
              <label className="block text-[11px] text-zinc-600 dark:text-zinc-400 mb-1">Hesap</label>
              <select value={ruleAccountId} onChange={(e) => setRuleAccountId(e.target.value)} className="input">
                <option value="">Seç…</option>
                {(accounts || []).map((a) => (
                  <option key={a.id} value={a.id}>{a.name}</option>
                ))}
              </select>
            </div>
          )}

          {ruleType && (
            <p className="text-[10px] text-brand-600 dark:text-brand-400">
              Bu kural seçildiğinde işlem <strong>gerçekten engellenir</strong> — koçun onayına bağlı değildir.
            </p>
          )}
        </div>

        <label className="flex items-center gap-2 text-sm text-zinc-700 dark:text-zinc-300">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="w-4 h-4 rounded"
          />
          Aktif (koç bu kuralı dikkate alır)
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

function ConfirmDeleteModal({ checkpoint, onClose, onConfirm }) {
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
    <Modal title="Kuralı sil" onClose={onClose}>
      <div className="flex items-start gap-3 mb-4 p-3 rounded-lg bg-negative-50 dark:bg-negative-950/30 border border-negative-200 dark:border-negative-800">
        <AlertTriangle className="w-5 h-5 text-negative-600 dark:text-negative-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm">
          <p className="font-semibold text-negative-700 dark:text-negative-300 mb-1">
            {checkpoint.title}
          </p>
          <p className="text-zinc-700 dark:text-zinc-300">
            Bu kural kalıcı olarak silinecek. Koç bir daha bu kuralı dikkate almayacak.
            Aktif/pasif geçişi yerine pasifleştirme tercih edilebilir.
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
        className="card p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto"
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
