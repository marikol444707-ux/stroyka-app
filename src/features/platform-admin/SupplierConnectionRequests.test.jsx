import {act,fireEvent,render,screen} from '@testing-library/react';
import SupplierConnectionRequests from './SupplierConnectionRequests';
import SupplierBuyerConnectionRequests from '../supply/SupplierBuyerConnectionRequests';

const response=body=>({ok:true,json:async()=>body});
const item={id:'synthetic-request',companyId:2,companyName:'Synthetic buyer A',supplierName:'Synthetic cabinet',inn:'7700010001',targetSupplierId:8,status:'pending',version:1,expiresAt:'2030-01-01T12:00:00Z'};
const props={prefix:'/system/companies/2',supplierId:7,cabinet:{supplierId:8,name:'Synthetic cabinet'},sourceVersion:3,canRequest:true};
beforeEach(()=>{Object.defineProperty(window,'crypto',{configurable:true,value:{randomUUID:jest.fn(()=> 'synthetic-operation')}});});
afterEach(()=>jest.restoreAllMocks());

test('correction review is available only for accepted requests when enabled',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED;
  process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED='1';
  try {
    global.fetch=jest.fn().mockResolvedValue(response({items:[item,{...item,id:'accepted-request',status:'accepted'}],hasMore:false}));
    render(<SupplierConnectionRequests {...props}/>);
    const buttons=await screen.findAllByRole('button',{name:'Проверить ошибочное подключение'});
    expect(buttons).toHaveLength(1);
    global.fetch.mockResolvedValueOnce({ok:false,json:async()=>({detail:'Проверка недоступна'})});
    fireEvent.click(buttons[0]);
    expect(await screen.findByText('Проверка недоступна')).toBeInTheDocument();
    expect(fetch.mock.calls.at(-1)[0]).toContain('/participants/7/connection-requests/accepted-request/correction-preview');
  } finally {
    if(previous===undefined)delete process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED;
    else process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED=previous;
  }
});

test('correction review is hidden by default',async()=>{
  const previous=process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED;
  delete process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED;
  try {
    global.fetch=jest.fn().mockResolvedValue(response({items:[{...item,status:'accepted'}],hasMore:false}));
    render(<SupplierConnectionRequests {...props}/>);
    await screen.findByText('Подключено');
    expect(screen.queryByRole('button',{name:'Проверить ошибочное подключение'})).not.toBeInTheDocument();
  } finally {
    if(previous!==undefined)process.env.REACT_APP_PARTICIPANT_CORRECTION_PREVIEW_ENABLED=previous;
  }
});

test('admin confirms exact buyer request, double click cannot send it twice, and can revoke',async()=>{
  let finish;
  let created=false;
  global.fetch=jest.fn((url,options)=>{
    if(options.method==='POST')return new Promise(resolve=>{finish=()=>{created=true;resolve(response(item));};});
    return Promise.resolve(response({items:created?[item]:[],hasMore:false}));
  });
  render(<SupplierConnectionRequests {...props}/>);
  const button=await screen.findByRole('button',{name:'Запросить подключение'});
  expect(button).toBeDisabled();fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(button);fireEvent.click(button);
  expect(fetch.mock.calls.filter(([,o])=>o.method==='POST')).toHaveLength(1);
  expect(JSON.parse(fetch.mock.calls.find(([,o])=>o.method==='POST')[1].body)).toEqual({requestId:'synthetic-operation',targetSupplierId:8,expectedSourceVersion:3,confirmed:true});
  await act(async()=>finish());
  expect(await screen.findByText('Ожидает ответа')).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Запросить подключение'})).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Отозвать запрос'}));
  expect(fetch.mock.calls.at(-1)[0]).toBe('/system/companies/2/participants/7/connection-requests/synthetic-request/revoke');
  await act(async()=>finish());
});

