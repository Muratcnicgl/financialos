import { useState, useEffect, useRef } from 'react';
import { Check, X, AlertCircle, Loader2, Pencil, Brain, TrendingUp } from 'lucide-react';
import { actionsApi, formatDate, todayLocalISO, parseTRNumber } from '../api.js';
import PremortemModal from './PremortemModal.jsx';
import HorizonsModal from './HorizonsModal.jsx';
import { formatPara, paraEtiketi } from '../lib/money.js';

/**
 * PendingActions — Onay bekleyen aksiyonlari listeler.
 * Her aksiyon icin "Onayla" / "Reddet" butonlari, payload onizlemesi.
 *
 * Props:
 *   actions: Aksiyon objesi (id veya action_id taşıyabilir)
 *     - GET /api/actions/pending -> PendingActionOut, 'id' field'i
 *     - POST /api/coach/chat response.proposed_actions -> 'action_id' field'i
 *   onResolved: (actionId, status) => void   [parent panel'de cockpit refresh icin]
 *
 * BUG #017 fix (2 May 2026): Iki farkli kaynak iki farkli field adi
 * kullaniyor. (a.id ?? a.action_id) ile her ikisini de destekliyoruz.
 */
// BUG #044 fix: add_transaction payload'ını okunabilir tabloya çevir
// Improvement #027: inline edit modu
// W3-009: bozuk JSON payload tüm listeyi çökertmesin — güvenli parse
function safeParsePayload(payload) {
  if (typeof payload !== 'string') return payload || {};
  try { return JSON.parse(payload); } catch { return {}; }
}

