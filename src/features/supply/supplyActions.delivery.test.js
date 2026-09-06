import { createSupplyActions } from './supplyActions';

const response = body => ({ ok: true, status: 200, json: async () => body });
const context = (overrides = {}) => ({
  API: '/api',
  companyContext: { mode: 'company', selectedCompanyId: 4 },
  user: { id: 7, name: 'Директор', role: 'директор' },
  showRequestKpModal: 31,
  selectedSupplierIds: [51, 52],
  notify: jest.fn(),
  refreshData: jest.fn().mockResolvedValue(),
  setShowRequestKpModal: jest.fn(),
  setSelectedSupplierIds: jest.fn(),
  setSuggestedSuppliers: jest.fn(),
  getProjectWorkPackageOptions: () => [],
  newRequest: {
    project: 'Лицей', items: [{ materialName: 'Труба', quantity: 10 }],
    selectedSuppliers: [51, 52],
  },
  setNewRequest: jest.fn(),
  setShowForm: jest.fn(),
  ...overrides,
});

describe('supplier notification evidence', () => {
  const originalFetch = global.fetch;
  beforeEach(() => { global.fetch = jest.fn(); });
  afterEach(() => { global.fetch = originalFetch; });

  it('reports created requests separately from SMTP failures and unlinked MAX', async () => {
    global.fetch.mockResolvedValue(response({
      ok: true, created: 2,
      notifications: [
        { supplierId: 51, emailStatus: 'Отправлено', maxStatus: 'В очереди MAX' },
        { supplierId: 52, emailStatus: 'Ошибка отправки', maxStatus: 'MAX не привязан' },
      ],
    }));
    const deps = context();
    await createSupplyActions(deps).sendKpRequest();
    const text = deps.notify.mock.calls[0][0];
    expect(text).toContain('Создано запросов КП: 2');
    expect(text).toContain('Передано SMTP: 1');
    expect(text).toContain('Ошибка отправки: 1');
    expect(text).toContain('В очереди MAX: 1');
    expect(text).toContain('MAX не привязан: 1');
    expect(text).toContain('Доставка и прочтение не подтверждены');
    expect(text).not.toContain('Отправлен запрос КП 2 поставщикам');
  });

  it('does not replace zero created requests with the number of selected suppliers', async () => {
    global.fetch.mockResolvedValue(response({ ok: true, created: 0, notifications: [] }));
    const deps = context();
    await createSupplyActions(deps).sendKpRequest();
    expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('Создано запросов КП: 0'), 'supply');
    expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('Статусы уведомлений неизвестны'), 'supply');
  });

  it('does not dispatch a newly created request before both approvals', async () => {
    global.fetch.mockResolvedValue(response({ id: 31, status: 'Новая' }));
    const deps = context();
    await createSupplyActions(deps).saveRequest();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('ожидает подтверждения прораба и утверждения директора'), 'supply');
  });

  it('does not duplicate dispatch when creation already returns notification evidence', async () => {
    global.fetch.mockResolvedValue(response({
      id: 31, status: 'КП запрошены',
      notifications: [{ supplierId: 51, emailStatus: 'SMTP не настроен', maxStatus: 'MAX не привязан' }],
    }));
    const deps = context();
    await createSupplyActions(deps).saveRequest();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('SMTP не настроен: 1'), 'supply');
  });

  it('retains fallback dispatch only when both approval timestamps are present', async () => {
    global.fetch
      .mockResolvedValueOnce(response({
        id: 31, status: 'Утверждена',
        prorabConfirmedAt: '2026-09-06T10:00:00Z', directorApprovedAt: '2026-09-06T11:00:00Z',
      }))
      .mockResolvedValueOnce(response({ ok: true, created: 2, notifications: [] }));
    const deps = context();
    await createSupplyActions(deps).saveRequest();
    expect(global.fetch).toHaveBeenCalledTimes(2);
    expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('Создано запросов КП: 2'), 'supply');
  });

  it.each([
    { directorApprovedAt: '2026-09-06T11:00:00Z' },
    { prorabConfirmedAt: '2026-09-06T10:00:00Z' },
    {},
  ])('does not treat the legacy approved status alone as evidence of both approvals: %j', async approvals => {
    global.fetch.mockResolvedValue(response({ id: 31, status: 'Утверждена', ...approvals }));
    const deps = context();
    await createSupplyActions(deps).saveRequest();
    expect(global.fetch).toHaveBeenCalledTimes(1);
    expect(deps.notify).toHaveBeenCalledWith(expect.stringContaining('ожидает'), 'supply');
  });
});
