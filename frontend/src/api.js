/**
 * FinancialOS API client — backend 35 endpoint sarmalayicisi.
 *
 * Mimari: Tum istekler vite proxy uzerinden /api -> http://localhost:8000.
 * Bu yuzden BASE_URL gerekmiyor, fetch('/api/cockpit') yeterli.
 *
 * Hata yonetimi: ApiError sinifi firlatilir, panel tarafinda yakalanir.
 * Sayisal/tarih donusumu: backend Turkce alan adlari (nakit_kasa vb.)
 * koruyor — frontend ayni isimle kullanir, ekstra mapping yok.
 */

// =============================================================
// HATA SINIFI
// =============================================================

export class ApiError extends Error {
  constructor(status, detail, raw) {
    const message = typeof detail === 'string'
      ? detail
      : (detail?.message || JSON.stringify(detail) || `HTTP ${status}`);
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.raw = raw;
  }
}

// =============================================================
// CORE FETCH
// =============================================================

async function request(path, { method = 'GET', body, params } = {}) {
  let url = path;

  // Query string ekle
  if (params && Object.keys(params).length > 0) {
    const usp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') {
        usp.append(k, String(v));
      }
    }
    const qs = usp.toString();
    if (qs) url += (path.includes('?') ? '&' : '?') + qs;
  }

  const init = {
    method,
    headers: { 'Accept': 'application/json' },
  };

  if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(body);
  }

  let res;
  try {
    res = await fetch(url, init);
  } catch (e) {
    // Network hatasi (backend kapali, internet yok vb.)
    throw new ApiError(0, `Baglanti hatasi: ${e.message}`, null);
  }

  // 204 No Content
  if (res.status === 204) return null;

  // Cevap body'yi oku (JSON oncelikli)
  let data;
  const contentType = res.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await res.json();
    } catch {
      data = null;
    }
  } else {
    data = await res.text();
  }

  if (!res.ok) {
    // FastAPI hatalari {detail: ...} sekleinde gelir
    const detail = data?.detail ?? data;
    throw new ApiError(res.status, detail, data);
  }

  return data;
}

// =============================================================
// USER (3)
// =============================================================

export const userApi = {
  get:    () => request('/api/user'),
  create: (name) => request('/api/user', { method: 'POST', body: { name } }),
  update: (name) => request('/api/user', { method: 'PUT', body: { name } }),
};

// =============================================================
// COCKPIT (1)
// =============================================================

export const cockpitApi = {
  get: () => request('/api/cockpit'),
};

// =============================================================
// ACCOUNTS (5)
// =============================================================

export const accountsApi = {
  list:   (params) => request('/api/accounts', { params }),
  get:    (id) => request(`/api/accounts/${id}`),
  create: (data) => request('/api/accounts', { method: 'POST', body: data }),
  update: (id, data) => request(`/api/accounts/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/api/accounts/${id}`, { method: 'DELETE' }),
};

// =============================================================
// TRANSACTIONS (4)
// =============================================================

export const transactionsApi = {
  list:   (params) => request('/api/transactions', { params }),
  create: (data) => request('/api/transactions', { method: 'POST', body: data }),
  // Hizli giris kisayolu
  quickAdd: (text) => request('/api/transactions', {
    method: 'POST',
    body: { quick_text: text, auto_update_balance: true },
  }),
  update: (id, data) => request(`/api/transactions/${id}`, { method: 'PUT', body: data }),
  delete: (id, revertBalance = false) => request(
    `/api/transactions/${id}`,
    { method: 'DELETE', params: { revert_balance: revertBalance } }
  ),
};

// =============================================================
// INCOMES (4)
// =============================================================

export const incomesApi = {
  list:       (activeOnly = false) => request('/api/incomes', { params: { active_only: activeOnly } }),
  create:     (data) => request('/api/incomes', { method: 'POST', body: data }),
  update:     (id, data) => request(`/api/incomes/${id}`, { method: 'PUT', body: data }),
  delete:     (id) => request(`/api/incomes/${id}`, { method: 'DELETE' }),
  triggerDue: () => request('/api/incomes/trigger-due', { method: 'POST' }),  // A2
};

// =============================================================
// RECURRING EXPENSES (A3)
// =============================================================

export const expensesApi = {
  list:       (activeOnly = false) => request('/api/expenses/recurring', { params: { active_only: activeOnly } }),
  create:     (data) => request('/api/expenses/recurring', { method: 'POST', body: data }),
  update:     (id, data) => request(`/api/expenses/recurring/${id}`, { method: 'PUT', body: data }),
  delete:     (id) => request(`/api/expenses/recurring/${id}`, { method: 'DELETE' }),
  triggerDue: () => request('/api/expenses/recurring/trigger-due', { method: 'POST' }),  // A3
};

// =============================================================
// ENVELOPES — kategori bütçe zarfları (FEAT-001)
// =============================================================

