import { createSupplyActions } from './supplyActions';

describe('supplier selection', () => {
  const originalFetch = global.fetch;
  afterEach(() => { global.fetch = originalFetch; });

  const deps = () => ({ API: '/api', setShowRequestKpModal: jest.fn(),
    setSuggestedSuppliers: jest.fn(), setSelectedSupplierIds: jest.fn(),
    setRequestKpLoading: jest.fn() });

  it('leaves every recipient unselected even when an older API recommends one', async () => {
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({
      suppliers: [{ id: 2, aiRecommend: true, alreadyRequested: false }],
    }) });
    const state = deps();
    await createSupplyActions(state).openRequestKpModal(7);
    expect(state.setSelectedSupplierIds.mock.calls).toEqual([[[]]]);
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it.each([403, 409, 503])('shows a failed HTTP %s without candidates', async status => {
    global.fetch = jest.fn().mockResolvedValue({ ok: false, status,
      json: async () => ({ detail: 'Выбранная компания недоступна' }) });
    const state = deps();
    await createSupplyActions(state).openRequestKpModal(7);
    expect(state.setSuggestedSuppliers).toHaveBeenLastCalledWith({
      suppliers: [], error: 'Выбранная компания недоступна',
    });
    expect(state.setRequestKpLoading).toHaveBeenLastCalledWith(false);
  });
});
