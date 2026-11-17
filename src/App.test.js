import { fireEvent, render, screen } from '@testing-library/react';
import App from './App';

test('opens login screen from public site', async () => {
  render(<App />);
  const [login] = await screen.findAllByRole('button', { name: /Личный кабинет/i }, { timeout: 5000 });
  fireEvent.click(login);
  expect(await screen.findByText(/Войти в систему/i, {}, { timeout: 5000 })).toBeInTheDocument();
});
