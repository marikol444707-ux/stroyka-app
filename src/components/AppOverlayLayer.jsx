import React from 'react';
import { FloatingCompanyChatPanel } from '../app/lazyComponents';
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
  return (
    <>
      <SystemStatusModal
        show={showSystemStatus}
        systemStatus={systemStatus}
        systemStatusLoading={systemStatusLoading}
        onRefresh={openSystemStatus}
        onClose={() => setShowSystemStatus(false)}
        C={C}
        badge={badge}
        btnG={btnG}
      />
      <MobileMenuSheet
        showMobileMenu={showMobileMenu}
        setShowMobileMenu={setShowMobileMenu}
        menuItems={menuItems}
        activePage={activePage}
        setActivePage={setActivePage}
        C={C}
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
