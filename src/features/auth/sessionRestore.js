import { clearLegacyBrowserAuthToken, normalizeStoredUser } from '../../utils/appRuntimeUtils';

const secretFields = ['authToken', 'password', 'two_factor_secret'];

export async function restoreCookieSession(apiBase) {
  let response;
  try {
    response = await fetch(String(apiBase || '') + '/auth/session', {
      method: 'GET',
      credentials: 'include',
      headers: {Accept: 'application/json'},
    });
  } catch {
    return {status: 'unavailable'};
  }
  if (response.status === 401 || response.status === 403) return {status: 'anonymous'};
  if (!response.ok) return {status: 'unavailable'};
  let data;
  try {
    data = await response.json();
  } catch {
    return {status: 'unavailable'};
  }
  const user = normalizeStoredUser(data);
  if (!user?.id || !user.role) return {status: 'anonymous'};
  if (secretFields.some((field) => Object.prototype.hasOwnProperty.call(user, field))) {
    return {status: 'anonymous'};
  }
  clearLegacyBrowserAuthToken();
  try {
    localStorage.setItem('user', JSON.stringify(user));
  } catch {}
  return {status: 'authenticated', user};
}
