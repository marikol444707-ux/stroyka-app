import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import SystemOwnerCabinet from './SystemOwnerCabinet';


const jsonResponse = (value, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: async () => value,
});

const colors = {
  bg: '#101828',
  bgWhite: '#fff',
  card: '#1d2939',
  text: '#fff',
  textSec: '#d0d5dd',
  textMuted: '#98a2b3',
  accent: '#f60',
  success: '#0a6',
  successLight: '#e8fff7',
  successBorder: '#0a6',
  warning: '#b70',
  warningLight: '#fff7e0',
  warningBorder: '#b70',
  danger: '#d22',
  dangerLight: '#fff0f0',
  dangerBorder: '#d22',
  info: '#2684ff',
  infoLight: '#eef6ff',
  infoBorder: '#2684ff',
  border: '#344054',
};

const company = {
  id: 42,
  platform_account_id: 3,
  platform_account_name: 'Клиентская группа',
  name: 'ООО Клиент',
  plan: 'pro',
  monthly_fee: 49900,
  max_projects: 10,
  max_users: 40,
  users_count: 2,
  users_active_count: 2,
  projects_count: 1,
  total_paid: 0,
};

const preview = {
  ok: true,
  dryRun: true,
  writesAttempted: 0,
  readyForDraft: true,
  shouldCreate: true,
  blockers: [],
  contract: {
    companyId: 42,
    contractDate: '2026-09-02',
    startsOn: '2026-09-02',
    endsOn: null,
    plan: 'pro',
    monthlyFee: '49900.00',
    currency: 'RUB',
    maxProjects: 10,
    maxUsers: 40,
    status: 'draft',
    licensorSnapshot: {legalName: 'ИП Правообладатель'},
    clientSnapshot: {legalName: 'ООО Клиент'},
  },
};

const createdContract = {
  ...preview.contract,
  id: 101,
  number: 'STK-2026-0101',
  createdAt: '2026-09-02T10:00:00',
};

function renderCabinet() {
  return render(
    <SystemOwnerCabinet
      user={{name: 'Владелец', role: 'system_owner'}}
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

describe('SystemOwnerCabinet client contracts', () => {
  beforeEach(() => {
    let listRequests = 0;
    global.fetch = jest.fn(async (url, options = {}) => {
      if (url === '/system/companies') return jsonResponse([company]);
      if (url === '/system/client-contracts?companyId=42') {
        listRequests += 1;
        return jsonResponse({
          companyId: 42,
          platformAccountId: 3,
          items: listRequests > 1 ? [createdContract] : [],
        });
      }
      if (url === '/system/client-contracts/preview' && options.method === 'POST') {
        return jsonResponse(preview);
      }
      if (url === '/system/client-contracts' && options.method === 'POST') {
        return jsonResponse({
          created: true,
          idempotent: false,
          contract: createdContract,
        });
      }
      return jsonResponse(url === '/system/dashboard' ? {} : []);
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('creates an auto-filled draft from the existing company card', async () => {
    renderCabinet();

    fireEvent.click(screen.getByRole('button', {name: /Аккаунты\/компании/}));
    expect(await screen.findByText('ООО Клиент')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: '📃 Договор'}));
    expect(await screen.findByText('Договоров пока нет')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Подготовить договор'}));

    expect(await screen.findByText('ИП Правообладатель')).toBeInTheDocument();
    expect(screen.getByText('49 900 ₽/мес')).toBeInTheDocument();
    expect(screen.getByText('10 объектов · 40 пользователей')).toBeInTheDocument();
    expect(screen.getByText('Реквизиты и условия заполнены автоматически')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Создать черновик договора'}));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Черновик STK-2026-0101 создан',
    );
    expect(screen.getByText('STK-2026-0101')).toBeInTheDocument();

    const previewRequest = global.fetch.mock.calls.find(([url]) => (
      url === '/system/client-contracts/preview'
    ));
    const createRequest = global.fetch.mock.calls.find(([url]) => (
      url === '/system/client-contracts'
    ));
    const previewBody = JSON.parse(previewRequest[1].body);
    const createBody = JSON.parse(createRequest[1].body);

    expect(previewBody).toEqual(expect.objectContaining({
      companyId: 42,
      status: 'draft',
    }));
    expect(previewBody.idempotencyKey).toMatch(/^client-contract-42-/);
    expect(createBody).toEqual(previewBody);
    expect(createBody).not.toHaveProperty('clientSnapshot');
    expect(createBody).not.toHaveProperty('licensorSnapshot');
    expect(createBody).not.toHaveProperty('monthlyFee');
    expect(createBody).not.toHaveProperty('maxProjects');
    expect(createBody).not.toHaveProperty('maxUsers');

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/system/client-contracts?companyId=42',
      expect.any(Object),
    ));
  });

  test('uses a fresh idempotency key for each new draft preview', async () => {
    renderCabinet();

    fireEvent.click(screen.getByRole('button', {name: /Аккаунты\/компании/}));
    expect(await screen.findByText('ООО Клиент')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: '📃 Договор'}));
    expect(await screen.findByText('Договоров пока нет')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Подготовить договор'}));
    expect(await screen.findByText('Реквизиты и условия заполнены автоматически')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', {name: 'Закрыть предпросмотр'}));
    fireEvent.click(screen.getByRole('button', {name: 'Подготовить договор'}));

    await waitFor(() => {
      const previewRequests = global.fetch.mock.calls.filter(([url]) => (
        url === '/system/client-contracts/preview'
      ));
      expect(previewRequests).toHaveLength(2);
      const first = JSON.parse(previewRequests[0][1].body);
      const second = JSON.parse(previewRequests[1][1].body);
      expect(second.idempotencyKey).not.toBe(first.idempotencyKey);
    });
  });
});
