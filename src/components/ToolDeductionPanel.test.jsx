import React from 'react';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import ToolDeductionPanel from './ToolDeductionPanel';
const reviewed={id:1,revision:1,company_id:4,staff_id:100,project_id:19,project_name:'Объект',staff_name:'Иван',tool_name:'Дрель',amount:1000,previously_deducted:0,allocations:[],events:[]};
const data={companyId:4,sources:[],reviewed:[reviewed],staff:[{id:100,name:'Иван'}],projects:[{id:19,name:'Объект'}]};
const props={companyContext:{mode:'company',selectedCompanyId:4},acts:[{id:10,companyId:4,masterId:100,project:'Объект'}]};
const response=result=>({ok:true,json:async()=>result});
const open=async()=>{fireEvent.click(screen.getByText('Обновить выдачи инструмента'));await screen.findByLabelText('Сумма удержания 1');};
const fill=()=>{
 fireEvent.change(screen.getByLabelText('Акт удержания 1'),{target:{value:'10'}});
 fireEvent.change(screen.getByLabelText('Сумма удержания 1'),{target:{value:'600'}});
 fireEvent.change(screen.getByLabelText('Основание распределения 1'),{target:{value:'Документы проверены'}});
 fireEvent.click(screen.getByLabelText('Подтверждаю распределение по выбранному акту или месяцу'));
};
beforeEach(()=>{global.fetch=jest.fn();});
afterEach(()=>jest.restoreAllMocks());

test('one request; conflict keeps draft and does not refresh or retry',async()=>{
 fetch.mockResolvedValueOnce(response(data));let finish;fetch.mockReturnValueOnce(new Promise(resolve=>{finish=resolve;}));
 const refreshData=jest.fn();render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();fill();
 const save=screen.getByText('Сохранить распределение');fireEvent.click(save);fireEvent.click(save);
 expect(fetch).toHaveBeenCalledTimes(2);
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({expectedRevision:1,actId:10,amount:'600',basis:'Документы проверены',confirmed:true});
 await act(async()=>finish({ok:false,status:409,json:async()=>({detail:'Распределение изменено в другой вкладке'})}));
 expect(screen.getByRole('alert')).toHaveTextContent('другой вкладке');
 expect(screen.getByLabelText('Сумма удержания 1')).toHaveValue(600);expect(refreshData).not.toHaveBeenCalled();
 expect(fetch).toHaveBeenCalledTimes(2);
});

test('late confirmation cannot refresh a different company',async()=>{
 fetch.mockResolvedValueOnce(response(data));let finish;fetch.mockReturnValueOnce(new Promise(resolve=>{finish=resolve;}));
 const refreshData=jest.fn();const view=render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();fill();fireEvent.click(screen.getByText('Сохранить распределение'));
 view.rerender(<ToolDeductionPanel {...props} companyContext={{mode:'company',selectedCompanyId:5}} refreshData={refreshData}/>);
 await act(async()=>finish(response({ok:true,id:1,revision:2})));
 expect(refreshData).not.toHaveBeenCalled();expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('legacy source requires exact staff, project and explicit previous deduction including zero',async()=>{
 const source={sourceKey:'history:10',history_id:10,tool_id:1,name:'Дрель',cost:1000,expectedState:'before'};
 fetch.mockResolvedValueOnce(response({...data,reviewed:[],sources:[source]}));
 render(<ToolDeductionPanel {...props}/>);fireEvent.click(screen.getByText('Обновить выдачи инструмента'));
 const previous=await screen.findByLabelText('Ранее удержано history:10');expect(previous).toHaveValue(null);
 const save=screen.getByText('Подтвердить выдачу для распределения');expect(save).toBeDisabled();
 fireEvent.change(screen.getByLabelText('Получатель history:10'),{target:{value:'100'}});
 fireEvent.change(screen.getByLabelText('Объект history:10'),{target:{value:'19'}});
 fireEvent.change(screen.getByLabelText('Стоимость history:10'),{target:{value:'1000'}});
 fireEvent.change(screen.getByLabelText('Основание history:10'),{target:{value:'Проверено'}});
 fireEvent.click(screen.getByLabelText('Получатель, стоимость и прошлые удержания проверены по документам'));
 expect(save).toBeDisabled();fireEvent.change(previous,{target:{value:'0'}});expect(save).toBeEnabled();
});
