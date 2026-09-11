/**
 * FE-026 / BUG #377 — BEKLEYEN EYLEM ÖZETİ HESABI "#3" DİYE GÖSTERİYORDU.
 *
 * Ölçülen: `PendingActions` her iki ebeveyninden de KOKPİT hesaplarını alır ve kokpit
 * hesabı `ad` taşır (rules_engine: `"ad": acc.name`). Dosyanın iki yeri `.ad` okurken
 * `PayloadOzeti.hesapAdi` `.name` okuyordu → `undefined || "#3"`. Düşüş dalı hatayı
 * bir görünüm sanmaya yetiyordu; kimse "hesap adı gelmiyor" demedi.
 *
 * Kilitlenen: kokpit biçimli hesap listesiyle özet tablosu hesap ADINI yazar, "#id" değil.
 *
 * KAPININ KENDİSİ DE KIRILDI: ilk yazım `add_transaction` kullanıyordu ve mutasyon
 * (`.ad` → `.name`) kapıyı kırmadı — `PayloadOzeti` yalnız add_transaction DIŞI türlerde
 * çizilir (BUG #266), yani test yanlış dalı ölçüyordu. Şimdi `update_account_balance`
 * ile doğru dal ölçülüyor ve ölçüm yalnız özet tablosuna (`<dl>`) bakıyor: sayfanın başka
 * yerinde "Enpara" geçmesi kapıyı geçirmez.
 */
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';

vi.mock('../src/api.js', async (orig) => {
  const m = await orig();
  return { ...m, actionsApi: { ...m.actionsApi, list: vi.fn().mockResolvedValue([]) } };
});

import PendingActions from './components/PendingActions.jsx';

const KOKPIT_HESAPLAR = [{ id: 3, ad: 'Enpara', tip: 'cash', bakiye: 4276 }];
const EYLEM = {
  id: 1, action_type: 'update_account_balance', status: 'pending', summary: 'Bakiye düzelt',
  payload: JSON.stringify({ account_id: 3, new_balance: 5000 }),
};

function ozetTablosu(accounts) {
  const { container } = render(
    <PendingActions actions={[EYLEM]} onResolved={() => {}} accounts={accounts} />,
  );
  const dl = container.querySelector('dl');
  expect(dl, 'özet tablosu çizilmedi — yanlış dal ölçülüyor').not.toBeNull();
  return dl.textContent;
}

describe('PendingActions hesap adı (FE-026)', () => {
  it('kokpit biçimli hesapla özet tablosu hesabın ADINI yazar, #id değil', () => {
    const metin = ozetTablosu(KOKPIT_HESAPLAR);
    expect(metin).toMatch(/Enpara/);
    expect(metin).not.toMatch(/#3(?!\d)/);
  });

  it('hesap gerçekten yoksa #id düşüşü kalır (bilinmeyen sıfır değildir)', () => {
    expect(ozetTablosu([])).toMatch(/#3(?!\d)/);
  });
});
