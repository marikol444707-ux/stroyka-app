import React from 'react';
import LoginPage from '../pages/LoginPage';
import {
  ClientAccountCabinet,
  PublicSitePage,
  RegisterPage,
  SystemOwnerCabinet,
} from '../app/lazyComponents';

export default function AppEntryRoutes({ user, page, pageFallback, ui, constants, state, actions }) {
  const { API, C, badge, btnG, btnGr, btnO, btnR, card, inp } = ui;
  const { ROLE_LABELS } = constants;
  const {
    email,
    loginError,
    password,
    regCode,
    regEmail,
    regInviteInfo,
    regName,
    regPassword,
    regSupplierData,
  } = state;
  const {
    handleLogin,
    handleLogout,
    handleRegister,
    handleTwoFactorLogin,
    setEmail,
    setLoginError,
    setPage,
    setPassword,
    setRegCode,
    setRegEmail,
    setRegName,
    setRegPassword,
    setRegSupplierData,
    setUser,
  } = actions;

  if (!user) {
    if (page === 'register') {
      return (
        <React.Suspense fallback={pageFallback}>
          <RegisterPage
            C={C}
            ROLE_LABELS={ROLE_LABELS}
            btnO={btnO}
            card={card}
            handleRegister={handleRegister}
            inp={inp}
            loginError={loginError}
            regCode={regCode}
            regEmail={regEmail}
            regInviteInfo={regInviteInfo}
            regName={regName}
            regPassword={regPassword}
            regSupplierData={regSupplierData}
            setLoginError={setLoginError}
            setPage={setPage}
            setRegCode={setRegCode}
            setRegEmail={setRegEmail}
            setRegName={setRegName}
            setRegPassword={setRegPassword}
            setRegSupplierData={setRegSupplierData}
          />
        </React.Suspense>
      );
    }
    if (page === 'login') {
      return (
        <LoginPage
          email={email}
          handleLogin={handleLogin}
          handleTwoFactorLogin={handleTwoFactorLogin}
          loginError={loginError}
          password={password}
          setEmail={setEmail}
          setLoginError={setLoginError}
          setPage={setPage}
          setPassword={setPassword}
        />
      );
    }
    return (
      <React.Suspense fallback={pageFallback}>
        <PublicSitePage onLogin={() => {
          if (typeof window !== 'undefined' && window.location.pathname !== '/app') {
            window.history.pushState({}, '', '/app');
          }
          setLoginError('');
          setPage('login');
        }} />
      </React.Suspense>
    );
  }

  if (['system_owner', 'platform_admin', 'platform_support', 'billing_admin'].includes(user.role)) {
    return (
      <React.Suspense fallback={pageFallback}>
        <SystemOwnerCabinet
          API={API}
          C={C}
          badge={badge}
          btnG={btnG}
          btnGr={btnGr}
          btnO={btnO}
          btnR={btnR}
          card={card}
          inp={inp}
          setUser={setUser}
          user={user}
        />
      </React.Suspense>
    );
  }

  if (['account_owner', 'account_admin'].includes(user.role)) {
    return (
      <React.Suspense fallback={pageFallback}>
        <ClientAccountCabinet
          API={API}
          C={C}
          badge={badge}
          btnG={btnG}
          card={card}
          handleLogout={handleLogout}
          setUser={setUser}
          user={user}
        />
      </React.Suspense>
    );
  }

  return null;
}
