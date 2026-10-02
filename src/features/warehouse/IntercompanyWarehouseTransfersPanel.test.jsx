import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { IntercompanyWarehouseTransfersWorkspace } from './IntercompanyWarehouseTransfersPanel';

const companies = [
  { companyId: 2, companyName: 'Компания А', role: 'директор' },
  { companyId: 3, companyName: 'Компания Б', role: 'директор' },
];
const lots = [{ lotId: 17, warehouseInvoiceId: 7, invoiceNumber: 'Н-7', materialName: 'Кабель', unit: 'м', availableQuantity: '10' }];

beforeEach(() => {
  sessionStorage.clear();
  Object.defineProperty(window, 'crypto', { configurable: true, value: { randomUUID: () => '7a990fae-9d83-4c5d-b22e-8f31d370e5f7' } });
  global.fetch = jest.fn()
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [], companyId: 2 }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: lots }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 11, requestId: 'request', side: 'source', status: 'pending', materialName: 'Кабель', unit: 'м', quantity: 4, counterparty: { companyId: 3, name: 'Компания Б' }, document: { kind: 'intercompany_dispatch' } }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [], companyId: 2 }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: lots }) });
});

afterEach(() => jest.restoreAllMocks());

test('source company creates a pending transfer without claiming immediate receipt', async () => {
  render(<IntercompanyWarehouseTransfersWorkspace companyId={2} companies={companies} editable />);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(2));
  fireEvent.change(screen.getByLabelText('Компания-получатель'), { target: { value: '3' } });
  fireEvent.change(screen.getByLabelText('Партия материала'), { target: { value: '17' } });
  fireEvent.change(screen.getByLabelText('Количество'), { target: { value: '4' } });
  fireEvent.change(screen.getByLabelText('Основание передачи'), { target: { value: 'Для другого объекта' } });
  fireEvent.click(screen.getByRole('button', { name: 'Отправить на подтверждение' }));
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
  const [url, options] = fetch.mock.calls[2];
  expect(url).toContain('/intercompany-warehouse-transfers');
  expect(options.headers).toMatchObject({ 'X-Company-Id': '2', 'X-Company-Mode': 'company' });
  expect(JSON.parse(options.body)).toMatchObject({ destinationCompanyId: 3, sourceLotId: 17, quantity: '4', reason: 'Для другого объекта' });
  expect(screen.getByText(/остатки изменятся после подтверждения получателем/i)).toBeInTheDocument();
});

test('destination can accept a pending incoming transfer', async () => {
  fetch.mockReset();
  fetch
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [{ id: 12, side: 'destination', status: 'pending', materialName: 'Кабель', unit: 'м', quantity: 2, counterparty: { companyId: 2, name: 'Компания А' }, document: { kind: 'intercompany_receipt' } }], companyId: 3 }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ id: 12, status: 'accepted' }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [], companyId: 3 }) })
    .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) });
  render(<IntercompanyWarehouseTransfersWorkspace companyId={3} companies={companies} editable />);
  const accept = await screen.findByRole('button', { name: 'Принять на склад' });
  fireEvent.click(accept);
  await waitFor(() => expect(fetch).toHaveBeenCalledTimes(5));
  expect(fetch.mock.calls[2][0]).toContain('/intercompany-warehouse-transfers/12/accept');
});
