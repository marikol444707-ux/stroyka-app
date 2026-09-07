import { existsSync, readFileSync } from 'fs';
import path from 'path';
import { fireEvent, render, screen } from '@testing-library/react';

import SystemOwnerCabinet from './SystemOwnerCabinet';

const stylesheetPath = path.join(__dirname, 'SystemOwnerCabinet.css');
const user = {
  name: 'Александр-Константин Александрович ОченьДлиннаяФамилияБезПробелов',
  role: 'system_owner',
};

describe('SystemOwnerCabinet mobile header', () => {
  let stylesheet;
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    global.fetch = jest.fn(async (url) => ({
      ok: true,
      json: async () => url === '/system/dashboard' ? {monthRevenue: 0, yearRevenue: 0} : [],
    }));
    // CRA mocks CSS imports; attach the real stylesheet for layout-rule checks.
    stylesheet = document.createElement('style');
    stylesheet.textContent = existsSync(stylesheetPath) ? readFileSync(stylesheetPath, 'utf8') : '';
    document.head.appendChild(stylesheet);
  });

  afterEach(() => {
    stylesheet.remove();
    global.fetch = originalFetch;
    localStorage.clear();
  });

  async function renderCabinet(setUser = jest.fn()) {
    const view = render(
      <SystemOwnerCabinet
        user={user}
        setUser={setUser}
        C={{bg: '#101828', text: '#fff', textSec: '#d0d5dd'}}
        card={{}}
        btnO={{}}
        btnG={{padding: '9px 18px'}}
        btnGr={{}}
        btnR={{}}
        inp={{}}
        badge={() => ({})}
        API=""
      />,
    );
    await screen.findByText('🏢 Активные компании');
    return view;
  }

  test('adds iPhone safe-area insets without an inline padding override', async () => {
    const { container } = await renderCabinet();
    // The outer shell has no user-facing role; inspect it for the CSS contract.
    // eslint-disable-next-line testing-library/no-node-access
    const shell = container.firstChild;
    expect(shell.style.padding).toBe('');
    expect(getComputedStyle(shell).boxSizing).toBe('border-box');

    // JSDOM cannot resolve env() or emulate an iPhone notch. Check the actual
    // attached CSS declaration; device geometry still needs browser verification.
    const rule = Array.from(stylesheet.sheet.cssRules).find((item) => (
      item.selectorText && shell.matches(item.selectorText)
    ));
    for (const edge of ['top', 'right', 'bottom', 'left']) {
      expect(rule?.style.getPropertyValue(`padding-${edge}`)).toBe(
        `calc(20px + env(safe-area-inset-${edge}, 0px))`,
      );
    }
  });

  test('lets long owner details wrap while preserving the logout tap target', async () => {
    await renderCabinet();
    const header = screen.getByRole('banner');
    // CSS layout wrappers are intentionally inspected, not used for interaction.
    // eslint-disable-next-line testing-library/no-node-access
    const identity = screen.getByText(/ОченьДлиннаяФамилияБезПробелов/).parentElement;
    const logout = screen.getByRole('button', {name: 'Выйти'});

    expect(getComputedStyle(header).flexWrap).toBe('wrap');
    expect(getComputedStyle(identity).minWidth).toBe('0');
    expect(getComputedStyle(identity).overflowWrap).toBe('anywhere');
    // eslint-disable-next-line testing-library/no-node-access
    expect(getComputedStyle(identity.parentElement).minWidth).toBe('0');
    expect(getComputedStyle(logout).minHeight).toBe('44px');
    expect(getComputedStyle(logout).minWidth).toBe('44px');
    expect(getComputedStyle(logout).flexShrink).toBe('0');
    expect(getComputedStyle(logout).whiteSpace).toBe('nowrap');
    expect(logout).toBeEnabled();
  });

  test('preserves the existing logout action', async () => {
    const setUser = jest.fn();
    localStorage.setItem('authToken', 'test-only-token');
    localStorage.setItem('user', JSON.stringify(user));
    await renderCabinet(setUser);

    fireEvent.click(screen.getByRole('button', {name: 'Выйти'}));

    expect(localStorage.getItem('authToken')).toBeNull();
    expect(localStorage.getItem('user')).toBeNull();
    expect(setUser).toHaveBeenCalledWith(null);
  });
});
