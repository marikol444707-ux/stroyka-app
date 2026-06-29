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
