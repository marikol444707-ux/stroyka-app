import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';

import AppSidebar from './AppSidebar';

const makeProps = (overrides = {}) => ({
  isMobile: false,
  sidebarVisible: true,
  setSidebarVisible: jest.fn(),
  user: { id: 1, name: 'QA Снабженец', role: 'снабженец' },
  roleLabels: { снабженец: 'Снабженец' },
  menuItems: [
    { id: 'warehouse', label: 'Склад', icon: '📦' },
    { id: 'supply', label: 'Снабжение', icon: '🛒' },
  ],
  supplyRequests: [],
  activePage: 'warehouse',
  navigateTo: jest.fn(),
  handleLogout: jest.fn(),
  ...overrides,
});

test('sidebar exposes stable native navigation buttons and active page', () => {
  const props = makeProps();
  render(<AppSidebar {...props} />);

  const warehouse = screen.getByRole('button', { name: 'Склад' });
  expect(warehouse).toHaveAttribute('type', 'button');
  expect(warehouse).toHaveAttribute('aria-current', 'page');
  expect(screen.getByRole('button', { name: 'Снабжение' })).not.toHaveAttribute('aria-current');

  fireEvent.click(warehouse);
  expect(props.navigateTo).toHaveBeenCalledWith('warehouse');
  expect(props.setSidebarVisible).not.toHaveBeenCalled();
});

test('mobile navigation closes the sidebar after selecting a page', () => {
  const props = makeProps({ isMobile: true });
  render(<AppSidebar {...props} />);

  fireEvent.click(screen.getByRole('button', { name: 'Снабжение' }));
  expect(props.navigateTo).toHaveBeenCalledWith('supply');
  expect(props.setSidebarVisible).toHaveBeenCalledWith(false);
});

test('logout is an accessible button and preserves logout behavior', () => {
  const props = makeProps();
  render(<AppSidebar {...props} />);

  const logout = screen.getByRole('button', { name: 'Выйти' });
  expect(logout).toHaveAttribute('type', 'button');
  fireEvent.click(logout);
  expect(props.handleLogout).toHaveBeenCalledTimes(1);
});