function TransactionTable({ actionId, payload, accounts, onEdited, setEditing: setParentEditing, editRequestedAt = 0 }) {
  const p = safeParsePayload(payload); // W3-009
  const todayISO = todayLocalISO();   // LOCAL bugün (UTC slice gece vardiyasında bir gün kayardı)

  const [editing, setEditing] = useState(false);
  const prevEditRequestedAt = useRef(0);
  const [saving, setSaving] = useState(false);
  const [edited, setEdited] = useState(false);
  const [editErr, setEditErr] = useState(null);
  const [form, setForm] = useState({
    amount: p?.amount ?? '',
    transaction_type: p?.transaction_type ?? 'expense',
    category: p?.category ?? '',
    transaction_date: p?.transaction_date ?? '',
    account_id: p?.account_id ?? '',
  });

  if (!p) return null;

  const startEdit = () => { setEditing(true); setParentEditing(true); setEditErr(null); };
  const cancelEdit = () => { setEditing(false); setParentEditing(false); setEditErr(null); };

  // E klavye kısayolundan edit tetikleme
  useEffect(() => {
    if (editRequestedAt > prevEditRequestedAt.current) {
      prevEditRequestedAt.current = editRequestedAt;
      if (!editing) startEdit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editRequestedAt]);

  const handleSave = async () => {
    setSaving(true);
    setEditErr(null);
    const newPayload = {
      ...p,
      amount: parseTRNumber(form.amount), // W3-001
      transaction_type: form.transaction_type,
      category: form.category.toLowerCase().trim(),
      account_id: form.account_id ? parseInt(form.account_id) : p.account_id,
      ...(form.transaction_date ? { transaction_date: form.transaction_date } : {}),
    };
    if (!form.transaction_date) delete newPayload.transaction_date;
    const summary = `${form.transaction_type === 'expense' ? 'Gider' : 'Gelir'}: ${formatPara(Number(form.amount))} — ${form.category}`;
    try {
      const updated = await actionsApi.edit(actionId, newPayload, summary);
      setEditing(false);
      setParentEditing(false);
      setEdited(true);
      onEdited?.(updated);
    } catch (e) {
      setEditErr(e.message || 'Kaydetme hatası.');
    } finally {
      setSaving(false);
    }
  };

  const accountName = accounts?.find(a => a.id === p.account_id)?.ad
    ?? (p.account_id ? `Hesap #${p.account_id}` : '—');
  const tarih = p.transaction_date
    ? formatDate(p.transaction_date, { withYear: true })
    : `Bugün (${formatDate(todayISO, { withYear: true })})`;

  if (editing) {
    return (
      <div className="mt-2 space-y-1.5 text-[11px]">
        <div className="grid grid-cols-2 gap-x-2 gap-y-1.5">
          <label className="text-zinc-500">Tutar ({paraEtiketi()})</label>
          <input type="number" step="0.01" value={form.amount}
            onChange={e => setForm(f => ({ ...f, amount: e.target.value }))}
            className="border border-zinc-300 dark:border-zinc-600 rounded px-1.5 py-0.5 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 w-full"
          />
          <label className="text-zinc-500">Tip</label>
          <select value={form.transaction_type}
            onChange={e => setForm(f => ({ ...f, transaction_type: e.target.value }))}
            className="border border-zinc-300 dark:border-zinc-600 rounded px-1.5 py-0.5 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 w-full"
          >
            <option value="expense">Gider</option>
            <option value="income">Gelir</option>
          </select>
          <label className="text-zinc-500">Kategori</label>
          <input type="text" value={form.category}
            onChange={e => setForm(f => ({ ...f, category: e.target.value }))}
            className="border border-zinc-300 dark:border-zinc-600 rounded px-1.5 py-0.5 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 w-full"
          />
          <label className="text-zinc-500">Tarih</label>
          <input type="date" value={form.transaction_date}
            onChange={e => setForm(f => ({ ...f, transaction_date: e.target.value }))}
            className="border border-zinc-300 dark:border-zinc-600 rounded px-1.5 py-0.5 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 w-full"
          />
          <label className="text-zinc-500">Hesap</label>
          <select value={form.account_id}
            onChange={e => setForm(f => ({ ...f, account_id: e.target.value }))}
            className="border border-zinc-300 dark:border-zinc-600 rounded px-1.5 py-0.5 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 w-full"
          >
            {accounts?.map(a => (
              <option key={a.id} value={a.id}>{a.ad}</option>
            ))}
          </select>
        </div>
        {editErr && <p className="text-red-500">{editErr}</p>}
        <div className="flex gap-1.5 mt-1">
          <button type="button" onClick={handleSave} disabled={saving}
            className="btn btn-positive !py-1 !text-[11px]">
            {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
            Kaydet
          </button>
          <button type="button" onClick={cancelEdit} disabled={saving}
            className="btn btn-secondary !py-1 !text-[11px]">
            <X className="w-3 h-3" /> İptal
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <table className="mt-2 w-full text-[11px] border-collapse">
        <tbody>
          {[
            ['Tutar',    formatPara(p.amount)],
            ['Tip',      p.transaction_type === 'expense' ? 'Gider' : 'Gelir'],
            ['Kategori', p.category || '—'],
            ['Tarih',    tarih],
            ['Hesap',    accountName],
          ].map(([label, val]) => (
            <tr key={label} className="border-b border-zinc-200 dark:border-zinc-700/50 last:border-0">
              <td className="py-0.5 pr-3 text-zinc-500 dark:text-zinc-400 whitespace-nowrap">{label}</td>
              <td className="py-0.5 font-medium text-zinc-800 dark:text-zinc-200">{val}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="flex items-center gap-2 mt-1.5">
        <button type="button" onClick={startEdit}
          className="btn btn-ghost !text-xs hover:!text-brand-600 dark:hover:!text-brand-600 dark:text-brand-400">
          <Pencil className="w-3 h-3" /> Düzenle
        </button>
        {edited && (
          <span className="chip chip-neutral text-[10px]">Değiştirildi</span>
        )}
      </div>
    </div>
  );
}

export default function PendingActions({ actions, onResolved, accounts }) {
  const [busyId, setBusyId] = useState(null);
  const [errorById, setErrorById] = useState({});
  const [editingById, setEditingById] = useState({});  // edit modu aktif aksiyon id'leri
  const [payloadById, setPayloadById] = useState({});  // edit sonrasi guncellenen payload
  const [editRequestTimes, setEditRequestTimes] = useState({});  // E kısayolu tetikleyici
  const [premortemActionId, setPremortemActionId] = useState(null);
  const [horizonsActionId, setHorizonsActionId] = useState(null);

  // Y/N/E klavye kısayolları — ilk bekleyen aksiyona uygulanır
  const actionsRef = useRef(actions);
  actionsRef.current = actions;
  const busyIdRef = useRef(busyId);
  busyIdRef.current = busyId;
  const editingByIdRef = useRef(editingById); // W3-006: handler tek sefer bağlanıyor, güncel edit durumu için ref
  editingByIdRef.current = editingById;

  useEffect(() => {
    const handler = (e) => {
      const tag = document.activeElement?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
      if (e.ctrlKey || e.metaKey || e.altKey) return;

      const acts = actionsRef.current;
      if (!acts?.length || busyIdRef.current) return;

      const firstId = acts[0]?.id ?? acts[0]?.action_id;
      if (!firstId) return;
      // W3-006: ilk aksiyon düzenleme modundaysa onay/red/düzenle butonları disabled —
      // klavye kısayolu da bypass etmemeli (yanlış onay/red riski).
      if (editingByIdRef.current[firstId]) return;

      if (e.key === 'y' || e.key === 'Y') {
        e.preventDefault();
        handleApprove(firstId);
      } else if (e.key === 'n' || e.key === 'N') {
        e.preventDefault();
        handleReject(firstId);
      } else if (e.key === 'e' || e.key === 'E') {
        e.preventDefault();
        setEditRequestTimes(prev => ({ ...prev, [firstId]: (prev[firstId] || 0) + 1 }));
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!actions || actions.length === 0) return null;

  // Yardimci: aksiyondan gercek id'yi cikar
  const getActionId = (a) => a?.id ?? a?.action_id;

  const handleApprove = async (actionId) => {
    setBusyId(actionId);
    setErrorById((prev) => ({ ...prev, [actionId]: null }));
    try {
      const res = await actionsApi.approve(actionId);
      onResolved?.(actionId, 'approved', res);
    } catch (e) {
      setErrorById((prev) => ({ ...prev, [actionId]: e.message }));
    } finally {
      setBusyId(null);
    }
  };

  const handleReject = async (actionId) => {
    setBusyId(actionId);
    setErrorById((prev) => ({ ...prev, [actionId]: null }));
    try {
      await actionsApi.reject(actionId);
      onResolved?.(actionId, 'rejected', null);
    } catch (e) {
      setErrorById((prev) => ({ ...prev, [actionId]: e.message }));
    } finally {
      setBusyId(null);
    }
  };

  // Aksiyon turune gore okunaklı baslık
  const typeLabels = {
    update_account_balance: 'Bakiye güncelle',
    add_transaction:        'İşlem ekle',
    mark_debt_paid:         'Borç ödendi',
    sell_investment:        'Yatırım sat',
    update_fund_price:      'Fiyat güncelle',
    add_master_checkpoint:  'Yeni kırmızı çizgi',
  };

  return (
    <>
    <div className="space-y-2 animate-slide-up">
      {actions.map((a) => {
        const aid = getActionId(a);
        const busy = busyId === aid;
        const isEditing = !!editingById[aid];
        const error = errorById[aid];
        const currentPayload = payloadById[aid] ?? a.payload;
        const payload = typeof currentPayload === 'string' ? currentPayload : JSON.stringify(currentPayload, null, 2);

        return (
          <div
            key={aid}
            className="card p-4 border-brand-300 dark:border-brand-700/50 bg-brand-50/50 dark:bg-brand-900/10"
          >
            <div className="flex items-start gap-3">
              <div className="w-8 h-8 rounded-lg bg-brand-100 dark:bg-brand-900/30 flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-4 h-4 text-brand-600 dark:text-brand-400" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="chip chip-neutral text-[10px]">
                    {typeLabels[a.action_type] || a.action_type}
                  </span>
                  <span className="text-[10px] text-zinc-500">#{aid}</span>
                </div>
                <p className="text-sm text-zinc-800 dark:text-zinc-200 leading-snug">
                  {a.summary}
                </p>

                {/* Payload onizleme — add_transaction: tablo; digerleri: JSON */}
                {a.action_type === 'add_transaction' ? (
                  <TransactionTable
                    actionId={aid}
                    payload={currentPayload}
                    accounts={accounts}
                    editRequestedAt={editRequestTimes[aid] || 0}
                    setEditing={(val) => setEditingById(prev => ({ ...prev, [aid]: val }))}
                    onEdited={(updated) => {
                      const p = safeParsePayload(updated.payload); // W3-009
                      setPayloadById(prev => ({ ...prev, [aid]: p }));
                    }}
                  />
                ) : (
                  <details className="mt-2">
                    <summary className="text-[11px] text-zinc-500 dark:text-zinc-400 cursor-pointer hover:text-zinc-700 dark:hover:text-zinc-200 select-none">
                      Detay
                    </summary>
                    <pre className="mt-2 text-[11px] bg-zinc-100 dark:bg-zinc-800/50 p-2 rounded font-numeric overflow-x-auto">
                      {payload}
                    </pre>
                  </details>
                )}

                {a.warning && (
                  <div className="mt-3 bg-warn-50 dark:bg-warn-900/20 border border-warn-300 dark:border-warn-700 rounded-md px-3 py-2 text-sm text-warn-800 dark:text-warn-200">
                    {a.warning}
                  </div>
                )}

                {error && (
                  <div className="mt-2 chip chip-negative text-[11px]">
                    <AlertCircle className="w-3 h-3" />
                    {error}
                  </div>
                )}

                <div className="flex gap-2 mt-3 flex-wrap">
                  <button
                    onClick={() => setPremortemActionId(aid)}
                    disabled={busy || isEditing}
                    className="btn btn-warn !py-1.5 !text-xs flex items-center gap-1"
                    title="6 ay sonra başarısızlık senaryolarını gör"
                  >
                    <Brain className="w-3.5 h-3.5" />
                    Premortem
                  </button>
                  <button
                    onClick={() => setHorizonsActionId(aid)}
                    disabled={busy || isEditing}
                    className="btn btn-primary !py-1.5 !text-xs flex items-center gap-1"
                    title="Bugün / 1 ay / 3 ay sonrasını gör"
                  >
                    <TrendingUp className="w-3.5 h-3.5" />
                    3 Ufuk
                  </button>
                  <button
                    onClick={() => handleApprove(aid)}
                    disabled={busy || isEditing}
                    className="btn btn-positive !py-1.5 !text-xs"
                  >
                    {busy ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Check className="w-3.5 h-3.5" />
                    )}
                    Onayla
                  </button>
                  <button
                    onClick={() => handleReject(aid)}
                    disabled={busy || isEditing}
                    className="btn btn-secondary !py-1.5 !text-xs"
                  >
                    <X className="w-3.5 h-3.5" />
                    Reddet
                  </button>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>

    {premortemActionId !== null && (
      <PremortemModal
        isOpen={premortemActionId !== null}
        onClose={() => setPremortemActionId(null)}
        actionId={premortemActionId}
        onApproved={(actionId, result) => {
          onResolved?.(actionId, 'approved', result);
        }}
      />
    )}
    {horizonsActionId !== null && (
      <HorizonsModal
        isOpen={horizonsActionId !== null}
        onClose={() => setHorizonsActionId(null)}
        actionId={horizonsActionId}
        onApproved={(actionId, result) => {
          onResolved?.(actionId, 'approved', result);
        }}
      />
    )}
  </>
  );
}