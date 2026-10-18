import React from 'react';
import {act,render,screen,fireEvent,waitFor} from '@testing-library/react';
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

it('ignores a late command from the previous cabinet without replacing the new team',async()=>{
 let finish;
 const changed=jest.fn();
 const next={...data,members:[{...data.members[0],id:18,name:'Новый менеджер'}]};
 global.fetch=jest.fn(async(url,options)=>options?.method==='POST'
  ?new Promise(resolve=>{finish=resolve;})
  :{ok:true,json:async()=>url.endsWith('/17')?next:data});
 const view=render(<SupplierTeam API="/api" context={context} onChanged={changed}/>);
 fireEvent.click(await screen.findByText('Создать приглашение менеджеру'));
 view.rerender(<SupplierTeam API="/api" context={{suppliers:[{id:17,name:'Другой поставщик',role:'leader'}]}} onChanged={changed}/>);
 await screen.findByText('Новый менеджер');
 await act(async()=>finish({ok:true,json:async()=>({})}));
 expect(screen.getByText('Новый менеджер')).toBeInTheDocument();
 expect(screen.queryByText('Изменения сохранены')).not.toBeInTheDocument();
 expect(changed).not.toHaveBeenCalled();
 expect(global.fetch.mock.calls.filter(([url,options])=>url.endsWith('/7')&&!options?.method)).toHaveLength(1);
});

it('clears the previous actor snapshot even when the new actor uses the same supplier',async()=>{
 let finish;
 const old={...context,scope:'/api:owner-a:поставщик'};
 const next={...context,scope:'/api:owner-b:поставщик'};
 global.fetch=jest.fn().mockResolvedValueOnce({ok:true,json:async()=>data})
  .mockImplementationOnce(()=>new Promise(resolve=>{finish=resolve;}));
 const view=render(<SupplierTeam API="/api" context={old}/>);
 await screen.findByText('Иван');
 view.rerender(<SupplierTeam API="/api" context={next}/>);
 expect(screen.queryByText('Иван')).not.toBeInTheDocument();
 await act(async()=>finish({ok:false,status:403,json:async()=>({detail:'Доступ отозван'})}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Доступ отозван');
});

it('does not refresh a parent after a command finishes on a closed team panel',async()=>{
 let finish;
 const changed=jest.fn();
 global.fetch=jest.fn(async(_url,options)=>options?.method==='POST'
  ?new Promise(resolve=>{finish=resolve;}) :{ok:true,json:async()=>data});
 const view=render(<SupplierTeam API="/api" context={context} onChanged={changed}/>);
 fireEvent.click(await screen.findByText('Создать приглашение менеджеру'));
 view.unmount();
 await act(async()=>finish({ok:true,json:async()=>({})}));
 expect(changed).not.toHaveBeenCalled();
 expect(fetch.mock.calls.filter(([,options])=>!options?.method)).toHaveLength(1);
});
