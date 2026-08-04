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
// AUTH TOKEN DEPOSU (M11 / ADR-033)
// =============================================================
// Access token bellekte + localStorage (sayfa yenilemede kalıcı). Refresh token da
// localStorage'da. request() her istekte Authorization: Bearer ekler (varsa).

const ACCESS_KEY = 'fos_access_token';
const REFRESH_KEY = 'fos_refresh_token';

export function getAccessToken() {
  try { return localStorage.getItem(ACCESS_KEY) || null; } catch { return null; }
}
export function setTokens({ access_token, refresh_token }) {
  try {
    if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
  } catch { /* localStorage yoksa yoksay */ }
}
export function clearTokens() {
  try { localStorage.removeItem(ACCESS_KEY); localStorage.removeItem(REFRESH_KEY); } catch { /* */ }
}
function getRefreshToken() {
  try { return localStorage.getItem(REFRESH_KEY) || null; } catch { return null; }
}

// M61 (BUG #158): 401 kurtarma. Ölü/süresi-geçmiş token uygulamayı KİLİTLEMESİN.
// Aynı anda çok istek 401 alırsa tek refresh yapılır (_refreshing guard).
let _refreshing = null;
async function _tryRefresh() {
  const rt = getRefreshToken();
  if (!rt) return false;
  if (!_refreshing) {
    _refreshing = (async () => {
      try {
        const r = await fetch('/api/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!r.ok) return false;
        const d = await r.json().catch(() => null);
        if (d && d.access_token) {
          // BUG #186 (P2): backend artık refresh token'ı ROTE EDİYOR (eski jti kara listeye
          // yazılır). Yeni refresh saklanmazsa bir sonraki yenileme 401 alır ve kullanıcı
          // durduk yere düşer — üstelik eski token'ı tekrar denemek "sızıntı" sayılıp
          // tüm oturumları kapatır.
          setTokens({ access_token: d.access_token, refresh_token: d.refresh_token });
          return true;
        }
        return false;
      } catch { return false; }
    })();
  }
  const ok = await _refreshing;
  _refreshing = null;
  return ok;
}

// Oturum kurtarılamadı → token temizle + AuthGate'e sinyal (App.jsx dinler → Login).
function _emitAuthExpired() {
  clearTokens();
  try { window.dispatchEvent(new CustomEvent('fos:auth-expired')); } catch { /* SSR/test */ }
}

// =============================================================
// CORE FETCH
// =============================================================

async function request(path, { method = 'GET', body, params, headers: extraHeaders, _retry = false } = {}) {
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

  // M11: JWT varsa Authorization ekle (AUTH_ENABLED kapalıyken backend zaten yok sayar)
  const _tok = getAccessToken();
  if (_tok) init.headers['Authorization'] = `Bearer ${_tok}`;

  // M43: aktif workspace her istekte gönderilir (panel'ler workspace'e göre filtrelenir).
  // Backend header yoksa personal'a düşer (köprü-desen), varsa üyelik doğrular.
  const _ws = getActiveWorkspaceId();
  if (_ws) init.headers['X-Workspace-Id'] = String(_ws);

  // M42: çağrı-özel ek header'lar (extraHeaders global aktif-workspace'i ezebilir)
  if (extraHeaders) Object.assign(init.headers, extraHeaders);

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

  // M61 (BUG #158): 401 → oturumu kurtarmayı dene (auth endpoint'lerinde DEĞİL, sonsuz döngü olmasın)
  if (res.status === 401 && !_retry && !path.startsWith('/api/auth/')) {
    const recovered = await _tryRefresh();
    if (recovered) {
      return request(path, { method, body, params, headers: extraHeaders, _retry: true });
    }
    // Kurtarılamadı: token'ı temizle + AuthGate'e sinyal (beyaz ekran/kilitlenme ASLA)
    _emitAuthExpired();
  }

  // BUG #162 fix: bayat/silinmis aktif-workspace 403'unde uygulama kilitlenmesin.
  // localStorage'daki workspace ID silinmis/uye-olunmayan bir workspace'e isaret ediyorsa
  // backend 403 "Bu workspace'e erisiminiz yok" doner. Bayat ID'yi temizleyip header'siz
  // bir kez tekrar dene → backend personal workspace'e duser (kopru-desen). _retry ile dongu yok.
  if (res.status === 403 && !_retry && _ws &&
      typeof (data?.detail) === 'string' && data.detail.includes('workspace')) {
    setActiveWorkspaceId(null);  // bayat secimi temizle
    return request(path, { method, body, params, headers: extraHeaders, _retry: true });
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

// FEAT-033: uygulama-içi geri bildirim (Şikayet/İstek/Öneri)
export const feedbackApi = {
  create: (kind, message, page) =>
    request('/api/feedback', { method: 'POST', body: { kind, message, page } }),
  list: () => request('/api/feedback'),
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

// FEAT-006/007: abonelik denetçisi
export const subscriptionsApi = {
  list: () => request('/api/subscriptions'),                      // {abonelikler, aylik_toplam, ...}
  toRecurring: (data) => request('/api/subscriptions/to-recurring', { method: 'POST', body: data }),
};

// FEAT-032: istek listesi / 24-saat impuls bekleme
export const wishlistApi = {
  list:    () => request('/api/wishlist'),                        // {items, bekleyen_adet, review_adet}
  add:     (data) => request('/api/wishlist', { method: 'POST', body: data }),
  resolve: (id, status) => request(`/api/wishlist/${id}/resolve`, { method: 'POST', params: { status } }),
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
  netWorthAttribution: () => request('/api/reports/net-worth-attribution'),   // FEAT-021
  realNetWorth: () => request('/api/reports/real-net-worth'),                 // FEAT-024
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
  // FEAT-014: konsolidasyon what-if — teklif edilen oran + vade ile tek-kredi karşılaştırması
  consolidation: ({ rate, term }) =>
    request('/api/debt-strategy/consolidation', {
      params: { rate, term },
    }),
  // FEAT-030: satın alma fırsat maliyeti — amount'ı harcamak vs borca ödemek
  opportunityCost: ({ amount }) =>
    request('/api/debt-strategy/opportunity-cost', {
      params: { amount },
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
// AUTH API (M11 / ADR-033)
// =============================================================

export const authApi = {
  async register({ email, password, name, kvkk_consent }) {
    const t = await request('/api/auth/register', {
      method: 'POST', body: { email, password, name, kvkk_consent },
    });
    setTokens(t);
    return t;
  },
  async login({ email, password }) {
    const t = await request('/api/auth/login', { method: 'POST', body: { email, password } });
    setTokens(t);
    return t;
  },
  async logout() {
    const refresh_token = getRefreshToken();
    try {
      if (refresh_token) await request('/api/auth/logout', { method: 'POST', body: { refresh_token } });
    } finally {
      clearTokens();
    }
  },
  me: () => request('/api/auth/me'),
  exportData: () => request('/api/users/me/export'),
  deleteMe: () => request('/api/users/me', { method: 'DELETE' }),
  passwordResetRequest: (email) =>
    request('/api/auth/password-reset-request', { method: 'POST', body: { email } }),
  passwordResetConfirm: (token, new_password) =>
    request('/api/auth/password-reset-confirm', { method: 'POST', body: { token, new_password } }),
  isLoggedIn: () => !!getAccessToken(),
  // M17: OAuth tam-sayfa yönlendirme (proxy /api → backend → provider → callback → frontend)
  oauthLogin(provider) {
    window.location.href = `/api/auth/oauth/${provider}/login`;
  },
};

// =============================================================
// WORKSPACES (M41/M42, ADR-036) — aile hesabı + izin
// =============================================================

const ACTIVE_WS_KEY = 'financialos_active_workspace_id';

export function getActiveWorkspaceId() {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(ACTIVE_WS_KEY) || null;
}

export function setActiveWorkspaceId(id) {
  if (typeof localStorage === 'undefined') return;
  if (id) localStorage.setItem(ACTIVE_WS_KEY, String(id));
  else localStorage.removeItem(ACTIVE_WS_KEY);
}

// Aktif workspace başlığı (seçili değilse backend personal'a düşer)
function _wsHeaders(workspaceId) {
  const id = workspaceId ?? getActiveWorkspaceId();
  return id ? { 'X-Workspace-Id': String(id) } : undefined;
}

export const workspaceApi = {
  list:   () => request('/api/workspaces'),
  create: (name) => request('/api/workspaces', { method: 'POST', body: { name } }),
  get:    (id) => request(`/api/workspaces/${id}`),
  invite: (id, email, role) => request(`/api/workspaces/${id}/invite`, {
    method: 'POST', body: { email, role }, headers: _wsHeaders(id),
  }),
  removeMember: (id, userId) => request(`/api/workspaces/${id}/members/${userId}`, {
    method: 'DELETE', headers: _wsHeaders(id),
  }),
  join: (token) => request('/api/workspaces/join', { params: { token } }),
};

// M42: davet linki FRONTEND_URL/workspaces/join?token=.. adresine gelir.
export function getJoinTokenFromUrl() {
  if (typeof window === 'undefined') return null;
  if (!(window.location.pathname || '').includes('/workspaces/join')) return null;
  return new URLSearchParams(window.location.search || '').get('token');
}

// M18: Brevo şifre-sıfırlama linki FRONTEND_URL/auth/reset?token=.. adresine gelir.
// SPA yüklenince token'ı çıkarır (yoksa null). AuthGate Login'i reset modunda açar.
export function getResetTokenFromUrl() {
  if (typeof window === 'undefined') return null;
  if (!(window.location.pathname || '').includes('/auth/reset')) return null;
  return new URLSearchParams(window.location.search || '').get('token');
}

// M17: OAuth callback redirect'ini yakala (router'sız tab-app).
// BUG #179 (P2): backend ARTIK token'ları URL'de göndermiyor (tarayıcı geçmişi/access log/
// Referer sızıntısı). URL yalnız tek-kullanımlık 60 sn'lik `code` taşır; token'lar
// POST /api/auth/oauth/exchange yanıt gövdesinde alınır. Async oldu — çağıran await etmeli.
export async function consumeOAuthRedirect() {
  if (typeof window === 'undefined') return { status: 'none' };
  const path = window.location.pathname || '';
  const params = new URLSearchParams(window.location.search || '');
  if (path.includes('/auth/oauth-success') && params.get('code')) {
    const code = params.get('code');
    try { window.history.replaceState({}, '', '/'); } catch { /* */ }  // kodu URL'den hemen sil
    try {
      const res = await fetch('/api/auth/oauth/exchange', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code }),
      });
      if (!res.ok) return { status: 'error', error: 'Oturum kodu geçersiz veya süresi geçti.' };
      const data = await res.json();
      setTokens({ access_token: data.access_token, refresh_token: data.refresh_token });
      return { status: 'success' };
    } catch {
      return { status: 'error', error: 'Oturum açılamadı (ağ hatası).' };
    }
  }
  if (path.includes('/auth/oauth-error')) {
    try { window.history.replaceState({}, '', '/'); } catch { /* */ }
    return { status: 'error', error: params.get('error') || 'OAuth başarısız oldu' };
  }
  return { status: 'none' };
}

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

/**
 * Kullanıcının girdiği sayıyı locale-toleranslı parse eder (formatTL'in tersi).
 * "1.234,56" -> 1234.56 · "1,234.56" -> 1234.56 · "1234,5" -> 1234.5 ·
 * "1.234" -> 1234 (TR binlik) · "1.5" -> 1.5 · "₺ 99,90" -> 99.9 · geçersiz -> NaN.
 *
 * W3-001 fix (BUG #156): eski kalıp `parseFloat(x.replace(',', '.'))` yalnız İLK
 * virgülü çeviriyordu → "1.234,56" (1234,56 TL) parseFloat("1.234.56")=1.234 olarak
 * ~1000× yanlış, UYARISIZ kaydediliyordu. Sessiz finansal veri bozulması.
 * Kural: iki ayraç varsa son görünen = ondalık; yalnız nokta ise TR binlik kabul
 * (birden fazla nokta VEYA son grup tam 3 hane → binlik, aksi halde ondalık).
 */
export function parseTRNumber(input) {
  if (typeof input === 'number') return Number.isFinite(input) ? input : NaN;
  if (input === null || input === undefined) return NaN;
  let s = String(input).trim().replace(/[^\d.,-]/g, ''); // TL sembolü/boşluk/harf at
  if (!s || s === '-' || s === '.' || s === ',') return NaN;
  const lastComma = s.lastIndexOf(',');
  const lastDot = s.lastIndexOf('.');
  if (lastComma >= 0 && lastDot >= 0) {
    // İki ayraç: son görünen ondalık, diğeri binlik
    if (lastComma > lastDot) s = s.replace(/\./g, '').replace(/,/g, '.');
    else s = s.replace(/,/g, '');
  } else if (lastComma >= 0) {
    // Yalnız virgül: TR ondalık (tek virgül) veya binlik (birden fazla)
    const commas = (s.match(/,/g) || []).length;
    s = commas > 1 ? s.replace(/,/g, '') : s.replace(',', '.');
  } else if (lastDot >= 0) {
    // Yalnız nokta: TR'de binlik. Birden fazla nokta VEYA son grup 3 hane = binlik
    const dots = (s.match(/\./g) || []).length;
    const afterDot = s.slice(lastDot + 1);
    if (dots > 1 || afterDot.length === 3) s = s.replace(/\./g, '');
    // aksi halde tek nokta = ondalık (1.5, 1.23, 1.2345), olduğu gibi bırak
  }
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : NaN;
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