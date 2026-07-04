import React from 'react';
import { FloatingCompanyChatPanel } from '../app/lazyComponents';
import { C as DEFAULT_C } from '../constants/uiTheme';
import SystemStatusModal from './SystemStatusModal';
import MobileMenuSheet from './MobileMenuSheet';

export default function AppOverlayLayer({
  showSystemStatus,
  systemStatus,
  systemStatusLoading,
  openSystemStatus,
  setShowSystemStatus,
  C,
  badge,
  btnG,
  showMobileMenu,
  setShowMobileMenu,
  menuItems,
  activePage,
  navigateTo,
  setActivePage,
  showChatPanel,
  setShowChatPanel,
  companyMessages,
  user,
  companyChatInput,
  setCompanyChatInput,
  sendCompanyChatMessage,
  uploadPhoto,
}) {
  const theme = C || DEFAULT_C;
  const closeSystemStatus = typeof setShowSystemStatus === 'function' ? setShowSystemStatus : () => {};
  const refreshSystemStatus = typeof openSystemStatus === 'function' ? openSystemStatus : () => {};
  return (
    <>
      <SystemStatusModal
        show={showSystemStatus}
        systemStatus={systemStatus}
        systemStatusLoading={systemStatusLoading}
        onRefresh={refreshSystemStatus}
        onClose={() => closeSystemStatus(false)}
        C={theme}
        badge={badge}
        btnG={btnG}
      />
      <MobileMenuSheet
        showMobileMenu={showMobileMenu}
        setShowMobileMenu={setShowMobileMenu}
        menuItems={menuItems}
        activePage={activePage}
        navigateTo={navigateTo}
        setActivePage={setActivePage}
        C={theme}
      />
      {showChatPanel && (
        <React.Suspense fallback={null}>
          <FloatingCompanyChatPanel
            showChatPanel={showChatPanel}
            setShowChatPanel={setShowChatPanel}
            companyMessages={companyMessages}
            user={user}
            companyChatInput={companyChatInput}
            setCompanyChatInput={setCompanyChatInput}
            sendCompanyChatMessage={sendCompanyChatMessage}
            uploadPhoto={uploadPhoto}
          />
        </React.Suspense>
      )}
    </>
  );
}
