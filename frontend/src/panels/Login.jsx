import { useState } from 'react';
import { LogIn, UserPlus, Loader2, AlertTriangle } from 'lucide-react';
import { authApi } from '../api.js';

/**
 * M11 (ADR-033) — Login / Register ekranı. AUTH_ENABLED açıkken ve token yokken
 * App.jsx bunu gösterir. Başarıda onAuthed() ile uygulamaya geçilir.
 */
export default function Login({ onAuthed }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [kvkk, setKvkk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const isRegister = mode === 'register';

  const submit = async (e) => {
    e.preventDefault();
    setError(null);
    if (!email.trim() || !password) { setError('E-posta ve şifre gerekli.'); return; }
    if (isRegister && password.length < 8) { setError('Şifre en az 8 karakter olmalı.'); return; }
    if (isRegister && !kvkk) { setError('Devam etmek için KVKK açık rızası zorunlu.'); return; }
    setBusy(true);
    try {
      if (isRegister) {
        await authApi.register({ email: email.trim(), password, name: name.trim() || undefined, kvkk_consent: kvkk });
      } else {
        await authApi.login({ email: email.trim(), password });
      }
      onAuthed?.();
    } catch (err) {
      setError(err?.message || 'Bir hata oluştu.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 p-4">
      <div className="w-full max-w-sm card p-6 space-y-5">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-zinc-100">FinancialOS</h1>
          <p className="text-sm text-zinc-400 mt-1">
            {isRegister ? 'Hesap oluştur' : 'Giriş yap'}
          </p>
        </div>

        {error && (
          <div className="rounded-lg border border-warn-600/50 bg-warn-950/30 p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-warn-300 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-warn-200">{error}</p>
          </div>
        )}

        <form onSubmit={submit} className="space-y-3">
          <div>
            <label className="text-xs text-zinc-400">E-posta</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              autoComplete="email" required
              className="mt-1 w-full rounded-md bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-zinc-100" />
          </div>
          {isRegister && (
            <div>
              <label className="text-xs text-zinc-400">Ad (opsiyonel)</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                className="mt-1 w-full rounded-md bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-zinc-100" />
            </div>
          )}
          <div>
            <label className="text-xs text-zinc-400">Şifre</label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              autoComplete={isRegister ? 'new-password' : 'current-password'} required
              className="mt-1 w-full rounded-md bg-zinc-800 border border-zinc-700 px-3 py-2 text-sm text-zinc-100" />
          </div>
          {isRegister && (
            <label className="flex items-start gap-2 text-xs text-zinc-300">
              <input type="checkbox" checked={kvkk} onChange={(e) => setKvkk(e.target.checked)}
                className="mt-0.5" />
              <span>
                <a href="/docs/legal/kvkk-consent-v1.md" target="_blank" rel="noreferrer"
                  className="text-brand-400 underline">KVKK açık rıza metnini</a> okudum, onaylıyorum.
              </span>
            </label>
          )}

          <button type="submit" disabled={busy}
            className="btn btn-primary w-full justify-center">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" />
              : isRegister ? <UserPlus className="w-4 h-4" /> : <LogIn className="w-4 h-4" />}
            {isRegister ? 'Kayıt ol' : 'Giriş yap'}
          </button>
        </form>

        <div className="text-center text-xs text-zinc-400">
          {isRegister ? 'Zaten hesabın var mı? ' : 'Hesabın yok mu? '}
          <button type="button" onClick={() => { setMode(isRegister ? 'login' : 'register'); setError(null); }}
            className="text-brand-400 underline">
            {isRegister ? 'Giriş yap' : 'Kayıt ol'}
          </button>
        </div>
      </div>
    </div>
  );
}
