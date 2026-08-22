import {
  HUMAN_ACTION_ANOMALIES,
  buildHumanActionSource,
  parseHumanApprovedActionCompanyIds,
  validateHumanActionDecisionReceipt,
  validateHumanActionProposalReceipt,
  validateWarehouseAnomalyPreview,
} from './humanApprovedActions';

const selected = {
  subjectKind: 'warehouseInvoice',
  subjectId: 91,
  anomalyCode: 'warehouse_invoice_project_mismatch',
};

const preview = {
  warehouseAnomalyRuntimeVersion: 1,
  ok: true,
  dryRun: true,
  writesAttempted: 0,
  previewOnly: true,
  stockMovementAllowed: false,
  inventoryAdjustmentAllowed: false,
  applyAllowed: false,
  state: 'preview_ready',
  candidate: {
    ...selected,
    recommendationCode: 'review_warehouse_invoice_lineage',
  },
  content: {
    title: 'Проверить объект складской накладной',
    finding: 'Складская накладная относится к другому объекту.',
    nextSafeAction: 'Сопоставьте объект накладной с заявкой и поставкой.',
  },
  blockers: [],
  readOnlyTransaction: true,
  rolledBack: true,
};

const proposal = {
  humanActionReceiptVersion: 1,
  state: 'proposed',
  actionKind: 'warehouse_anomaly_review_acknowledged',
  proposalId: 301,
  proposalSha256: 'a'.repeat(64),
  companyId: 4,
  projectId: 17,
  sourceJobId: 27,
  subjectKind: 'warehouseInvoice',
  subjectId: 91,
  actorUserId: 8,
  actorMembershipId: 12,
  expiresAt: '2026-08-23T12:15:00.000000Z',
  writesAttempted: 2,
  committed: true,
  idempotent: false,
};

const decision = {
  humanActionReceiptVersion: 1,
  state: 'applied',
  actionKind: 'warehouse_anomaly_review_acknowledged',
  proposalId: 301,
  proposalSha256: 'a'.repeat(64),
  companyId: 4,
  projectId: 17,
  sourceJobId: 27,
  subjectKind: 'warehouseInvoice',
  subjectId: 91,
  actorUserId: 8,
  actorMembershipId: 12,
  eventId: 501,
  auditEventId: 701,
  writesAttempted: 3,
  committed: true,
  idempotent: false,
};

describe('human approved action frontend contract', () => {
  test('parses exactly one canonical positive company id', () => {
    expect(parseHumanApprovedActionCompanyIds('4')).toEqual(new Set([4]));
    for (const raw of [undefined, '', '0', '04', '+4', '4 ', '4,5', '4,4', '9007199254740992']) {
      expect(parseHumanApprovedActionCompanyIds(raw)).toBeNull();
    }
  });

  test('builds one exact source and derives subject kind from the closed anomaly registry', () => {
    expect(HUMAN_ACTION_ANOMALIES.warehouse_invoice_project_mismatch.subjectKind)
      .toBe('warehouseInvoice');
    expect(buildHumanActionSource({
      projectId: '17',
      jobId: '27',
      subjectId: '91',
      anomalyCode: 'warehouse_invoice_project_mismatch',
    })).toEqual({ projectId: 17, jobId: 27, selected });

    expect(() => buildHumanActionSource({
      projectId: '17', jobId: '27', subjectId: '91', anomalyCode: 'unknown',
    })).toThrow('human_approved_action_ui_input_invalid');
  });

  test('accepts only detached exact preview and receipt shapes bound to the current source', () => {
    const source = { projectId: 17, jobId: 27, selected };
    expect(validateWarehouseAnomalyPreview(preview, source)).toEqual(preview);
    expect(validateHumanActionProposalReceipt(proposal, 4, source)).toEqual(proposal);
    expect(validateHumanActionDecisionReceipt(decision, 4, proposal)).toEqual(decision);

    for (const malformed of [
      { ...preview, applyAllowed: true },
      { ...preview, candidate: { ...preview.candidate, subjectId: 92 } },
      { ...preview, privateEvidence: 'do-not-render' },
    ]) {
      expect(() => validateWarehouseAnomalyPreview(malformed, source))
        .toThrow('human_approved_action_ui_response_invalid');
    }
    expect(() => validateHumanActionProposalReceipt(
      { ...proposal, projectId: 18 }, 4, source,
    )).toThrow('human_approved_action_ui_response_invalid');
    expect(() => validateHumanActionDecisionReceipt(
      { ...decision, proposalSha256: 'b'.repeat(64) }, 4, proposal,
    )).toThrow('human_approved_action_ui_response_invalid');
  });
});
