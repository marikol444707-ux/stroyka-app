import React from 'react';
import {render,screen,fireEvent,waitFor,act} from '@testing-library/react';
import ToolDeductionPanel from './ToolDeductionPanel';
const row={id:1,revision:1,company_id:4,staff_id:100,project_id:19,project_name:'Объект',staff_name:'Иван',tool_name:'Дрель',amount:1000,previously_deducted:600,allocations:[],events:[],historicalRefund:{reviewed:false,previouslyRefunded:null,refunded:0,remaining:null}};
const data={companyId:4,sources:[],reviewed:[row],staff:[{id:100,name:'Иван'}],projects:[{id:19,name:'Объект'}]};
const props={companyContext:{mode:'company',selectedCompanyId:4},acts:[]};
const ready={...row,revision:2,historicalRefund:{reviewed:true,previouslyRefunded:100,refunded:0,remaining:500}};
const response=data=>({ok:true,json:async()=>data});
const open=async()=>{fireEvent.click(screen.getByText('Обновить выдачи инструмента'));await screen.findByText('Возврат старых удержаний');fireEvent.click(screen.getByText('Возврат старых удержаний'));};
const fillRefund=()=>{
 fireEvent.change(screen.getByLabelText('Возврат старого удержания 1'),{target:{value:'200'}});
 fireEvent.change(screen.getByLabelText('Основание старого возврата 1'),{target:{value:'Расписка сотрудника'}});
 fireEvent.click(screen.getByLabelText('Подтверждаю фактический возврат старого удержания этому сотруднику'));
};
beforeEach(()=>{global.fetch=jest.fn();});
afterEach(()=>jest.restoreAllMocks());

test('opening requires explicit previously refunded amount including zero and sends no cash command',async()=>{
 fetch.mockResolvedValueOnce(response(data)).mockResolvedValueOnce(response({ok:true,id:1,revision:2})).mockResolvedValueOnce(response({...data,reviewed:[{...ready,historicalRefund:{...ready.historicalRefund,previouslyRefunded:0,remaining:600}}]}));
 const refreshData=jest.fn();render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();
 const amount=screen.getByLabelText('Ранее возвращено вне реестра 1');expect(amount).toHaveValue(null);
 fireEvent.change(screen.getByLabelText('Основание сверки возвратов 1'),{target:{value:'Все документы проверены'}});
 fireEvent.click(screen.getByLabelText('Прежние возвраты проверены по документам, включая отсутствие возвратов'));
 const save=screen.getByText('Подтвердить прежние возвраты');expect(save).toBeDisabled();
 fireEvent.change(amount,{target:{value:'0'}});expect(save).toBeDisabled();
 fireEvent.click(screen.getByLabelText('Прежние возвраты проверены по документам, включая отсутствие возвратов'));
 fireEvent.click(save);await waitFor(()=>expect(refreshData).toHaveBeenCalledTimes(1));
 expect(fetch.mock.calls[1][0]).toMatch(/\/tool-deductions\/1\/historical-refund-review$/);
 expect(fetch.mock.calls[1][1].method).toBe('PUT');
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({expectedRevision:1,previouslyRefunded:'0',basis:'Все документы проверены',confirmed:true});
 expect(screen.queryByText('Подтвердить прежние возвраты')).not.toBeInTheDocument();
 expect(screen.getByLabelText('Возврат старого удержания 1')).toBeInTheDocument();
});

test('historical refund conflict retains input with one request and no success or retry',async()=>{
 let finish;fetch.mockResolvedValueOnce(response({...data,reviewed:[ready]})).mockReturnValueOnce(new Promise(r=>{finish=r;}));
 const refreshData=jest.fn();render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();fillRefund();
 const save=screen.getByText('Записать возврат старого удержания');fireEvent.click(save);fireEvent.click(save);
 expect(fetch).toHaveBeenCalledTimes(2);expect(fetch.mock.calls[1][0]).toMatch(/\/historical-refunds$/);
 expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({expectedRevision:2,amount:'200',basis:'Расписка сотрудника',confirmed:true});
 await act(async()=>finish({ok:false,status:409,json:async()=>({detail:'Другая вкладка изменила остаток'})}));
 expect(screen.getByRole('alert')).toHaveTextContent('Другая вкладка');expect(screen.getByLabelText('Возврат старого удержания 1')).toHaveValue(200);
 expect(screen.queryByRole('status')).not.toBeInTheDocument();expect(refreshData).not.toHaveBeenCalled();expect(fetch).toHaveBeenCalledTimes(2);
});

