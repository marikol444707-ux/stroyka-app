import {render, screen} from '@testing-library/react';
import AppEntryRoutes from './AppEntryRoutes';

test('cookie check does not show the login form before the server answers', () => {
  render(<AppEntryRoutes user={null} sessionChecked={false} page="login" />);
  expect(screen.getByRole('status')).toHaveTextContent('Проверяем вход');
  expect(screen.queryByText('Войти в систему')).toBeNull();
});

test('a rejected cookie session shows the login form', () => {
  render(<AppEntryRoutes user={null} sessionChecked page="login" state={{loginError: ''}} actions={{}} />);
  expect(screen.getByText('Войти в систему')).toBeTruthy();
});
