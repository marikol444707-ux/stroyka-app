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
  const persistLogin = (data) => {
    if (data.authToken) localStorage.setItem('authToken', data.authToken);
    localStorage.setItem('user', JSON.stringify(data));
    setInitialDataLoaded(false);
    setUser(data);
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
    setInitialDataLoaded(false);
    setUser(null);
  };

  const handleLogin = async () => {
    try {
      const res = await fetch(API + '/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({email: (email || '').trim().toLowerCase(), password: (password || '').trim()})});
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
    try {
      const endpoint = mode === 'setup' ? '/login/2fa/setup-confirm' : '/login/2fa/verify';
      const body = mode === 'setup' ? {setupToken: token, code} : {challengeToken: token, code};
      const res = await fetch(API + endpoint, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
      const data = await res.json();
      if (!res.ok) return {ok: false, error: data.detail || 'Неверный код 2FA'};
      persistLogin(data);
      return {ok: true, data};
    } catch {
      return {ok: false, error: 'Ошибка подключения к серверу'};
    }
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
      const res = await fetch(API + '/register', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
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
