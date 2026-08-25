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
  ACCOUNTING_EXCEPTION_REASON_CONTRACTS,
  accountingExceptionReasonLabel,
  parseAccountingExceptionCompanyIds,
  validateAccountingExceptionChecks,
} from './accountingExceptionChecks';
import { buildSafeAccountingLinkPlans } from './accountingExceptionRemediation';

const DEFAULT_ENABLED = process.env.REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_ENABLED === 'true';
const DEFAULT_ALLOWED_COMPANY_IDS = parseAccountingExceptionCompanyIds(
  process.env.REACT_APP_ACCOUNTING_EXCEPTION_CHECKS_COMPANY_IDS,
) || new Set();
const FINANCE_ROLES = new Set(['директор', 'зам_директора', 'бухгалтер']);
const SUBJECT_LABELS = {
  brigade_payment: 'Выплата бригаде',
  supplier_invoice: 'Накладная поставщика',
  warehouse_invoice: 'Складская накладная',
  accountable_expense: 'Подотчётный расход',
  accountable_payment: 'Подотчётный аванс',
  expense_report: 'Авансовый отчёт',
  salary_payment: 'Выплата зарплаты',
  own_expense: 'Личная трата',
  manual_expense: 'Ручная трата',
};
const MONEY_LABELS = {
  storedAmount: 'Сохранённая сумма',
  linkedAmount: 'Связанная сумма',
  invoiceAmount: 'Сумма документа',
  paidAmount: 'Оплачено',
  storedSpentAmount: 'Сохранено как потраченное',
  childAmountSum: 'Сумма расходов',
  advanceAmount: 'Сумма аванса',
  issuedAmount: 'Выдано',
  spentAmount: 'Потрачено',
  storedBalance: 'Сохранённый остаток',
  expectedBalance: 'Расчётный остаток',
};
const linkCountLabel = count => {
  const tail = count % 100;
  const last = count % 10;
  if (tail >= 11 && tail <= 19) return `${count} однозначных связей`;
  if (last === 1) return `${count} однозначную связь`;
  if (last >= 2 && last <= 4) return `${count} однозначные связи`;
  return `${count} однозначных связей`;
};

export default function AccountingExceptionChecksPanel({
  API = '',
  C = {},
  allowedCompanyIds = DEFAULT_ALLOWED_COMPANY_IDS,
  card = {},
  companyMode,
  enabled = DEFAULT_ENABLED,
  invoices = [],
  isMobile = false,
  projects = [],
  refreshData,
  selectedCompanyId,
  supplierInvoices = [],
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
  const [repairing, setRepairing] = React.useState(false);
  const [repairMessage, setRepairMessage] = React.useState(null);
  const [showFindings, setShowFindings] = React.useState(false);

  const repairSummary = React.useMemo(() => buildSafeAccountingLinkPlans({
    companyId: selectedCompanyId,
    findings: result?.findings || [],
    invoices,
    projects,
    supplierInvoices,
  }), [invoices, projects, result, selectedCompanyId, supplierInvoices]);

  React.useEffect(() => {
    setRepairMessage(null);
    setRepairing(false);
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

  const repairSafeLinks = async () => {
    const plans = repairSummary.plans;
    if (!plans.length || repairing) return;
    const confirmed = window.confirm(
      `Исправить ${linkCountLabel(plans.length)}? Спорные документы изменены не будут.`,
    );
    if (!confirmed) return;

    setRepairing(true);
    setRepairMessage(null);
    let repaired = 0;
    let failed = 0;
    for (const plan of plans) {
      try {
        const response = await fetch(`${API}/supplier-invoices/${plan.supplierInvoiceId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            accountingExceptionRepair: true,
            warehouseInvoiceId: plan.warehouseInvoiceId,
          }),
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok || body.detail || body.error) {
          failed += 1;
        } else {
          repaired += 1;
        }
      } catch (_reason) {
        failed += 1;
      }
    }

    if (repaired > 0 && typeof refreshData === 'function') {
      await refreshData();
    }
    setRepairMessage({ repaired, failed });
    setRepairing(false);
    setShowFindings(false);
    setReloadKey(value => value + 1);
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
  const unresolvedFindingCount = repairSummary.unresolvedCount + Math.max(
    0,
    Number(result?.findingCount || 0) - (result?.findings?.length || 0),
  );

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
            Находит противоречия и исправляет только однозначные связи документов. Оплаты не выполняются.
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
          role={repairMessage.failed ? 'alert' : 'status'}
          style={{ marginTop: '14px', padding: '11px', borderRadius: '8px', color: repairMessage.failed ? palette.danger : palette.success, background: repairMessage.failed ? palette.dangerLight : palette.successLight }}
        >
          Исправлено связей: {repairMessage.repaired}.
          {repairMessage.failed > 0 ? ` Не удалось исправить: ${repairMessage.failed}. Список уже обновлён.` : ' Проверка обновлена.'}
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
              {repairSummary.plans.length > 0
                ? `Однозначно определено связей: ${repairSummary.plans.length}. Их можно исправить одним действием.`
                : 'Однозначных совпадений пока нет — система не будет угадывать.'}
              {unresolvedFindingCount > 0 ? ` Осталось спорных: ${unresolvedFindingCount}.` : ''}
            </p>
            {repairSummary.plans.length > 0 && (
              <button
                type="button"
                onClick={repairSafeLinks}
                disabled={repairing || loading}
                style={{ marginTop: '10px', border: 'none', background: C.accent || '#f97316', color: '#fff', borderRadius: '8px', padding: '9px 12px', fontWeight: 800, cursor: repairing || loading ? 'default' : 'pointer', display: 'inline-flex', alignItems: 'center', gap: '7px', opacity: repairing || loading ? 0.65 : 1 }}
              >
                <Link2 size={15} aria-hidden="true" />
                {repairing ? 'Исправляем связи…' : `Исправить безопасные связи (${repairSummary.plans.length})`}
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
            {showFindings ? 'Скрыть список' : 'Показать список'}
          </button>
          {showFindings && (
            <>
              {result.truncated && <p style={{ color: palette.muted, fontSize: '11px' }}>Показаны первые {result.findings.length} записей.</p>}
              <div role="list" style={{ display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'repeat(2, minmax(0, 1fr))', gap: '10px' }}>
                {result.findings.map(finding => {
                  const contract = ACCOUNTING_EXCEPTION_REASON_CONTRACTS[finding.reasonCode];
                  return (
                    <article key={`${finding.reasonCode}:${finding.subjectKind}:${finding.subjectId}`} role="listitem" style={{ border: `1px solid ${palette.border}`, borderRadius: '10px', padding: '12px', minWidth: 0 }}>
                      <h3 style={{ margin: 0, color: palette.text, fontSize: '14px' }}>{accountingExceptionReasonLabel(finding.reasonCode)}</h3>
                      <p style={{ margin: '7px 0 0', color: palette.textSec, fontSize: '12px' }}>
                        {SUBJECT_LABELS[finding.subjectKind]} №{finding.subjectId}
                        {finding.projectId !== null ? ` · Объект №${finding.projectId}` : ''}
                        {contract.ids.map(field => ` · Связанный документ №${finding[field]}`).join('')}
                      </p>
                      {contract.money.length > 0 && (
                        <ul style={{ margin: '8px 0 0', paddingLeft: '18px', color: palette.textSec, fontSize: '12px' }}>
                          {contract.money.map(field => <li key={field}>{MONEY_LABELS[field]}: {finding[field]} ₽</li>)}
                        </ul>
                      )}
                    </article>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
