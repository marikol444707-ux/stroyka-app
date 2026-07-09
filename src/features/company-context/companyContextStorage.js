export const COMPANY_CONTEXT_MODE_HEADER = 'X-Company-Mode';
export const COMPANY_CONTEXT_ID_HEADER = 'X-Company-Id';

export const companyContextStorageKeyForUser = (user) => (
  `stroyka.companyContext.v1.${user?.id || user?.email || 'guest'}`
);

export const asCompanyId = (value) => {
  const id = Number(value);
  return Number.isInteger(id) && id > 0 ? id : null;
};

export const readStoredCompanySelection = (user, storage = null) => {
  if (!user) return null;
  try {
    const targetStorage = storage || (typeof window !== 'undefined' ? window.localStorage : null);
    if (!targetStorage) return null;
    const raw = targetStorage.getItem(companyContextStorageKeyForUser(user));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch (_e) {
    return null;
  }
};

export const writeStoredCompanySelection = (user, selection, storage = null) => {
  if (!user) return;
  try {
    const targetStorage = storage || (typeof window !== 'undefined' ? window.localStorage : null);
    if (!targetStorage) return;
    targetStorage.setItem(companyContextStorageKeyForUser(user), JSON.stringify(selection || {}));
  } catch (_e) {}
};

export const readStoredCompanyRequestContext = (storage = null) => {
  try {
    const targetStorage = storage || (typeof window !== 'undefined' ? window.localStorage : null);
    if (!targetStorage) return null;
    const rawUser = targetStorage.getItem('user');
    if (!rawUser) return null;
    const user = JSON.parse(rawUser);
    if (!user || typeof user !== 'object' || (!user.id && !user.email)) return null;
    const selection = readStoredCompanySelection(user, targetStorage);
    if (selection?.mode === 'all_companies') {
      return { mode: 'all_companies', companyId: null };
    }
    const companyId = asCompanyId(selection?.companyId);
    if (selection?.mode !== 'company' || !companyId) return null;
    return { mode: 'company', companyId };
  } catch (_e) {
    return null;
  }
};

export const withStoredCompanyContextHeaders = (init = {}, storage = null) => {
  const context = readStoredCompanyRequestContext(storage);
  if (!context) return init;
  const headers = new Headers(init.headers || {});
  headers.set(COMPANY_CONTEXT_MODE_HEADER, context.mode);
  if (context.mode === 'company') {
    headers.set(COMPANY_CONTEXT_ID_HEADER, String(context.companyId));
  } else {
    headers.delete(COMPANY_CONTEXT_ID_HEADER);
  }
  return { ...init, headers };
};
