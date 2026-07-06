import { useEffect, useState } from 'react';
import { detectMobileLayout } from '../../constants/uiTheme';
import {
  initialGuestPage,
  loadStoredUser,
  requestPushPermission,
} from '../../utils/appRuntimeUtils';
import { quickActionPageFor } from '../quick-actions/quickActionRegistry';

export function useResponsiveLayout() {
  const [isMobile, setIsMobile] = useState(detectMobileLayout);
  const [isCompactHeader, setIsCompactHeader] = useState(
    typeof window !== 'undefined' && window.innerWidth < 1180
  );

  useEffect(() => {
    const onResize = () => {
      setIsMobile(detectMobileLayout());
      setIsCompactHeader(window.innerWidth < 1180);
    };
    window.addEventListener('resize', onResize);
    window.visualViewport?.addEventListener('resize', onResize);
    onResize();
    return () => {
      window.removeEventListener('resize', onResize);
      window.visualViewport?.removeEventListener('resize', onResize);
    };
  }, []);

  return { isMobile, isCompactHeader };
}

export function useDarkModeState() {
  const [darkMode, setDarkMode] = useState(
    typeof window !== 'undefined' && localStorage.getItem('darkMode') === '1'
  );

  useEffect(() => {
    if (typeof document !== 'undefined') document.documentElement.dataset.theme = darkMode ? 'dark' : 'light';
    try { localStorage.setItem('darkMode', darkMode ? '1' : '0'); } catch (e) {}
  }, [darkMode]);

  return [darkMode, setDarkMode];
}

export function useAuthEntryState() {
  const [user, setUser] = useState(loadStoredUser);
  const [page, setPage] = useState(initialGuestPage);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regCode, setRegCode] = useState('');
  const [regInviteInfo, setRegInviteInfo] = useState(null);
  const [regSupplierData, setRegSupplierData] = useState({
    companyName: '',
    inn: '',
    kpp: '',
    ogrn: '',
    phone: '',
    legalAddress: '',
    bank: '',
    bik: '',
    account: '',
    directorName: '',
    category: '',
    specialization: '',
  });

  useInviteRouteEffect({ setRegCode, setPage });

  const [loginError, setLoginError] = useState(() => {
    try {
      if (typeof window !== 'undefined' && sessionStorage.getItem('authExpiredNotice')) {
        sessionStorage.removeItem('authExpiredNotice');
        return 'Сессия истекла, войдите снова';
      }
    } catch (e) {}
    return '';
  });

  return {
    email,
    loginError,
    page,
    password,
    regCode,
    regEmail,
    regInviteInfo,
    regName,
    regPassword,
    regSupplierData,
    setEmail,
    setLoginError,
    setPage,
    setPassword,
    setRegCode,
    setRegEmail,
    setRegInviteInfo,
    setRegName,
    setRegPassword,
    setRegSupplierData,
    setUser,
    user,
  };
}

export function useShellOverlayState() {
  const [showAiChat, setShowAiChat] = useState(false);
  const [showMobileMenu, setShowMobileMenu] = useState(false);
  const [showQuickActions, setShowQuickActions] = useState(false);
  const [systemStatus, setSystemStatus] = useState(null);
  const [systemStatusLoading, setSystemStatusLoading] = useState(false);
  const [showSystemStatus, setShowSystemStatus] = useState(false);
  const [showChatPanel, setShowChatPanelRaw] = useState(false);
  const [companyChatInput, setCompanyChatInput] = useState('');
  const [showScanInvoice, setShowScanInvoice] = useState(false);
  const [showScannedInvoiceForm, setShowScannedInvoiceForm] = useState(false);
  const [showReceiveDialog, setShowReceiveDialog] = useState(false);
  const [scanningInvoice, setScanningInvoice] = useState(false);

  return {
    companyChatInput,
    scanningInvoice,
    setCompanyChatInput,
    setScanningInvoice,
    setShowAiChat,
    setShowChatPanelRaw,
    setShowMobileMenu,
    setShowQuickActions,
    setShowReceiveDialog,
    setShowScanInvoice,
    setShowScannedInvoiceForm,
    setShowSystemStatus,
    setSystemStatus,
    setSystemStatusLoading,
    showAiChat,
    showChatPanel,
    showMobileMenu,
    showQuickActions,
    showReceiveDialog,
    showScanInvoice,
    showScannedInvoiceForm,
    showSystemStatus,
    systemStatus,
    systemStatusLoading,
  };
}

