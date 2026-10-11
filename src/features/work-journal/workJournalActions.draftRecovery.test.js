import {createWorkJournalActions} from './workJournalActions';
import {pendingWorkBatch, resumeWorkBatch, clearWorkBatch} from '../work-material-accounting/workCommands';
import {clearSubmittedDrafts} from '../work-material-accounting/workDrafts';

const scope = {companyId: 2, userId: 11};
const key = '7:0:0';
const material = {name: 'Краска', quantity: 2, unit: 'кг', warehouseQuantity: 2, warehouseMaterialId: 8};

function fixture() {
  const state = {
    estimateDoneDrafts: {[key]: '1'}, estimateWorkMaterials: {[key]: [material]},
    estimateWorkParams: {[key]: {roomName: 'Кабинет 1', comment: 'Первый слой'}},
  };
  const bindings = {estimateDraftValueRef: {current: {[key]: '1'}}};
  for (const name of Object.keys(state)) {
    bindings['set' + name[0].toUpperCase() + name.slice(1)] = update => { state[name] = update(state[name]); };
  }
  const item = {id: 'work-1', estimateItemKey: 'work-1', name: 'Покраска', quantity: 10, doneQuantity: 0,
    unit: 'м²', estId: 7, sectionIdx: 0, itemIdx: 0, contractItemId: 5, executionPricePerUnit: 10};
  const refreshData = jest.fn();
  const actions = createWorkJournalActions({
    API: '', companyContext: {selectedCompanyId: 2}, user: {id: 11},
    ...state, ...bindings, masterProjectId: '3', projects: [{id: 3, name: 'Лицей'}],
    estimatesList: [{id: 7, sections: [{items: [item]}]}], rooms: [],
    denormalizeMeasure: Number, toNum: Number, fmtMeasure: String,
    estimateWorkKey: () => key, estimatePackage: () => 'Основная',
    isPersonalMaterialRole: () => true, autoFillNormMaterialsForWork: () => [material],
    materialWriteoffBlockMessage: () => '', materialNormOverrunReason: () => '',
    applyMaterialOverNormReason: (_project, rows) => rows, prepareWorkMaterialGroups: () => [[material]],
    setEstimatesList: jest.fn(), refreshData, notify: jest.fn(),
  });
  return {state, bindings, refreshData, submit: () => actions.submitEstimateWorkDone(item, 1, bindings.estimateDraftValueRef)};
}

describe('estimate work form survives failed sending', () => {
  const originalFlag = process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
  const originalFetch = window.fetch;
  const originalCrypto = window.crypto;
  beforeAll(() => { Object.defineProperty(window, 'crypto', {configurable: true, value: require('crypto').webcrypto}); });
  beforeEach(() => {
    process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = '1';
    sessionStorage.clear();
    jest.spyOn(window, 'alert').mockImplementation(() => {});
    jest.spyOn(window, 'confirm').mockReturnValue(true);
  });
  afterEach(() => { jest.restoreAllMocks(); window.fetch = originalFetch; sessionStorage.clear(); });
  afterAll(() => {
    Object.defineProperty(window, 'crypto', {configurable: true, value: originalCrypto});
    if (originalFlag === undefined) delete process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED;
    else process.env.REACT_APP_WORK_MATERIAL_ACCOUNTING_ENABLED = originalFlag;
  });

  it.each(['offline', 'rejected'])('preserves quantity, materials and room after %s', async failure => {
    const f = fixture();
    const before = JSON.parse(JSON.stringify(f.state));
    window.fetch = jest.fn(async () => {
      if (failure === 'offline') throw new Error('offline');
      return {ok: false, status: 409, json: async () => ({detail: 'Недостаточно материала'})};
    });
    await f.submit();
    expect(f.state).toEqual(before);
    expect(f.bindings.estimateDraftValueRef.current).toEqual(before.estimateDoneDrafts);
    expect(f.refreshData).not.toHaveBeenCalled();
    expect(Boolean(pendingWorkBatch(scope))).toBe(failure === 'offline');
  });

  it('replays the saved payload after lost reply and only then clears submitted fields', async () => {
    const f = fixture();
    window.fetch = jest.fn().mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce({ok: true, json: async () => ({ok: true})});
    await f.submit();
    const savedBody = window.fetch.mock.calls[0][1].body;
    const completed = await resumeWorkBatch({API: '', scope});
    expect(window.fetch.mock.calls[1][1].body).toBe(savedBody);
    clearSubmittedDrafts(completed, f.bindings);
    clearWorkBatch(scope);
    expect(f.state).toEqual({estimateDoneDrafts: {}, estimateWorkMaterials: {}, estimateWorkParams: {}});
    expect(f.bindings.estimateDraftValueRef.current).toEqual({});
    expect(pendingWorkBatch(scope)).toBeNull();
  });

  it('keeps edits made while waiting for a successful server reply', async () => {
    const f = fixture();
    let resolve;
    window.fetch = jest.fn(() => new Promise(done => { resolve = done; }));
    const sending = f.submit();
    f.state.estimateDoneDrafts[key] = '3';
    f.bindings.estimateDraftValueRef.current[key] = '3';
    f.state.estimateWorkMaterials[key] = [{...material, quantity: 4}];
    f.state.estimateWorkParams[key] = {roomName: 'Кабинет 2'};
    resolve({ok: true, json: async () => ({ok: true})});
    await sending;
    expect(f.state.estimateDoneDrafts[key]).toBe('3');
    expect(f.state.estimateWorkMaterials[key][0].quantity).toBe(4);
    expect(f.state.estimateWorkParams[key]).toEqual({roomName: 'Кабинет 2'});
    expect(f.bindings.estimateDraftValueRef.current[key]).toBe('3');
  });
});
