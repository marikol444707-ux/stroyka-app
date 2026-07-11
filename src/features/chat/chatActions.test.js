import {createChatActions} from './chatActions';

const response = ({ok = true, status = 200, body = {}} = {}) => ({
  ok,
  status,
  json: jest.fn().mockResolvedValue(body),
});

const buildActions = (overrides = {}) => {
  const deps = {
    API: '',
    canUseCompanyChat: true,
    companyChatContextKey: '7:4',
    isCompanyChatContextCurrent: jest.fn().mockReturnValue(true),
    loadProjectChat: jest.fn(),
    notify: jest.fn(),
    reloadCompanyMessages: jest.fn().mockResolvedValue(true),
    setCompanyChatMessage: jest.fn(),
    setShowChatPanelRaw: jest.fn(),
    setProjectChatMessage: jest.fn(),
    showChatPanel: false,
    unreadMessagesCount: 0,
    user: {id: 7, name: 'Директор', role: 'директор'},
    ...overrides,
  };
  return {actions: createChatActions(deps), deps};
};

describe('company chat actions', () => {
  beforeEach(() => {
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  test('does not send or clear the draft without a selected company', async () => {
    const {actions, deps} = buildActions({canUseCompanyChat: false});

    const sent = await actions.sendCompanyChatMessage('Сообщение', '');

    expect(sent).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
    expect(deps.setCompanyChatMessage).not.toHaveBeenCalled();
    expect(deps.notify).toHaveBeenCalledWith('Для чата выберите конкретную компанию', 'chat');
  });

  test('keeps the draft when the server rejects a message', async () => {
    global.fetch.mockResolvedValue(response({
      ok: false,
      status: 409,
      body: {detail: 'Фото относится к другой компании'},
    }));
    const {actions, deps} = buildActions();

    const sent = await actions.sendCompanyChatMessage('Сообщение', '/tenant-files/1/content');

    expect(sent).toBe(false);
    expect(deps.reloadCompanyMessages).not.toHaveBeenCalled();
    expect(deps.setCompanyChatMessage).not.toHaveBeenCalled();
    expect(deps.notify).toHaveBeenCalledWith(
      'Не удалось отправить сообщение: Фото относится к другой компании',
      'chat',
    );
  });

  test('reloads the selected company chat after a successful send', async () => {
    global.fetch.mockResolvedValue(response({body: {id: 11}}));
    const {actions, deps} = buildActions();

    const sent = await actions.sendCompanyChatMessage('Сообщение', '');

    expect(sent).toBe(true);
    expect(deps.reloadCompanyMessages).toHaveBeenCalledTimes(1);
    expect(deps.setCompanyChatMessage).toHaveBeenCalledWith('');
  });

  test('does not clear another company draft after the context changes mid-send', async () => {
    let resolveSend;
    global.fetch.mockImplementation(() => new Promise((resolve) => { resolveSend = resolve; }));
    let current = true;
    const {actions, deps} = buildActions({
      isCompanyChatContextCurrent: jest.fn(() => current),
    });

    const sending = actions.sendCompanyChatMessage('Компания 4', '');
    current = false;
    resolveSend(response({body: {id: 12}}));
    const sent = await sending;

    expect(sent).toBe(true);
    expect(deps.reloadCompanyMessages).not.toHaveBeenCalled();
    expect(deps.setCompanyChatMessage).not.toHaveBeenCalled();
  });

  test('does not mark messages read locally when the server rejects the request', async () => {
    global.fetch.mockResolvedValue(response({
      ok: false,
      status: 400,
      body: {detail: 'Для чата выберите конкретную компанию'},
    }));
    const {actions, deps} = buildActions({unreadMessagesCount: 2});

    const marked = await actions.setShowChatPanel(true);

    expect(marked).toBe(false);
    expect(deps.setShowChatPanelRaw).toHaveBeenCalledWith(true);
    expect(deps.reloadCompanyMessages).not.toHaveBeenCalled();
    expect(deps.notify).toHaveBeenCalledWith(
      'Не удалось отметить сообщения прочитанными: Для чата выберите конкретную компанию',
      'chat',
    );
  });
});
