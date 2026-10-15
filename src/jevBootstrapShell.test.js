import { cleanup, render, screen } from '@testing-library/react';
import App from './App';

// The server validation and CDP isolation are covered in Python. This is the
// real React application's side of that contract, not a fabricated QA page.
const publicIdentity = { id: 21, companyId: 17, role: 'кладовщик', name: 'QA Viewer', email: 'qa@example.test' };
let originalFetch;
beforeEach(() => {
  localStorage.clear();
  window.history.replaceState({}, '', '/app');
  originalFetch = global.fetch;
  global.fetch = jest.fn().mockRejectedValue(new TypeError('QA bootstrap: business API denied before send'));
});
afterEach(() => {
  cleanup();
  localStorage.clear();
  global.fetch = originalFetch;
  window.history.replaceState({}, '', '/');
});

test('a clean context stays on login without a public UI identity', async () => {
  const { container } = render(<App />);
  expect(await screen.findByText(/Войти в систему/i)).toBeInTheDocument();
  expect(container.querySelector('.app-authenticated-shell')).toBeNull();
  expect(screen.queryByRole('button', { name: 'Склад' })).toBeNull();
});

test('verified public identity opens the real shell without successful business API responses', async () => {
  localStorage.setItem('user', JSON.stringify(publicIdentity));
  const { container } = render(<App />);
  expect(await screen.findByRole('button', { name: 'Склад' })).toBeVisible();
  expect(container.querySelector('.app-authenticated-shell')).toBeInTheDocument();
  expect(localStorage.getItem('authToken')).toBeNull();
  expect(JSON.parse(localStorage.getItem('user'))).toEqual(publicIdentity);
  expect(global.fetch).toHaveBeenCalled();
});

test('a valid role without warehouse access is not promoted just to pass smoke', async () => {
  const identity = { ...publicIdentity, role: 'сметчик' };
  localStorage.setItem('user', JSON.stringify(identity));
  const { container } = render(<App />);
  expect(await screen.findByRole('button', { name: 'Проекты' })).toBeVisible();
  expect(container.querySelector('.app-authenticated-shell')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Склад' })).toBeNull();
  expect(JSON.parse(localStorage.getItem('user'))).toEqual(identity);
});
