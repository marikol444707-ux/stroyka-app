import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import ReceiveMaterialDialog from './ReceiveMaterialDialog';

test('manual receipt opens original review and preserves the current draft', () => {
  const setNewInvoice=jest.fn(),setShowScanInvoice=jest.fn(),setShowScannedInvoiceForm=jest.fn();
  render(<ReceiveMaterialDialog showReceiveDialog C={{}} setShowReceiveDialog={()=>{}}
    setNewInvoice={setNewInvoice} setShowScanInvoice={setShowScanInvoice}
    setShowScannedInvoiceForm={setShowScannedInvoiceForm}/>);
  fireEvent.click(screen.getByRole('button',{name:/Ввести вручную/}));
  expect(setShowScanInvoice).toHaveBeenCalledWith(true);
  expect(setShowScannedInvoiceForm).not.toHaveBeenCalled();
  expect(setNewInvoice.mock.calls[0][0]({location:'Объект',items:[{name:'Цемент'}]}))
    .toEqual({location:'Объект',items:[{name:'Цемент'}],manualReceiptReview:true});
});
