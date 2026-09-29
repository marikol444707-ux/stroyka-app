import React from 'react';
import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import Choice from './SavedContractChoice';
const props={API:'/api',companyId:1,offerId:41,onSaved:jest.fn(),onFallback:jest.fn()};
const items=[{id:10,number:'A',date:'2026-09-01',sourceFileId:31},{id:11,number:'B',date:'2026-09-02',sourceFileId:32}];
let old;
beforeEach(()=>{old=global.fetch;jest.clearAllMocks();});
afterEach(()=>{global.fetch=old;});
test('one choice saves only source id with company scope and no review fields',async()=>{
 global.fetch=jest.fn(async(url,options)=>({ok:true,json:async()=>options.method==='POST'?{id:20,offerId:41,companyId:1,sourceContractId:11}:{items}}));
 render(<Choice {...props}/>);
 fireEvent.click((await screen.findAllByText('Использовать'))[1]);
 await waitFor(()=>expect(props.onSaved).toHaveBeenCalledTimes(1));
 const options=global.fetch.mock.calls[1][1];
 expect(JSON.parse(options.body)).toEqual({contractId:11});expect(options.headers['X-Company-Id']).toBe('1');
 expect(screen.queryByRole('checkbox')).toBeNull();
});
test('lost response permits retry of same selection but not another choice',async()=>{
 global.fetch=jest.fn(async(url,options)=>{if(options.method==='POST')throw new Error('Connection lost');return {ok:true,json:async()=>({items})};});
 render(<Choice {...props}/>);fireEvent.click((await screen.findAllByText('Использовать'))[0]);
 await screen.findByRole('alert');expect(props.onSaved).not.toHaveBeenCalled();
 expect(screen.getByText('Использовать').disabled).toBe(true);expect(screen.getByText('Повторить выбор').disabled).toBe(false);
});
test('no eligible contracts returns to full review',async()=>{
 global.fetch=jest.fn(async()=>({ok:true,json:async()=>({items:[]})}));render(<Choice {...props}/>);
 await waitFor(()=>expect(props.onFallback).toHaveBeenCalledTimes(1));
});