export const envelopesApi = {
  list:   () => request('/api/envelopes'),                        // {envelopes, durum}
  create: (data) => request('/api/envelopes', { method: 'POST', body: data }),
  update: (id, data) => request(`/api/envelopes/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/api/envelopes/${id}`, { method: 'DELETE' }),
};

// =============================================================
// DEBTS (4)
// =============================================================

export const debtsApi = {
  list:   (params) => request('/api/debts', { params }),
  create: (data) => request('/api/debts', { method: 'POST', body: data }),
  update: (id, data) => request(`/api/debts/${id}`, { method: 'PUT', body: data }),
  delete: (id) => request(`/api/debts/${id}`, { method: 'DELETE' }),
  // 'Odendi' kisayolu — paid_date set ederek
  markPaid: (id, date = null) => request(`/api/debts/${id}`, {
    method: 'PUT',
    body: { paid_date: date || todayLocalISO() },
  }),
};

// =============================================================
// CHECKPOINTS (4)
// =============================================================

export const checkpointsApi = {
  list:   (params) => request('/api/checkpoints', { params }),
  create: (data) => request('/api/checkpoints', { method: 'POST', body: data }),
  update: (id, data) => request(`/api/checkpoints/${id}`, { method: 'PUT', body: data }),
  delete: (id, hard = false) => request(`/api/checkpoints/${id}`, {
    method: 'DELETE',
    params: { hard },
  }),
};

// =============================================================
// COACH (4)
// =============================================================

export const coachApi = {
  chat:    (message, includeCockpit = true) => request('/api/coach/chat', {
    method: 'POST',
    body: { message, include_cockpit: includeCockpit },
  }),
  history: (limit = 50) => request('/api/coach/history', { params: { limit } }),
  reset:   () => request('/api/coach/reset', { method: 'POST' }),
  usage:   () => request('/api/coach/usage'),
  trace:   (memoryId) => request(`/api/coach/trace/${memoryId}`),
};

// =============================================================
// ACTIONS (4)
// =============================================================

export const actionsApi = {
  pending: () => request('/api/actions/pending'),
  approve: (id) => request(`/api/actions/${id}/approve`, { method: 'POST' }),
  reject:  (id, reason = null) => request(`/api/actions/${id}/reject`, {
    method: 'POST',
    body: reason ? { reason } : null,
  }),
  history: (params) => request('/api/actions/history', { params }),
  edit: (id, payload, summary) => request(`/api/actions/${id}/edit`, {
    method: 'POST',
    body: { payload, summary },
  }),
};

// =============================================================
// FUND PRICE (3)
// =============================================================

// =============================================================
// REPORTS (1)
// =============================================================

export const reportsApi = {
  categoryBreakdown: (days = 30, type = 'expense') =>
    request('/api/reports/category-breakdown', { params: { days, type } }),
  netWorthTrend: (days = 30) =>
    request('/api/reports/net-worth-trend', { params: { days } }),
  upcomingCashflow: (days = 30) =>
    request('/api/reports/upcoming-cashflow', { params: { days } }),
  // A3: aylık özet (gelir/gider/net + kategori + önceki-ay trend). Boş param = içinde bulunulan ay.
  monthlySummary: ({ year = null, month = null } = {}) =>
    request('/api/reports/monthly-summary', {
      params: {
        ...(year !== null && { year }),
        ...(month !== null && { month }),
      },
    }),
};

export const fundPriceApi = {
  update:    (accountId, newPrice) => request('/api/fund-price/update', {
    method: 'POST',
    body: { account_id: accountId, new_price: newPrice },
  }),
  freshness: () => request('/api/fund-price/freshness'),
  tefasLink: (fundCode) => request(`/api/fund-price/tefas-link/${fundCode}`),
};

// =============================================================
// PREMORTEM (1)
// =============================================================

export const premortemApi = {
  run: (actionId) => request(`/api/premortem/${actionId}`, { method: 'POST' }),
};

export const simulationApi = {
  run: (actionId) => request(`/api/simulate/${actionId}`, { method: 'POST' }),
};

// =============================================================
// CASHFLOW (1)
// =============================================================

export const cashflowApi = {
  getForecast: ({ days = 60, accountId = null, include = null, crunchThreshold = 0 } = {}) =>
    request('/api/cashflow/forecast', {
      params: {
        days,
        ...(accountId !== null && { account_id: accountId }),
        include: include ? include.join(',') : 'incomes,expenses,receivables,payables',
        crunch_threshold: crunchThreshold,
      },
    }),
};

export const debtStrategyApi = {
  compare: ({ extraMonthly = 0 } = {}) =>
    request('/api/debt-strategy/compare', {
      params: { extra_monthly: extraMonthly },
    }),
};

// =============================================================
// GOALS (13) — H2G5 Goal Engine (allocation-based, ADR-025)
// =============================================================

