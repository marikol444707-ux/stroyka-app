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

  test('shows a failed recognition honestly and keeps signer defaults empty', async () => {
    const previousFetch = global.fetch;
    global.fetch = jest.fn(async (url, options) => url === '/system/client-card/recognize'
      ? jsonResponse({ok: true, source: 'empty', fields: {}, warnings: ['OCR: нет доступа (HTTP 403).']})
      : previousFetch(url, options));
    const {container} = render(<SystemOwnerCabinet
      user={{name: 'Владелец', role: 'system_owner'}} setUser={jest.fn()} C={colors}
      card={{}} btnO={{}} btnG={{}} btnGr={{}} btnR={{}} inp={{}} badge={() => ({})} API="" />);
    fireEvent.click(screen.getByRole('button', {name: /Аккаунты\/компании/}));
    fireEvent.click(screen.getByRole('button', {name: /Подключить аккаунт\/компанию/}));
    expect(screen.getByPlaceholderText('Должность руководителя')).toHaveValue('');
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: {files: [new File(['card'], 'card.jpg', {type: 'image/jpeg'})]},
    });
    await screen.findByText('Не удалось распознать реквизиты');
    expect(screen.queryByText('Распознано: AI/OCR')).not.toBeInTheDocument();
    expect(screen.getByPlaceholderText('Компания / юрлицо * (например: ООО Земля 1)')).toHaveValue('');
  });

  test('recognition and reapplication preserve manual fields including edits while scanning', async () => {
    let completeRecognition;
    const previousFetch = global.fetch;
    global.fetch = jest.fn((url, options) => url === '/system/client-card/recognize'
      ? new Promise(resolve => { completeRecognition = resolve; })
      : previousFetch(url, options));
    const {container} = render(<SystemOwnerCabinet
      user={{name: 'Владелец', role: 'system_owner'}} setUser={jest.fn()} C={colors}
      card={{}} btnO={{}} btnG={{}} btnGr={{}} btnR={{}} inp={{}} badge={() => ({})} API="" />);
    fireEvent.click(screen.getByRole('button', {name: /Аккаунты\/компании/}));
    fireEvent.click(screen.getByRole('button', {name: /Подключить аккаунт\/компанию/}));
    const name = screen.getByPlaceholderText(/Компания \/ юрлицо/);
    const inn = screen.getByPlaceholderText('ИНН');
    const bik = screen.getByPlaceholderText('БИК');
    fireEvent.change(name, {target: {value: 'ООО Проверенная компания'}});
    fireEvent.change(inn, {target: {value: '1234567890'}});
    fireEvent.change(screen.getByPlaceholderText('Руководитель'), {target: {value: 'Ручной Подписант'}});
    fireEvent.change(container.querySelector('input[type="file"]'), {
      target: {files: [new File(['card'], 'card.jpg', {type: 'image/jpeg'})]},
    });
    await waitFor(() => expect(completeRecognition).toBeDefined());
    fireEvent.change(bik, {target: {value: '044525225'}});
    completeRecognition(jsonResponse({ok: true, source: 'ocr', warnings: [], fields: {
      companyName: 'ООО Из файла', inn: '0987654321', bik: '044525411', directorName: 'Подписант из файла',
      contactEmail: 'card@example.test', legalAddress: 'Адрес из карты',
    }}));
    const apply = await screen.findByRole('button', {name: 'Заполнить пустые поля'});
    expect(name).toHaveValue('ООО Проверенная компания');
    expect(inn).toHaveValue('1234567890');
    expect(bik).toHaveValue('044525225');
    expect(screen.getByPlaceholderText('Руководитель')).toHaveValue('Ручной Подписант');
    expect(screen.getByPlaceholderText('Юридический адрес')).toHaveValue('Адрес из карты');
    expect(screen.getByPlaceholderText('Email')).toHaveValue('card@example.test');
    fireEvent.change(screen.getByPlaceholderText('Email'), {target: {value: 'manual@example.test'}});
    fireEvent.click(apply);
    expect(screen.getByPlaceholderText('Email')).toHaveValue('manual@example.test');
    expect(name).toHaveValue('ООО Проверенная компания');
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
    fireEvent.change(screen.getByPlaceholderText('ОГРН / ОГРНИП'), {
      target: {value: '1234567890123'},
    });
    fireEvent.change(screen.getByPlaceholderText('Юридический адрес'), {
      target: {value: 'Москва, ул. Тестовая, 1'},
    });
    fireEvent.change(screen.getByPlaceholderText('БИК'), {
      target: {value: '044525225'},
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
      ogrn: '1234567890123',
      legalAddress: 'Москва, ул. Тестовая, 1',
      bik: '044525225',
    }));
    expect(JSON.parse(createRequest[1].body)).not.toHaveProperty('createdBy');
  });
});
