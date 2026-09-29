const key = userId => 'stroyka:platform-payment:v1:' + userId;

export function pendingPayment(userId) {
  const raw = sessionStorage.getItem(key(userId));
  return raw ? JSON.parse(raw) : null;
}

export function preparePayment(userId, draft) {
  const pending = pendingPayment(userId);
  if (pending) return pending;
  const bytes = window.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = [...bytes].map(byte => byte.toString(16).padStart(2, '0')).join('');
  const requestId = [hex.slice(0,8), hex.slice(8,12), hex.slice(12,16), hex.slice(16,20), hex.slice(20)].join('-');
  const command = {...draft, requestId};
  sessionStorage.setItem(key(userId), JSON.stringify(command));
  return command;
}

export function finishPayment(userId) {
  sessionStorage.removeItem(key(userId));
}
