import {
  ACCOUNTING_EXCEPTION_REASON_CONTRACTS,
  ACCOUNTING_EXCEPTION_SOURCES,
  accountingExceptionReasonLabel,
  groupAccountingExceptionFindings,
  parseAccountingExceptionCompanyIds,
  validateAccountingExceptionChecks,
} from './accountingExceptionChecks';

const counts = () => Object.fromEntries(
  ACCOUNTING_EXCEPTION_SOURCES.map(source => [source, 0]),
);

const clearReport = (companyId = 4) => ({
  version: 'accounting-exception-projection-v1',
  companyId,
  state: 'clear',
  scanComplete: true,
  sourceCounts: counts(),
  findingCount: 0,
  findings: [],
  truncated: false,
  blockers: [],
});

const reviewReport = (companyId = 4) => ({
  ...clearReport(companyId),
  state: 'review_required',
  findingCount: 1,
  findings: [{
    reasonCode: 'accounting_supplier_invoice_overpaid',
    subjectKind: 'supplier_invoice',
    subjectId: 91,
    projectId: 17,
    invoiceAmount: '1000.5',
    paidAmount: '1001',
  }],
});

describe('accounting exception checks frontend contract', () => {
  test('parses only a strict duplicate-free positive safe-integer allowlist', () => {
    expect(parseAccountingExceptionCompanyIds('4')).toEqual(new Set([4]));
    expect(parseAccountingExceptionCompanyIds('4,17')).toEqual(new Set([4, 17]));
    for (const value of [
      undefined, null, '', '1,1', '01', ' 1', '1 ', '1,,2', '+1',
      '１', '9007199254740992', Array.from({ length: 101 }, (_, i) => i + 1).join(','),
    ]) {
      expect(parseAccountingExceptionCompanyIds(value)).toBeNull();
    }
  });

  test('accepts, detaches and labels only the closed clear/review results', () => {
    const source = reviewReport();
    const validated = validateAccountingExceptionChecks(source, 4);

    expect(validated).toEqual(source);
    expect(validated).not.toBe(source);
    expect(validated.findings[0]).not.toBe(source.findings[0]);
    expect(accountingExceptionReasonLabel(
      validated.findings[0].reasonCode,
    )).toBe('По накладной поставщика оплачено больше суммы документа');

    source.findings[0].paidAmount = 'PRIVATE_MUTATION';
    source.sourceCounts.staff = 999;
    expect(validated.findings[0].paidAmount).toBe('1001');
    expect(validated.sourceCounts.staff).toBe(0);
  });

  test('accepts only the two fixed incomplete blockers', () => {
    for (const blocker of [
      'accounting_exception_projection_input_invalid',
      'accounting_exception_projection_source_incomplete',
    ]) {
      const report = {
        ...clearReport(),
        state: 'incomplete',
        scanComplete: false,
        blockers: [blocker],
      };
      expect(validateAccountingExceptionChecks(report, 4)).toEqual(report);
    }
  });

  test('rejects unknown, cross-company, oversized and internally inconsistent data', () => {
    const mutations = [];
    mutations.push({ ...clearReport(), rawRows: [{ secret: 'PRIVATE' }] });
    mutations.push({ ...clearReport(), companyId: 5 });
    mutations.push({ ...clearReport(), state: 'review_required' });
    mutations.push({ ...clearReport(), scanComplete: false });
    mutations.push({ ...clearReport(), sourceCounts: { ...counts(), private: 1 } });
    mutations.push({ ...clearReport(), sourceCounts: { ...counts(), staff: 1001 } });
    mutations.push({ ...clearReport(), blockers: ['PRIVATE_BLOCKER'] });
    mutations.push({
      ...reviewReport(),
      findings: [{ ...reviewReport().findings[0], note: 'PRIVATE_NOTE' }],
    });
    mutations.push({
      ...reviewReport(),
      findings: [{ ...reviewReport().findings[0], reasonCode: 'PRIVATE_REASON' }],
    });
    mutations.push({
      ...reviewReport(),
      findings: [{ ...reviewReport().findings[0], subjectId: 9007199254740992 }],
    });
    mutations.push({
      ...reviewReport(),
      findings: [{ ...reviewReport().findings[0], paidAmount: '01.00' }],
    });
    mutations.push({
      ...reviewReport(),
      findingCount: 2,
    });

    mutations.forEach(report => {
      expect(() => validateAccountingExceptionChecks(report, 4))
        .toThrow('accounting_exception_checks_invalid');
    });
  });

  test('does not invent a label for an unknown reason code', () => {
    expect(accountingExceptionReasonLabel('PRIVATE_REASON')).toBeNull();
  });

  test('groups repeated findings by business reason without losing records', () => {
    const findings = [
      {
        reasonCode: 'accounting_supplier_warehouse_link_not_found',
        subjectKind: 'supplier_invoice',
        subjectId: 91,
        projectId: 17,
        relatedId: 501,
      },
      {
        reasonCode: 'accounting_supplier_warehouse_link_not_found',
        subjectKind: 'supplier_invoice',
        subjectId: 92,
        projectId: 17,
        relatedId: 502,
      },
      {
        reasonCode: 'accounting_supplier_invoice_overpaid',
        subjectKind: 'supplier_invoice',
        subjectId: 93,
        projectId: 17,
        invoiceAmount: '1000',
        paidAmount: '1100',
      },
    ];

    const groups = groupAccountingExceptionFindings(findings);

    expect(groups.map(group => ({
      reasonCode: group.reasonCode,
      count: group.count,
      subjectIds: group.findings.map(finding => finding.subjectId),
    }))).toEqual([
      {
        reasonCode: 'accounting_supplier_warehouse_link_not_found',
        count: 2,
        subjectIds: [91, 92],
      },
      {
        reasonCode: 'accounting_supplier_invoice_overpaid',
        count: 1,
        subjectIds: [93],
      },
    ]);
    expect(groups[0].findings).not.toBe(findings);
  });

  test('keeps every rendering rule and its field allowlists immutable', () => {
    expect(Object.isFrozen(ACCOUNTING_EXCEPTION_REASON_CONTRACTS)).toBe(true);
    Object.values(ACCOUNTING_EXCEPTION_REASON_CONTRACTS).forEach(contract => {
      expect(typeof contract.nextStep).toBe('string');
      expect(contract.nextStep.length).toBeGreaterThan(20);
      expect(Object.isFrozen(contract)).toBe(true);
      expect(Object.isFrozen(contract.subjects)).toBe(true);
      expect(Object.isFrozen(contract.ids)).toBe(true);
      expect(Object.isFrozen(contract.money)).toBe(true);
    });
  });
});
