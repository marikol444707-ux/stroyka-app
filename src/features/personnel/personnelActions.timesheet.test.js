import { canEditTimesheet, createPersonnelActions } from './personnelActions';

describe('timesheet edits stay inside one company', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('does not edit the aggregate view or pretend the day changed', async () => {
    const notify = jest.fn();
    const setTimesheet = jest.fn();
    global.fetch = jest.fn();
    const actions = createPersonnelActions({
      API: '/api',
      ROLE_LABELS: {},
      companyContext: { mode: 'all_companies', selectedCompanyId: null },
      notify,
      setTimesheet,
    });

    await actions.toggleDay(5, '2026-07-01');

    expect(canEditTimesheet({ mode: 'all_companies' })).toBe(false);
    expect(fetch).not.toHaveBeenCalled();
    expect(setTimesheet).not.toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith('Чтобы отметить день, выберите одну компанию', 'staff');
  });

  it('keeps the previous mark when the server rejects the day', async () => {
    const notify = jest.fn();
    const setTimesheet = jest.fn();
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      text: async () => JSON.stringify({ detail: 'Сотрудник не найден в выбранной компании' }),
    });
    const actions = createPersonnelActions({
      API: '/api',
      ROLE_LABELS: {},
      companyContext: { mode: 'company', selectedCompanyId: 10 },
      notify,
      readApiResult: async (response) => {
        const data = JSON.parse(await response.text());
        if (!response.ok) throw new Error(data.detail);
        return data;
      },
      setTimesheet,
    });

    await actions.toggleDay(5, '2026-07-01');

    expect(fetch).toHaveBeenCalledWith('/api/timesheet', expect.objectContaining({ method: 'POST' }));
    expect(setTimesheet).not.toHaveBeenCalled();
    expect(notify).toHaveBeenCalledWith('Сотрудник не найден в выбранной компании', 'staff');
  });

  it('marks the day only after the selected company accepts it', async () => {
    const setTimesheet = jest.fn();
    global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    const actions = createPersonnelActions({
      API: '/api',
      ROLE_LABELS: {},
      companyContext: { mode: 'company', selectedCompanyId: 10 },
      readApiResult: async (response) => response.json(),
      setTimesheet,
    });

    await actions.toggleDay(5, '2026-07-01');

    expect(setTimesheet).toHaveBeenCalledTimes(1);
    const next = setTimesheet.mock.calls[0][0]({ '5-2026-07-01': false });
    expect(next['5-2026-07-01']).toBe(true);
  });
});
