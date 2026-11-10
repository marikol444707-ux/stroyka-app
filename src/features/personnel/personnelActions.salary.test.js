import { createPersonnelActions } from './personnelActions';


describe('salary payment ownership payload', () => {
  beforeEach(() => {
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({ok: true})
      .mockResolvedValueOnce({ok:true,json: async () => []});
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
      {id: 5, name: 'Клиентское имя', net: 1000, expectedToolState:'verified', toolHold:0},
      '2026-07',
    );

    const [, request] = global.fetch.mock.calls[0];
    const body = JSON.parse(request.body);
    expect(body).toEqual({staffId: 5, month: '2026-07', amount: 1000, expectedToolState:'verified', toolDeductionAmount:0});
    expect(body).not.toHaveProperty('staffName');
    expect(body).not.toHaveProperty('paidBy');
    expect(body).not.toHaveProperty('paidDate');
    expect(request.body).not.toContain('Клиентская подмена');
  });
});

const salaryActions = setter => createPersonnelActions({API:'',ROLE_LABELS:{},setSalaryPayments:setter});
const salaryRow = {id:5,name:'Мастер',net:7700,toolHold:1000,expectedToolState:'revision',companyId:4};
test.each([409,500])('salary rejection %s does not refresh or report success', async status => {
  global.confirm=jest.fn(()=>true);global.alert=jest.fn();
  global.fetch=jest.fn().mockResolvedValue({ok:false,status,json:async()=>({detail:'Выплата не записана'})});
  const setter=jest.fn();expect(await salaryActions(setter).paySalary(salaryRow,'2026-07')).toBe(false);
  expect(setter).not.toHaveBeenCalled();expect(fetch).toHaveBeenCalledTimes(1);
  expect(alert).toHaveBeenCalledWith('Выплата не записана');
});
test('lost salary response has no automatic retry or success notification',async()=>{
  global.confirm=jest.fn(()=>true);global.alert=jest.fn();global.fetch=jest.fn().mockRejectedValue(Error('offline'));
  const setter=jest.fn();expect(await salaryActions(setter).paySalary(salaryRow,'2026-07')).toBe(false);
  expect(fetch).toHaveBeenCalledTimes(1);expect(setter).not.toHaveBeenCalled();expect(alert).toHaveBeenCalledWith(expect.stringContaining('Ответ о выплате не получен'));
});
