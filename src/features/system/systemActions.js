import { AUDIT_LOG_PAGE_LIMIT } from '../../constants/appConfig';
import { buildPagedPath } from '../../utils/appRuntimeUtils';

export const createSystemActions = ({
  API,
  setAuditLog,
  setShowSystemStatus,
  setSystemStatus,
  setSystemStatusLoading,
}) => {
  const openSystemStatus = async () => {
    setShowSystemStatus(true);
    setSystemStatusLoading(true);
    try {
      const res = await fetch(API + '/system-status');
      const data = await res.json().catch(() => ({ ok: false, error: 'bad_json' }));
      setSystemStatus(res.ok ? data : { ...data, ok: false, httpStatus: res.status });
    } catch (e) {
      setSystemStatus({ ok: false, error: e.message });
    } finally {
      setSystemStatusLoading(false);
    }
  };

  const loadAuditLog = async () => {
    try {
      const data = await fetch(
        API + buildPagedPath('/audit-log', { limit: AUDIT_LOG_PAGE_LIMIT }),
      ).then((r) => (r.ok ? r.json() : []));
      setAuditLog(Array.isArray(data) ? data : []);
    } catch (e) {
      setAuditLog([]);
    }
  };

  return {
    loadAuditLog,
    openSystemStatus,
  };
};
