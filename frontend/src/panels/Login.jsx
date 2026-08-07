import { useEffect, useState } from 'react';
import SistemDurumu from '../components/SistemDurumu.jsx';
import { LogIn, UserPlus, Loader2, AlertTriangle, KeyRound, MailCheck } from 'lucide-react';
import { authApi, metaApi } from '../api.js';

/**
 * M11/M17/M18 (ADR-033) — Auth ekranı. AUTH_ENABLED açıkken token yokken App.jsx gösterir.
 * Modlar (router'sız tab-app): login | register | reset-request | reset.
 * - reset: Brevo e-postasındaki /auth/reset?token=.. linki → AuthGate resetToken geçirir.
 */
export default function Login({ onAuthed, initialError = null, initialMode = 'login', resetToken = null }) {
  const [mode, setMode] = useState(initialMode);      // login | register | reset-request | reset
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [kvkk, setKvkk] = useState(false);
  const [inviteCode, setInviteCode] = useState('');  // P7: kapalı beta davet kodu
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(initialError);
  const [notice, setNotice] = useState(null);         // başarı/bilgi mesajı
  // P8 (BUG #210): destek kanalı + kayıt modu. Giriş yapamayan kullanıcının
  // uygulama-içi geri bildirim widget'ına da erişimi yoktur; tek kanal budur.
  const [meta, setMeta] = useState(null);
  const [durumAcik, setDurumAcik] = useState(false);  // BUG #253: kimliksiz sistem durumu

  useEffect(() => {
    let iptal = false;
    metaApi.get().then((m) => { if (!iptal) setMeta(m); }).catch(() => {});
    return () => { iptal = true; };
  }, []);

  const isRegister = mode === 'register';
  const isResetReq = mode === 'reset-request';
  const isReset = mode === 'reset';
  const isLogin = mode === 'login';

  const go = (m) => { setMode(m); setError(null); setNotice(null); };

  const submit = async (e) => {
    e.preventDefault();
    setError(null); setNotice(null);
    try {
      setBusy(true);
      if (isResetReq) {
        if (!email.trim()) { setError('E-posta gerekli.'); return; }
        await authApi.passwordResetRequest(email.trim());
        setNotice('E-posta kayıtlıysa sıfırlama bağlantısı gönderildi. Gelen kutunu (ve spam) kontrol et.');
        return;
      }
      if (isReset) {
        if (password.length < 8) { setError('Şifre en az 8 karakter olmalı.'); return; }
        await authApi.passwordResetConfirm(resetToken, password);
        setNotice('Şifren güncellendi. Şimdi giriş yapabilirsin.');
        setMode('login'); setPassword('');
        return;
      }
      // login | register
      if (!email.trim() || !password) { setError('E-posta ve şifre gerekli.'); return; }
      if (isRegister && password.length < 8) { setError('Şifre en az 8 karakter olmalı.'); return; }
      if (isRegister && !kvkk) { setError('Devam etmek için KVKK açık rızası zorunlu.'); return; }
      if (isRegister) {
        await authApi.register({ email: email.trim(), password, name: name.trim() || undefined,
          kvkk_consent: kvkk, invite_code: inviteCode.trim() || undefined });
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

  const subtitle = isRegister ? 'Hesap oluştur'
    : isResetReq ? 'Şifre sıfırlama'
    : isReset ? 'Yeni şifre belirle'
    : 'Giriş yap';

  const submitLabel = isRegister ? 'Kayıt ol'
    : isResetReq ? 'Sıfırlama bağlantısı gönder'
    : isReset ? 'Şifreyi güncelle'
    : 'Giriş yap';

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-50 dark:bg-zinc-950 p-4">
      <div className="w-full max-w-sm card p-6 space-y-5">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-100">FinancialOS</h1>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">{subtitle}</p>
        </div>

        {error && (
          <div className="rounded-lg border border-warn-600/50 bg-warn-950/30 p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-warn-700 dark:text-warn-300 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-warn-200">{error}</p>
          </div>
        )}
        {notice && (
          <div className="rounded-lg border border-positive-600/50 bg-positive-950/30 p-3 flex items-start gap-2">
            <MailCheck className="w-4 h-4 text-positive-700 dark:text-positive-300 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-positive-200">{notice}</p>
          </div>
        )}

        <form onSubmit={submit} className="space-y-3">
          {/* E-posta: login/register/reset-request'te var, reset'te YOK */}
          {!isReset && (
            <div>
              <label className="text-xs text-zinc-500 dark:text-zinc-400">E-posta</label>
              <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                autoComplete="email" required
                className="mt-1 w-full rounded-md bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100" />
            </div>
          )}
          {isRegister && (
            <div>
              <label className="text-xs text-zinc-500 dark:text-zinc-400">Ad (opsiyonel)</label>
              <input type="text" value={name} onChange={(e) => setName(e.target.value)}
                autoComplete="name"
                className="mt-1 w-full rounded-md bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100" />
            </div>
          )}
          {/* Şifre: login/register/reset'te var, reset-request'te YOK */}
          {!isResetReq && (
            <div>
              <label className="text-xs text-zinc-500 dark:text-zinc-400">{isReset ? 'Yeni şifre' : 'Şifre'}</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                autoComplete={isRegister || isReset ? 'new-password' : 'current-password'} required
                className="mt-1 w-full rounded-md bg-zinc-100 dark:bg-zinc-800 border border-zinc-300 dark:border-zinc-700 px-3 py-2 text-sm text-zinc-900 dark:text-zinc-100" />
            </div>
          )}
          {isRegister && (
            <div>
              {/* P7 (BUG #199): kapalı betada kayıt davetlilere açıktır. Alan opsiyonel
                  görünür çünkü açık beta/dev modunda gerekmez; backend karar verir. */}
              <label className="block text-xs text-zinc-500 dark:text-zinc-400 mb-1">Davet kodu</label>
              <input
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                className="input"
                placeholder="Kapalı beta davet kodun (varsa)"
                autoComplete="off"
              />
            </div>
          )}
          {isRegister && (
            <label className="flex items-start gap-2 text-xs text-zinc-700 dark:text-zinc-300">
              <input type="checkbox" checked={kvkk} onChange={(e) => setKvkk(e.target.checked)} className="mt-0.5" />
              {/* BUG #191 (P4): eski link /docs/legal/...md idi — prod imajında docs/ YOK,
                  nginx SPA fallback'i index.html'e düşürüyordu → kullanıcı rıza verdiği metni
                  OKUYAMIYORDU. Metinler artık API'den sunuluyor. */}
              <span>
                <a href="/api/legal/kvkk" target="_blank" rel="noreferrer"
                  className="text-brand-600 dark:text-brand-400 underline">KVKK açık rıza metnini</a> ve{' '}
                <a href="/api/legal/kullanim-sartlari" target="_blank" rel="noreferrer"
                  className="text-brand-600 dark:text-brand-400 underline">kullanım şartlarını</a> okudum, onaylıyorum.
                <span className="block mt-1 text-zinc-500">
                  FinancialOS yatırım/finans tavsiyesi vermez; kararların sorumluluğu sana aittir.
                </span>
              </span>
            </label>
          )}

          <button type="submit" disabled={busy} className="btn btn-primary w-full justify-center">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" />
              : isRegister ? <UserPlus className="w-4 h-4" />
              : (isReset || isResetReq) ? <KeyRound className="w-4 h-4" />
              : <LogIn className="w-4 h-4" />}
            {submitLabel}
          </button>
        </form>

        {/* OAuth yalnız login/register'de */}
        {(isLogin || isRegister) && (
          <>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span className="flex-1 h-px bg-zinc-200 dark:bg-zinc-700" /> veya <span className="flex-1 h-px bg-zinc-200 dark:bg-zinc-700" />
            </div>
            <div className="space-y-2">
              <button type="button" onClick={() => authApi.oauthLogin('google')}
                className="btn btn-secondary w-full justify-center">
                <span aria-hidden="true">🔵</span> Google ile devam et
              </button>
              <button type="button" onClick={() => authApi.oauthLogin('github')}
                className="btn btn-secondary w-full justify-center">
                <span aria-hidden="true">⚫</span> GitHub ile devam et
              </button>
            </div>
          </>
        )}

        {/* Alt navigasyon */}
        <div className="text-center text-xs text-zinc-500 dark:text-zinc-400 space-y-1">
          {isLogin && (
            <>
              <div>
                <button type="button" onClick={() => go('reset-request')} className="text-zinc-500 dark:text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 underline">
                  Şifremi unuttum
                </button>
              </div>
              <div>Hesabın yok mu?{' '}
                <button type="button" onClick={() => go('register')} className="text-brand-600 dark:text-brand-400 underline">Kayıt ol</button>
              </div>
            </>
          )}
          {isRegister && (
            <div>Zaten hesabın var mı?{' '}
              <button type="button" onClick={() => go('login')} className="text-brand-600 dark:text-brand-400 underline">Giriş yap</button>
            </div>
          )}
          {(isResetReq || isReset) && (
            <button type="button" onClick={() => go('login')} className="text-brand-600 dark:text-brand-400 underline">← Girişe dön</button>
          )}
        </div>

        {/* P8 (BUG #210): DESTEK + hukuki metinler. Giriş yapamayan kullanıcı buradan
            ulaşır; kayıt öncesi KVKK/şartlar okunabilir olmalı. */}
        {meta && (
          <div className="pt-4 mt-4 border-t border-zinc-300 dark:border-zinc-700/60 text-center text-[11px] text-zinc-500 space-y-1">
            <div>
              <button type="button" onClick={() => setDurumAcik(true)}
                      className="text-zinc-500 dark:text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 underline">
                Sistem durumunu kontrol et
              </button>
            </div>
            <div>
              Sorun mu var?{' '}
              {meta.destek?.includes('@') ? (
                <a href={`mailto:${meta.destek}`} className="text-zinc-500 dark:text-zinc-400 hover:text-brand-600 dark:hover:text-brand-400 underline">
                  {meta.destek}
                </a>
              ) : (
                <span className="text-zinc-500 dark:text-zinc-400">{meta.destek}</span>
              )}
            </div>
            {meta.davet_kodu_gerekli && <div>Kayıt şu an <b>davetlilere</b> açık.</div>}
            <div className="flex items-center justify-center gap-3">
              {Object.entries(meta.hukuki || {}).map(([slug, url]) => (
                <a key={slug} href={url} target="_blank" rel="noreferrer"
                   className="text-zinc-500 hover:text-brand-600 dark:hover:text-brand-400 underline">{slug}</a>
              ))}
            </div>
            <div className="text-zinc-600">v{meta.surum}</div>
          </div>
        )}
      </div>
      {durumAcik && <SistemDurumu onClose={() => setDurumAcik(false)} />}
    </div>
  );
}
