import { createUserAccessActions } from './userAccessActions';
const setup=overrides=>({API:'/api',companyContext:{mode:'company',selectedCompanyId:7},user:{id:1},newUser:{name:'Person',email:'p@example.test',password:'test-password',role:'бухгалтер'},suppliers:[],refreshData:jest.fn(),setNewUser:jest.fn(),setEditingItem:jest.fn(),setShowForm:jest.fn(),...overrides});
beforeEach(()=>{window.confirm=jest.fn(()=>true);window.alert=jest.fn();});
test('access commands carry selected company and do not refresh after rejected write',async()=>{
 const props=setup();global.fetch=jest.fn(async()=>({ok:false,status:403,json:async()=>({detail:'Нет доступа'})}));
 await createUserAccessActions(props).toggleUserActive({id:9},false);
 expect(fetch.mock.calls[0][1].headers).toMatchObject({'X-Company-Id':'7','X-Company-Mode':'company'});
 expect(props.refreshData).not.toHaveBeenCalled();expect(alert).toHaveBeenCalledWith('Нет доступа');
});
test('successful user creation is company scoped',async()=>{
 const props=setup();global.fetch=jest.fn(async()=>({ok:true,json:async()=>({id:8})}));
 await createUserAccessActions(props).saveUser();
 expect(fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('7');
 expect(props.refreshData).toHaveBeenCalledTimes(1);
});
test('all-company mode cannot mutate an implicit default company',async()=>{
 const props=setup({companyContext:{mode:'all_companies'}});global.fetch=jest.fn();
 await createUserAccessActions(props).saveUser();
 expect(fetch).not.toHaveBeenCalled();expect(alert).toHaveBeenCalled();
});
