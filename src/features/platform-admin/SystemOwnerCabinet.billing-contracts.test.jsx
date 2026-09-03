import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import SystemOwnerCabinet from './SystemOwnerCabinet';


const jsonResponse = (value, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: async () => value,
});

const colors = {
  bg: '#101828', bgWhite: '#fff', card: '#1d2939', text: '#fff',
  textSec: '#d0d5dd', textMuted: '#98a2b3', accent: '#f60',
  success: '#0a6', successLight: '#e8fff7', successBorder: '#0a6',
  warning: '#b70', warningLight: '#fff7e0', warningBorder: '#b70',
  danger: '#d22', dangerLight: '#fff0f0', dangerBorder: '#d22',
  info: '#2684ff', infoLight: '#eef6ff', infoBorder: '#2684ff',
  border: '#344054',
};

const company = {
  id: 42,
  platform_account_id: 3,
  platform_account_name: 'Группа клиента',
  name: 'ООО Клиент',
  monthly_fee: 49900,
};

const contract = {
  id: 101,
  platform_account_id: 3,
  company_id: 42,
  number: 'STK-2026-0101',
  status: 'active',
  company_name: 'ООО Клиент',
};

const foreignContract = {
  ...contract,
  id: 202,
  company_id: 77,
  number: 'STK-2026-0202',
  company_name: 'ООО Другая',
};

const billingDocument = {
  id: 81,
  platform_account_id: 3,
  company_id: 42,
  client_contract_id: null,
  client_contract_number: null,
  document_type: 'invoice',
  documentTypeLabel: 'Счет',
  number: 'INV-81',
  status: 'draft',
  statusLabel: 'Черновик',
  amount: 49900,
  company_name: 'ООО Клиент',
};

function renderCabinet() {
  return render(
    <SystemOwnerCabinet
      user={{name: 'Биллинг', role: 'billing_admin'}}
      setUser={jest.fn()}
      C={colors}
      card={{}}
      btnO={{}}
      btnG={{}}
      btnGr={{}}
      btnR={{}}
      inp={{}}
      badge={() => ({})}
      API=""
    />,
  );
}

describe('SystemOwnerCabinet billing contract links', () => {
  beforeEach(() => {
    global.fetch = jest.fn(async (url, options = {}) => {
      if (url === '/system/companies') return jsonResponse([company]);
      if (url === '/system/billing-documents') {
        if (options.method === 'POST') {
          const request = JSON.parse(options.body);
          return jsonResponse({
            ok: true,
            document: {
              ...billingDocument,
              id: 82,
              client_contract_id: request.clientContractId || null,
            },
          });
        }
        return jsonResponse([billingDocument]);
      }
      if (url === '/system/billing-contract-options') {
        return jsonResponse([contract, foreignContract]);
      }
      if (url === '/system/billing-documents/81/client-contract' && options.method === 'PUT') {
        return jsonResponse({
          ok: true,
          changed: true,
          document: {
            ...billingDocument,
            client_contract_id: 101,
            client_contract_number: contract.number,
            client_contract_status: contract.status,
          },
        });
      }
      return jsonResponse(url === '/system/dashboard' ? {} : []);
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('links an existing document immediately and hides foreign contracts', async () => {
    renderCabinet();
    fireEvent.click(screen.getByRole('button', {name: '💰 Платежи'}));

    expect(await screen.findByText(/INV-81/)).toBeInTheDocument();
    const selector = screen.getByLabelText('Договор для INV-81');
    expect(selector).toHaveDisplayValue('Без договора');
    expect(screen.getByRole('option', {name: 'STK-2026-0101 · Действует'})).toBeInTheDocument();
    expect(screen.queryByRole('option', {name: /STK-2026-0202/})).not.toBeInTheDocument();

    fireEvent.change(selector, {target: {value: '101'}});

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/system/billing-documents/81/client-contract',
      expect.objectContaining({
        method: 'PUT',
        body: JSON.stringify({clientContractId: 101}),
      }),
    ));
    expect(await screen.findByText('Договор STK-2026-0101 связан')).toBeInTheDocument();
    expect(screen.getByLabelText('Договор для INV-81')).toHaveValue('101');
  });

  test('creates a document with the selected same-company contract', async () => {
    renderCabinet();
    fireEvent.click(screen.getByRole('button', {name: '💰 Платежи'}));
    await screen.findByText(/INV-81/);
    fireEvent.click(screen.getByRole('button', {name: '+ Счет/акт'}));

    fireEvent.change(screen.getByLabelText('Компания документа'), {target: {value: '42'}});
    fireEvent.change(screen.getByLabelText('Договор документа'), {target: {value: '101'}});
    fireEvent.change(screen.getByPlaceholderText('Сумма ₽ *'), {target: {value: '49900'}});
    fireEvent.click(screen.getByRole('button', {name: '✓ Создать документ'}));

    await waitFor(() => {
      const request = global.fetch.mock.calls.find(([url, options]) => (
        url === '/system/billing-documents' && options.method === 'POST'
      ));
      expect(JSON.parse(request[1].body)).toEqual(expect.objectContaining({
        companyId: 42,
        clientContractId: 101,
      }));
    });
  });
});
