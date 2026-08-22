import { createPersonnelActions } from './personnelActions';


describe('salary payment ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({ok: true})
      .mockResolvedValueOnce({json: async () => []});
    global.alert = jest.fn();
    global.confirm = jest.fn(() => true);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('submits only the stored staff ID and canonical payment facts', async () => {
    const noop = jest.fn();
    const actions = createPersonnelActions({
      API: '',
      ROLE_LABELS: {},
      contracts: [],
      interimActs: [],
      masterRatings: {},
      masterProfiles: [],
      projects: [],
      staff: [],
      users: [],
      workJournal: [],
      user: {name: 'Клиентская подмена'},
      setSalaryPayments: noop,
      setMasterRatings: noop,
    });

    await actions.paySalary(
      {id: 5, name: 'Клиентское имя', net: 1000},
      '2026-07',
    );

    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual({staffId: 5, month: '2026-07', amount: 1000});
    expect(body).not.toHaveProperty('staffName');
    expect(body).not.toHaveProperty('paidBy');
    expect(body).not.toHaveProperty('paidDate');
    expect(request.body).not.toContain('Клиентская подмена');
  });
});
