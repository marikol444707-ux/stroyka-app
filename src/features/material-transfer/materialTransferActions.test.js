import { createMaterialTransferActions } from './materialTransferActions';
const setup = (changes = {}) => ({ API: '/api', user: {id: 7},
  companyContext: {mode: 'company', selectedCompanyId: 2}, receiptScopeRef: {current: null},
  setMaterialTransfers: jest.fn(), alertFn: jest.fn(), ...changes });
const response = (ok, body) => ({ok, json: async () => body});
const originalFetch = global.fetch;
afterEach(() => { global.fetch = originalFetch; });

test.each([response(false, {detail:'Передача аннулирована'}), response(false, {ok:true}), response(true, {})])('failed or unconfirmed response never signs locally', async reply => {
  global.fetch = jest.fn().mockResolvedValue(reply);
  const deps = setup();
  expect(await createMaterialTransferActions(deps).confirmMaterialReceipt(11)).toBe(false);
  expect(deps.setMaterialTransfers).not.toHaveBeenCalled();
  expect(deps.alertFn).toHaveBeenCalled();
});
test('network failure preserves state and allows retry of the same id', async () => {
  global.fetch = jest.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(response(true, {ok:true}));
  const deps = setup(), actions = createMaterialTransferActions(deps);
  await actions.confirmMaterialReceipt(11);
  expect(deps.setMaterialTransfers).not.toHaveBeenCalled();
  expect(await actions.confirmMaterialReceipt(11)).toBe(true);
  const update = deps.setMaterialTransfers.mock.calls[0][0];
  expect(update([{id:11,signed:false},{id:12,signed:false}])).toEqual([{id:11,signed:true},{id:12,signed:false}]);
  expect(global.fetch).toHaveBeenLastCalledWith('/api/material-transfers/11/sign', {method:'PUT',headers:{'X-Company-Id':'2','X-Company-Mode':'company'}});
});
test('pending command stays single across rerender and stale company response cannot update state', async () => {
  let resolve;
  global.fetch = jest.fn(() => new Promise(r => {resolve=r;}));
  const deps = setup();
  const first = createMaterialTransferActions(deps).confirmMaterialReceipt(11);
  expect(await createMaterialTransferActions(deps).confirmMaterialReceipt(11)).toBe(false);
  createMaterialTransferActions({...deps,companyContext:{mode:'company',selectedCompanyId:3}});
  resolve(response(true,{ok:true}));
  expect(await first).toBe(false);
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(deps.setMaterialTransfers).not.toHaveBeenCalled();
});
test('loading or aggregate company context cannot submit', async () => {
  global.fetch = jest.fn();
  for (const companyContext of [{mode:'all_companies'},{mode:'company',selectedCompanyId:2,loading:true}]) {
    expect(await createMaterialTransferActions(setup({companyContext})).confirmMaterialReceipt(11)).toBe(false);
  }
  expect(global.fetch).not.toHaveBeenCalled();
});
