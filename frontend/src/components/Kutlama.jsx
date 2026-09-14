// UX-035 (BUG #480): kutlama pankartı + tek seferlik, kısa konfeti.
// Pankart `role="status"`: ekran okuyucu duyurur, odak çalmaz. Konfeti salt süs —
// `aria-hidden`, hareket azaltma tercihinde HİÇ çizilmez, 1,8 sn sonra kaldırılır ve aynı
// anahtar için bir daha oynamaz (localStorage). Kütüphane yok: 14 span + CSS animasyonu.
import { useEffect, useState } from 'react';
import { hareketAzaltilmisMi, kutlandi, kutlandiMi } from '../lib/kutlama.js';

export const KONFETI_SURESI_MS = 1800;
const PARCA = 14;
const RENKLER = ['bg-brand-500', 'bg-positive-500', 'bg-warn-500', 'bg-negative-500'];

export default function Kutlama({ kutlama }) {
  // Karar bir kez, bağlanırken verilir (çağıran `key={anahtar}` ile bağlar): konfeti yalnız
  // taze anahtar + hareket serbestken; anahtar o anda "kutlandı" olarak yazılır.
  const [konfeti, setKonfeti] = useState(() => {
    if (!kutlama || hareketAzaltilmisMi() || kutlandiMi(kutlama.anahtar)) return false;
    kutlandi(kutlama.anahtar);
    return true;
  });

  useEffect(() => {
    if (!konfeti) return undefined;
    const t = setTimeout(() => setKonfeti(false), KONFETI_SURESI_MS);
    return () => clearTimeout(t);
  }, [konfeti]);

  if (!kutlama) return null;
  return (
    <div
      role="status"
      data-testid="kutlama"
      className="card p-4 relative overflow-hidden border-brand-200 dark:border-brand-800 bg-brand-50/60 dark:bg-brand-950/30"
    >
      {konfeti && (
        <div aria-hidden="true" data-testid="konfeti" className="pointer-events-none absolute inset-0">
          {Array.from({ length: PARCA }, (_, i) => (
            <span
              key={i}
              className={`kutlama-parca ${RENKLER[i % RENKLER.length]}`}
              style={{ left: `${(i * 100) / PARCA + 3}%`, animationDelay: `${(i % 5) * 90}ms` }}
            />
          ))}
        </div>
      )}
      <p className="font-semibold text-brand-800 dark:text-brand-200">{kutlama.baslik}</p>
      {kutlama.detay && <p className="text-sm text-zinc-600 dark:text-zinc-300 mt-0.5">{kutlama.detay}</p>}
    </div>
  );
}
