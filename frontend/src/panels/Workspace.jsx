import { useState, useEffect, useCallback } from 'react';
import { Loader2, Plus, Trash2, Users, Mail, Check } from 'lucide-react';
import {
  workspaceApi, getActiveWorkspaceId, setActiveWorkspaceId,
} from '../api';
import { useToast } from '../components/Toast.jsx';

/**
 * M42/M43 (ADR-036) — Aile Hesabı / Workspace paneli.
 * Workspace listesi + aktif seçim (localStorage) + yeni workspace + üye listesi + davet.
 * İzinler backend'de (require_workspace); UI sadece owner'a davet/çıkar butonu gösterir.
 */
const ROLE_TR = { owner: 'Sahip', editor: 'Düzenleyici', viewer: 'Görüntüleyici' };

export default function Workspace() {
  const toast = useToast();
  const [list, setList] = useState([]);
  const [activeId, setActive] = useState(getActiveWorkspaceId());
  const [detail, setDetail] = useState(null);       // {members, role, ...}
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState('');
  const [invite, setInvite] = useState({ email: '', role: 'viewer' });
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(async () => {
    try {
      setLoading(true);
      const ws = await workspaceApi.list();
      setList(ws);
      // aktif yoksa personal'ı seç
      const active = getActiveWorkspaceId() || (ws.find((w) => w.is_personal) || ws[0])?.id;
      if (active) { setActive(String(active)); setActiveWorkspaceId(active); }
    } catch (e) {
      toast.error(e.message || 'Workspace listesi yüklenemedi');
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadDetail = useCallback(async (id) => {
    if (!id) return;
    try {
      setDetail(await workspaceApi.get(id));
    } catch (e) {
      toast.error(e.message || 'Workspace detayı yüklenemedi');
      setDetail(null);
    }
  }, [toast]);

  useEffect(() => { loadList(); }, [loadList]);
  useEffect(() => { loadDetail(activeId); }, [activeId, loadDetail]);

  const selectWs = (id) => { setActive(String(id)); setActiveWorkspaceId(id); };

  const createWs = async (e) => {
    e.preventDefault();
    if (!newName.trim()) return;
    try {
      setBusy(true);
      const ws = await workspaceApi.create(newName.trim());
      setNewName('');
      toast.success(`"${ws.name}" oluşturuldu`);
      await loadList();
      selectWs(ws.id);
    } catch (e) {
      toast.error(e.message || 'Oluşturulamadı');
    } finally { setBusy(false); }
  };

  const sendInvite = async (e) => {
    e.preventDefault();
    if (!invite.email.trim() || !detail) return;
    try {
      setBusy(true);
      const res = await workspaceApi.invite(detail.id, invite.email.trim(), invite.role);
      setInvite({ email: '', role: 'viewer' });
      toast.success(res.email_sent ? 'Davet e-postası gönderildi' : 'Davet linki oluşturuldu (e-posta yapılandırılmamış)');
      loadDetail(detail.id);
    } catch (e) {
      toast.error(e.message || 'Davet gönderilemedi');
    } finally { setBusy(false); }
  };

  const removeMember = async (userId) => {
    try {
      await workspaceApi.removeMember(detail.id, userId);
      toast.success('Üye çıkarıldı');
      loadDetail(detail.id);
    } catch (e) {
      toast.error(e.message || 'Çıkarılamadı');
    }
  };

  if (loading) {
    return <div className="flex justify-center py-12"><Loader2 className="animate-spin text-zinc-500 dark:text-zinc-400" /></div>;
  }

  const isOwner = detail?.role === 'owner';
  const canShare = detail && !detail.is_personal;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center gap-2 text-zinc-900 dark:text-zinc-100">
        <Users size={20} /><h2 className="text-lg font-semibold">Aile Hesabı / Workspace</h2>
      </div>

      {/* Workspace seçici */}
      <div className="flex flex-wrap gap-2">
        {list.map((w) => (
          <button
            key={w.id}
            onClick={() => selectWs(w.id)}
            className={`px-3 py-2 min-h-[44px] rounded-lg text-sm border transition ${
              String(w.id) === String(activeId)
                ? 'bg-blue-600 border-blue-500 text-white'
                : 'bg-zinc-100 dark:bg-zinc-800 border-zinc-300 dark:border-zinc-700 text-zinc-700 dark:text-zinc-300 hover:border-zinc-500'
            }`}
          >
            {w.name}
            {w.is_personal && <span className="ml-1 text-xs opacity-70">(kişisel)</span>}
            <span className="ml-2 text-xs opacity-60">{ROLE_TR[w.role]}</span>
          </button>
        ))}
      </div>

      {/* Yeni workspace */}
      <form onSubmit={createWs} className="flex gap-2">
        <input
          value={newName} onChange={(e) => setNewName(e.target.value)}
          placeholder="Yeni workspace adı (örn. Aile Bütçesi)"
          className="input flex-1 text-sm"
        />
        <button disabled={busy} className="px-3 py-2 min-h-[44px] rounded-lg bg-zinc-200 dark:bg-zinc-700 hover:bg-zinc-300 dark:hover:bg-zinc-600 text-zinc-900 dark:text-zinc-100 text-sm flex items-center gap-1">
          <Plus size={16} /> Oluştur
        </button>
      </form>

      {/* Üyeler */}
      {detail && (
        <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900/50 p-4 space-y-3">
          <div className="text-sm font-medium text-zinc-800 dark:text-zinc-200">
            {detail.name} — Üyeler ({detail.members.length})
          </div>
          <ul className="divide-y divide-zinc-200 dark:divide-zinc-800">
            {detail.members.map((m) => (
              <li key={m.user_id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-zinc-700 dark:text-zinc-300">
                  {m.name || m.email || `Kullanıcı #${m.user_id}`}
                  <span className="ml-2 text-xs text-zinc-500">{ROLE_TR[m.role]}</span>
                </span>
                {isOwner && m.user_id !== detail.owner_user_id && (
                  <button type="button" onClick={() => removeMember(m.user_id)}
                          className="text-zinc-500 hover:text-red-400 min-w-[44px] min-h-[44px] inline-flex items-center justify-center shrink-0 -my-2" title="Üyeyi çıkar">
                    <Trash2 size={15} />
                  </button>
                )}
              </li>
            ))}
          </ul>

          {/* Davet formu — sadece owner + paylaşımlı workspace */}
          {isOwner && canShare && (
            <form onSubmit={sendInvite} className="flex flex-wrap gap-2 pt-2 border-t border-zinc-200 dark:border-zinc-800">
              <input
                type="email" value={invite.email}
                onChange={(e) => setInvite({ ...invite, email: e.target.value })}
                placeholder="Davet edilecek e-posta"
                className="input flex-1 min-w-[180px] text-sm"
              />
              <select
                value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}
                className="input w-auto text-sm"
              >
                <option value="viewer">Görüntüleyici</option>
                <option value="editor">Düzenleyici</option>
              </select>
              <button disabled={busy} className="btn btn-primary text-sm">
                <Mail size={15} /> Davet et
              </button>
            </form>
          )}
          {detail.is_personal && (
            <p className="text-xs text-zinc-500 pt-2 border-t border-zinc-200 dark:border-zinc-800">
              Kişisel workspace paylaşılamaz. Aile paylaşımı için yeni bir workspace oluşturun.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** M42 — davet kabul ekranı (router'sız, /workspaces/join?token= URL'inde gösterilir). */
export function WorkspaceJoin({ token, onDone }) {
  const toast = useToast();
  const [state, setState] = useState('loading');  // loading | done | error
  const [msg, setMsg] = useState('');

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await workspaceApi.join(token);
        if (!alive) return;
        setActiveWorkspaceId(res.workspace_id);
        setState('done');
        setMsg(res.joined ? 'Workspace\'e katıldınız.' : 'Zaten bu workspace\'in üyesisiniz.');
      } catch (e) {
        if (!alive) return;
        setState('error');
        setMsg(typeof e.message === 'string' ? e.message : 'Davet kabul edilemedi.');
      }
    })();
    return () => { alive = false; };
  }, [token]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 p-4">
      <div className="max-w-sm w-full rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 p-6 text-center space-y-4">
        <Users className="mx-auto text-blue-600 dark:text-blue-400" size={28} />
        <h1 className="text-lg font-semibold">Workspace Daveti</h1>
        {state === 'loading' && <Loader2 className="animate-spin mx-auto text-zinc-500 dark:text-zinc-400" />}
        {state === 'done' && (
          <p className="text-sm text-emerald-600 dark:text-emerald-400 flex items-center justify-center gap-1">
            <Check size={16} /> {msg}
          </p>
        )}
        {state === 'error' && <p className="text-sm text-red-400">{msg}</p>}
        <button type="button" onClick={onDone}
                className="w-full px-3 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-sm">
          Uygulamaya git
        </button>
      </div>
    </div>
  );
}