export function useInviteRouteEffect({ setRegCode, setPage }) {
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const params = new URLSearchParams(window.location.search);
      const code = params.get('invite');
      if (code) {
        setRegCode(code.toUpperCase());
        setPage('register');
        window.history.replaceState({}, '', window.location.pathname);
      }
    } catch (_) {}
  }, [setRegCode, setPage]);
}

export function useNotificationDismissEffect(setShowNotifications) {
  useEffect(() => {
    const handleOutside = (event) => {
      const target = event.target;
      if (target && typeof target.closest === 'function' && target.closest('[data-notification-root="1"]')) return;
      setShowNotifications(false);
    };
    const handleKey = (event) => {
      if (event.key === 'Escape') setShowNotifications(false);
    };
    document.addEventListener('pointerdown', handleOutside);
    document.addEventListener('touchstart', handleOutside, { passive: true });
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('pointerdown', handleOutside);
      document.removeEventListener('touchstart', handleOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [setShowNotifications]);
}

export function useInviteCodeCheckEffect({
  checkInviteCode,
  regCode,
  setRegInviteInfo,
}) {
  useEffect(() => {
    if (!regCode) {
      setRegInviteInfo(null);
      return undefined;
    }
    const timerId = setTimeout(() => {
      checkInviteCode(regCode);
    }, 400);
    return () => clearTimeout(timerId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [regCode]);
}

export function useAuthenticatedAppBootstrapEffect({
  API,
  isMobile,
  loadMasterProfile,
  loadMobileInitial,
  mobileApiRequestsRef,
  mobileLoadedScopesRef,
  refreshData,
  setActivePage,
  setCompanyName,
  setInitialDataLoaded,
  setPushEnabled,
  storageSetters = {},
  user,
}) {
  useEffect(() => {
    if (!user) return undefined;

    mobileLoadedScopesRef.current.clear();
    mobileApiRequestsRef.current.clear();
    const initialLoader = typeof loadMobileInitial === 'function' ? loadMobileInitial : refreshData;
    const loadFallbackTimer = typeof setInitialDataLoaded === 'function'
      ? setTimeout(() => setInitialDataLoaded(true), 15000)
      : null;
    const clearLoadFallback = () => {
      if (loadFallbackTimer) clearTimeout(loadFallbackTimer);
    };
    if (typeof initialLoader === 'function') {
      Promise.resolve(initialLoader())
        .catch((error) => {
          console.error('initial app data load failed', error);
          if (typeof setInitialDataLoaded === 'function') setInitialDataLoaded(true);
        })
        .finally(clearLoadFallback);
    } else {
      if (typeof setInitialDataLoaded === 'function') setInitialDataLoaded(true);
      clearLoadFallback();
    }

    if (['мастер', 'субподрядчик', 'бригадир'].includes(user.role)) {
      if (typeof loadMasterProfile === 'function') loadMasterProfile();
      setActivePage('works');
    }

    try {
      const params = new URLSearchParams(window.location.search || '');
      const quickAction = params.get('quickAction') || '';
      const targetPage = params.get('page') || quickActionPageFor(quickAction);
      if (targetPage) {
        setActivePage(targetPage);
        if (!quickAction) window.history.replaceState({}, '', window.location.pathname);
      }
    } catch (_) {}

    const savedCompanyName = localStorage.getItem('companyName');
    if (savedCompanyName) setCompanyName(savedCompanyName);

    Object.entries(storageSetters).forEach(([key, setter]) => {
      const rawValue = localStorage.getItem(key);
      if (!rawValue || typeof setter !== 'function') return;
      try {
        setter(JSON.parse(rawValue));
      } catch (_) {}
    });

    requestPushPermission().then(granted => setPushEnabled(granted));

    const pingOnline = async () => {
      try {
        await fetch(API + '/online', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            userId: user.id,
            userName: user.name,
            userRole: user.role,
            lastSeen: new Date().toISOString(),
          }),
        });
      } catch (_) {}
    };

    pingOnline();
    const pingInterval = setInterval(pingOnline, 30000);
    return () => {
      clearLoadFallback();
      clearInterval(pingInterval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);
}