test('lost response retries same operation key and failed list is not an empty success',async()=>{
  global.fetch=jest.fn((url,options)=>options.method==='POST'?Promise.reject(new Error('Synthetic connection lost')):Promise.resolve(response({items:[],hasMore:false})));
  render(<SupplierConnectionRequests {...props}/>);
  fireEvent.click(await screen.findByRole('checkbox'));
  fireEvent.click(screen.getByRole('button',{name:'Запросить подключение'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Synthetic connection lost');
  fireEvent.click(screen.getByRole('button',{name:'Запросить подключение'}));
  await screen.findByRole('alert');
  const commands=fetch.mock.calls.filter(([,o])=>o.method==='POST');
  expect(commands).toHaveLength(2);expect(commands[0][1].body).toEqual(commands[1][1].body);
});

test('owner sees addressed buyer and server refusal never claims connection succeeded',async()=>{
  global.fetch=jest.fn((url,options)=>options.method==='POST'?Promise.resolve({ok:false,json:async()=>({detail:'Запрос устарел'})}):Promise.resolve(response({items:[item],hasMore:false})));
  const onChanged=jest.fn();
  render(<SupplierBuyerConnectionRequests API="" user={{id:15,role:'поставщик'}} onChanged={onChanged}/>);
  expect(await screen.findByText('Synthetic buyer A')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Подключить покупателя'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Запрос устарел');
  expect(screen.queryByText('Компания подключена к вашему кабинету.')).not.toBeInTheDocument();
  expect(onChanged).not.toHaveBeenCalled();
});

test('changing owner discards previous buyer response and pending command',async()=>{
  let late;
  global.fetch=jest.fn().mockImplementationOnce(()=>new Promise(resolve=>{late=resolve;})).mockResolvedValue(response({items:[],hasMore:false}));
  const view=render(<SupplierBuyerConnectionRequests API="" user={{id:15,role:'поставщик'}}/>);
  view.rerender(<SupplierBuyerConnectionRequests API="" user={{id:16,role:'поставщик'}}/>);
  expect(await screen.findByText('Новых запросов нет.')).toBeInTheDocument();
  await act(async()=>late(response({items:[item],hasMore:false})));
  expect(screen.queryByText('Synthetic buyer A')).not.toBeInTheDocument();
});

test('accepted decision survives a failed refresh and owner can page requests',async()=>{
  let accepted=false;
  global.fetch=jest.fn((url,options)=>{
    if(options.method==='POST'){accepted=true;return Promise.resolve(response({...item,status:'accepted',version:2}));}
    return Promise.resolve(response({items:accepted?[]:[item],hasMore:!accepted}));
  });
  render(<SupplierBuyerConnectionRequests API="" user={{id:15,role:'поставщик'}} onChanged={()=>Promise.reject(new Error('Refresh failed'))}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Подключить покупателя'}));
  expect(await screen.findByText('Компания подключена к вашему кабинету.')).toBeInTheDocument();
  expect(await screen.findByText('Новых запросов нет.')).toBeInTheDocument();
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});

test('owner switch during acceptance never refreshes or shows the old buyer result',async()=>{
  let finish;const onChanged=jest.fn();let reads=0;
  global.fetch=jest.fn((url,options)=>{
    if(options.method==='POST')return new Promise(resolve=>{finish=()=>resolve(response({...item,status:'accepted',version:2}));});
    return Promise.resolve(response({items:++reads===1?[item]:[],hasMore:false}));
  });
  const view=render(<SupplierBuyerConnectionRequests API="" user={{id:15,role:'поставщик'}} onChanged={onChanged}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Подключить покупателя'}));
  view.rerender(<SupplierBuyerConnectionRequests API="" user={{id:16,role:'поставщик'}} onChanged={onChanged}/>);
  expect(await screen.findByText('Новых запросов нет.')).toBeInTheDocument();
  await act(async()=>finish());
  expect(screen.queryByText('Компания подключена к вашему кабинету.')).not.toBeInTheDocument();
  expect(onChanged).not.toHaveBeenCalled();
});

test('pagination requests the next addressed page and a load failure remains visible',async()=>{
  global.fetch=jest.fn().mockResolvedValueOnce(response({items:[item],hasMore:true}))
    .mockResolvedValueOnce({ok:false,json:async()=>({detail:'Synthetic page unavailable'})});
  render(<SupplierBuyerConnectionRequests API="" user={{id:15,role:'поставщик'}}/>);
  fireEvent.click(await screen.findByRole('button',{name:'Далее'}));
  expect(await screen.findByRole('alert')).toHaveTextContent('Synthetic page unavailable');
  expect(fetch.mock.calls.at(-1)[0]).toBe('/supplier/connection-requests?limit=25&offset=25');
  expect(screen.queryByText('Новых запросов нет.')).not.toBeInTheDocument();
});
