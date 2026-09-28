import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import AccountingIncomingDocumentsPanel from './AccountingIncomingDocumentsPanel';

jest.mock('../features/supplier-payments/SupplierPaymentDialog', () => props => (
  <div role="dialog">{props.documentKind}:{props.documentId}<button onClick={props.onClose}>Закрыть</button></div>
));

test('both partial receipts open the same invoice payment and have no separate debt action', () => {
  const flag = process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
  process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED = 'true';
  try {
    render(<AccountingIncomingDocumentsPanel C={{}} card={{}} btnO={{}} btnG={{}} btnB={{}}
      btnR={{}} btnGr={{}} inp={{}} companyContext={{mode:'company',selectedCompanyId:2}}
      user={{id:7}} warehouseInvoiceEstimateControl={() => []}
      invoices={[91,92].map(id => ({id,companyId:2,settlementInvoiceId:4,number:String(id),
        supplierId:3,supplierName:'Поставщик',project:'Объект',totalWithVat:100,items:[]}))}
      supplierInvoices={[{id:4,companyId:2,invoiceNumber:'СЧ-4',supplierId:3,amount:200,paidAmount:40}]}
    />);
    expect(screen.getAllByText('Стоимость поступления')).toHaveLength(2);
    expect(screen.getByText('Без отдельного долга')).toBeInTheDocument();
    expect(screen.queryByRole('button',{name:'Оплатить'})).not.toBeInTheDocument();
    const buttons = screen.getAllByRole('button',{name:'Оплата и история'});
    fireEvent.click(buttons[0]);
    expect(screen.getByRole('dialog')).toHaveTextContent('invoice:4');
    fireEvent.click(screen.getByRole('button',{name:'Закрыть'}));
    fireEvent.click(buttons[1]);
    expect(screen.getByRole('dialog')).toHaveTextContent('invoice:4');
  } finally {
    if (flag === undefined) delete process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED;
    else process.env.REACT_APP_SUPPLIER_PAYMENTS_ENABLED = flag;
  }
});
