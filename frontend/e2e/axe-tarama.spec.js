/**
 * A11Y-019 KAPISI (BUG #452) — OTOMATİK ERİŞİLEBİLİRLİK TARAMASI (axe-core).
 *
 * Ölçülen (13 Eyl 2026): a11y kapıları elle yazılmış ölçümlerdi (kontrast, dokunma hedefi,
 * etiket bağı, odak); kural motoru yoktu. axe-core her panel × iki temada koşar ve
 * "serious"/"critical" ihlalleri sayar (WCAG 2.1 A/AA kural kümesi).
 *
 * Ölçüm önce: kapı 0 ihlalle koşuyor; "minor/moderate" bulgular raporlanır ama kapıyı kırmaz
 * (önce say, sonra kapıya çevir — kontrast kapısındaki yol).
 * Koşum: python -m scripts.e2e_izole --test axe-tarama
 */
import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const API = process.env.E2E_API || 'http://localhost:8000';
let token;

test.beforeAll(async ({ request }) => {
  const r = await request.post(`${API}/api/auth/register`, {
    data: { email: `axe-${Date.now()}@example.com`, password: 'Kx7#vBnq2Lm!Zp94', kvkk_consent: true },
  });
  expect(r.status(), `register 201 — ${await r.text()}`).toBe(201);
  token = (await r.json()).access_token;
  // Bos hesapta acilis "Kurulum sihirbazi" modali sekmeleri kapatir (tema-mobil ile ayni kurulum):
  // en az bir nakit + bir kart hesabiyla paneller DOLU taranir.
  const h = { Authorization: `Bearer ${token}` };
  await request.post(`${API}/api/accounts`, { headers: h, data: { name: 'Axe Kasa', account_type: 'cash', balance: 5000 } });
  await request.post(`${API}/api/accounts`, {
    headers: h,
    data: { name: 'Axe Kart', account_type: 'credit_card', balance: -3000, credit_limit: 20000, statement_day: 5, due_day: 15 },
  });
});
test.afterAll(async ({ request }) => {
  if (token) await request.delete(`${API}/api/users/me`, { headers: { Authorization: `Bearer ${token}` } });
});

const PANELLER = ['Cockpit', 'Koç', 'Hesaplar', 'İşlemler', 'Gelir', 'Kırmızı', 'Raporlar',
                  'Akış', 'Borç Stratejisi', 'Hedefler', 'Bütçe', 'Aile', 'Hesap'];

for (const tema of ['dark', 'light']) {
  test(`axe / ${tema} tema: serious+critical ihlal yok`, async ({ page }) => {
    test.setTimeout(180_000);   // 13 panel × axe analizi (~2 sn) — varsayılan 30 sn yetmez
    await page.addInitScript(([t, th]) => {
      localStorage.setItem('fos_access_token', t);
      localStorage.setItem('theme', th);
      localStorage.setItem('fos_gorunum_modu', 'detayli');
    }, [token, tema]);
    await page.goto('/');
    await expect(page.getByRole('tab', { name: /Cockpit/ }).first()).toBeVisible();

    const ciddi = [];
    const hafif = [];
    for (const ad of PANELLER) {
      const btn = page.getByRole('tab', { name: new RegExp(ad) }).first();
      await btn.click();
      await page.waitForTimeout(700);
      const sonuc = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
      for (const v of sonuc.violations) {
        const satir = `[${ad}/${tema}] ${v.id} (${v.impact}): ${v.help} — ${v.nodes.length} öğe, örn. ${v.nodes[0]?.target?.join(' ')}`;
        (v.impact === 'serious' || v.impact === 'critical' ? ciddi : hafif).push(satir);
      }
    }
    if (hafif.length) console.log(`[axe/${tema}] hafif bulgular (kapıyı kırmaz):\n  ` + hafif.join('\n  '));
    expect(ciddi, ciddi.join('\n')).toEqual([]);
  });
}
