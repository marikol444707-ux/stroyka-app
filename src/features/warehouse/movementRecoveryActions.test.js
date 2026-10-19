import {createWarehouseCrudActions} from './warehouseCrudActions';
const scope = {key:'12:2', actorUserId:12, companyId:2};
const form = () => ({fromLocation:'Основной склад',toLocation:'Объект',notes:'',selectedMaterials:[{name:'Кабель',quantity:2,unit:'м'},{name:'Краска',quantity:3,unit:'л'}]});
const props = overrides => ({API:'/api',user:{id:12,name:'Директор'},movementScope:scope,isMovementScopeCurrent:()=>true,newMovement:form(),setNewMovement:jest.fn(),refreshData:jest.fn(),notify:jest.fn(),...overrides});
const response = data => ({ok:true,json:async()=>data});
let draft, ledger, lost, failSecond;
const envelope = () => ({...scope,draftId:draft.draftId,complete:draft.commands.every(c=>ledger.has(c.commandId)),commands:draft.commands.map(command=>({command,status:ledger.has(command.commandId)?'committed':'pending',response:ledger.get(command.commandId)||null}))});
beforeEach(()=>{
  global.alert=jest.fn(); global.crypto=require('crypto').webcrypto;
  draft=null; ledger=new Map(); lost=false; failSecond=false;
  global.fetch=jest.fn(async(url,options)=>{
    expect(options.headers['X-Company-Id']).toBe('2');
    expect(options.headers['X-Company-Mode']).toBe('company');
    if(options.method==='GET') return response({...scope,drafts:draft?[envelope()]:[]});
    const body=JSON.parse(options.body);
    expect(body.expectedActorUserId).toBe(12);
    if(url.endsWith('/warehouse-movement-drafts')) { draft ||= body; return response(envelope()); }
    if(failSecond && ledger.size===1) return {ok:false,json:async()=>({detail:'Недостаточный остаток'})};
    if(!ledger.has(body.commandId)) ledger.set(body.commandId,{id:ledger.size+1,documentSnapshot:{document:{number:'М11'}}});
    if(lost) {lost=false; throw new Error('Lost committed response');}
    return response(ledger.get(body.commandId));
  });
});
test('prepares durable draft before stock; explicit identity and stable command envelopes',async()=>{
  const result=await createWarehouseCrudActions(props()).applyWarehouseMovement();
  expect(result.success).toBe(true); expect(result.movements).toHaveLength(2);
  expect(fetch.mock.calls.map(([url])=>url.split('?')[0])).toEqual(['/api/warehouse-movement-drafts','/api/warehouse-movement-drafts','/api/warehouse-movements','/api/warehouse-movements']);
  expect(ledger.size).toBe(2);
});
test('reload after lost committed response reconciles and skips committed command',async()=>{
  lost=true;
  expect((await createWarehouseCrudActions(props()).applyWarehouseMovement()).success).toBe(false);
  expect(ledger.size).toBe(1);
  const saved=envelope();
  fetch.mockClear();
  const result=await createWarehouseCrudActions(props({newMovement:form()})).applyWarehouseMovement(saved);
  expect(result.success).toBe(true); expect(ledger.size).toBe(2);
  expect(fetch.mock.calls.filter(([url])=>url.endsWith('/warehouse-movements'))).toHaveLength(1);
});
test('partial business failure preserves durable batch and blocks unrelated new draft',async()=>{
  failSecond=true;
  expect((await createWarehouseCrudActions(props()).applyWarehouseMovement()).success).toBe(false);
  expect(ledger.size).toBe(1);
  fetch.mockClear();
  expect((await createWarehouseCrudActions(props()).applyWarehouseMovement()).success).toBe(false);
  expect(fetch).toHaveBeenCalledTimes(1);
  failSecond=false;
  expect((await createWarehouseCrudActions(props()).applyWarehouseMovement(envelope())).success).toBe(true);
  expect(ledger.size).toBe(2);
});
test('account switch during GET causes no prepare or stock request',async()=>{
  let current=true;
  fetch.mockImplementationOnce(async()=>{current=false;return response({...scope,drafts:[]});});
  expect((await createWarehouseCrudActions(props({isMovementScopeCurrent:()=>current})).applyWarehouseMovement()).success).toBe(false);
  expect(fetch).toHaveBeenCalledTimes(1);expect(alert).not.toHaveBeenCalled();
});
test('scope switch during postcommit refresh never returns snapshots or notifies',async()=>{
  let current=true;const notify=jest.fn();
  const result=await createWarehouseCrudActions(props({isMovementScopeCurrent:()=>current,refreshData:async()=>{current=false;},notify})).applyWarehouseMovement();
  expect(result).toEqual({success:false});expect(notify).not.toHaveBeenCalled();expect(ledger.size).toBe(2);
});
test('server scope mismatch fails closed before prepare',async()=>{
  fetch.mockImplementationOnce(async()=>response({...scope,companyId:3,drafts:[]}));
  expect((await createWarehouseCrudActions(props()).applyWarehouseMovement()).success).toBe(false);
  expect(fetch).toHaveBeenCalledTimes(1);
});
test('same-render duplicate submission launches one batch',async()=>{
  const actions=createWarehouseCrudActions(props());
  const [first,second]=await Promise.all([actions.applyWarehouseMovement(),actions.applyWarehouseMovement()]);
  expect(first.success).toBe(true);expect(second.success).toBe(false);expect(ledger.size).toBe(2);
});
test('recovered cross-company draft is never posted',async()=>{
  expect((await createWarehouseCrudActions(props()).applyWarehouseMovement({...scope,companyId:9,commands:[]})).success).toBe(false);
  expect(fetch).toHaveBeenCalledTimes(1);
});
