import fs from 'fs';
import path from 'path';

import { createSupplyActions } from './supplyActions';


const response = (ok, body, status = ok ? 200 : 409) => ({
  ok,
  status,
  json: jest.fn().mockResolvedValue(body),
});


const buildActions = (role) => {
  const notify = jest.fn();
  const refreshData = jest.fn().mockResolvedValue(undefined);

  const actions = createSupplyActions({
    API: '/api',
    user: {
      id: 77,
      name: 'Тестовый пользователь',
      role,
    },
    notify,
    refreshData,
  });

  return { actions, notify, refreshData };
};


describe('supply request leadership fallback UI', () => {
  const originalFetch = global.fetch;
  const originalAlert = window.alert;
  const originalPrompt = window.prompt;

  beforeEach(() => {
    global.fetch = jest.fn();
    window.alert = jest.fn();
    window.prompt = jest.fn().mockReturnValue('  Ответственный в отпуске  ');
  });

  afterEach(() => {
    global.fetch = originalFetch;
    window.alert = originalAlert;
    window.prompt = originalPrompt;
  });

  test('shows the explicit director fallback wording', () => {
    const source = fs.readFileSync(
      path.resolve(
        __dirname,
        '../../components/supply/SupplyRequestsListParts.jsx',
      ),
      'utf8',
    );

    expect(source).toContain('Подтвердить вместо прораба');
    expect(source).toContain('Подтвердил заявку:');
    expect(source).not.toContain('👷 Прораб:');
  });

  test('director fallback reports success only after backend success', async () => {
    global.fetch.mockResolvedValue(
      response(true, {
        id: 15,
        status: 'Подтверждена прорабом',
      }),
    );

    const { actions, notify, refreshData } = buildActions(
      'директор',
    );

    await expect(
      actions.confirmSupplyAsProrab(15),
    ).resolves.toBe(true);

    expect(notify).toHaveBeenCalledWith(
      'Заявка подтверждена руководителем вместо прораба — теперь требуется отдельное утверждение',
      'supply',
    );
    expect(refreshData).toHaveBeenCalledTimes(1);
    expect(JSON.parse(global.fetch.mock.calls[0][1].body).reviewerAbsenceReason)
      .toBe('Ответственный в отпуске');
    expect(window.alert).not.toHaveBeenCalled();
  });

  test('backend rejection is shown without false success', async () => {
    global.fetch.mockResolvedValue(
      response(false, {
        detail:
          'На объект назначен активный прораб',
      }),
    );

    const { actions, notify, refreshData } = buildActions(
      'зам_директора',
    );

    await expect(
      actions.confirmSupplyAsProrab(16),
    ).resolves.toBe(false);

    expect(window.alert).toHaveBeenCalledWith(
      'На объект назначен активный прораб',
    );
    expect(notify).not.toHaveBeenCalled();
    expect(refreshData).not.toHaveBeenCalled();
  });

  test('foreman keeps the ordinary confirmation message', async () => {
    global.fetch.mockResolvedValue(
      response(true, {
        id: 17,
        status: 'Подтверждена прорабом',
      }),
    );

    const { actions, notify } = buildActions('прораб');

    await expect(
      actions.confirmSupplyAsProrab(17),
    ).resolves.toBe(true);

    expect(notify).toHaveBeenCalledWith(
      'Заявка подтверждена прорабом — ждёт директора',
      'supply',
    );
    expect(window.prompt).not.toHaveBeenCalled();
  });

  test.each([null, '', '   ', 'x'.repeat(501)])('does not submit invalid/cancelled reason: %s', async reason => {
    window.prompt.mockReturnValue(reason);
    const { actions, notify } = buildActions('директор');
    expect(await actions.confirmSupplyAsProrab(15)).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
    expect(notify).not.toHaveBeenCalled();
  });
});
