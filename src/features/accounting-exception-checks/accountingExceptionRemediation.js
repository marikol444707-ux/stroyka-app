const PREVIEW_FIELDS = [
  'version',
  'companyId',
  'state',
  'repairCount',
  'unresolvedCount',
  'proofCounts',
  'planSha256',
  'blockers',
];
const APPLY_FIELDS = ['ok', 'appliedCount', 'unresolvedCount', 'planSha256'];
const PROOFS = ['reciprocal', 'delivery', 'request'];
const SHA256 = /^[0-9a-f]{64}$/;

const exactKeys = (value, fields) => (
  value
  && typeof value === 'object'
  && !Array.isArray(value)
  && Object.keys(value).length === fields.length
  && fields.every(field => Object.prototype.hasOwnProperty.call(value, field))
);

const boundedCount = (value, maximum) => (
  Number.isSafeInteger(value) && value >= 0 && value <= maximum
);

export const validateAccountingLinkRepairPreview = (value, expectedCompanyId) => {
  const validBase = (
    exactKeys(value, PREVIEW_FIELDS)
    && value.version === 'accounting-exception-link-repair-v1'
    && Number.isSafeInteger(expectedCompanyId)
    && expectedCompanyId > 0
    && value.companyId === expectedCompanyId
    && ['clear', 'ready', 'blocked'].includes(value.state)
    && boundedCount(value.repairCount, 100)
    && boundedCount(value.unresolvedCount, 2000)
    && exactKeys(value.proofCounts, PROOFS)
    && PROOFS.every(proof => boundedCount(value.proofCounts[proof], 100))
    && PROOFS.reduce((sum, proof) => sum + value.proofCounts[proof], 0) === value.repairCount
    && typeof value.planSha256 === 'string'
    && SHA256.test(value.planSha256)
    && Array.isArray(value.blockers)
  );
  const validState = validBase && (
    (value.state === 'ready' && value.repairCount > 0 && value.blockers.length === 0)
    || (value.state === 'clear' && value.repairCount === 0 && value.blockers.length === 0)
    || (
      value.state === 'blocked'
      && value.repairCount === 0
      && value.blockers.length === 1
      && value.blockers[0] === 'accounting_link_repair_plan_too_large'
    )
  );
  if (!validState) throw new Error('accounting_link_repair_preview_invalid');
  return {
    version: value.version,
    companyId: value.companyId,
    state: value.state,
    repairCount: value.repairCount,
    unresolvedCount: value.unresolvedCount,
    proofCounts: Object.fromEntries(PROOFS.map(proof => [proof, value.proofCounts[proof]])),
    planSha256: value.planSha256,
    blockers: [...value.blockers],
  };
};

export const buildAccountingLinkRepairApplyBody = preview => ({
  confirm: 'APPLY_ACCOUNTING_EXCEPTION_LINK_REPAIRS',
  expectedRepairCount: preview.repairCount,
  expectedPlanSha256: preview.planSha256,
});

export const validateAccountingLinkRepairApplyResult = (value, preview) => {
  if (
    !exactKeys(value, APPLY_FIELDS)
    || value.ok !== true
    || value.appliedCount !== preview?.repairCount
    || !boundedCount(value.unresolvedCount, 2000)
    || value.planSha256 !== preview?.planSha256
  ) {
    throw new Error('accounting_link_repair_apply_invalid');
  }
  return {
    ok: true,
    appliedCount: value.appliedCount,
    unresolvedCount: value.unresolvedCount,
    planSha256: value.planSha256,
  };
};
