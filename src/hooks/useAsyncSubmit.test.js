import { act, renderHook } from '@testing-library/react';
import useAsyncSubmit from './useAsyncSubmit';

test('default unknown-error message does not encourage blind retry', async () => {
  const {result} = renderHook(() => useAsyncSubmit(jest.fn().mockRejectedValue(undefined)));
  await act(async () => { await result.current.submit(); });

  expect(result.current.error).toContain('Проверьте результат перед повторной отправкой');
  expect(result.current.error).not.toContain('Попробуйте ещё раз');
});

test('blocks same-tick calls and keeps the guard when the action is replaced on rerender', async () => {
  let finish;
  const pending = new Promise(resolve => { finish = resolve; });
  const action = jest.fn(() => pending);
  const nextAction = jest.fn().mockResolvedValue('retried');
  const {result, rerender} = renderHook(({onSubmit}) => useAsyncSubmit(onSubmit), {
    initialProps: {onSubmit: action},
  });
  let firstSubmission;

  act(() => {
    firstSubmission = result.current.submit('draft');
    result.current.submit('draft');
  });
  expect(action).toHaveBeenCalledTimes(1);
  expect(action).toHaveBeenCalledWith('draft');
  expect(result.current.pending).toBe(true);

  rerender({onSubmit: nextAction});
  await act(async () => { await result.current.submit('another draft'); });
  expect(nextAction).not.toHaveBeenCalled();
  await act(async () => { finish('created'); await firstSubmission; });
  expect(result.current.pending).toBe(false);

  await act(async () => { await result.current.submit('next draft'); });
  expect(nextAction).toHaveBeenCalledWith('next draft');
});

test.each([
  ['rejection', () => Promise.reject(new Error('Сеть недоступна'))],
  ['synchronous error', () => { throw new Error('Сеть недоступна'); }],
])('handles %s without a rejected handler promise and releases the guard', async (_name, fail) => {
  const action = jest.fn().mockImplementationOnce(fail).mockResolvedValueOnce('created');
  const {result} = renderHook(() => useAsyncSubmit(action));

  await act(async () => { await expect(result.current.submit()).resolves.toBeUndefined(); });
  expect(result.current.error).toBe('Сеть недоступна');
  expect(result.current.pending).toBe(false);

  await act(async () => { await result.current.submit(); });
  expect(action).toHaveBeenCalledTimes(2);
  expect(result.current.error).toBe('');
  expect(result.current.pending).toBe(false);
});
