import { createProjectCrudActions } from './projectCrudActions';

beforeEach(() => {
  Object.defineProperty(global, 'crypto', {configurable:true, value:{randomUUID:()=> '11111111-1111-4111-8111-111111111111'}});
  global.alert=jest.fn();
});

test('project creation does not create a second account or submit old password fields', async () => {
  const props = {
    API:'/api',newProject:{name:'Object',budget:0,clientEmail:'old@example.test',clientPassword:'old-secret'},
    readApiResult:async response=>response.json(),notify:jest.fn(),refreshData:jest.fn(),addActivity:jest.fn(),
    setNewProject:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn(),
  };
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({id:1,companyId:7,name:'Object'})}));
  await createProjectCrudActions(props).saveProject();
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][0]).toBe('/api/projects');
  const body=JSON.parse(fetch.mock.calls[0][1].body);
  expect(body.clientEmail).toBeUndefined();expect(body.clientPassword).toBeUndefined();
  expect(props.setShowForm).toHaveBeenCalledWith(false);
});

test('project creation sends exact selected customer id', async () => {
  const props = {
    API:'/api',newProject:{name:'Object',budget:0,clientId:12,client:'Displayed name'},
    readApiResult:async response=>response.json(),notify:jest.fn(),refreshData:jest.fn(),addActivity:jest.fn(),
    setNewProject:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn(),
  };
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({id:1,companyId:7,name:'Object'})}));
  await createProjectCrudActions(props).saveProject();
  const body=JSON.parse(fetch.mock.calls[0][1].body);
  expect(body.clientId).toBe(12);
});

test('customer update does not submit server ownership fields', async () => {
  const props={
    API:'/api',editingItem:{id:12},newClient:{id:12,companyId:3,name:'ООО Заказчик',status:'Активный'},
    readApiResult:async response=>response.json(),refreshData:jest.fn(),
    setNewClient:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn(),
  };
  global.fetch=jest.fn(async()=>({ok:true,json:async()=>({ok:true})}));
  await createProjectCrudActions(props).saveClient();
  const body=JSON.parse(fetch.mock.calls[0][1].body);
  expect(body.id).toBeUndefined();
  expect(body.companyId).toBeUndefined();
});

test('double save across action recreation uses one in-flight project command', async () => {
  let release;
  global.fetch=jest.fn(()=>new Promise(resolve=>{release=()=>resolve({ok:true,json:async()=>({id:1})});}));
  const props={API:'/api',projectSaveRef:{current:false},newProject:{name:'Учебный объект',budget:0},
    readApiResult:async response=>response.json(),notify:jest.fn(),refreshData:jest.fn(),addActivity:jest.fn(),
    setNewProject:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn()};
  const first=createProjectCrudActions(props).saveProject();
  await createProjectCrudActions(props).saveProject();
  expect(fetch).toHaveBeenCalledTimes(1);
  release();await first;
  expect(props.projectSaveRef.current).toBe(false);
});

test('retry after an unknown network outcome preserves creation command identity', async () => {
  const props={API:'/api',projectSaveRef:{current:false},projectCreateCommandRef:{current:null},newProject:{name:'Учебный объект',budget:0},
    readApiResult:async response=>response.json(),notify:jest.fn(),refreshData:jest.fn(),addActivity:jest.fn(),
    setNewProject:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn()};
  global.fetch=jest.fn().mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({ok:true,json:async()=>({id:1})});
  await createProjectCrudActions(props).saveProject();
  await createProjectCrudActions(props).saveProject();
  const payloads=fetch.mock.calls.map(call=>JSON.parse(call[1].body));
  expect(payloads[0].requestKey).toBe(payloads[1].requestKey);
  expect(props.projectCreateCommandRef.current).toBeNull();
});
