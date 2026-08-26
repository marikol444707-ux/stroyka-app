import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AccountingIncomingDocumentsPanel from './AccountingIncomingDocumentsPanel';

jest.mock('./DocumentRecognitionPanel', () => function RecognitionStub({onApplyExtracted}) {
  return (
    <button onClick={() => onApplyExtracted({
      extracted: {
        counterpartyName: 'ООО "Старт-Строй"',
        inn: '2632001234',
        kpp: '263201001',
        ogrn: '1022600001234',
      },
    })}>
      Подтянуть распознанное
    </button>
  );
});

const colors = {
  text: '#fff', textSec: '#bbb', textMuted: '#888', bg: '#111', bgAlt: '#181818', card: '#222',
  border: '#444', accent: '#f70', accentLight: '#321', accentBorder: '#f70', warning: '#fb0',
  warningLight: '#321', warningBorder: '#a70', success: '#0c8', successLight: '#123', successBorder: '#087',
  danger: '#f66', dangerLight: '#311', dangerBorder: '#933', info: '#59f', infoLight: '#123', infoBorder: '#357',
};

const renderPanel = (overrides = {}) => render(
  <AccountingIncomingDocumentsPanel
    C={colors}
    card={{}}
    btnO={{}}
    btnG={{}}
    btnB={{}}
    btnR={{}}
    btnGr={{}}
    inp={{}}
    invoices={[{
      id: 14555,
      number: '14555',
      date: '2026-08-10',
      supplierName: 'ООО "Старт-Строй"',
      supplierId: null,
      project: 'Кисловодск Лицей 4',
      location: 'Кисловодск Лицей 4',
      accountingStatus: 'Нужно уточнение',
      photos: ['/uploads/invoice-14555.jpg'],
      totalWithVat: 94380,
      items: [{name: 'Штукатурка', quantity: 1, unit: 'шт', price: 94380}],
    }]}
    supplierInvoices={[{
      id: 111,
      warehouseInvoiceId: 14555,
      invoiceNumber: '14555',
      supplierName: 'ООО "Старт-Строй"',
      supplierId: null,
      projectName: 'Кисловодск Лицей 4',
      amount: 94380,
    }]}
    suppliers={[]}
    warehouseInvoiceEstimateControl={() => []}
    fileSrc={value => value}
    uploadPhoto={jest.fn()}
    refreshData={jest.fn()}
    {...overrides}
  />,
);

test('a missing supplier keeps the payment action enabled for automatic resolution', async () => {
  renderPanel();

  expect(await screen.findByRole('button', {name: 'К оплате'})).toBeEnabled();
});

test('recognized requisites are sent as structured supplier data', async () => {
  global.fetch = jest.fn(async () => ({ok: true, json: async () => ({ok: true})}));
  const refreshData = jest.fn();
  renderPanel({refreshData});

  fireEvent.click(await screen.findByRole('button', {name: 'Открыть'}));
  fireEvent.click(await screen.findByRole('button', {name: 'Подтянуть распознанное'}));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  const [url, request] = global.fetch.mock.calls[0];
  expect(url).toContain('/warehouse-invoices/14555/accounting');
  expect(request.method).toBe('PUT');
  expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
    supplierRequisites: expect.objectContaining({
      name: 'ООО "Старт-Строй"',
      inn: '2632001234',
      kpp: '263201001',
      ogrn: '1022600001234',
    }),
  }));
});

test('payment action resolves a new supplier from the attached invoice in one flow', async () => {
  const responses = [
    {ok: true, blob: async () => new Blob(['invoice'], {type: 'image/jpeg'})},
    {ok: true, json: async () => ({
      ok: true,
      data: {
        supplierName: 'ООО "Старт-Строй"',
        supplierInn: '2632001234',
        supplierKpp: '263201001',
        supplierOgrn: '1022600001234',
      },
    })},
    {ok: true, json: async () => ({ok: true, supplierId: 77, supplierCreated: true})},
  ];
  global.fetch = jest.fn(async () => responses.shift());
  renderPanel();

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
  expect(global.fetch.mock.calls[1][0]).toContain('/scan-invoice');
  const updateRequest = global.fetch.mock.calls[2][1];
  expect(JSON.parse(updateRequest.body)).toEqual(expect.objectContaining({
    accountingStatus: 'К оплате',
    supplierRequisites: expect.objectContaining({
      name: 'ООО "Старт-Строй"',
      inn: '2632001234',
      kpp: '263201001',
      ogrn: '1022600001234',
    }),
  }));
});
