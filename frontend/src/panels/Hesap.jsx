/**
 * Hesap paneli — KVKK haklarının ARAYÜZDEKİ karşılığı (P4.4, BUG #215/#216).
 *
 * Sorun: KVKK rıza metni "verilerinizi uygulama üzerinden güncelleyebilir, dışa
 * aktarabilir, hesabınızı silebilirsiniz" diyordu. Gerçekte:
 *  - e-postayı değiştiren HİÇBİR uç yoktu (BUG #215),
 *  - dışa aktarma/silme uçları vardı ama arayüzde HİÇBİR YERDE kullanılmıyordu,
 *  - tek "Verimi indir" bağlantısı düz <a href> idi; Authorization başlığı taşımadığı
 *    için giriş açıkken 401 indiriyordu (BUG #216).
 * L8 dersi: belgelenen ≠ ulaşılabilir. Bu panel üç hakkı da fiilen kullanılabilir yapar.
 */
import { useState, useEffect } from 'react';
import { KeyRound, Mail, Download, Trash2, ShieldCheck } from 'lucide-react';
import { authApi, userApi, clearTokens, ApiError } from '../api.js';

const SILME_ONAY = 'HESABIMI SIL';

function Bolum({ ikon: Ikon, baslik, aciklama, children }) {
  return (
    <section className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-4 space-y-3">
      <div className="flex items-start gap-2">
        <Ikon className="w-4 h-4 mt-0.5 text-brand-600 dark:text-brand-400 flex-shrink-0" />
        <div>
          <h2 className="text-sm font-semibold">{baslik}</h2>
          {aciklama && <p className="text-xs text-zinc-500 mt-0.5">{aciklama}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

export default function Hesap() {
  const [profil, setProfil] = useState(null);
  const [durum, setDurum] = useState(null);      // {tip: 'ok'|'hata', mesaj}

  const [yeniEposta, setYeniEposta] = useState('');
  const [epostaSifre, setEpostaSifre] = useState('');
  const [mevcutSifre, setMevcutSifre] = useState('');
  const [yeniSifre, setYeniSifre] = useState('');
  const [silmeOnay, setSilmeOnay] = useState('');
  const [mesgul, setMesgul] = useState(false);

  useEffect(() => {
    authApi.me().then(setProfil).catch(() => userApi.get().then(setProfil).catch(() => {}));
  }, []);

  const calistir = async (is) => {
    setMesgul(true); setDurum(null);
    try {
      await is();
    } catch (e) {
      setDurum({ tip: 'hata', mesaj: e instanceof ApiError ? e.message : 'Beklenmedik hata.' });
    } finally {
      setMesgul(false);
    }
  };

  const epostaDegistir = (e) => {
    e.preventDefault();
    calistir(async () => {
      const r = await authApi.changeEmail(yeniEposta.trim(), epostaSifre);
      setDurum({ tip: 'ok', mesaj: r?.message || 'Doğrulama bağlantısı gönderildi.' });
      setYeniEposta(''); setEpostaSifre('');
    });
  };

  const sifreDegistir = (e) => {
    e.preventDefault();
    calistir(async () => {
      await authApi.changePassword(mevcutSifre, yeniSifre);
      setDurum({ tip: 'ok', mesaj: 'Şifren güncellendi. Diğer cihazlardaki oturumlar kapatıldı.' });
      setMevcutSifre(''); setYeniSifre('');
    });
  };

  const veriIndir = () => calistir(async () => {
    // Düz <a href> Authorization taşımaz (BUG #216) → veriyi yetkili istekle al, sonra indir.
    const veri = await authApi.exportData();
    const blob = new Blob([JSON.stringify(veri, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'financialos-verilerim.json';
    a.click();
    URL.revokeObjectURL(url);
    setDurum({ tip: 'ok', mesaj: 'Verilerin indirildi.' });
  });

  const hesabiSil = () => calistir(async () => {
    await authApi.deleteMe();
    clearTokens();
    window.location.reload();
  });

  return (
    <div className="space-y-4 max-w-2xl">
      <div>
        <h1 className="text-lg font-semibold">Hesap</h1>
        <p className="text-xs text-zinc-500 mt-1">
          Verilerin senin. Buradan düzeltebilir, indirebilir veya tamamen silebilirsin.
        </p>
      </div>

      {durum && (
        <div
          role="status"
          className={`text-sm rounded-lg px-3 py-2 ${
            durum.tip === 'ok'
              ? 'bg-positive-50 text-positive-700 dark:bg-positive-950/30 dark:text-positive-300'
              : 'bg-negative-50 text-negative-700 dark:bg-negative-950/30 dark:text-negative-300'
          }`}
        >
          {durum.mesaj}
        </div>
      )}

      <Bolum ikon={ShieldCheck} baslik="Kimlik">
        <dl className="text-sm space-y-1">
          <div className="flex gap-2">
            <dt className="text-zinc-500 w-24">Ad</dt>
            <dd>{profil?.name || '—'}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="text-zinc-500 w-24">E-posta</dt>
            <dd>{profil?.email || '—'}</dd>
          </div>
        </dl>
      </Bolum>

      <Bolum
        ikon={Mail}
        baslik="E-posta adresini değiştir"
        aciklama="Adres hemen değişmez: yeni adrese bir doğrulama bağlantısı gönderilir. Yanlış yazarsan hiçbir şey olmaz."
      >
        <form onSubmit={epostaDegistir} className="space-y-2">
          <input
            type="email" required value={yeniEposta} onChange={(e) => setYeniEposta(e.target.value)}
            placeholder="yeni@adres.com" aria-label="Yeni e-posta"
            className="input w-full"
          />
          <input
            type="password" value={epostaSifre} onChange={(e) => setEpostaSifre(e.target.value)}
            placeholder="Mevcut şifren" aria-label="Mevcut şifre (e-posta)"
            className="input w-full"
          />
          <button type="submit" disabled={mesgul} className="btn btn-primary min-h-[44px]">
            Doğrulama bağlantısı gönder
          </button>
        </form>
      </Bolum>

      <Bolum
        ikon={KeyRound}
        baslik="Şifreni değiştir"
        aciklama="Değiştirdiğinde diğer cihazlardaki oturumlar kapanır."
      >
        <form onSubmit={sifreDegistir} className="space-y-2">
          <input
            type="password" required value={mevcutSifre} onChange={(e) => setMevcutSifre(e.target.value)}
            placeholder="Mevcut şifren" aria-label="Mevcut şifre" className="input w-full"
          />
          <input
            type="password" required minLength={8} value={yeniSifre}
            onChange={(e) => setYeniSifre(e.target.value)}
            placeholder="Yeni şifren (en az 8 karakter)" aria-label="Yeni şifre" className="input w-full"
          />
          <button type="submit" disabled={mesgul} className="btn btn-primary min-h-[44px]">
            Şifreyi değiştir
          </button>
        </form>
      </Bolum>

      <Bolum
        ikon={Download}
        baslik="Verilerini indir"
        aciklama="Tüm verin taşınabilir JSON olarak iner — başka bir araca aktarabilirsin."
      >
        <button onClick={veriIndir} disabled={mesgul} className="btn btn-secondary min-h-[44px]">
          Verilerimi indir
        </button>
      </Bolum>

      <Bolum
        ikon={Trash2}
        baslik="Hesabını sil"
        aciklama="Hesabın ve tüm finansal verin kalıcı olarak silinir. Geri alınamaz."
      >
        <input
          value={silmeOnay} onChange={(e) => setSilmeOnay(e.target.value)}
          placeholder={`Onaylamak için "${SILME_ONAY}" yaz`}
          aria-label="Silme onayı" className="input w-full"
        />
        <button
          onClick={hesabiSil}
          disabled={mesgul || silmeOnay.trim() !== SILME_ONAY}
          className="btn btn-negative min-h-[44px] disabled:opacity-40"
        >
          Hesabımı kalıcı olarak sil
        </button>
      </Bolum>

      <p className="text-xs text-zinc-500">
        <a href="/api/legal/kvkk" className="underline">KVKK aydınlatma metni</a>
        {' · '}
        <a href="/api/legal/kullanim-sartlari" className="underline">Kullanım şartları</a>
      </p>
    </div>
  );
}
