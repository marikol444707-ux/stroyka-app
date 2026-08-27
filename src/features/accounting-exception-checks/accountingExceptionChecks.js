export const ACCOUNTING_EXCEPTION_SOURCES = Object.freeze([
  'brigade_contracts',
  'brigade_payments',
  'project_payments',
  'supplier_invoices',
  'warehouse_invoices',
  'accountable_payments',
  'accountable_expenses',
  'expense_reports',
  'staff',
  'salary_payments',
  'own_expenses',
  'expenses',
]);

export const ACCOUNTING_EXCEPTION_REASON_CONTRACTS = Object.freeze({
  accounting_brigade_ledger_link_missing: {
    label: 'У выплаты бригаде отсутствует обязательная связь с платёжным реестром',
    subjects: ['brigade_payment'], ids: [], money: [],
  },
  accounting_brigade_ledger_not_found: {
    label: 'Связанный платёжный реестр выплаты бригаде не найден',
    subjects: ['brigade_payment'], ids: ['relatedId'], money: [],
  },
  accounting_brigade_ledger_project_mismatch: {
    label: 'Выплата бригаде и платёжный реестр относятся к разным объектам',
    subjects: ['brigade_payment'], ids: ['relatedId'], money: [],
  },
  accounting_brigade_ledger_amount_mismatch: {
    label: 'Сумма выплаты бригаде не совпадает с платёжным реестром',
    subjects: ['brigade_payment'], ids: [], money: ['storedAmount', 'linkedAmount'],
  },
  accounting_supplier_warehouse_link_not_found: {
    label: 'Связанный складской или поставщицкий документ не найден',
    subjects: ['supplier_invoice', 'warehouse_invoice'], ids: ['relatedId'], money: [],
  },
  accounting_supplier_warehouse_link_nonreciprocal: {
    label: 'Связь накладных поставщика и склада не является взаимной',
    subjects: ['supplier_invoice', 'warehouse_invoice'], ids: ['relatedId'], money: [],
  },
  accounting_supplier_invoice_overpaid: {
    label: 'По накладной поставщика оплачено больше суммы документа',
    subjects: ['supplier_invoice'], ids: [], money: ['invoiceAmount', 'paidAmount'],
  },
  accounting_accountable_expense_parent_not_found: {
    label: 'Для подотчётного расхода не найден подтверждённый аванс',
    subjects: ['accountable_expense'], ids: ['relatedId'], money: [],
  },
  accounting_accountable_expense_parent_project_mismatch: {
    label: 'Подотчётный расход и аванс относятся к разным объектам',
    subjects: ['accountable_expense'], ids: ['relatedId'], money: [],
  },
  accounting_accountable_spent_sum_mismatch: {
    label: 'Сумма подотчётных расходов не совпадает с сохранённым итогом',
    subjects: ['accountable_payment'], ids: [], money: ['storedSpentAmount', 'childAmountSum'],
  },
  accounting_accountable_advance_exceeded: {
    label: 'Сумма подотчётных расходов превышает выданный аванс',
    subjects: ['accountable_payment'], ids: [], money: ['advanceAmount', 'childAmountSum'],
  },
  accounting_expense_report_balance_mismatch: {
    label: 'Остаток авансового отчёта не совпадает с расчётным',
    subjects: ['expense_report'],
    ids: [],
    money: ['issuedAmount', 'spentAmount', 'storedBalance', 'expectedBalance'],
  },
  accounting_salary_staff_not_found: {
    label: 'Для выплаты зарплаты не найден подтверждённый сотрудник',
    subjects: ['salary_payment'], ids: ['relatedId'], money: [],
  },
  accounting_salary_month_invalid: {
    label: 'У выплаты зарплаты некорректно сохранён расчётный месяц',
    subjects: ['salary_payment'], ids: [], money: [],
  },
  accounting_own_expense_link_not_found: {
    label: 'Связанная личная или ручная трата не найдена',
    subjects: ['own_expense', 'manual_expense'], ids: ['relatedId'], money: [],
  },
  accounting_own_expense_link_nonreciprocal: {
    label: 'Связь личной и ручной траты не является взаимной',
    subjects: ['own_expense', 'manual_expense'], ids: ['relatedId'], money: [],
  },
  accounting_own_expense_link_project_mismatch: {
    label: 'Связанные личная и ручная траты относятся к разным объектам',
    subjects: ['own_expense', 'manual_expense'], ids: ['relatedId'], money: [],
  },
});

Object.values(ACCOUNTING_EXCEPTION_REASON_CONTRACTS).forEach(contract => {
  Object.freeze(contract.subjects);
  Object.freeze(contract.ids);
  Object.freeze(contract.money);
  Object.freeze(contract);
});

const PUBLIC_FIELDS = new Set([
  'version', 'companyId', 'state', 'scanComplete', 'sourceCounts',
  'findingCount', 'findings', 'truncated', 'blockers',
]);
const BASE_FINDING_FIELDS = ['reasonCode', 'subjectKind', 'subjectId', 'projectId'];
const BLOCKERS = new Set([
  'accounting_exception_projection_input_invalid',
  'accounting_exception_projection_source_incomplete',
]);
const MONEY_RE = /^-?(?:0|[1-9][0-9]{0,63})(?:\.[0-9]{1,64})?$/;
const MAX_SOURCE_ROWS = 1000;
const MAX_FINDINGS = 100;
const MAX_TOTAL_FINDINGS = 20000;

