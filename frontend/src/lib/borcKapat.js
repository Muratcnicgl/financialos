// UX-013 (BUG #477): "Ödedim" / "Geldi" tek kaynak.
// Aynı işlem iki yerden tetiklenir (Gelir & Borç paneli, kokpit vade satırı). Gövde tek
// yerde: PUT ile kapat, sonucu kullanıcıya nakit ayağıyla birlikte söyle (BUG #241 — kayıt
// kapandı ama bakiye değişmediyse bunu SAKLAMA). Çağıran yalnız listeyi tazeler.
import { debtsApi, todayLocalISO } from '../api.js';
import { formatPara } from './money.js';

/**
 * @param {object} debt   {id, amount, direction}
 * @param {Array}  accounts  hesap listesi ({id, name} | {id, ad})
 * @param {object} toast  useToast() sonucu
 * @returns {Promise<object|null>} güncel kayıt; hata durumunda null (toast atılır)
 */
export async function borcuKapat(debt, accounts, toast) {
  try {
    const guncel = await debtsApi.update(debt.id, { is_paid: true, paid_date: todayLocalISO() });
    const tahsilat = debt.direction === 'receivable';
    const hesap = (accounts || []).find((a) => a.id === guncel?.settlement_account_id);
    if (hesap) {
      toast.success(
        `${tahsilat ? 'Tahsilat' : 'Ödeme'} işlendi: ${tahsilat ? '+' : '−'}${formatPara(debt.amount)}`,
        { detail: `${hesap.name || hesap.ad} bakiyesine yansıdı` },
      );
    } else {
      toast.warning('Kayıt ödendi olarak işaretlendi ama nakit bakiyesi değişmedi', {
        detail: 'Nakit hesap bulunamadı — Hesaplar sekmesinden bir nakit hesap ekle.',
      });
    }
    return guncel;
  } catch (e) {
    toast.error(`Ödendi işaretlenemedi: ${e.message}`);
    return null;
  }
}