test('confirmed refund refreshes history and remaining amount without restoring allocation capacity',async()=>{
 const updated={...ready,revision:3,historicalRefund:{...ready.historicalRefund,refunded:200,remaining:300},events:[{revision:3,actor:'Бухгалтер',change:{operation:'historical_refund',amount:200,basis:'Расписка сотрудника',projectPaymentId:51}}]};
 fetch.mockResolvedValueOnce(response({...data,reviewed:[ready]})).mockResolvedValueOnce(response({ok:true,id:1,revision:3,projectPaymentId:51})).mockResolvedValueOnce(response({...data,reviewed:[updated]}));
 const refreshData=jest.fn();render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();fillRefund();fireEvent.click(screen.getByText('Записать возврат старого удержания'));
 await waitFor(()=>expect(refreshData).toHaveBeenCalledTimes(1));
 expect(screen.getByText(/Доступно к возврату старых удержаний/)).toHaveTextContent('300 ₽');
 expect(screen.getByText(/Стоимость 1/)).toHaveTextContent('Осталось 400 ₽');
 expect(screen.getByText(/Платёж №51/)).toHaveTextContent('200 ₽');
 expect(screen.getByLabelText('Подтверждаю фактический возврат старого удержания этому сотруднику')).not.toBeChecked();
});

test('changing refund value clears confirmation and disallows over-limit amount',async()=>{
 fetch.mockResolvedValue(response({...data,reviewed:[ready]}));render(<ToolDeductionPanel {...props}/>);await open();fillRefund();
 fireEvent.change(screen.getByLabelText('Возврат старого удержания 1'),{target:{value:'501'}});
 expect(screen.getByLabelText('Подтверждаю фактический возврат старого удержания этому сотруднику')).not.toBeChecked();
 fireEvent.click(screen.getByLabelText('Подтверждаю фактический возврат старого удержания этому сотруднику'));
 expect(screen.getByText('Записать возврат старого удержания')).toBeDisabled();
});

test('late historical refund response cannot refresh another company',async()=>{
 let finish;fetch.mockResolvedValueOnce(response({...data,reviewed:[ready]})).mockReturnValueOnce(new Promise(r=>{finish=r;}));
 const refreshData=jest.fn();const v=render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();fillRefund();fireEvent.click(screen.getByText('Записать возврат старого удержания'));
 v.rerender(<ToolDeductionPanel {...props} companyContext={{mode:'company',selectedCompanyId:5}} refreshData={refreshData}/>);
 await act(async()=>finish(response({ok:true,id:1,revision:3,projectPaymentId:51})));
 expect(refreshData).not.toHaveBeenCalled();expect(screen.queryByRole('status')).not.toBeInTheDocument();
});

test('late historical refund after unmount cannot replace a reopened draft',async()=>{
 let finish;fetch.mockResolvedValueOnce(response({...data,reviewed:[ready]})).mockReturnValueOnce(new Promise(r=>{finish=r;}));
 const refreshData=jest.fn();const v=render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();fillRefund();fireEvent.click(screen.getByText('Записать возврат старого удержания'));v.unmount();
 fetch.mockResolvedValueOnce(response({...data,reviewed:[ready]}));render(<ToolDeductionPanel {...props} refreshData={refreshData}/>);await open();
 fireEvent.change(screen.getByLabelText('Возврат старого удержания 1'),{target:{value:'125'}});
 await act(async()=>finish(response({ok:true,id:1,revision:3,projectPaymentId:51})));
 expect(screen.getByLabelText('Возврат старого удержания 1')).toHaveValue(125);expect(refreshData).not.toHaveBeenCalled();expect(screen.queryByRole('status')).not.toBeInTheDocument();
});
