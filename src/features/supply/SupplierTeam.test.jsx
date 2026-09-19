import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import SupplierTeam from './SupplierTeam';
const originalFetch=global.fetch;
const context={suppliers:[{id:7,name:'Поставщик',role:'leader'}]};
const data={members:[{id:8,name:'Иван',email:'manager@local.invalid',role:'manager',active:true,userActive:true,version:1}],customers:[{id:2,name:'Альфа',memberId:null,version:0},{id:3,name:'Бета',memberId:null,version:0}],invites:[]};
beforeEach(()=>{Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:()=> '0be9d7b2-1335-4f27-85a4-a1304a799f55'}});});
afterEach(()=>{global.fetch=originalFetch;jest.restoreAllMocks();});
it('assigns each customer to the same manager with its own current version',async()=>{
 global.fetch=jest.fn(async(_url,options)=>({ok:true,json:async()=>options?.method==='POST'?{}:data}));
 render(<SupplierTeam API="/api" context={context} mode="customers"/>);
 fireEvent.change(await screen.findByLabelText('Ответственный за Альфа'),{target:{value:'8'}});
 await screen.findByText('Изменения сохранены');
 fireEvent.change(screen.getByLabelText('Ответственный за Бета'),{target:{value:'8'}});
 await waitFor(()=>expect(global.fetch.mock.calls.filter(c=>c[1]?.method==='POST')).toHaveLength(2));
 const commands=global.fetch.mock.calls.filter(c=>c[1]?.method==='POST').map(c=>JSON.parse(c[1].body));
 expect(commands.map(c=>[c.companyId,c.memberId,c.version])).toEqual([[2,8,0],[3,8,0]]);
});
it('does not expose team management to a manager',()=>{
 render(<SupplierTeam API="/api" context={{suppliers:[{id:7,role:'manager'}]}}/>);
 expect(screen.queryByText('Создать приглашение менеджеру')).not.toBeInTheDocument();
});
it('removes stale names and invite links when authorization is revoked on reload',async()=>{
 let revoked=false;
 global.fetch=jest.fn(async()=>({ok:!revoked,json:async()=>revoked?{detail:'Доступ отозван'}:data}));
 render(<SupplierTeam API="/api" context={context}/>);
 await screen.findByText('Иван');revoked=true;
 fireEvent.click(screen.getByText('Обновить команду и назначения'));
 await screen.findByRole('alert');expect(screen.queryByText('Иван')).not.toBeInTheDocument();
});
it('preserves operation id when an uncertain network result is retried',async()=>{
 let attempts=0;
 global.fetch=jest.fn(async(_url,options)=>{
  if(options?.method==='POST'&&attempts++===0)throw new Error('Связь прервана');
  return {ok:true,json:async()=>options?.method==='POST'?{}:data};
 });
 render(<SupplierTeam API="/api" context={context}/>);
 fireEvent.click(await screen.findByText('Создать приглашение менеджеру'));
 await screen.findByText('Связь прервана');
 fireEvent.click(screen.getByText('Создать приглашение менеджеру'));
 await screen.findByText('Изменения сохранены');
 const commands=global.fetch.mock.calls.filter(c=>c[1]?.method==='POST').map(c=>JSON.parse(c[1].body));
 expect(commands[0].requestId).toEqual(commands[1].requestId);
});
