import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import useCustomerCommands from './useCustomerCommands';
function Harness({ onSuccess, refresh = jest.fn(), scope = '1:7' }) {
  const command = useCustomerCommands({ scope, companyId: 1, refresh });
  return <><button disabled={command.blocked} onClick={() => command.run('/prescriptions', { method: 'POST', body: { violation: 'text' }, onSuccess })}>Отправить</button>
    {command.error && <p role="alert">{command.error}</p>}</>;
}
afterEach(() => jest.restoreAllMocks());
test('403 preserves input and never reports success', async () => {
  global.fetch = jest.fn(async () => ({ ok: false, status: 403, json: async () => ({ detail: 'Нет доступа' }) }));
  const success = jest.fn(); render(<Harness onSuccess={success} />);
  fireEvent.click(screen.getByRole('button'));
  await screen.findByText('Нет доступа'); expect(success).not.toHaveBeenCalled();
});
test('double click sends once and only confirmed success clears input', async () => {
  let resolve; global.fetch = jest.fn(() => new Promise(r => { resolve = r; }));
  const success = jest.fn(); render(<Harness onSuccess={success} />);
  fireEvent.click(screen.getByRole('button')); fireEvent.click(screen.getByRole('button'));
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(fetch.mock.calls[0][1].headers['X-Company-Id']).toBe('1');
  resolve({ ok: true, json: async () => ({ ok: true }) });
  await waitFor(() => expect(success).toHaveBeenCalledTimes(1));
});
test('unknown result blocks blind repeat', async () => {
  global.fetch = jest.fn(async () => { throw new TypeError('network'); });
  render(<Harness onSuccess={jest.fn()} />);fireEvent.click(screen.getByRole('button'));
  await screen.findByRole('alert'); expect(screen.getByRole('button').disabled).toBe(true);
});
test('late result after scope change never clears new project input', async () => {
  let resolve; global.fetch = jest.fn(() => new Promise(r => { resolve = r; }));
  const success = jest.fn();const view = render(<Harness scope="1:7" onSuccess={success} />);
  fireEvent.click(screen.getByRole('button'));view.rerender(<Harness scope="1:8" onSuccess={success} />);
  await act(async () => { resolve({ ok: true, json: async () => ({ ok: true }) }); });
  expect(screen.getByRole('button').disabled).toBe(false);
  expect(success).not.toHaveBeenCalled();
});

test('saved command with failed refresh blocks repeating from stale data', async () => {
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => ({ ok: true }) }));
  render(<Harness onSuccess={jest.fn()} refresh={async () => { throw new Error('refresh failed'); }} />);
  fireEvent.click(screen.getByRole('button'));
  await screen.findByText(/Изменение сохранено/);
  expect(screen.getByRole('button').disabled).toBe(true);
});
