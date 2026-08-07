import {
  BudgetAdjustmentClientError,
  budgetAdjustmentErrorMessage,
  createProjectBudgetAdjustmentActions,
} from './projectBudgetAdjustmentActions';

const HASH = 'a'.repeat(64);

const jsonResponse = (body, {ok = true, status = 200} = {}) => ({
  ok,
  status,
  json: jest.fn().mockResolvedValue(body),
});

const preview = (overrides = {}) => ({
  reconciliationId: 15,
  companyId: 4,
  projectId: 14,
  baseEstimateId: 100,
  nextEstimateId: 101,
  projectBudgetBefore: '1000000.00',
  estimateBaseTotal: '250000.00',
  estimateNextTotal: '275000.00',
  adjustmentAmount: '25000.00',
  projectBudgetAfter: '1025000.00',
  planSha256: HASH,
  readyForApproval: true,
  blockers: [],
  ...overrides,
});

const receipt = (overrides = {}) => ({
  id: 9,
  companyId: 4,
  projectId: 14,
  reconciliationId: 15,
  baseEstimateId: 100,
  nextEstimateId: 101,
  projectBudgetBefore: '1000000.00',
  estimateBaseTotal: '250000.00',
  estimateNextTotal: '275000.00',
  adjustmentAmount: '25000.00',
  projectBudgetAfter: '1025000.00',
  planSha256: HASH,
  approvedByUserId: 7,
  approvedByName: 'Николай',
  approvedByRole: 'директор',
  approvedAt: '2026-08-07T12:00:00+00:00',
  createdAt: '2026-08-07T12:00:00+00:00',
  ...overrides,
});

const actionsFor = (fetchFn) => createProjectBudgetAdjustmentActions({
  API: 'https://example.test',
  apiAuthHeaders: (headers = {}) => ({...headers, Authorization:'Bearer test'}),
  fetchFn,
});

describe('project budget adjustment actions', () => {
  it('loads and allowlists one exact canonical preview', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse({...preview(), ignored:'secret'}));

    const result = await actionsFor(fetchFn).loadBudgetAdjustmentPreview(15);

    expect(fetchFn).toHaveBeenCalledWith(
      'https://example.test/estimate-reconciliations/15/budget-adjustment-preview',
      {headers:{Authorization:'Bearer test'}},
    );
    expect(result).toEqual(preview());
    expect(result).not.toHaveProperty('ignored');
  });

  it('approves only the exact preview hash and never sends monetary values', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(receipt({idempotent:false})));

    const result = await actionsFor(fetchFn).approveProjectBudgetAdjustment(15, HASH);

    expect(fetchFn).toHaveBeenCalledTimes(1);
    expect(fetchFn).toHaveBeenCalledWith(
      'https://example.test/estimate-reconciliations/15/budget-adjustment-approval',
      {
        method:'POST',
        headers:{'Content-Type':'application/json', Authorization:'Bearer test'},
        body:JSON.stringify({planSha256:HASH}),
      },
    );
    expect(result).toEqual(receipt({idempotent:false}));
  });

  it('rejects malformed server money before it reaches the UI', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(preview({projectBudgetAfter:'NaN'})));

    await expect(actionsFor(fetchFn).loadBudgetAdjustmentPreview(15)).rejects.toEqual(
      expect.objectContaining({
        name:'BudgetAdjustmentClientError',
        code:'budget_adjustment_response_invalid',
      }),
    );
  });

  it('rejects an approval receipt without explicit idempotency evidence', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(receipt()));

    await expect(actionsFor(fetchFn).approveProjectBudgetAdjustment(15, HASH)).rejects.toEqual(
      expect.objectContaining({code:'budget_adjustment_response_invalid'}),
    );
  });

  it('loads bounded newest-first history with a positive cursor', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse({
      projectId:14,
      items:[receipt()],
      nextBeforeId:9,
    }));

    const result = await actionsFor(fetchFn).loadProjectBudgetAdjustments(14, {limit:25, beforeId:10});

    expect(fetchFn).toHaveBeenCalledWith(
      'https://example.test/projects/14/budget-adjustments?limit=25&beforeId=10',
      {headers:{Authorization:'Bearer test'}},
    );
    expect(result).toEqual({projectId:14, items:[receipt()], nextBeforeId:9});
  });

  it('uses fixed public messages instead of an arbitrary server detail', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(
      {detail:'<img src=x onerror=alert(1)>'},
      {ok:false, status:500},
    ));

    let failure;
    try {
      await actionsFor(fetchFn).loadBudgetAdjustmentPreview(15);
    } catch (error) {
      failure = error;
    }

    expect(failure).toBeInstanceOf(BudgetAdjustmentClientError);
    expect(failure.code).toBe('budget_adjustment_request_failed');
    expect(budgetAdjustmentErrorMessage(failure)).toBe('Не удалось выполнить операцию с бюджетом. Повторите попытку.');
    expect(budgetAdjustmentErrorMessage(failure)).not.toContain('img');
  });

  it('maps a stale approval to an explicit refresh instruction', async () => {
    const fetchFn = jest.fn().mockResolvedValue(jsonResponse(
      {detail:'budget_adjustment_plan_stale'},
      {ok:false, status:409},
    ));

    await expect(actionsFor(fetchFn).approveProjectBudgetAdjustment(15, HASH)).rejects.toEqual(
      expect.objectContaining({code:'budget_adjustment_plan_stale', status:409}),
    );
    expect(budgetAdjustmentErrorMessage(new BudgetAdjustmentClientError(
      'budget_adjustment_plan_stale',
      409,
    ))).toBe('Расчёт устарел. Обновите предварительный расчёт и подтвердите его заново.');
  });
});
