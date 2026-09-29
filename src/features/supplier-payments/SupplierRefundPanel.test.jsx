import React from 'react';
import {fireEvent,render,screen,waitFor} from '@testing-library/react';
import Panel from './SupplierRefundPanel';
import {refundContext,readRefundPending,submitRefund,cancelRefund} from './refundClient';
jest.mock('./refundClient');
const props={API:'/api',userId:7,companyId:2,invoiceId:12,onBlocked:jest.fn(),onSuccess:jest.fn()};
const context={companyId:2,invoiceId:12,groupId:8,version:1,payments:[{paymentId:10,remainingAmount:'100.00',unallocatedAmount:'20.00'}],receipts:[{receiptId:30,warehouseId:40}],allocations:[{paymentId:10,receiptId:30,amount:'80.00'}]};
const flag=process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED;
beforeEach(()=>{jest.clearAllMocks();process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED='true';readRefundPending.mockReturnValue(null);refundContext.mockResolvedValue(context);submitRefund.mockResolvedValue({operationId:50,amount:'25.00'});});
afterAll(()=>{if(flag===undefined)delete process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED;else process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED=flag;});
test('selects source and explicit receipt split with factual confirmation',async()=>{
 render(<Panel {...props}/>);fireEvent.click(screen.getByText('Оформить возврат по оплате'));
 fireEvent.change(await screen.findByLabelText('Исходная оплата'),{target:{value:'10'}});
 fireEvent.change(screen.getByLabelText('Из свободного остатка, ₽'),{target:{value:'5'}});
 fireEvent.change(screen.getByLabelText('Снять с накладной #40, ₽'),{target:{value:'20'}});
 fireEvent.change(screen.getByLabelText('Основание возврата'),{target:{value:'Выписка №7'}});
 expect(screen.getByText('Подтвердить возврат')).toBeDisabled();
 fireEvent.click(screen.getByLabelText('Возврат денег фактически получен'));
 fireEvent.click(screen.getByText('Подтвердить возврат'));
 await waitFor(()=>expect(submitRefund).toHaveBeenCalledTimes(1));
 expect(submitRefund.mock.calls[0][0].draft).toEqual(expect.objectContaining({paymentId:10,amount:'25.00',unallocatedAmount:'5',releases:[{receiptId:30,amount:'20'}]}));
 expect(await screen.findByText(/Возврат подтверждён/)).toBeInTheDocument();
});
test('restores exact pending without fetching a new context',async()=>{
 const pending={context,body:{paymentId:10,amount:'25.00',reason:'Выписка',paidAt:'2026-09-28'}};readRefundPending.mockReturnValue(pending);
 render(<Panel {...props}/>);fireEvent.click(await screen.findByText('Повторить сохранённый возврат'));
 await waitFor(()=>expect(submitRefund).toHaveBeenCalledWith(expect.objectContaining({expectedPending:pending})));
 expect(refundContext).not.toHaveBeenCalled();
});
test('company switch ignores late context and does not send old draft',async()=>{
 let resolve;refundContext.mockImplementation(()=>new Promise(done=>{resolve=done;}));
 const view=render(<Panel {...props}/>);fireEvent.click(screen.getByText('Оформить возврат по оплате'));
 view.rerender(<Panel {...props} companyId={3}/>);resolve(context);
 await waitFor(()=>expect(screen.queryByLabelText('Исходная оплата')).not.toBeInTheDocument());
 expect(submitRefund).not.toHaveBeenCalled();
});
test('pending cancellation offers only cancellation retry',async()=>{
 readRefundPending.mockReturnValue({context,cancelRequested:true,body:{paymentId:10,amount:'25.00',reason:'Выписка'}});
 cancelRefund.mockResolvedValue({status:'cancelled'});render(<Panel {...props}/>);
 expect(screen.queryByText('Повторить сохранённый возврат')).not.toBeInTheDocument();
 fireEvent.click(screen.getByText('Повторить отмену попытки'));
 expect(await screen.findByText(/Попытка отменена/)).toBeInTheDocument();
 expect(submitRefund).not.toHaveBeenCalled();
});
test('disabled flag hides panel',()=>{delete process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED;expect(render(<Panel {...props}/>).container).toBeEmptyDOMElement();});
