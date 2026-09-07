import { createPersonnelActions } from './personnelActions';

describe('current account staff linkage', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('links the current account, refreshes personnel and reports success', async () => {
    const refreshData = jest.fn().mockResolvedValue(undefined);
    const notify = jest.fn();
    const readApiResult = jest.fn().mockResolvedValue({
      ok: true,
      created: true,
      staffId: 12,
    });
    global.fetch = jest.fn().mockResolvedValue({ ok: true });
    const actions = createPersonnelActions({
      API: '/api',
      ROLE_LABELS: {},
      contracts: [],
      interimActs: [],
      masterProfiles: [],
      masterRatings: {},
      projects: [],
      staff: [],
      users: [],
      workJournal: [],
      readApiResult,
      refreshData,
      notify,
    });

    const result = await actions.linkCurrentUserToStaff();

    expect(global.fetch).toHaveBeenCalledWith(
      '/api/staff/current-user-link',
      { method: 'POST' },
    );
    expect(readApiResult).toHaveBeenCalled();
    expect(refreshData).toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith(
      'Основной аккаунт добавлен в персонал',
      'staff',
    );
    expect(result.staffId).toBe(12);
  });
});
