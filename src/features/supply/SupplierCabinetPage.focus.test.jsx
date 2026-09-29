import React from 'react';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import SupplierCabinetPage from './SupplierCabinetPage';
import useSupplierTeam from './useSupplierTeam';
const user={id:1,role:'поставщик',name:'Руководитель'};
const suppliers=[{id:7,userId:1,name:'Исходное название',role:'leader'}];
const profile={supplierId:7,fields:{name:'Исходное название',phone:'123'},version:'v1',canEdit:true,tariff:{status:'not_configured'}};
const details={members:[],customers:[],invites:[]};
const setRequisites=jest.fn();
function Cabinet({tab='profile'}) {
 const teamContext=useSupplierTeam('/api',user);
 return <SupplierCabinetPage API="/api" C={{}} user={user} suppliers={suppliers} teamContext={teamContext}
  supplierTab={tab} supplierRequisites={{}} setSupplierRequisites={setRequisites} inboxState={{status:'ready'}}/>;
}
const originalFetch=global.fetch;
afterEach(()=>{global.fetch=originalFetch;jest.restoreAllMocks();});
it('preserves a dirty profile through focus and updates header after save, then hides revoked profile',async()=>{
 let finish,role='leader';
 global.fetch=jest.fn(async(path,options)=>({ok:true,json:async()=>{
  if(path.endsWith('/requisites'))return options?.method==='PUT'?{...profile,fields:{...profile.fields,phone:'456',name:'Новое название'}}:profile;
  if(path.endsWith('/customers'))return [];
  return [{...suppliers[0],role}];
 }}));
 render(<Cabinet/>);
 fireEvent.change(await screen.findByLabelText('Телефон'),{target:{value:'456'}});
 global.fetch.mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
 act(()=>window.dispatchEvent(new Event('focus')));
 expect(screen.getByLabelText('Телефон')).toHaveValue('456');
 await act(async()=>finish({ok:true,json:async()=>suppliers}));
 expect(screen.getByLabelText('Телефон')).toHaveValue('456');
 fireEvent.change(screen.getByLabelText('Название компании'),{target:{value:'Новое название'}});
 fireEvent.click(screen.getByText('Сохранить реквизиты'));
 await screen.findByText('Реквизиты сохранены');
 expect(screen.getByText('Новое название',{selector:'p'})).toBeInTheDocument();
 role='manager';act(()=>window.dispatchEvent(new Event('focus')));
 await waitFor(()=>expect(screen.queryByLabelText('Телефон')).not.toBeInTheDocument());
});
it('retains invite retry UUID through a focus refresh after uncertain network result',async()=>{
 let attempts=0,uuid=0;
 Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:()=>`operation-${++uuid}`}});
 global.fetch=jest.fn(async(path,options)=>{
  if(options?.method==='POST'&&attempts++===0)throw new Error('Связь прервана');
  return {ok:true,json:async()=>options?.method==='POST'?{}:path.endsWith('/customers')?[]:path.endsWith('/7')?details:suppliers};
 });
 render(<Cabinet tab="team"/>);
 fireEvent.click(await screen.findByText('Создать приглашение менеджеру'));
 await screen.findByText('Связь прервана');
 await act(async()=>window.dispatchEvent(new Event('focus')));
 fireEvent.click(await screen.findByText('Создать приглашение менеджеру'));
 await screen.findByText('Изменения сохранены');
 const calls=global.fetch.mock.calls.filter(c=>c[1]?.method==='POST').map(c=>JSON.parse(c[1].body));
 expect(calls).toHaveLength(2);expect(calls[0].requestId).toEqual(calls[1].requestId);
});
