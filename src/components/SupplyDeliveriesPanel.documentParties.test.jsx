import React from 'react';
import {fireEvent, render, screen} from '@testing-library/react';
import SupplyDeliveriesPanel from './SupplyDeliveriesPanel';

const colors = new Proxy({}, {get: (_, key) => key});
const props = {
  C: colors, card: {}, inp: {}, btnO: {}, btnG: {}, btnB: {}, btnGr: {},
  badge: () => ({}), role: 'кладовщик', supplyClaims: [], receivingDeliveryId: 1,
  setReceivingDeliveryId: jest.fn(), receiveForm: {receivedQuantity:'2', qualityStatus:'Принято', qualityNotes:'', photoUrl:'', claimDescription:''},
  setReceiveForm: jest.fn(), deliveryAiLoadingId: null, setDeliveryAiLoadingId: jest.fn(),
  deliveryAiResultById: {}, setDeliveryAiResultById: jest.fn(), runDeliveryAiCheck: jest.fn(),
  receiveSupplyDelivery: jest.fn(), invoices: [], showPreview: jest.fn(), buildInvoiceContent: jest.fn(), uploadPhoto: jest.fn(),
};

test('shows frozen destination and requires receiver to confirm it', () => {
  render(<SupplyDeliveriesPanel {...props} supplyDeliveries={[{
    id:1, status:'В пути', materialName:'Кабель', shippedQuantity:2, unit:'м', project:'Лицей', supplierName:'Текущее имя',
    documentParties:{reviewRequired:false, buyer:{fullName:'ООО Покупатель'}, supplier:{fullName:'ООО Поставщик'},
      consignee:{companyName:'ООО Покупатель', deliveryAddress:'Кисловодск, ул. Школьная, 4', contactName:'Иван Петров', contactPhone:'+7 911'},
      contract:{number:'Д-7',date:'2026-09-20'}},
  }]} />);
  expect(screen.getByText(/Кисловодск, ул. Школьная, 4/)).toBeInTheDocument();
  expect(screen.getByText(/ООО Поставщик → ООО Покупатель/)).toBeInTheDocument();
  expect(screen.getByText(/Договор № Д-7/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole('checkbox'));
  expect(props.setReceiveForm).not.toHaveBeenCalled();
});

test('warns on historical delivery without frozen parties', () => {
  render(<SupplyDeliveriesPanel {...props} receivingDeliveryId={null} supplyDeliveries={[{
    id:2, status:'В пути', materialName:'Кабель', shippedQuantity:2, unit:'м', project:'Лицей',
    documentParties:{reviewRequired:true,reviewReason:'Историческая поставка без сохранённых реквизитов'},
  }]} />);
  expect(screen.getByText(/Историческая поставка без сохранённых реквизитов/)).toBeInTheDocument();
});
