import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import CustomerDocuments from './CustomerDocuments';
const props={project:{id:1,companyId:12},user:{id:8},C:{},card:{},refresh:jest.fn(async()=>{}),fileSrc:value=>value};
let oldFetch;
beforeEach(()=>{oldFetch=global.fetch;props.refresh.mockClear();});
afterEach(()=>{global.fetch=oldFetch;});
async function attach(){
 fireEvent.click(screen.getByRole('button',{name:'Отправить файл'}));
 fireEvent.change(screen.getByLabelText('Файл (до 50 МБ)'),{target:{files:[new File(['test'],'plan.pdf',{type:'application/pdf'})]}});
 await waitFor(()=>expect(screen.getByLabelText('Название').value).toBe('plan.pdf'));
}
test('uploads to exact project and sends owned file as incoming correspondence',async()=>{
 global.fetch=jest.fn(async(url,options)=>({ok:true,json:async()=>url.endsWith('/upload-photo')?{companyId:12,projectId:1,contentUrl:'/tenant-files/31/content'}:{ok:true,id:7}}));
 render(<CustomerDocuments {...props}/>);await attach();
 fireEvent.click(screen.getByRole('button',{name:'Отправить',exact:true}));
 await screen.findByText('Файл отправлен. Он доступен в переписке объекта.');
 const upload=fetch.mock.calls[0][1];expect(upload.body.get('projectId')).toBe('1');expect(upload.headers['X-Company-Id']).toBe('12');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({projectId:1,fileId:31,subject:'plan.pdf',body:''});
 expect(props.refresh).toHaveBeenCalledTimes(1);
});
test('rejects upload from another company',async()=>{
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({companyId:99,projectId:1,contentUrl:'/tenant-files/31/content'})}));
 render(<CustomerDocuments {...props}/>);
 fireEvent.click(screen.getByRole('button',{name:'Отправить файл'}));
 fireEvent.change(screen.getByLabelText('Файл (до 50 МБ)'),{target:{files:[new File(['test'],'plan.pdf')]}});
 await screen.findByRole('alert');expect(screen.getByRole('button',{name:'Отправить',exact:true}).disabled).toBe(true);
});
test('unknown save blocks a duplicate and keeps the description',async()=>{
 global.fetch=jest.fn(async url=>{if(url.endsWith('/upload-photo'))return {ok:true,json:async()=>({companyId:12,projectId:1,contentUrl:'/tenant-files/31/content'})};throw new Error('Network');});
 render(<CustomerDocuments {...props}/>);await attach();fireEvent.click(screen.getByRole('button',{name:'Отправить',exact:true}));
 await screen.findByRole('alert');expect(screen.getByLabelText('Название').value).toBe('plan.pdf');
 expect(screen.getByRole('button',{name:'Отправить',exact:true}).disabled).toBe(true);expect(fetch).toHaveBeenCalledTimes(2);
});
test('switching project drops draft and ignores late upload',async()=>{
 let resolve;global.fetch=jest.fn(()=>new Promise(r=>{resolve=r;}));
 const view=render(<CustomerDocuments {...props}/>);fireEvent.click(screen.getByRole('button',{name:'Отправить файл'}));
 fireEvent.change(screen.getByLabelText('Файл (до 50 МБ)'),{target:{files:[new File(['test'],'old.pdf')]}});
 view.rerender(<CustomerDocuments {...props} project={{id:2,companyId:12}}/>);
 resolve({ok:true,json:async()=>({companyId:12,projectId:1,contentUrl:'/tenant-files/31/content'})});
 fireEvent.click(screen.getByRole('button',{name:'Отправить файл'}));
 await waitFor(()=>expect(screen.getByLabelText('Название').value).toBe(''));
 expect(screen.getByRole('button',{name:'Отправить',exact:true}).disabled).toBe(true);
});
