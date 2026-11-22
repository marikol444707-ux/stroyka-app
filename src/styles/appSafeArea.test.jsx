import { readFileSync } from 'fs';
import path from 'path';
import { render, screen } from '@testing-library/react';
import AppHeaderBar from '../components/AppHeaderBar';
import MobileBottomNav from '../components/MobileBottomNav';
import LoginPage from '../pages/LoginPage';
import MasterCabinetPage from '../components/MasterCabinetPage';

const safeCss = readFileSync(path.join(__dirname, 'safeArea.css'), 'utf8');
const appCss = readFileSync(path.join(__dirname, '../App.css'), 'utf8');
const indexSource = readFileSync(path.join(__dirname, '../index.js'), 'utf8');

function ruleBody(css, selector) {
  const at = css.indexOf(selector);
  const open = css.indexOf('{', at);
  const close = css.indexOf('}', open);
  return css.slice(open + 1, close);
}

describe('app shell iOS safe area', () => {
  test('defines one set of insets and uses them on headers, pages and bottom bars', () => {
    expect(indexSource).toContain("import './styles/safeArea.css'");
    for (const edge of ['top', 'right', 'bottom', 'left']) {
      expect(safeCss).toContain(`--safe-${edge}: env(safe-area-inset-${edge}, 0px);`);
    }
    const header = ruleBody(safeCss, '.safe-top-bar,');
    expect(header).toContain('padding-top: calc(var(--safe-pad-top, 0px) + var(--safe-top));');
    expect(header).toContain('padding-left: calc(var(--safe-pad-left, var(--safe-pad-x, 0px)) + var(--safe-left));');
    expect(ruleBody(safeCss, '.safe-bottom-bar')).toContain('padding-bottom: calc(var(--safe-pad-bottom, 0px) + var(--safe-bottom));');
    expect(ruleBody(safeCss, '.safe-page')).toContain('padding-top: calc(var(--safe-pad-top, 0px) + var(--safe-top));');
    expect(ruleBody(safeCss, '.safe-drawer')).toContain('padding-top: var(--safe-top);');
    expect(safeCss).toContain('top: calc(var(--safe-edge-top, 18px) + var(--safe-top))');
  });

  test('keeps the desktop app header padding and only adds the safe area in CSS', () => {
    const { container } = render(<AppHeaderBar activePage="projects" allMenuItems={[{ id: 'projects', label: 'Объекты' }]} user={{ role: 'директор', name: 'Директор' }} />);
    const header = container.querySelector('.app-header-bar');
    expect(header.className).toContain('safe-top-bar');
    expect(header.style.paddingTop).toBe('');
    expect(header.style.getPropertyValue('--safe-pad-top')).toBe('12px');
    expect(header.style.getPropertyValue('--safe-pad-x')).toBe('24px');
    expect(header.style.getPropertyValue('--safe-pad-bottom')).toBe('12px');
  });

  test('uses the same header contract on a phone-width shell', () => {
    const { container } = render(<AppHeaderBar isMobile activePage="accounting" allMenuItems={[{ id: 'accounting', label: 'Бухгалтерия' }]} user={{ role: 'бухгалтер', name: 'Бухгалтер' }} />);
    const header = container.querySelector('.app-header-bar');
    expect(header.style.getPropertyValue('--safe-pad-top')).toBe('6px');
    expect(header.style.getPropertyValue('--safe-pad-x')).toBe('12px');
  });

  test('pads the mobile tab bar from the shared bottom inset', () => {
    const { container } = render(<MobileBottomNav isMobile activePage="warehouse" menuItems={[{ id: 'warehouse', label: 'Склад' }, { id: 'dashboard', label: 'Главная' }]} />);
    const nav = container.querySelector('.mobile-bottom-nav');
    expect(nav.className).toContain('safe-bottom-bar');
    expect(nav.style.padding).toBe('');
    expect(nav.style.getPropertyValue('--safe-pad-top')).toBe('6px');
    expect(nav.style.getPropertyValue('--safe-pad-bottom')).toBe('8px');
    expect(nav.style.display).toBe('flex');
  });

  test('keeps the login card at 20px on desktop and clears the status bar in CSS', () => {
    render(<LoginPage email="" setEmail={() => {}} password="" setPassword={() => {}} handleLogin={async () => null} loginError="" setLoginError={() => {}} setPage={() => {}} />);
    const screenNode = document.querySelector('.auth-screen');
    const back = screen.getByRole('button', { name: 'На сайт СтройКа' });
    expect(back.className).toContain('safe-edge-button');
    expect(appCss).toContain('padding-top: calc(20px + var(--safe-top)) !important;');
    expect(appCss).toContain('padding-top: max(24px, calc(var(--safe-top) + 16px)) !important;');
    expect(appCss).not.toContain('var(--safe-top) + var(--safe-top)');
    expect(appCss).toContain('padding-bottom: max(24px, calc(var(--safe-bottom) + 16px)) !important;');
    expect(screenNode).toBeTruthy();
  });

  test('keeps the field cabinet brand and check-in below the status bar and the tabs above the home indicator', () => {
    render(
      <MasterCabinetPage
        API="/api"
        activePage="works"
        C={{ bg: '#f9fafb', text: '#111', textSec: '#666', border: '#ddd', bgGray: '#eee', accent: '#f97316', accentLight: '#fff7ed', textMuted: '#999', danger: '#ef4444', success: '#10b981', successLight: '#ecfdf5', successBorder: '#a7f3d0', warning: '#d97706', warningLight: '#fffbeb', warningBorder: '#fde68a', info: '#2563eb', infoLight: '#eff6ff', infoBorder: '#bfdbfe' }}
        ROLE_LABELS={{ субподрядчик: 'Субподрядчик' }}
        user={{ id: 4, name: 'Иван', role: 'субподрядчик' }}
        isMobile
        piecework={[]}
        projects={[]}
        materialTransfers={[]}
        pricelistItems={[]}
        rooms={[]}
        tools={[]}
        estimatesList={[]}
        interimActs={[]}
        workJournal={[]}
        notifications={[]}
        supplyRequests={[]}
        ownExpenses={[]}
        brigadeContracts={[]}
        contracts={[]}
      />,
    );

    expect(screen.getByRole('heading', { name: 'СтройКа' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Отметиться/ })).toBeInTheDocument();
    expect(screen.getByText('Иван — Субподрядчик')).toBeInTheDocument();
    for (const label of ['Работы', 'Поруч.', 'История', 'Склад', 'Кабель', 'Снабжение', 'Документы']) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
    const header = screen.getByRole('heading', { name: 'СтройКа' }).closest('.safe-sticky-header');
    const nav = document.querySelector('.master-cabinet-nav');
    expect(header.style.getPropertyValue('--safe-pad-top')).toBe('15px');
    expect(header.style.getPropertyValue('--safe-pad-x')).toBe('15px');
    expect(nav.className).toContain('safe-bottom-bar');
    expect(nav.style.getPropertyValue('--safe-pad-bottom')).toBe('14px');
    expect(nav.style.padding).toBe('');
  });
});
