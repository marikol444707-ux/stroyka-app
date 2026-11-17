import {executeManualCommand,finishManualCommand,manualCommandScope,prepareManualCommand,readManualCommand} from './manualCommandRecovery';

jest.mock('../../utils/commandUuid',()=>({commandUuid:()=> '619c59a4-88af-4c11-9e58-765f2b232680'}));
const scope=manualCommandScope({mode:'company',selectedCompanyId:4},{id:9},'contract',{id:17});
const payload={projectId:17,brigadeName:'Бригада Север',contractorId:null};
const receipt={ok:true,id:70,companyId:4,projectId:17,manualRequestId:'619c59a4-88af-4c11-9e58-765f2b232680'};
const options=extra=>({API:'/api',scope,...extra});
beforeEach(()=>sessionStorage.clear());

test('a reloaded reader retains exact body and scope and cannot replace it with a new draft',()=>{
  const saved=prepareManualCommand(scope,payload);
  expect(readManualCommand(scope)).toEqual(saved);
  expect(()=>prepareManualCommand(scope,{...payload,brigadeName:'Другая бригада'})).toThrow('Сначала завершите');
  expect(readManualCommand(scope).body).toBe(saved.body);
  expect(readManualCommand({...scope,userId:10})).toBeNull();
  expect(readManualCommand({...scope,companyId:5})).toBeNull();
  expect(readManualCommand({...scope,sourceId:18})).toBeNull();
});

test('network loss preserves the exact request and retry pins the company and actor',async()=>{
  const saved=prepareManualCommand(scope,payload);
  await expect(executeManualCommand(options({fetchFn:jest.fn().mockRejectedValue(new Error('network'))}))).rejects.toThrow();
  const fetchFn=jest.fn().mockResolvedValue({ok:true,json:async()=>receipt});
  await executeManualCommand(options({fetchFn}));
  expect(fetchFn.mock.calls[0]).toEqual(['/api/brigade-contracts',expect.objectContaining({body:saved.body,
    headers:expect.objectContaining({'X-Company-Id':'4','X-Company-Mode':'company'})})]);
  expect(JSON.parse(saved.body)).toMatchObject({expectedCompanyId:4,expectedActorId:9});
});

test('confirmed result survives a failed UI refresh and needs no second POST',async()=>{
  prepareManualCommand(scope,payload);
  await executeManualCommand(options({fetchFn:jest.fn().mockResolvedValue({ok:true,json:async()=>receipt})}));
  const fetchFn=jest.fn();
  const command=await executeManualCommand(options({fetchFn}));
  expect(fetchFn).not.toHaveBeenCalled();
  expect(command.receipt).toEqual(receipt);
  finishManualCommand(scope,command.body);
  expect(readManualCommand(scope)).toBeNull();
});

test.each([401,403,409,500])('HTTP %s after an uncertain attempt never discards the request',async status=>{
  prepareManualCommand(scope,payload);
  await expect(executeManualCommand(options({fetchFn:jest.fn().mockRejectedValue(new Error('network'))}))).rejects.toThrow();
  await expect(executeManualCommand(options({fetchFn:jest.fn().mockResolvedValue({ok:false,status,json:async()=>({detail:'Отказ'})})}))).rejects.toThrow('Отказ');
  expect(readManualCommand(scope).receipt).toBeNull();
});

test('an initial validation rejection permits correction but the same error after uncertainty does not',async()=>{
  const rejected=jest.fn().mockResolvedValue({ok:false,status:400,json:async()=>({detail:'Исправьте данные'})});
  prepareManualCommand(scope,payload);
  await expect(executeManualCommand(options({fetchFn:rejected}))).rejects.toThrow('Исправьте');
  expect(readManualCommand(scope)).toBeNull();
  prepareManualCommand(scope,payload);
  await expect(executeManualCommand(options({fetchFn:jest.fn().mockRejectedValue(new Error('network'))}))).rejects.toThrow();
  await expect(executeManualCommand(options({fetchFn:rejected}))).rejects.toThrow();
  expect(readManualCommand(scope)).not.toBeNull();
});

test.each([{companyId:5},{projectId:18},{manualRequestId:'another'},{ok:false}])('unknown or mismatched success is retained: %j',async change=>{
  prepareManualCommand(scope,payload);
  await expect(executeManualCommand(options({fetchFn:jest.fn().mockResolvedValue({ok:true,json:async()=>({...receipt,...change})})}))).rejects.toThrow('не подтвердил');
  expect(readManualCommand(scope).receipt).toBeNull();
});

test('storage damage blocks dispatch and storage failure blocks preparation',async()=>{
  prepareManualCommand(scope,payload);
  const key=sessionStorage.key(0);
  sessionStorage.setItem(key,'damaged');
  const fetchFn=jest.fn();
  await expect(executeManualCommand(options({fetchFn}))).rejects.toThrow('повреждена');
  expect(fetchFn).not.toHaveBeenCalled();
  sessionStorage.clear();
  const failure=jest.spyOn(Storage.prototype,'setItem').mockImplementation(()=>{throw new Error('quota');});
  try{expect(()=>prepareManualCommand(scope,payload)).toThrow();}finally{failure.mockRestore();}
});

test('scope requires the current company, real user and matching source owner',()=>{
  expect(manualCommandScope({mode:'all_companies'}, {id:9},'contract',{id:17})).toBeNull();
  expect(manualCommandScope({mode:'company',selectedCompanyId:4},null,'contract',{id:17})).toBeNull();
  expect(manualCommandScope({mode:'company',selectedCompanyId:4},{id:9},'contract',{id:17,companyId:5})).toBeNull();
});