export const goalsApi = {
  // Hedef CRUD
  list:   ({ statusFilter, goalType } = {}) =>
    request('/api/goals', {
      params: {
        ...(statusFilter !== undefined && { status_filter: statusFilter }),
        ...(goalType !== undefined && { goal_type: goalType }),
      },
    }),
  get:    (id) => request(`/api/goals/${id}`),
  create: (data) => request('/api/goals', { method: 'POST', body: data }),
  update: (id, data) => request(`/api/goals/${id}`, { method: 'PATCH', body: data }),
  delete: (id) => request(`/api/goals/${id}`, { method: 'DELETE' }),

  // Progress yenile (deterministik recompute)
  refresh: (id) => request(`/api/goals/${id}/refresh`, { method: 'POST' }),

  // Allocations (manuel + transaction-linked)
  allocations: {
    list:   (goalId) => request(`/api/goals/${goalId}/allocations`),
    create: (goalId, data) => request(`/api/goals/${goalId}/allocations`, {
      method: 'POST',
      body: data,
    }),
    delete: (allocationId) => request(`/api/goals/allocations/${allocationId}`, {
      method: 'DELETE',
    }),
  },

  // Otomatik kurallar (rule engine)
  rules: {
    list:   (goalId) => request(`/api/goals/${goalId}/rules`),
    create: (goalId, data) => request(`/api/goals/${goalId}/rules`, {
      method: 'POST',
      body: data,
    }),
    update: (ruleId, data) => request(`/api/goals/rules/${ruleId}`, {
      method: 'PATCH',
      body: data,
    }),
    delete: (ruleId) => request(`/api/goals/rules/${ruleId}`, {
      method: 'DELETE',
    }),
  },
};

// =============================================================
// HEALTH (1)
// Vite proxy sadece /api/* yonlendirdigi icin /api/health kullaniyoruz.
// Backend hem '/' hem '/api/health' icin ayni cevabi verir.
// =============================================================

export const healthApi = {
  check: () => request('/api/health'),
};

// =============================================================
// FORMATTER YARDIMCILARI — Tum panellerde tekrar kullanilir
// =============================================================

const tlFormatter = new Intl.NumberFormat('tr-TR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const tlCompactFormatter = new Intl.NumberFormat('tr-TR', {
  minimumFractionDigits: 0,
  maximumFractionDigits: 0,
});

/** 1234.56 -> "1.234,56" */
export function formatTL(amount, { compact = false } = {}) {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  const fmt = compact ? tlCompactFormatter : tlFormatter;
  return fmt.format(amount);
}

/** 1234.56 -> "1.234,56 TL" */
export function formatTLSuffix(amount, opts) {
  if (amount === null || amount === undefined || isNaN(amount)) return '—';
  return formatTL(amount, opts) + ' TL';
}

/** Yuzdeyi format eder: 36.3 -> "+%36,3" */
export function formatPercent(value, { showSign = true } = {}) {
  if (value === null || value === undefined || isNaN(value)) return '—';
  const sign = showSign && value > 0 ? '+' : '';
  const formatted = value.toFixed(2).replace('.', ',');
  return `${sign}%${formatted}`;
}

/** ISO tarihi Turkce olarak: "2026-05-11" -> "11 May" */
const TURKISH_MONTHS_SHORT = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz',
                              'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
export function formatDate(isoStr, { withYear = false } = {}) {
  if (!isoStr) return '—';
  // Date-only ("YYYY-MM-DD") string'i LOCAL parse et: 'new Date("2026-05-11")' UTC gece-yarısı
  // demektir, UTC-batı saat dilimlerinde bir gün geri kayar. 'T00:00:00' eklemek (Reports.jsx'in
  // zaten kullandığı desen) gösterilen günü saat diliminden BAĞIMSIZ kılar. Datetime string'lere
  // (T içerenler) dokunma — kendi tz suffix'leri (UtcDateTime +00:00) var.
  const local = isoStr.length === 10 && !isoStr.includes('T') ? isoStr + 'T00:00:00' : isoStr;
  const d = new Date(local);
  if (isNaN(d.getTime())) return isoStr;
  const day = d.getDate();
  const month = TURKISH_MONTHS_SHORT[d.getMonth()];
  return withYear ? `${day} ${month} ${d.getFullYear()}` : `${day} ${month}`;
}

/** Pozitif/negatif degere class doner — UI rengi icin */
export function signClass(value) {
  if (value === null || value === undefined || isNaN(value) || value === 0) {
    return 'text-zinc-500 dark:text-zinc-400';
  }
  return value > 0
    ? 'text-positive-600 dark:text-positive-400'
    : 'text-negative-600 dark:text-negative-400';
}

/**
 * Bugünün LOCAL tarihi "YYYY-MM-DD".
 * `new Date().toISOString().slice(0,10)` UTC tarihi verir → Türkiye'de (+3) gece
 * 00:00-03:00 arası BİR GÜN GERİ kayar. Murat gece vardiyası çalıştığından geç saatte
 * girilen paid_date/transaction_date bir gün önceye kaydolabiliyordu — bu onu düzeltir.
 */
export function todayLocalISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

/** Bugünün LOCAL yıl-ayı "YYYY-MM" (aynı saat-dilimi güvenliği). */
export function currentYearMonthLocal() {
  return todayLocalISO().slice(0, 7);
}