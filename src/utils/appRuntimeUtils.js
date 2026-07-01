export const loadStoredUser = () => {
  if (typeof window === 'undefined') return null;
  try {
    const token = localStorage.getItem('authToken');
    const rawUser = localStorage.getItem('user');
    if (!token || !rawUser) return null;
    return JSON.parse(rawUser);
  } catch {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    return null;
  }
};

export const readStoredJson = (key, fallback) => {
  if (typeof window === 'undefined') return fallback;
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    return fallback;
  }
};

export const writeStoredJson = (key, value) => {
  if (typeof window === 'undefined') return value;
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {}
  return value;
};

export const initialGuestPage = () => {
  if (typeof window === 'undefined') return 'site';
  const path = window.location.pathname.toLowerCase();
  const host = window.location.hostname.toLowerCase();
  const appHost = host === 'app.stroyka26.pro' || host.startsWith('app.');
  if (path.includes('register')) return 'register';
  if (path.includes('login')) return 'login';
  if (appHost) return 'login';
  return 'site';
};

export const mobileScopeForPage = (page) => {
  if (page === 'dashboard') return 'mobile:dashboard';
  if (['projects', 'site', 'works', 'documents', 'cable'].includes(page)) return 'mobile:projects-docs';
  if (page === 'estimates') return 'mobile:estimates';
  if (['warehouse', 'materials'].includes(page)) return 'mobile:warehouse';
  if (['supply', 'suppliers'].includes(page)) return 'mobile:supply';
  if (['personnel', 'users'].includes(page)) return 'mobile:people';
  if (page === 'accounting') return 'mobile:accounting';
  if (page === 'history') return 'mobile:history';
  if (page === 'myexpenses') return 'mobile:myexpenses';
  if (page === 'clients') return 'mobile:clients';
  if (page === 'pricelists') return 'mobile:pricelists';
  if (page === 'crm') return 'mobile:crm';
  if (page === 'analytics') return 'mobile:analytics';
  if (page === 'settings') return 'mobile:settings';
  if (page === 'companychat') return 'mobile:chat';
  return '';
};

export const daysInMonth = Array.from({length: 31}, (_, i) => String(i + 1));

export const requestPushPermission = async () => {
  if (!('Notification' in window)) return false;
  if (Notification.permission === 'granted') return true;
  const permission = await Notification.requestPermission();
  return permission === 'granted';
};

export const sendPushNotification = (title, body) => {
  if (Notification.permission === 'granted') {
    new Notification('🏗️ ' + title, { body, icon: '/favicon.ico' });
  }
};

export const doPrint = (content) => {
  const iframe = document.createElement('iframe');
  iframe.style.cssText = 'position:fixed;top:0;left:0;width:0;height:0;border:none;';
  document.body.appendChild(iframe);
  const doc = iframe.contentDocument || iframe.contentWindow.document;
  doc.open();
  doc.write('<!DOCTYPE html><html><head><meta charset="utf-8"><style>body{font-family:Arial,sans-serif;padding:30px;font-size:12px;color:#000}table{width:100%;border-collapse:collapse;margin:15px 0}td,th{border:1px solid #333;padding:6px;text-align:left}th{background:#f5f5f5}h2{text-align:center;margin-bottom:5px}p{margin:4px 0}.signatures{display:flex;justify-content:space-between;margin-top:40px}.sig{text-align:center;width:30%}.sig-line{border-top:1px solid #333;margin-top:30px;padding-top:5px}@media print{body{padding:15px}}</style></head><body>'+content+'</body></html>');
  doc.close();
  setTimeout(() => { iframe.contentWindow.focus(); iframe.contentWindow.print(); setTimeout(() => document.body.removeChild(iframe), 2000); }, 300);
};

export const generateQR = (text) => {
  const size = 150;
  return `https://api.qrserver.com/v1/create-qr-code/?size=${size}x${size}&data=${encodeURIComponent(text)}`;
};

export const createFileSrc = (apiBase = '') => (url) => {
  const value = String(url || '').trim();
  if (!value) return '';
  if (/^(https?:|data:|blob:)/i.test(value)) return value;
  return apiBase + value;
};

export const calcVat = (total, vatType) => {
  const amount = Number(total || 0);
  const match = String(vatType || '').match(/НДС\s*(\d+(?:[,.]\d+)?)%/i);
  if (match) {
    const rate = Number(match[1].replace(',', '.')) / 100;
    if (rate > 0) {
      const base = Math.round((amount / (1 + rate)) * 100) / 100;
      return { base, vat: Math.round((amount - base) * 100) / 100, total: amount };
    }
  }
  return { base: amount, vat: 0, total: amount };
};

export const matchSearchFields = (query, ...fields) => {
  if (!query || query.trim().length < 2) return true;
  const needle = query.toLowerCase().trim();
  return fields.some(field => String(field || '').toLowerCase().includes(needle));
};

export const buildPagedPath = (path, params = {}) => {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '') return;
    query.set(key, String(value));
  });
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
};

export const readApiResult = async (res) => {
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch (e) {}
  if (!res.ok) {
    throw new Error(data?.detail || data?.error || text.slice(0, 240) || ('HTTP ' + res.status));
  }
  return data;
};

export const mergeRowsByIdValue = (current = [], incoming = []) => {
  const rows = new Map();
  [...(Array.isArray(current) ? current : []), ...(Array.isArray(incoming) ? incoming : [])].forEach((row, index) => {
    if (!row) return;
    const key = row.id !== undefined && row.id !== null ? `id:${row.id}` : `row:${index}:${JSON.stringify(row)}`;
    rows.set(key, row);
  });
  return Array.from(rows.values());
};

export const createWorkJournalPageState = (
  { projectName = '', search = '', dateFrom = '', dateTo = '', rows = [], loading = false, error = '' } = {},
  pageLimit = 0,
) => ({
  projectName,
  search,
  dateFrom,
  dateTo,
  hasMore: Array.isArray(rows) && rows.length === pageLimit,
  loading,
  error,
});

export const createMaterialNormsPageState = ({ search = '', rows = [], loading = false, error = '' } = {}, pageLimit = 0) => ({
  search,
  hasMore: Array.isArray(rows) && rows.length === pageLimit,
  loading,
  error,
});

export const createMaterialsPageState = (
  { projectName = '', search = '', rows = [], loading = false, error = '' } = {},
  pageLimit = 0,
) => ({
  projectName,
  search,
  hasMore: Array.isArray(rows) && rows.length === pageLimit,
  loading,
  error,
});
