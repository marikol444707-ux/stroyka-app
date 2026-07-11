import { createEstimateChatActions } from './estimateChatActions';


const deferred = () => {
  let resolve;
  let reject;
  const promise = new Promise((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
};

const createDeps = (overrides = {}) => ({
  API: '',
  alertFn: jest.fn(),
  buildContext: jest.fn(() => 'Контекст'),
  estimateChatInput: '',
  estimateChatLoading: false,
  estimateChatMessages: [],
  estimateChatRequestRef: { current: 0 },
  fetchFn: jest.fn(),
  readApiResult: jest.fn(async (response) => response.data),
  selectedEstimate: { id: 7, name: 'Смета' },
  setEstimateChatInput: jest.fn(),
  setEstimateChatLoading: jest.fn(),
  setEstimateChatMessages: jest.fn(),
  setShowEstimateChat: jest.fn(),
  ...overrides,
});

describe('estimateChatActions', () => {
  test('ignores history that arrives after the company context changed', async () => {
    const pending = deferred();
    const deps = createDeps({ fetchFn: jest.fn(() => pending.promise) });
    const actions = createEstimateChatActions(deps);

    const loading = actions.handleOpenSelectedEstimateChat();
    deps.estimateChatRequestRef.current += 1;
    pending.resolve({ data: [{ id: 11, role: 'user', content: 'Старая компания' }] });
    await loading;

    expect(deps.setShowEstimateChat).toHaveBeenCalledWith(true);
    expect(deps.setEstimateChatMessages).toHaveBeenCalledTimes(1);
    expect(deps.setEstimateChatMessages).toHaveBeenCalledWith([]);
  });

  test('ignores assistant response that arrives for a stale estimate context', async () => {
    const pending = deferred();
    const deps = createDeps({
      estimateChatInput: 'Вопрос',
      estimateChatMessages: [{ id: 1, role: 'assistant', content: 'Ранее' }],
      fetchFn: jest.fn(() => pending.promise),
    });
    const actions = createEstimateChatActions(deps);

    const sending = actions.sendEstimateChatMessage();
    deps.estimateChatRequestRef.current += 1;
    pending.resolve({ data: { response: 'Ответ старой компании', assistantMessageId: 22 } });
    await sending;

    expect(deps.setEstimateChatMessages).toHaveBeenCalledTimes(1);
    expect(deps.setEstimateChatMessages.mock.calls[0][0]).toEqual([
      { id: 1, role: 'assistant', content: 'Ранее' },
      expect.objectContaining({ role: 'user', content: 'Вопрос' }),
    ]);
    expect(deps.setEstimateChatLoading).toHaveBeenCalledTimes(1);
    expect(deps.setEstimateChatLoading).toHaveBeenCalledWith(true);
  });

  test('does not clear local history when the delete request fails', async () => {
    const deps = createDeps({
      fetchFn: jest.fn(async () => ({ data: null })),
      readApiResult: jest.fn(async () => { throw new Error('Нет доступа'); }),
    });
    const actions = createEstimateChatActions(deps);

    const result = await actions.clearEstimateChatHistory();

    expect(result).toBe(false);
    expect(deps.setEstimateChatMessages).not.toHaveBeenCalled();
    expect(deps.alertFn).toHaveBeenCalledWith('Не удалось очистить чат: Нет доступа');
  });

  test('clears local history only after a successful delete', async () => {
    const deps = createDeps({ fetchFn: jest.fn(async () => ({ data: { ok: true } })) });
    const actions = createEstimateChatActions(deps);

    const result = await actions.clearEstimateChatHistory();

    expect(result).toBe(true);
    expect(deps.setEstimateChatMessages).toHaveBeenCalledWith([]);
    expect(deps.setEstimateChatInput).toHaveBeenCalledWith('');
  });
});
