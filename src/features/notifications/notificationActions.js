import {
  notificationPageForType,
  notificationsForUser,
} from '../../utils/notificationUtils';

export const createNotificationActions = ({
  API,
  activePage,
  loadAuditLog,
  notifications,
  pushEnabled,
  sendPushNotification,
  setActivityLog,
  setNotifications,
  setShowNotifications,
  user,
}) => {
  const getNotifPage = (type) => notificationPageForType(type);

  const myNotifications = (notifs) => notificationsForUser(notifs, user);

  const toggleNotifications = (e) => {
    e?.stopPropagation?.();
    setShowNotifications((v) => !v);
  };

  const closeNotifications = () => setShowNotifications(false);

  const markMyNotificationsRead = () => {
    const visibleIds = new Set(myNotifications(notifications).map((n) => n.id));
    const updated = notifications.map((n) => (visibleIds.has(n.id) ? { ...n, read: true } : n));
    setNotifications(updated);
    localStorage.setItem('notifications', JSON.stringify(updated));
  };

  const notify = (text, type) => {
    const n = {
      id: Date.now(),
      text,
      type,
      time: new Date().toLocaleString('ru-RU'),
      read: false,
    };
    setNotifications((prev) => {
      const updated = [n, ...prev].slice(0, 50);
      localStorage.setItem('notifications', JSON.stringify(updated));
      return updated;
    });
    if (pushEnabled) sendPushNotification('СтройКа', text);
  };

  const addActivity = (action) => {
    const entry = {
      id: Date.now(),
      action,
      user: user ? user.name : '',
      role: user ? user.role : '',
      time: new Date().toLocaleString('ru-RU'),
    };
    setActivityLog((prev) => {
      const updated = [entry, ...prev].slice(0, 100);
      localStorage.setItem('activityLog', JSON.stringify(updated));
      return updated;
    });
    try {
      const token = localStorage.getItem('authToken');
      if (token && user) {
        fetch(API + '/audit-log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
          body: JSON.stringify({ action, entityType: 'ui', description: action }),
        })
          .then((res) => {
            if (res.ok && activePage === 'activitylog') loadAuditLog();
          })
          .catch(() => {});
      }
    } catch {}
  };

  return {
    addActivity,
    closeNotifications,
    getNotifPage,
    markMyNotificationsRead,
    myNotifications,
    notify,
    toggleNotifications,
  };
};