const plainObject = value => (
  value !== null
  && typeof value === 'object'
  && !Array.isArray(value)
  && Object.getPrototypeOf(value) === Object.prototype
);
const exactKeys = (value, expected) => {
  const keys = Object.keys(value);
  return keys.length === expected.size && keys.every(key => expected.has(key));
};
const positiveId = value => Number.isSafeInteger(value) && value > 0;
const optionalPositiveId = value => value === null || positiveId(value);
const invalid = () => {
  throw new Error('accounting_exception_checks_invalid');
};

export const parseAccountingExceptionCompanyIds = raw => {
  if (typeof raw !== 'string') return null;
  const parts = raw.split(',');
  if (parts.length < 1 || parts.length > 100) return null;
  const companyIds = new Set();
  for (const part of parts) {
    if (!/^[1-9][0-9]*$/.test(part)) return null;
    const companyId = Number(part);
    if (!Number.isSafeInteger(companyId) || companyIds.has(companyId)) return null;
    companyIds.add(companyId);
  }
  return companyIds;
};

export const accountingExceptionReasonLabel = reasonCode => (
  ACCOUNTING_EXCEPTION_REASON_CONTRACTS[reasonCode]?.label || null
);

export const groupAccountingExceptionFindings = findings => {
  const groups = new Map();
  findings.forEach(finding => {
    const existing = groups.get(finding.reasonCode);
    if (existing) {
      existing.findings.push(finding);
      existing.count += 1;
      return;
    }
    groups.set(finding.reasonCode, {
      reasonCode: finding.reasonCode,
      count: 1,
      findings: [finding],
    });
  });
  return [...groups.values()];
};

const validatedFinding = value => {
  if (!plainObject(value)) invalid();
  const contract = ACCOUNTING_EXCEPTION_REASON_CONTRACTS[value.reasonCode];
  if (!contract) invalid();
  const expected = new Set([...BASE_FINDING_FIELDS, ...contract.ids, ...contract.money]);
  if (
    !exactKeys(value, expected)
    || !contract.subjects.includes(value.subjectKind)
    || !positiveId(value.subjectId)
    || !optionalPositiveId(value.projectId)
    || contract.ids.some(field => !positiveId(value[field]))
    || contract.money.some(field => typeof value[field] !== 'string' || !MONEY_RE.test(value[field]))
  ) invalid();
  return Object.fromEntries([...expected].map(field => [field, value[field]]));
};

export const validateAccountingExceptionChecks = (value, expectedCompanyId) => {
  if (
    !plainObject(value)
    || !positiveId(expectedCompanyId)
    || !exactKeys(value, PUBLIC_FIELDS)
    || value.version !== 'accounting-exception-projection-v1'
    || value.companyId !== expectedCompanyId
    || !['clear', 'review_required', 'incomplete'].includes(value.state)
    || typeof value.scanComplete !== 'boolean'
    || !Number.isSafeInteger(value.findingCount)
    || value.findingCount < 0
    || value.findingCount > MAX_TOTAL_FINDINGS
    || !Array.isArray(value.findings)
    || value.findings.length > MAX_FINDINGS
    || typeof value.truncated !== 'boolean'
    || !Array.isArray(value.blockers)
  ) invalid();

  if (!plainObject(value.sourceCounts)) invalid();
  const sourceFields = new Set(ACCOUNTING_EXCEPTION_SOURCES);
  if (
    !exactKeys(value.sourceCounts, sourceFields)
    || ACCOUNTING_EXCEPTION_SOURCES.some(source => (
      !Number.isSafeInteger(value.sourceCounts[source])
      || value.sourceCounts[source] < 0
      || value.sourceCounts[source] > MAX_SOURCE_ROWS
    ))
  ) invalid();

  const findings = value.findings.map(validatedFinding);
  const clear = value.state === 'clear' && value.scanComplete === true
    && value.findingCount === 0 && findings.length === 0
    && value.truncated === false && value.blockers.length === 0;
  const review = value.state === 'review_required' && value.scanComplete === true
    && value.findingCount > 0
    && findings.length === Math.min(value.findingCount, MAX_FINDINGS)
    && value.truncated === (value.findingCount > MAX_FINDINGS)
    && value.blockers.length === 0;
  const incomplete = value.state === 'incomplete' && value.scanComplete === false
    && value.findingCount === 0 && findings.length === 0
    && value.truncated === false && value.blockers.length === 1
    && BLOCKERS.has(value.blockers[0]);
  if (!clear && !review && !incomplete) invalid();

  return {
    version: value.version,
    companyId: value.companyId,
    state: value.state,
    scanComplete: value.scanComplete,
    sourceCounts: Object.fromEntries(
      ACCOUNTING_EXCEPTION_SOURCES.map(source => [source, value.sourceCounts[source]]),
    ),
    findingCount: value.findingCount,
    findings,
    truncated: value.truncated,
    blockers: [...value.blockers],
  };
};
