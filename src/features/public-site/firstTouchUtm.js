export const FIRST_TOUCH_UTM_KEY = 'stroykaFirstTouchUtm';
export const FIRST_TOUCH_UTM_TTL_MS = 30 * 24 * 60 * 60 * 1000;
export const UTM_KEYS = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term'];

const emptyStorage = {
  getItem: () => null,
  setItem: () => {},
  removeItem: () => {},
};

const readStored = (storage, now) => {
  let raw = '';
  try {
    raw = storage.getItem(FIRST_TOUCH_UTM_KEY) || '';
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    const savedAt = Number(parsed?.savedAt);
    const utm = parsed?.utm;
    if (!Number.isFinite(savedAt) || now - savedAt > FIRST_TOUCH_UTM_TTL_MS || !utm || typeof utm !== 'object') {
      try { storage.removeItem(FIRST_TOUCH_UTM_KEY); } catch { /* ignore quota or private mode */ }
      return null;
    }
    const kept = {};
    UTM_KEYS.forEach((key) => {
      const value = String(utm[key] || '').trim().slice(0, 120);
      if (value) kept[key] = value;
    });
    return Object.keys(kept).length ? kept : null;
  } catch {
    try { storage.removeItem(FIRST_TOUCH_UTM_KEY); } catch { /* ignore */ }
    return null;
  }
};

const utmFromSearch = (search) => {
  const query = String(search || '').replace(/^\?/, '');
  const params = new URLSearchParams(query);
  const utm = {};
  UTM_KEYS.forEach((key) => {
    const value = String(params.get(key) || '').trim().slice(0, 120);
    if (value) utm[key] = value;
  });
  return utm;
};

export const captureFirstTouchUtm = ({ search = '', storage = emptyStorage, now = Date.now() } = {}) => {
  const existing = readStored(storage, now);
  if (existing) return existing;
  const utm = utmFromSearch(search);
  if (!Object.keys(utm).length) return {};
  try {
    storage.setItem(FIRST_TOUCH_UTM_KEY, JSON.stringify({ savedAt: now, utm }));
  } catch {
    return utm;
  }
  return utm;
};
