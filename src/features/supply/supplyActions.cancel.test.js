import { createSupplyActions } from './supplyActions';
const setup = (changes={}) => ({API:'/api', user:{id:7}, companyContext:{mode:'company',selectedCompanyId:2},
  requestCancellationRef:{current:null},refreshData:jest.fn().mockResolvedValue(),...changes});
const reply = (ok=true,body={id:11,status:'Отменена'}) => ({ok,json:async()=>body});
const originalFetch = global.fetch;
let alert;
beforeEach(()=>{alert=jest.spyOn(window,'alert').mockImplementation(()=>{});});
afterEach(()=>{global.fetch=originalFetch;alert.mockRestore();});
test('sends the supported cancel command and refreshes only acknowledged request',async()=>{
  global.fetch=jest.fn().mockResolvedValue(reply());const deps=setup();
  expect(await createSupplyActions(deps).cancelRequest(11)).toBe(true);
  expect(global.fetch).toHaveBeenCalledWith('/api/supply-requests/11',expect.objectContaining({
    body:JSON.stringify({action:'cancel',companyId:2}),headers:{'Content-Type':'application/json','X-Company-Id':'2','X-Company-Mode':'company'}}));
  expect(deps.refreshData).toHaveBeenCalledTimes(1);expect(alert).not.toHaveBeenCalled();
});
test.each([reply(false,{detail:'Не разрешено'}),reply(true,{id:12,status:'Отменена'}),reply(true,{id:11,status:'Новая'}),reply(true,{})])('rejects error or unconfirmed response',async response=>{
  global.fetch=jest.fn().mockResolvedValue(response);const deps=setup();
  expect(await createSupplyActions(deps).cancelRequest(11)).toBe(false);
  expect(deps.refreshData).not.toHaveBeenCalled();expect(alert).toHaveBeenCalled();
});
test('network failure allows retry but does not report cancellation',async()=>{
  global.fetch=jest.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValue(reply());const deps=setup(),actions=createSupplyActions(deps);
  expect(await actions.cancelRequest(11)).toBe(false);expect(deps.refreshData).not.toHaveBeenCalled();
  expect(await actions.cancelRequest(11)).toBe(true);expect(deps.refreshData).toHaveBeenCalledTimes(1);
});
test('refresh failure distinguishes already saved cancellation',async()=>{
  global.fetch=jest.fn().mockResolvedValue(reply());const deps=setup({refreshData:jest.fn().mockRejectedValue(new Error('offline'))});
  await createSupplyActions(deps).cancelRequest(11);
  expect(alert).toHaveBeenCalledWith(expect.stringContaining('Заявка отменена, но список не обновился'));
  expect(global.fetch).toHaveBeenCalledTimes(1);
});
test('repeated click across rerender is single and late response cannot refresh another company',async()=>{
  let resolve;global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));const deps=setup();
  const first=createSupplyActions(deps).cancelRequest(11);
  expect(await createSupplyActions(deps).cancelRequest(11)).toBe(false);
  createSupplyActions({...deps,companyContext:{mode:'company',selectedCompanyId:3}});
  resolve(reply());await first;
  expect(global.fetch).toHaveBeenCalledTimes(1);expect(deps.refreshData).not.toHaveBeenCalled();
});
