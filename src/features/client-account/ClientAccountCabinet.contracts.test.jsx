import { render, screen, waitFor } from '@testing-library/react';

import ClientAccountCabinet from './ClientAccountCabinet';


const response = value => ({ok: true, status: 200, json: async () => value});

const colors = {
  bg: '#101828', card: '#1d2939', text: '#fff', textSec: '#d0d5dd',
  textMuted: '#98a2b3', border: '#344054', info: '#2684ff',
  infoLight: '#eef6ff', infoBorder: '#2684ff', success: '#0a6',
  successLight: '#e8fff7', successBorder: '#0a6', warning: '#b70',
  warningLight: '#fff7e0', warningBorder: '#b70', danger: '#d22',
  dangerLight: '#fff0f0', dangerBorder: '#d22',
};

const dashboard = {
  account: {id: 3, name: 'Клиентская группа', planLabel: 'Про', status: 'active'},
  user: {name: 'Владелец', roleLabel: 'Владелец клиентского аккаунта'},
  tariff: {name: 'Про', includedCompanies: 2},
  usage: {companies: 1, activeCompanies: 1, activeUsers: 1, totalUsers: 1, projects: 1, billingDocuments: 0, openFollowups: 0},
  limitWarnings: [], companies: [], users: [], billingDocuments: [],
  followups: [], supportSessions: [],
};

const contracts = {
  readOnly: true,
  items: [{
    id: 101,
    companyId: 42,
    companyName: 'ООО Клиент',
    number: 'STK-2026-0101',
    startsOn: '2026-09-02',
    endsOn: '2027-09-01',
    monthlyFee: 49900,
    status: 'active',
    statusLabel: 'Действует',
    generatedFileUrl: '/tenant-files/501/content',
    signedFileUrl: '/tenant-files/502/content',
    statusHistory: [{
      fromStatus: 'issued', toStatus: 'active', reason: 'Подписан',
      changedAt: '2026-09-03T12:00:00',
    }],
  }],
};

describe('ClientAccountCabinet contracts', () => {
  beforeEach(() => {
    global.fetch = jest.fn(async url => {
      if (url === '/account/dashboard') return response(dashboard);
      if (url === '/account/client-contracts') return response(contracts);
      return response({});
    });
  });

  afterEach(() => jest.restoreAllMocks());

  test('shows protected contract documents and history without management actions', async () => {
    render(
      <ClientAccountCabinet
        user={{name: 'Владелец', role: 'account_owner'}}
        setUser={jest.fn()}
        C={colors}
        card={{}}
        btnG={{}}
        API=""
        handleLogout={jest.fn()}
      />,
    );

    expect(await screen.findByText('STK-2026-0101')).toBeInTheDocument();
    expect(screen.getByText('Только просмотр')).toBeInTheDocument();
    expect(screen.getByRole('link', {name: 'Открыть договор'})).toHaveAttribute(
      'href', '/tenant-files/501/content',
    );
    expect(screen.getByRole('link', {name: 'Подписанный договор'})).toHaveAttribute(
      'href', '/tenant-files/502/content',
    );
    expect(screen.getByText('История статусов: 1')).toBeInTheDocument();
    expect(screen.getByText(/Выдан → Действует/)).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: /активировать|аннулировать|прекратить/i})).not.toBeInTheDocument();

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(2));
    expect(global.fetch).toHaveBeenCalledWith(
      '/account/client-contracts',
      expect.objectContaining({credentials: 'include', cache: 'no-store'}),
    );
    expect(global.fetch.mock.calls.every(([_url, options]) => !options?.method)).toBe(true);
  });
});
