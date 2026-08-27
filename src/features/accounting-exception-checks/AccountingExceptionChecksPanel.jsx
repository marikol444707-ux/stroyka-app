import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Link2,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';

import {
  groupAccountingExceptionFindings,
  parseAccountingExceptionCompanyIds,
  validateAccountingExceptionChecks,
} from './accountingExceptionChecks';
import AccountingExceptionFindingGroups from './AccountingExceptionFindingGroups';
import {
  buildAccountingLinkRepairApplyBody,
  validateAccountingLinkRepairApplyResult,
  validateAccountingLinkRepairPreview,
} from './accountingExceptionRemediation';

const DEFAULT_ENABLED = process.env.REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_ENABLED === 'true';
const DEFAULT_ALLOWED_COMPANY_IDS = parseAccountingExceptionCompanyIds(
  process.env.REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS,
) || new Set();
const FINANCE_ROLES = new Set(['директор', 'зам_директора', 'бухгалтер']);

export default function AccountingExceptionChecksPanel({
  API = '',
  C = {},
  allowedCompanyIds = DEFAULT_ALLOWED_COMPANY_IDS,
  card = {},
  companyMode,
  enabled = DEFAULT_ENABLED,
  isMobile = false,
  refreshData,
  selectedCompanyId,
  user = {},
}) {
  const allowed = (
    enabled === true
    && companyMode === 'company'
    && Number.isSafeInteger(selectedCompanyId)
    && selectedCompanyId > 0
    && allowedCompanyIds instanceof Set
    && allowedCompanyIds.has(selectedCompanyId)
    && FINANCE_ROLES.has(user?.role)
  );
  const [reloadKey, setReloadKey] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [result, setResult] = React.useState(null);
  const [repairPreview, setRepairPreview] = React.useState(null);
  const [repairLoading, setRepairLoading] = React.useState(false);
  const [repairing, setRepairing] = React.useState(false);
  const [repairMessage, setRepairMessage] = React.useState(null);
  const [showFindings, setShowFindings] = React.useState(false);
  const selectedCompanyIdRef = React.useRef(selectedCompanyId);
  selectedCompanyIdRef.current = selectedCompanyId;

  React.useEffect(() => {
    setRepairPreview(null);
    setRepairMessage(null);
    setRepairing(false);
    setRepairLoading(false);
    setShowFindings(false);
  }, [selectedCompanyId]);

  React.useEffect(() => {
    setResult(null);
    setError('');
    setLoading(false);
    if (!allowed) return undefined;

    const controller = new AbortController();
    setLoading(true);
    fetch(`${API}/accounting-exception-checks`, {
      credentials: 'include',
      signal: controller.signal,
    })
      .then(response => {
        if (!response.ok) throw new Error('accounting_exception_checks_unavailable');
        return response.json();
      })
      .then(body => {
        if (controller.signal.aborted) return;
        setResult(validateAccountingExceptionChecks(body, selectedCompanyId));
      })
      .catch(reason => {
        if (controller.signal.aborted || reason?.name === 'AbortError') return;
        setResult(null);
        setError('Проверка бухгалтерских связей временно недоступна');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [API, allowed, reloadKey, selectedCompanyId]);

  React.useEffect(() => {
    setRepairPreview(null);
    setRepairLoading(false);
    if (!allowed) return undefined;

    const controller = new AbortController();
    setRepairLoading(true);
    fetch(`${API}/accounting-exception-link-repairs`, {
      credentials: 'include',
      signal: controller.signal,
    })
      .then(response => {
        if (!response.ok) throw new Error('accounting_link_repair_preview_unavailable');
        return response.json();
      })
      .then(body => {
        if (controller.signal.aborted) return;
        setRepairPreview(validateAccountingLinkRepairPreview(body, selectedCompanyId));
      })
      .catch(reason => {
        if (controller.signal.aborted || reason?.name === 'AbortError') return;
        setRepairPreview(null);
      })
      .finally(() => {
        if (!controller.signal.aborted) setRepairLoading(false);
      });
    return () => controller.abort();
  }, [API, allowed, reloadKey, selectedCompanyId]);

  const repairSafeLinks = async () => {
    const preview = repairPreview;
    if (preview?.state !== 'ready' || preview.repairCount < 1 || repairing) return;
    const isCurrentCompany = () => (
      selectedCompanyIdRef.current === preview.companyId
    );
    const confirmed = window.confirm(
      `Исправить ${preview.repairCount} записей? Точные связи будут восстановлены, ссылки на отсутствующие документы — удалены. Суммы, оплаты и складские остатки не изменятся.`,
    );
    if (!confirmed) return;

    setRepairing(true);
    setRepairMessage(null);
    try {
      const response = await fetch(`${API}/accounting-exception-link-repairs`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildAccountingLinkRepairApplyBody(preview)),
      });
      if (response.status === 409) {
        if (isCurrentCompany()) {
          setRepairMessage({
            error: 'Данные изменились. Обновите проверку и повторите действие.',
          });
        }
        return;
      }
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error('accounting_link_repair_apply_unavailable');
      const receipt = validateAccountingLinkRepairApplyResult(body, preview);
      if (!isCurrentCompany()) return;
      if (typeof refreshData === 'function') await refreshData();
      if (!isCurrentCompany()) return;
      setRepairMessage({ repaired: receipt.appliedCount });
      setShowFindings(false);
      setReloadKey(value => value + 1);
    } catch (_reason) {
      if (isCurrentCompany()) {
        setRepairMessage({
          error: 'Исправление связей временно недоступно. Данные не изменены.',
        });
      }
    } finally {
      if (isCurrentCompany()) setRepairing(false);
    }
  };

  if (!allowed) return null;

  const palette = {
    text: C.text || '#111827',
    textSec: C.textSec || '#4b5563',
    muted: C.textMuted || '#6b7280',
    border: C.border || '#d1d5db',
    success: C.success || '#15803d',
    successLight: C.successLight || '#f0fdf4',
    warning: C.warning || '#a16207',
    warningLight: C.warningLight || '#fefce8',
    danger: C.danger || '#b91c1c',
    dangerLight: C.dangerLight || '#fef2f2',
  };
  const checkedRows = result
    ? Object.values(result.sourceCounts).reduce((sum, count) => sum + count, 0)
    : 0;
  const unresolvedFindingCount = repairPreview?.unresolvedCount
    ?? Number(result?.findingCount || 0);
  const findingGroups = result?.state === 'review_required'
    ? groupAccountingExceptionFindings(result.findings)
    : [];

  return (
    <section
      aria-labelledby="accounting-exception-checks-title"
      style={{ ...card, padding: isMobile ? '14px' : '18px', marginBottom: '16px' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
        <div>
          <h2 id="accounting-exception-checks-title" style={{ margin: 0, color: palette.text, fontSize: '18px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={19} aria-hidden="true" />Проверка бухгалтерских связей
          </h2>
          <p style={{ margin: '6px 0 0', color: palette.textSec, fontSize: '12px' }}>
            Исправляет точные связи и убирает ссылки на уже отсутствующие документы. Оплаты не выполняются.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setReloadKey(value => value + 1)}
          disabled={loading}
          style={{ border: `1px solid ${palette.border}`, background: 'transparent', color: palette.text, borderRadius: '8px', padding: '8px 11px', fontWeight: 700, cursor: loading ? 'default' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
        >
          <RefreshCw size={14} aria-hidden="true" />Обновить проверку
        </button>
      </div>

      {loading && (
        <div role="status" aria-live="polite" style={{ padding: '18px 0 4px', color: palette.textSec }}>
          Проверяем бухгалтерские связи…
        </div>
      )}
      {error && (
        <div role="alert" style={{ marginTop: '14px', padding: '11px', borderRadius: '8px', color: palette.danger, background: palette.dangerLight }}>
          {error}
        </div>
      )}
      {repairMessage && (
        <div
          role={repairMessage.error ? 'alert' : 'status'}
          style={{ marginTop: '14px', padding: '11px', borderRadius: '8px', color: repairMessage.error ? palette.danger : palette.success, background: repairMessage.error ? palette.dangerLight : palette.successLight }}
        >
          {repairMessage.error || `Исправлено записей: ${repairMessage.repaired}. Проверка обновлена.`}
        </div>
      )}
      {result?.state === 'clear' && (
        <div role="status" style={{ marginTop: '14px', padding: '12px', borderRadius: '8px', color: palette.success, background: palette.successLight, display: 'flex', gap: '8px', alignItems: 'center' }}>
          <CheckCircle2 size={18} aria-hidden="true" />
          <span><b>Противоречий в проверенном контуре не найдено</b><br /><small>Проверено записей: {checkedRows}</small></span>
        </div>
      )}
      {result?.state === 'incomplete' && (
        <div role="alert" style={{ marginTop: '14px', padding: '12px', borderRadius: '8px', color: palette.warning, background: palette.warningLight, display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
          <AlertTriangle size={18} aria-hidden="true" />
          <span><b>Проверка не завершена: часть данных не прошла безопасные ограничения</b><br /><small>Выводы не показываются, пока чтение не будет полным.</small></span>
        </div>
      )}
      {result?.state === 'review_required' && (
        <div style={{ marginTop: '14px' }}>
          <div style={{ padding: '12px', borderRadius: '10px', color: palette.warning, background: palette.warningLight }}>
            <b>Требуется проверка: {result.findingCount}</b>
            <p style={{ margin: '5px 0 0', color: palette.textSec, fontSize: '12px' }}>
              {repairPreview?.state === 'ready'
                ? `Безопасных исправлений: ${repairPreview.repairCount}. Их можно применить одним действием.`
                : 'Безопасных исправлений пока нет — система не будет угадывать.'}
              {unresolvedFindingCount > 0 ? ` Осталось спорных: ${unresolvedFindingCount}.` : ''}
            </p>
            {repairPreview?.state === 'ready' && repairPreview.repairCount > 0 && (
              <button
                type="button"
                onClick={repairSafeLinks}
                disabled={repairing || loading || repairLoading}
                style={{ marginTop: '10px', border: 'none', background: C.accent || '#f97316', color: '#fff', borderRadius: '8px', padding: '9px 12px', fontWeight: 800, cursor: repairing || loading || repairLoading ? 'default' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '7px', opacity: repairing || loading || repairLoading ? 0.65 : 1 }}
              >
                <Link2 size={15} aria-hidden="true" />
                {repairing ? 'Исправляем…' : `Исправить безопасно (${repairPreview.repairCount})`}
              </button>
            )}
          </div>
          <button
            type="button"
            onClick={() => setShowFindings(value => !value)}
            aria-expanded={showFindings}
            style={{ marginTop: '10px', border: 'none', background: 'transparent', color: palette.textSec, padding: '4px 0', fontWeight: 700, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '5px' }}
          >
            {showFindings ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}
            {showFindings ? 'Скрыть причины' : 'Показать причины'}
          </button>
          {showFindings && (
            <>
              {result.truncated && <p style={{ color: palette.muted, fontSize: '11px' }}>Показаны первые {result.findings.length} записей.</p>}
              <AccountingExceptionFindingGroups
                groups={findingGroups}
                isMobile={isMobile}
                palette={palette}
              />
            </>
          )}
        </div>
      )}
    </section>
  );
}
