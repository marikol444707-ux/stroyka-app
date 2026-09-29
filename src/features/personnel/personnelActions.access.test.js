import { createPersonnelActions } from './personnelActions';

const employeeUser = { id: 42, name: 'Иван', email: 'old@example.test', role: 'прораб' };
const staffRow = { id: 7, name: 'Иван', accessUserId: 42, email: 'old@example.test', project: 'Лицей' };

function setup(overrides = {}) {
  const deps = {
    API: '/api',
    ROLE_LABELS: { прораб: 'Прораб', субподрядчик: 'Субподрядчик', бухгалтер: 'Бухгалтер' },
    users: [employeeUser], projects: [{ id: 1, name: 'Лицей' }],
    editingItem: staffRow,
    newStaff: { ...staffRow, email: 'new@example.test', password: '', systemRole: 'бухгалтер' },
    readApiResult: async response => response.json(),
    refreshData: jest.fn().mockResolvedValue(undefined),
    setNewStaff: jest.fn(), setEditingItem: jest.fn(), setShowForm: jest.fn(),
    ...overrides,
  };
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 42 }) });
  return { actions: createPersonnelActions(deps), deps };
}

describe('personnel access keeps the linked account identity', () => {
  const originalFetch = global.fetch;
  beforeEach(() => {
    jest.spyOn(window, 'alert').mockImplementation(() => {});
    jest.spyOn(window, 'prompt').mockImplementation(() => null);
  });
  afterEach(() => {
    jest.restoreAllMocks();
    global.fetch = originalFetch;
  });

  it('saves a changed email and role without requiring a new password for linked staff', async () => {
    const { actions, deps } = setup();
    await actions.saveStaff();
    expect(fetch).toHaveBeenCalledWith('/api/staff/7', expect.objectContaining({ method: 'PUT' }));
    const body = JSON.parse(fetch.mock.calls[0][1].body);
    expect(body).toEqual(expect.objectContaining({ email: 'new@example.test', systemRole: 'бухгалтер' }));
    expect(deps.refreshData).toHaveBeenCalledTimes(1);
  });

  it('updates email, password and role on the linked user instead of creating another account', async () => {
    const { actions } = setup();
    window.prompt.mockReturnValueOnce('new@example.test').mockReturnValueOnce('new-password').mockReturnValueOnce('бухгалтер');
    await actions.createStaffAccessFromPrompt(staffRow);
    expect(fetch).toHaveBeenCalledWith('/api/users/42', expect.objectContaining({ method: 'PUT' }));
    expect(fetch.mock.calls.some(([url, options]) => url === '/api/users' && options.method === 'POST')).toBe(false);
    const body = JSON.parse(fetch.mock.calls.find(([url]) => url === '/api/users/42')[1].body);
    expect(body).toEqual(expect.objectContaining({ email: 'new@example.test', password: 'new-password', role: 'бухгалтер' }));
  });

  it('does not replace another user’s password or role when the requested email is occupied', async () => {
    const { actions, deps } = setup({ users: [employeeUser, { id: 99, email: 'other@example.test', role: 'директор' }] });
    window.prompt.mockReturnValueOnce('other@example.test').mockReturnValueOnce('new-password').mockReturnValueOnce('бухгалтер');
    await actions.createStaffAccessFromPrompt(staffRow);
    expect(fetch).not.toHaveBeenCalled();
    expect(deps.refreshData).not.toHaveBeenCalled();
    expect(window.alert).toHaveBeenCalled();
  });

  it('rejects an occupied email in the employee edit form before saving either record', async () => {
    const { actions, deps } = setup({
      users: [employeeUser, { id: 99, email: 'other@example.test', role: 'директор' }],
      newStaff: { ...staffRow, email: 'other@example.test', password: 'new-password', systemRole: 'бухгалтер' },
    });
    await actions.saveStaff();
    expect(fetch).not.toHaveBeenCalled();
    expect(deps.refreshData).not.toHaveBeenCalled();
    expect(window.alert).toHaveBeenCalled();
  });
});
