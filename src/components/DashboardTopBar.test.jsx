import React from 'react';
import { render } from '@testing-library/react';
import DashboardTopBar from './DashboardTopBar';

const props = {
  C: { bgGray: '#111827', border: '#334155', textSec: '#cbd5e1', danger: '#ef4444' },
  btnG: {},
  btnO: {},
  companyContext: {},
  darkMode: true,
  myNotifications: () => [],
  notifications: [],
  setDarkMode: jest.fn(),
  setNotifications: jest.fn(),
  setShowAiAssistant: jest.fn(),
  setShowChatPanel: jest.fn(),
  setShowNotifications: jest.fn(),
  setShowQuickActions: jest.fn(),
  setSidebarVisible: jest.fn(),
  setUser: jest.fn(),
  toggleNotifications: jest.fn(),
  user: { role: 'директор' },
};

describe('DashboardTopBar', () => {
  it('does not clip the desktop notifications dropdown', () => {
    const { container } = render(<DashboardTopBar {...props} />);

    expect(container.firstChild.style.overflow).toBe('visible');
  });
});
