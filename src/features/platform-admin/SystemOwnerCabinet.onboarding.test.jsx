import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import SystemOwnerCabinet from './SystemOwnerCabinet';


const jsonResponse = (value, ok = true) => ({
  ok,
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

describe('SystemOwnerCabinet company onboarding', () => {
  beforeEach(() => {
    global.fetch = jest.fn(async (url, options = {}) => {
      if (url === '/system/companies/preview' && options.method === 'POST') {
        return jsonResponse({
          canCreate: true,
          plan: 'demo',
          tariff: {name: 'Демо'},
          blockingReasons: [],
          duplicates: [],
          limitWarnings: [],
        });
      }
      if (url === '/system/companies' && options.method === 'POST') {
        return jsonResponse({
          id: 42,
          inviteCode: 'DIRECT01',
          onboarding: {
            companyName: 'ООО Новая компания',
            recipientName: 'Иван Петров',
            recipientEmail: 'director@example.test',
            roleLabel: 'Директор компании',
            expiresAt: '2026-10-01 12:30:00',
          },
        });
      }
      return jsonResponse(url === '/system/dashboard' ? {} : []);
    });
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('creates a company and shows the first director handoff', async () => {
    render(
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

    fireEvent.click(screen.getByRole('button', {name: /Аккаунты\/компании/}));
    fireEvent.click(screen.getByRole('button', {name: /Подключить аккаунт\/компанию/}));

    fireEvent.change(screen.getByPlaceholderText(/Клиентский аккаунт \/ группа/), {
      target: {value: 'Новый клиент'},
    });
    fireEvent.change(screen.getByPlaceholderText(/Компания \/ юрлицо/), {
      target: {value: 'ООО Новая компания'},
    });
    fireEvent.change(screen.getByPlaceholderText('Контактное лицо'), {
      target: {value: 'Иван Петров'},
    });
    fireEvent.change(screen.getByPlaceholderText('Email'), {
      target: {value: 'director@example.test'},
    });
    fireEvent.click(screen.getByRole('button', {
      name: '✓ Создать компанию и приглашение директору',
    }));

    expect(await screen.findByRole('status')).toHaveTextContent(
      'Компания «ООО Новая компания» создана',
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'Директор компании',
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'Иван Петров · director@example.test',
    );
    expect(screen.getByRole('status')).toHaveTextContent(
      'http://localhost/?invite=DIRECT01',
    );

    fireEvent.click(screen.getByRole('button', {name: '👥 Проверить регистрацию'}));
    expect(await screen.findByText('Пользователи клиентских групп (0)')).toBeInTheDocument();
    expect(screen.getByText('Пользователей по выбранным фильтрам нет')).toBeInTheDocument();

    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      '/system/companies',
      expect.objectContaining({method: 'POST'}),
    ));
    const createRequest = global.fetch.mock.calls.find(([url, options]) => (
      url === '/system/companies' && options.method === 'POST'
    ));
    expect(JSON.parse(createRequest[1].body)).toEqual(expect.objectContaining({
      name: 'ООО Новая компания',
      contactName: 'Иван Петров',
      contactEmail: 'director@example.test',
    }));
    expect(JSON.parse(createRequest[1].body)).not.toHaveProperty('createdBy');
  });
});
