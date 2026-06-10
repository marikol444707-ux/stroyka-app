export const API = typeof window !== 'undefined' && window.location.hostname === 'localhost'
  ? 'http://localhost:8001'
  : '';

export const installAuthFetch = () => {
  if (typeof window === 'undefined' || window.__stroykaAuthFetchInstalled) return;
  const nativeFetch = window.fetch.bind(window);
  window.fetch = async (input, init = {}) => {
    const token = localStorage.getItem('authToken');
    if (!token) return nativeFetch(input, init);
    const headers = new Headers(init.headers || {});
    if (!headers.has('Authorization')) headers.set('Authorization', 'Bearer ' + token);
    const response = await nativeFetch(input, {...init, headers});
    // Токен истёк или стал недействителен — сервер отвечает 401.
    // Чистим сессию и возвращаем на экран входа, чтобы приложение не показывало
    // пустые данные (нули, «Проектов нет»), как будто всё удалено.
    if (response.status === 401 && !window.__stroykaSessionExpiring) {
      window.__stroykaSessionExpiring = true;
      try {
        localStorage.removeItem('authToken');
        localStorage.removeItem('user');
        sessionStorage.setItem('authExpiredNotice', '1');
      } catch (e) {}
      window.location.reload();
    }
    return response;
  };
  window.__stroykaAuthFetchInstalled = true;
};
