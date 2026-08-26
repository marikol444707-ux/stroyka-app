import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import AccountingIncomingDocumentsPanel from './AccountingIncomingDocumentsPanel';

const colors = {
  text: '#fff', textSec: '#bbb', textMuted: '#888', bg: '#111', bgAlt: '#181818', card: '#222',
  border: '#444', accent: '#f70', accentLight: '#321', accentBorder: '#f70', warning: '#fb0',
  warningLight: '#321', warningBorder: '#a70', success: '#0c8', successLight: '#123', successBorder: '#087',
  danger: '#f66', dangerLight: '#311', dangerBorder: '#933', info: '#59f', infoLight: '#123', infoBorder: '#357',
};

afterEach(() => jest.restoreAllMocks());

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

test('an uploaded invoice with a linked supplier bill hides recovery controls by default', async () => {
  renderPanel();

  fireEvent.click(await screen.findByRole('button', {name: 'Открыть'}));

  expect(await screen.findByText(/Счёт № 14555/)).toBeInTheDocument();
  expect(screen.queryByText('Поставщик не определен')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Связать поставщика'})).not.toBeInTheDocument();
  expect(screen.queryByRole('button', {name: 'Подтянуть распознанное'})).not.toBeInTheDocument();
  expect(screen.queryByText('Добавить фото')).not.toBeInTheDocument();
});

test('an opened invoice replaces its compact card instead of rendering twice', async () => {
  renderPanel();

  fireEvent.click(await screen.findByRole('button', {name: 'Открыть'}));

  expect(await screen.findByRole('button', {name: 'Свернуть'})).toHaveAttribute('aria-expanded', 'true');
  expect(screen.queryAllByRole('button', {name: 'Открыть'})).toHaveLength(0);
  expect(screen.getAllByText('ООО "Старт-Строй" · 2026-08-10 · Кисловодск Лицей 4')).toHaveLength(1);
});

test('an unreadable document opens only compact recovery actions', async () => {
  global.fetch = jest.fn().mockResolvedValue({ok: false});
  renderPanel({supplierInvoices: []});

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));

  expect(await screen.findByText('Не удалось прочитать документ')).toBeInTheDocument();
  expect(screen.getByText('Не удалось открыть файл накладной или связанного счёта')).toBeInTheDocument();
  expect(screen.getByRole('combobox')).toBeInTheDocument();
  expect(screen.getByText('Заменить фото')).toBeInTheDocument();
  expect(screen.queryByText('Распознавание документа')).not.toBeInTheDocument();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});

test('manual supplier recovery completes the original payment-ready action', async () => {
  jest.spyOn(window, 'alert').mockImplementation(() => {});
  global.fetch = jest.fn().mockResolvedValueOnce({ok: false, json: async () => ({})});
  renderPanel({suppliers: [{id: 77, name: 'ООО «Старт-Строй»', inn: '2632001234'}]});

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));
  fireEvent.change(await screen.findByRole('combobox'), {target: {value: '77'}});
  global.fetch.mockResolvedValueOnce({ok: true, json: async () => ({ok: true})});
  fireEvent.click(screen.getByRole('button', {name: 'Связать поставщика'}));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual(expect.objectContaining({
    accountingStatus: 'К оплате',
    supplierId: 77,
    supplierInvoiceId: 111,
  }));
  expect(await screen.findByRole('button', {name: 'Открыть'})).toHaveAttribute('aria-expanded', 'false');
  expect(screen.queryByRole('button', {name: 'Свернуть'})).not.toBeInTheDocument();
});

test('a linked supplier bill resolves the supplier on the server without reopening an old file', async () => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ok: true, supplierId: 77, supplierCreated: true}),
  });
  renderPanel();

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  const [url, request] = global.fetch.mock.calls[0];
  expect(url).toContain('/warehouse-invoices/14555/accounting');
  expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
    accountingStatus: 'К оплате',
    supplierInvoiceId: 111,
    resolveLinkedSupplier: true,
  }));
  expect(global.fetch.mock.calls.map(([calledUrl]) => calledUrl)).not.toContain('/uploads/invoice-14555.jpg');
  expect(screen.queryByText('Не удалось прочитать документ')).not.toBeInTheDocument();
  expect(await screen.findByRole('button', {name: 'Открыть'})).toHaveAttribute('aria-expanded', 'false');
});

test('supplier resolution shows immediate progress while document recognition is pending', async () => {
  global.fetch = jest.fn(() => new Promise(() => {}));
  renderPanel();

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));

  const pendingButtons = await screen.findAllByRole('button', {name: 'Определяем поставщика…'});
  expect(pendingButtons.length).toBeGreaterThan(0);
  pendingButtons.forEach(button => expect(button).toBeDisabled());
  expect(screen.getByRole('status')).toHaveTextContent('Читаем связанный счёт и определяем поставщика');
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
  renderPanel({supplierInvoices: []});

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

test('payment action links the one existing supplier with the exact document name without rescanning', async () => {
  global.fetch = jest.fn().mockResolvedValue({ok: true, json: async () => ({ok: true})});
  renderPanel({
    suppliers: [{id: 77, name: 'ООО «Старт-Строй»'}],
  });

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
  const [url, request] = global.fetch.mock.calls[0];
  expect(url).toContain('/warehouse-invoices/14555/accounting');
  expect(JSON.parse(request.body)).toEqual(expect.objectContaining({
    accountingStatus: 'К оплате',
    supplierId: 77,
    supplierInvoiceId: 111,
  }));
});

test('payment action reads a warehouse document when no supplier bill is linked', async () => {
  const responses = [
    {ok: true, blob: async () => new Blob(['supplier invoice'], {type: 'application/pdf'})},
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
  renderPanel({
    supplierInvoices: [],
  });

  fireEvent.click(await screen.findByRole('button', {name: 'К оплате'}));

  await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(3));
  expect(global.fetch.mock.calls[0][0]).toBe('/uploads/invoice-14555.jpg');
  expect(global.fetch.mock.calls[1][0]).toContain('/scan-invoice');
  expect(screen.queryByText('Поставщик не определен')).not.toBeInTheDocument();
});
