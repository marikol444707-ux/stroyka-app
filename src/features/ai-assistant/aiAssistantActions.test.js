import {act, renderHook} from '@testing-library/react';
import {createAiAssistantActions} from './aiAssistantActions';
import {useAiAssistantState} from './useAiAssistantState';

const context = (userId = 1, companyId = 11, mode = 'company') => ({user: {id: userId}, companyContext: {mode, selectedCompanyId: companyId}});
const response = text => ({ok: true, json: async () => ({response: text})});
const deferred = () => {let resolve; const promise = new Promise(done => {resolve = done;}); return {promise, resolve};};
let oldFetch;
beforeEach(() => {oldFetch = global.fetch; global.fetch = jest.fn(); jest.useFakeTimers();});
afterEach(() => {global.fetch = oldFetch; jest.clearAllTimers(); jest.useRealTimers();});

function setup(initial = context()) {
  const scrollIntoView = jest.fn();
  const hook = renderHook(props => {
    const state = useAiAssistantState(props);
    return {...state, ...createAiAssistantActions({...state, API: '/api', chatEndRef: {current: {scrollIntoView}}})};
  }, {initialProps: initial});
  const type = value => act(() => hook.result.current.setAiMessage(value));
  return {...hook, type, scrollIntoView};
}

test('two turns send bounded real history and construction mode; repeated send is suppressed', async () => {
  const first = deferred();
  global.fetch.mockReturnValueOnce(first.promise).mockResolvedValueOnce(response('Посчитаем'));
  const hook = setup();
  hook.type('Нормы расхода штукатурки?');
  let pending;
  act(() => {const send = hook.result.current.sendAiMessage; pending = send(); send();});
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(hook.result.current.aiLoading).toBe(true);
  await act(async () => {first.resolve(response('Какая толщина слоя?')); await pending;});
  hook.type('  10 мм  ');
  await act(async () => hook.result.current.sendAiMessage());
  expect(JSON.parse(global.fetch.mock.calls[1][1].body)).toEqual({mode: 'construction', messages: [
    {role: 'user', content: 'Нормы расхода штукатурки?'},
    {role: 'assistant', content: 'Какая толщина слоя?'},
    {role: 'user', content: '  10 мм  '},
  ]});
  expect(hook.result.current.aiLoading).toBe(false);
});

test.each([
  ['company', context(1, 22)], ['user', context(2, 11)],
  ['all companies', context(1, null, 'all_companies')], ['logout', {user: null, companyContext: {}}],
])('%s change clears draft/chat/loading and ignores even an abort-ignoring old response', async (_, nextContext) => {
  const oldRequest = deferred();
  global.fetch.mockReturnValueOnce(oldRequest.promise).mockResolvedValueOnce(response('New answer'));
  const hook = setup();
  hook.type('Old company private question');
  let pending;
  act(() => {pending = hook.result.current.sendAiMessage();});
  const oldSetChat = hook.result.current.setAiChat;
  hook.type('Old draft');
  hook.rerender(nextContext);
  expect(global.fetch.mock.calls[0][1].signal.aborted).toBe(true);
  expect(hook.result.current.aiChat).toEqual([]);
  expect(hook.result.current.aiMessage).toBe('');
  expect(hook.result.current.aiLoading).toBe(false);
  act(() => oldSetChat([{role: 'assistant', content: 'Old setter'}]));
  await act(async () => {oldRequest.resolve(response('Old company secret answer')); await pending;});
  act(() => jest.runOnlyPendingTimers());
  expect(hook.result.current.aiChat).toEqual([]);
  expect(hook.scrollIntoView).not.toHaveBeenCalled();
  if (nextContext.user) {
    hook.type('New question');
    await act(async () => hook.result.current.sendAiMessage());
    expect(JSON.parse(global.fetch.mock.calls[1][1].body).messages).toEqual([{role: 'user', content: 'New question'}]);
  }
});

test('switching away and back does not resurrect an old response or old context', async () => {
  const oldRequest = deferred();
  global.fetch.mockReturnValueOnce(oldRequest.promise);
  const hook = setup();
  hook.type('Old question');
  let pending;
  act(() => {pending = hook.result.current.sendAiMessage();});
  hook.rerender(context(1, 22));
  hook.rerender(context());
  await act(async () => {oldRequest.resolve(response('Old secret')); await pending;});
  expect(hook.result.current.aiChat).toEqual([]);
});

test.each([
  ['HTTP error', {ok: false, json: async () => ({response: 'private server failure'})}],
  ['HTTP 200 model gateway error', {ok: true, json: async () => ({ok: false, response: 'private server failure'})}],
])('%s remains visible but never becomes context for the retry', async (_, failedResponse) => {
  global.fetch.mockResolvedValueOnce(failedResponse)
    .mockResolvedValueOnce(response('Done'));
  const hook = setup();
  hook.type('First attempt');
  await act(async () => hook.result.current.sendAiMessage());
  expect(hook.result.current.aiChat[1].error).toBe(true);
  expect(hook.result.current.aiChat[1].content).not.toContain('private server failure');
  hook.type('Retry');
  await act(async () => hook.result.current.sendAiMessage());
  expect(JSON.parse(global.fetch.mock.calls[1][1].body).messages).toEqual([{role: 'user', content: 'Retry'}]);
});

test('unmount aborts a pending request without updating state', async () => {
  const request = deferred();
  global.fetch.mockReturnValueOnce(request.promise);
  const hook = setup();
  hook.type('Question');
  let pending;
  act(() => {pending = hook.result.current.sendAiMessage();});
  hook.unmount();
  expect(global.fetch.mock.calls[0][1].signal.aborted).toBe(true);
  await act(async () => {request.resolve(response('Too late')); await pending;});
  expect(hook.scrollIntoView).not.toHaveBeenCalled();
});


test('unresolved company context cannot send, and a resolved context starts without its draft/history', async () => {
  const initial = context();
  initial.companyContext.loading = true;
  global.fetch.mockResolvedValueOnce(response('Ready'));
  const hook = setup(initial);
  hook.type('Do not send while company is loading');
  await act(async () => hook.result.current.sendAiMessage());
  expect(hook.result.current.aiRequestSession.active).toBe(false);
  expect(global.fetch).not.toHaveBeenCalled();
  expect(hook.result.current.aiLoading).toBe(false);
  hook.rerender(context());
  expect(hook.result.current.aiRequestSession.active).toBe(true);
  expect(hook.result.current.aiMessage).toBe('');
  expect(hook.result.current.aiChat).toEqual([]);
  hook.type('Resolved company question');
  await act(async () => hook.result.current.sendAiMessage());
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(JSON.parse(global.fetch.mock.calls[0][1].body).messages).toEqual([{role: 'user', content: 'Resolved company question'}]);
});
