import { readFileSync } from 'fs';
import path from 'path';
import { render, screen } from '@testing-library/react';
import { PublicSiteHero } from './PublicSiteHero';

const designCss = readFileSync(path.join(__dirname, 'PublicSiteDesign.css'), 'utf8');
const staticCss = readFileSync(path.join(__dirname, '../../../public/static-site.css'), 'utf8');

function declarationBlocks(css, selector) {
  const blocks = [];
  let from = 0;
  while (from < css.length) {
    const at = css.indexOf(selector, from);
    if (at === -1) break;
    const next = css[at + selector.length];
    const open = css.indexOf('{', at);
    if (next && /[A-Za-z0-9_-]/.test(next)) {
      from = at + selector.length;
      continue;
    }
    if (open === -1) break;
    const between = css.slice(at + selector.length, open);
    if (!/^[\s,]*$/.test(between)) {
      from = at + selector.length;
      continue;
    }
    let depth = 1;
    let cursor = open + 1;
    for (; cursor < css.length && depth > 0; cursor += 1) {
      if (css[cursor] === '{') depth += 1;
      else if (css[cursor] === '}') depth -= 1;
    }
    blocks.push(css.slice(open + 1, cursor - 1));
    from = cursor;
  }
  return blocks;
}

describe('public site iOS safe area', () => {
  test('keeps the logo and Menu below the status bar without changing the usual padding', () => {
    const blocks = declarationBlocks(designCss, '.public-site .public-design-nav');
    expect(blocks).toHaveLength(3);
    const [base, tablet, phone] = blocks;

    expect(base).toContain('--public-header-pad-y: 20px;');
    expect(base).toContain('--public-header-pad-x: 40px;');
    expect(base).toContain('padding-top: calc(var(--public-header-pad-y) + env(safe-area-inset-top, 0px));');
    expect(base).toContain('padding-right: calc(var(--public-header-pad-x) + env(safe-area-inset-right, 0px));');
    expect(base).toContain('padding-bottom: var(--public-header-pad-y);');
    expect(base).toContain('padding-left: calc(var(--public-header-pad-x) + env(safe-area-inset-left, 0px));');

    expect(tablet).toContain('--public-header-pad-y: 18px;');
    expect(tablet).toContain('--public-header-pad-x: 28px;');
    expect(phone).toContain('--public-header-pad-y: 18px;');
    expect(phone).toContain('--public-header-pad-x: 20px;');
    expect(phone).toContain('position: relative;');

    for (const block of blocks) {
      expect(block).not.toMatch(/(^|\s)padding\s*:/);
    }
  });

  test('drops the mobile menu below the taller header and in from the side insets', () => {
    const blocks = declarationBlocks(designCss, '.public-site .public-design-navigation');
    const drawer = blocks.find((block) => block.includes('position: absolute'));
    expect(drawer).toContain('top: calc(77px + env(safe-area-inset-top, 0px));');
    expect(drawer).toContain('padding: 22px calc(22px + env(safe-area-inset-right, 0px)) 22px calc(22px + env(safe-area-inset-left, 0px));');
    expect(designCss).not.toMatch(/top:\s*77px\s*;/);
  });

  test('insets static public pages, including the header, by the same safe area', () => {
    const blocks = declarationBlocks(staticCss, '.page');
    expect(blocks).toHaveLength(3);
    const [base, wide, phone] = blocks;

    expect(base).toContain('padding-top: calc(32px + env(safe-area-inset-top, 0px));');
    expect(base).toContain('padding-right: calc(18px + env(safe-area-inset-right, 0px));');
    expect(base).toContain('padding-bottom: calc(56px + env(safe-area-inset-bottom, 0px));');
    expect(base).toContain('padding-left: calc(18px + env(safe-area-inset-left, 0px));');
    expect(wide).not.toMatch(/padding/);
    expect(phone).toContain('padding-top: calc(18px + env(safe-area-inset-top, 0px));');
    expect(phone).toContain('padding-right: calc(12px + env(safe-area-inset-right, 0px));');
    expect(phone).toContain('padding-bottom: calc(40px + env(safe-area-inset-bottom, 0px));');
    expect(phone).toContain('padding-left: calc(12px + env(safe-area-inset-left, 0px));');
  });

  test('renders the public header without an inline padding override', () => {
    render(<PublicSiteHero onLogin={jest.fn()} scrollTo={jest.fn()} onChooseDirection={jest.fn()} />);
    const header = screen.getByRole('banner');
    expect(header).toHaveClass('public-design-nav');
    expect(header.style.padding).toBe('');
    expect(screen.getByRole('button', { name: 'Меню ☰' })).toBeEnabled();
  });
});
