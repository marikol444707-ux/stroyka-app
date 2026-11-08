import {createWorkJournalActions} from './workJournalActions';

test.each([false, true])('confirmation respects evaluated finance capability: %s', async canEditMoney => {
  const originalFetch = global.fetch;
  global.fetch = jest.fn(async () => ({ok: true}));
  const role = jest.fn(() => canEditMoney);
  const actions = createWorkJournalActions({API:'/api', user:{name:'Прораб'}, isFinanceRole:role,
    toNum:Number, refreshData:jest.fn(), updateProjectProgress:jest.fn(),
    setConfirmingEntry:jest.fn(),setConfirmAcceptedQty:jest.fn(),setConfirmComment:jest.fn(),
    notify:jest.fn(),addActivity:jest.fn()});
  try {
    await actions.confirmJ({id:1,quantity:3,executionPricePerUnit:50,customerPricePerUnit:100},3,'');
    const body=JSON.parse(fetch.mock.calls[0][1].body);
    expect(body).toMatchObject({status:'Подтверждено',quantity:3});
    expect(Object.hasOwn(body,'executionTotal')).toBe(canEditMoney);
    expect(role).toHaveBeenCalled();
  } finally {global.fetch=originalFetch;}
});
