import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import Panel from './SupplierAllocationPanel';
import { allocationContext, readAllocationPending, submitAllocation } from './allocationClient';
jest.mock('./allocationClient');
const props={API:'/api',userId:7,companyId:2,invoiceId:12,onBlocked:jest.fn(),onSuccess:jest.fn()};
const context={groupId:8,payments:[{paymentId:10,remainingAmount:'120.00',unallocatedAmount:'100.00'},{paymentId:11,remainingAmount:'20.00',unallocatedAmount:'0.00'}],receipts:[{receiptId:30,warehouseId:40,amount:'100.00',allocated:'40.00'}],allocations:[{paymentId:10,receiptId:30,amount:'20.00'},{paymentId:11,receiptId:30,amount:'20.00'}]};
const original=process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED;
beforeEach(()=>{jest.clearAllMocks();process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED='true';readAllocationPending.mockReturnValue(null);allocationContext.mockResolvedValue(context);submitAllocation.mockResolvedValue({});});
afterAll(()=>{if(original===undefined)delete process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED;else process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED=original;});
test('editing one payment preserves the complete map including other payments',async()=>{
 render(<Panel {...props}/>);fireEvent.click(screen.getByText('Распределить оплату по приёмкам'));
 fireEvent.change(await screen.findByLabelText('Оплата для распределения'),{target:{value:'10'}});
 expect(screen.getByLabelText('На накладную #40, ₽')).toHaveValue('20.00');
 fireEvent.change(screen.getByLabelText('На накладную #40, ₽'),{target:{value:'60'}});
 fireEvent.change(screen.getByLabelText('Основание распределения'),{target:{value:'Сверка'}});
 expect(screen.getByText('Сохранить распределение')).toBeDisabled();
 fireEvent.click(screen.getByLabelText('Подтверждаю распределение всех оплат этого счёта'));
 fireEvent.click(screen.getByText('Сохранить распределение'));
 await waitFor(()=>expect(submitAllocation).toHaveBeenCalledTimes(1));
 expect(submitAllocation.mock.calls[0][0].draft.rows).toEqual([{paymentId:10,receiptId:30,amount:'60'},{paymentId:11,receiptId:30,amount:'20.00'}]);
 expect(await screen.findByText(/Распределение сохранено/)).toBeInTheDocument();
});
test('saved intent reloads without a new context and blocks other actions',async()=>{
 const pending={context,body:{reason:'Сверка',rows:[]}};readAllocationPending.mockReturnValue(pending);
 render(<Panel {...props}/>);fireEvent.click(await screen.findByText('Повторить сохранённое распределение'));
 await waitFor(()=>expect(submitAllocation).toHaveBeenCalledWith(expect.objectContaining({expectedPending:pending})));
 expect(allocationContext).not.toHaveBeenCalled();expect(props.onBlocked).toHaveBeenCalledWith(true);
});
test('company switch ignores late response',async()=>{
 let resolve;allocationContext.mockImplementation(()=>new Promise(done=>{resolve=done;}));
 const view=render(<Panel {...props}/>);fireEvent.click(screen.getByText('Распределить оплату по приёмкам'));
 view.rerender(<Panel {...props} companyId={3}/>);resolve(context);
 await waitFor(()=>expect(screen.queryByLabelText('Оплата для распределения')).not.toBeInTheDocument());
});
test('default off renders nothing and does not read pending',()=>{
 delete process.env.REACT_APP_SUPPLIER_ALLOCATED_REFUNDS_ENABLED;
 const view=render(<Panel {...props}/>);expect(view.container).toBeEmptyDOMElement();expect(readAllocationPending).not.toHaveBeenCalled();
});
