import { fireEvent, render, screen } from '@testing-library/react';
import App from './App';

test('opens login screen from public site', async () => {
  render(<App />);
  fireEvent.click(await screen.findByRole('button', { name: /Вход в ERP/i }));
  expect(await screen.findByText(/Войти в систему/i)).toBeInTheDocument();
});
