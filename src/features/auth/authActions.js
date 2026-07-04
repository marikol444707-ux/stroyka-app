export const createAuthActions = ({
  API,
  consentChecked,
  email,
  password,
  profileData,
  refreshData,
  regEmail,
  regCode,
  regInviteInfo,
  regName,
  regPassword,
  regSupplierData,
  setInitialDataLoaded,
  setLoginError,
  setMasterProfile,
  setRegInviteInfo,
  setRegSupplierData,
  setShowProfileForm,
  setUser,
  user,
}) => {
  const readResponseJson = async (res) => {
    if (!res) return {};
    if (typeof res.text === 'function') {
      const raw = await res.text();
      try {
        return raw ? JSON.parse(raw) : {};
      } catch {
        return {detail: raw ? raw.slice(0, 180) : ''};
      }
    }
    if (typeof res.json === 'function') {
      try {
        return await res.json();
      } catch {
        return {};
      }
    }
    return {};
  };

  const persistLogin = (data) => {
    if (!data?.authToken) throw new Error('сервер не вернул токен входа');
    if (data.authToken) localStorage.setItem('authToken', data.authToken);
    localStorage.setItem('user', JSON.stringify(data));
    if (typeof setInitialDataLoaded === 'function') setInitialDataLoaded(false);
    if (typeof setUser === 'function') setUser(data);
  };

  const handleLogout = () => {
    fetch(API + '/logout', {method: 'POST', credentials: 'include'}).catch(() => {});
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    if (typeof setInitialDataLoaded === 'function') setInitialDataLoaded(false);
    if (typeof setUser === 'function') setUser(null);
  };

  const handleLogin = async () => {
    try {
      const res = await fetch(API + '/login', {method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: (email || '').trim().toLowerCase(), password: (password || '').trim()})});
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setLoginError(data.detail || 'Неверный email или пароль');
        return null;
      }
      if (data.twoFactorRequired || data.twoFactorSetupRequired) {
        setLoginError('');
        return data;
      }
      if (!data.authToken) {
        setLoginError('Сервер не вернул токен входа');
        return null;
      }
      persistLogin(data);
      return data;
    } catch {
      setLoginError('Ошибка подключения к серверу');
      return null;
    }
  };

  const handleTwoFactorLogin = async ({mode, token, code}) => {
    let res;
    let data = {};
    try {
      const endpoint = mode === 'setup' ? '/login/2fa/setup-confirm' : '/login/2fa/verify';
      const body = mode === 'setup' ? {setupToken: token, code} : {challengeToken: token, code};
      res = await fetch(API + endpoint, {method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      data = await readResponseJson(res);
    } catch (err) {
      return {ok: false, error: `Ошибка подключения к серверу: ${err?.message || 'проверьте интернет и обновите страницу'}`};
    }
    if (!res.ok) return {ok: false, error: data.detail || `Ошибка 2FA: сервер ответил ${res.status}`};
    try {
      persistLogin(data);
    } catch (err) {
      return {ok: false, error: `2FA подтверждена, но сессия не сохранена: ${err?.message || 'обновите страницу и войдите снова'}`};
    }
    return {ok: true, data};
  };

  const handleRegister = async () => {
    if (!regName || !regEmail || !regPassword || !regCode) {
      setLoginError('Заполните все поля');
      return;
    }
    try {
      const body = {name: regName, email: regEmail, password: regPassword, code: regCode};
      if (regInviteInfo?.role === 'поставщик') {
        Object.assign(body, regSupplierData);
      }
      const res = await fetch(API + '/register', {method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      if (!res.ok) {
        const err = await res.json();
        setLoginError(err.detail);
        return;
      }
      const data = await res.json();
      persistLogin(data);
    } catch {
      setLoginError('Ошибка подключения');
    }
  };

  const checkInviteCode = async (code) => {
    if (!code || code.length < 4) {
      setRegInviteInfo(null);
      return;
    }
    try {
      const r = await fetch(API + '/invite-codes/' + encodeURIComponent(code) + '/info');
      const data = await r.json();
      if (data.valid) {
        setRegInviteInfo(data);
        if (data.role === 'поставщик') {
          setRegSupplierData(prev => ({...prev, companyName: data.presetName || '', category: data.presetCategory || ''}));
        }
      } else {
        setRegInviteInfo(null);
      }
    } catch (_) {
      setRegInviteInfo(null);
    }
  };

  const saveProfile = async () => {
    if (!profileData.fullName || !profileData.inn || !profileData.bankAccount) {
      alert('Заполните обязательные поля');
      return;
    }
    if (!consentChecked) {
      alert('Необходимо согласие на обработку ПД');
      return;
    }
    const res = await fetch(API + '/master-profile', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({...profileData, userId: user.id})});
    setMasterProfile(await res.json());
    setShowProfileForm(false);
    await fetch(API + '/pd-consents', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({userId: user.id, signedAt: new Date().toLocaleString('ru-RU'), scanUrl: '', uploadedBy: user.name})});
    await refreshData();
  };

  return {
    handleLogout,
    handleLogin,
    handleTwoFactorLogin,
    handleRegister,
    checkInviteCode,
    saveProfile,
  };
};
