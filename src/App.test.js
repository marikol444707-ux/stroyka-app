import { render, screen } from '@testing-library/react';
import App from './App';

test('renders login screen', () => {
  render(<App />);
  expect(screen.getByText(/СТРОЙ/i)).toBeInTheDocument();
  expect(screen.getByText(/КА/i)).toBeInTheDocument();
  expect(screen.getByText(/Войти в систему/i)).toBeInTheDocument();
});
