import React from 'react';

export default function RegisterPage({
  C,
  ROLE_LABELS,
  btnO,
  card,
  handleRegister,
  inp,
  loginError,
  regCode,
  regEmail,
  regInviteInfo,
  regName,
  regPassword,
  regSupplierData,
  setLoginError,
  setPage,
  setRegCode,
  setRegEmail,
  setRegName,
  setRegPassword,
  setRegSupplierData,
}) {
  const isSupplierInvite = regInviteInfo?.role === 'поставщик';

  return (
    <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', backgroundColor: C.bg, padding: '20px' }}>
      <div style={{ ...card, padding: '30px', width: isSupplierInvite ? '560px' : '420px', maxWidth: '100%', boxShadow: '0 20px 60px rgba(0,0,0,0.08)', maxHeight: '95vh', overflowY: 'auto' }}>
        <div style={{ textAlign: 'center', marginBottom: '24px' }}>
          <div style={{ fontSize: '42px', marginBottom: '8px' }}>{isSupplierInvite ? '🏭' : '🏗️'}</div>
          <h2 style={{ margin: 0, color: C.text, fontSize: '22px', fontWeight: '800' }}>СтройКа</h2>
          <p style={{ color: C.textSec, fontSize: '13px', margin: '8px 0 0' }}>
            {isSupplierInvite ? 'Регистрация поставщика' : 'Регистрация по коду приглашения'}
          </p>
        </div>

        {regInviteInfo && regInviteInfo.role && (
          <div style={{ padding: '10px 12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, borderRadius: '8px', marginBottom: '14px', fontSize: '12px', color: C.text }}>
            ✅ Приглашение действительно — роль: <b>{ROLE_LABELS[regInviteInfo.role] || regInviteInfo.role}</b>
            {regInviteInfo.presetName && (
              <>
                <br />
                📛 Компания: <b>{regInviteInfo.presetName}</b>
              </>
            )}
            {regInviteInfo.presetCategory && (
              <>
                <br />
                📂 Категория: <b>{regInviteInfo.presetCategory}</b>
              </>
            )}
          </div>
        )}

        <input placeholder={isSupplierInvite ? 'ФИО контактного лица' : 'Ваше имя'} value={regName} onChange={(e) => setRegName(e.target.value)} style={inp} />
        <input type="email" placeholder="Email" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} style={inp} />
        <input type="password" placeholder="Пароль (минимум 5 символов)" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} style={inp} />
        <input placeholder="КОД ПРИГЛАШЕНИЯ" value={regCode} onChange={(e) => setRegCode(e.target.value.toUpperCase())} style={{ ...inp, letterSpacing: '4px', textAlign: 'center', fontSize: '18px', fontWeight: '700' }} />

        {isSupplierInvite && (
          <div style={{ marginTop: '12px', padding: '14px', backgroundColor: C.bg, border: '1.5px solid ' + C.border, borderRadius: '10px' }}>
            <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '10px' }}>📋 Данные компании (можно заполнить позже в кабинете)</b>
            <input placeholder="Название компании *" value={regSupplierData.companyName} onChange={(e) => setRegSupplierData({ ...regSupplierData, companyName: e.target.value })} style={inp} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <input placeholder="ИНН" value={regSupplierData.inn} onChange={(e) => setRegSupplierData({ ...regSupplierData, inn: e.target.value })} style={{ ...inp, marginBottom: '8px' }} />
              <input placeholder="КПП" value={regSupplierData.kpp} onChange={(e) => setRegSupplierData({ ...regSupplierData, kpp: e.target.value })} style={{ ...inp, marginBottom: '8px' }} />
            </div>
            <input placeholder="ОГРН/ОГРНИП" value={regSupplierData.ogrn} onChange={(e) => setRegSupplierData({ ...regSupplierData, ogrn: e.target.value })} style={inp} />
            <input placeholder="Юридический адрес" value={regSupplierData.legalAddress} onChange={(e) => setRegSupplierData({ ...regSupplierData, legalAddress: e.target.value })} style={inp} />
            <input placeholder="Телефон" value={regSupplierData.phone} onChange={(e) => setRegSupplierData({ ...regSupplierData, phone: e.target.value })} style={inp} />
            <input placeholder="Банк" value={regSupplierData.bank} onChange={(e) => setRegSupplierData({ ...regSupplierData, bank: e.target.value })} style={inp} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '8px' }}>
              <input placeholder="БИК" value={regSupplierData.bik} onChange={(e) => setRegSupplierData({ ...regSupplierData, bik: e.target.value })} style={{ ...inp, marginBottom: '8px' }} />
              <input placeholder="Расчётный счёт" value={regSupplierData.account} onChange={(e) => setRegSupplierData({ ...regSupplierData, account: e.target.value })} style={{ ...inp, marginBottom: '8px' }} />
            </div>
            <input placeholder="ФИО директора" value={regSupplierData.directorName} onChange={(e) => setRegSupplierData({ ...regSupplierData, directorName: e.target.value })} style={inp} />
            <input placeholder="Специализация (что поставляете)" value={regSupplierData.specialization} onChange={(e) => setRegSupplierData({ ...regSupplierData, specialization: e.target.value })} style={inp} />
            <p style={{ color: C.textMuted, fontSize: '11px', margin: 0 }}>Договор поставки и прайс-лист загрузите в личном кабинете после регистрации.</p>
          </div>
        )}

        {loginError && <p style={{ color: C.danger, fontSize: '13px', marginTop: '12px', marginBottom: 0 }}>{loginError}</p>}

        <button onClick={handleRegister} style={{ ...btnO, width: '100%', padding: '13px', justifyContent: 'center', fontSize: '15px', marginTop: '12px', marginBottom: '10px' }}>
          Зарегистрироваться
        </button>

        <p style={{ textAlign: 'center', color: C.textSec, fontSize: '13px' }}>
          Уже есть аккаунт?{' '}
          <span onClick={() => { setPage('login'); setLoginError(''); }} style={{ color: C.accent, cursor: 'pointer', fontWeight: '600' }}>
            Войти
          </span>
        </p>
      </div>
    </div>
  );
}
