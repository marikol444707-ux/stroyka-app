import {
  buildAccountingLinkRepairApplyBody,
  validateAccountingLinkRepairApplyResult,
  validateAccountingLinkRepairPreview,
} from './accountingExceptionRemediation';

const preview = (overrides = {}) => ({
  version: 'accounting-exception-link-repair-v1',
  companyId: 4,
  state: 'ready',
  repairCount: 2,
  unresolvedCount: 29,
  proofCounts: { reciprocal: 0, delivery: 2, request: 0 },
  planSha256: 'a'.repeat(64),
  blockers: [],
  ...overrides,
});

describe('accounting exception link repair contract', () => {
  test('accepts and detaches one strict server preview', () => {
    const source = preview();
    const result = validateAccountingLinkRepairPreview(source, 4);

    expect(result).toEqual(source);
    expect(result).not.toBe(source);
    expect(result.proofCounts).not.toBe(source.proofCounts);
  });

  test('rejects private fields, wrong company, inconsistent counts and invalid states', () => {
    const invalid = [
      preview({ privateRows: [] }),
      preview({ companyId: 5 }),
      preview({ repairCount: 3 }),
      preview({ state: 'clear' }),
      preview({ planSha256: 'A'.repeat(64) }),
      preview({ blockers: ['private'] }),
    ];

    invalid.forEach(value => {
      expect(() => validateAccountingLinkRepairPreview(value, 4))
        .toThrow('accounting_link_repair_preview_invalid');
    });
  });

  test('builds the exact confirmation body with no document data', () => {
    expect(buildAccountingLinkRepairApplyBody(preview())).toEqual({
      confirm: 'APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS',
      expectedRepairCount: 2,
      expectedPlanSha256: 'a'.repeat(64),
    });
  });

  test('validates an apply receipt against the exact preview', () => {
    const result = validateAccountingLinkRepairApplyResult({
      ok: true,
      appliedCount: 2,
      unresolvedCount: 29,
      planSha256: 'a'.repeat(64),
    }, preview());

    expect(result).toEqual({
      ok: true,
      appliedCount: 2,
      unresolvedCount: 29,
      planSha256: 'a'.repeat(64),
    });
    expect(() => validateAccountingLinkRepairApplyResult({
      ok: true,
      appliedCount: 1,
      unresolvedCount: 29,
      planSha256: 'a'.repeat(64),
    }, preview())).toThrow('accounting_link_repair_apply_invalid');
  });
});
