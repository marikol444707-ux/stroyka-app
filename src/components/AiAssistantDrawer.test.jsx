import React, {useState} from 'react';
import {readFileSync} from 'fs';
import path from 'path';
import {fireEvent, render, screen} from '@testing-library/react';
import AiAssistantDrawer from './AiAssistantDrawer';

const props = {
  C: {bgWhite: '#1e293b', bg: '#0f172a', sidebar: '#020617', border: '#334155', text: '#f8fafc'},
  inp: {}, btnG: {}, btnO: {}, aiChat: [], aiLoading: false, aiMessage: '',
  setAiMessage: jest.fn(), sendAiMessage: jest.fn(), chatEndRef: {current: null},
};

function OpenDrawer({aiLoading = false}) {
  const [open, setOpen] = useState(true);
  return <AiAssistantDrawer {...props} showAiAssistant={open} setShowAiAssistant={setOpen} aiLoading={aiLoading} />;
}

test('the close button is focused and closes the assistant even while a reply is loading', () => {
  render(<OpenDrawer aiLoading />);
  const close = screen.getByRole('button', {name: 'Закрыть ИИ-помощника'});
  expect(close).toHaveFocus();
  expect(close).toBeEnabled();
  fireEvent.click(close);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('Escape closes the assistant from the message input', () => {
  render(<OpenDrawer />);
  fireEvent.keyDown(screen.getByPlaceholderText('Задайте вопрос...'), {key: 'Escape'});
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('clicking inside keeps the chat open, while the backdrop closes it', () => {
  render(<OpenDrawer />);
  fireEvent.click(screen.getByText('Спросите меня!'));
  const dialog = screen.getByRole('dialog', {name: '🤖 ИИ Помощник'});
  expect(dialog).toBeInTheDocument();
  // The backdrop is deliberately not exposed as an interactive control.
  // eslint-disable-next-line testing-library/no-node-access
  fireEvent.click(dialog.parentElement);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
});

test('safe-area padding protects the fixed header and composer without shrinking the close target', () => {
  const style = document.createElement('style');
  style.textContent = readFileSync(path.join(__dirname, 'AiAssistantDrawer.css'), 'utf8');
  document.head.appendChild(style);
  try {
    render(<OpenDrawer />);
    const rule = selector => Array.from(style.sheet.cssRules).find(item => item.selectorText === selector)?.style;
    const header = rule('.ai-assistant-header');
    const footer = rule('.ai-assistant-composer');
    expect(header.getPropertyValue('padding-top')).toBe('calc(16px + env(safe-area-inset-top, 0px))');
    expect(footer.getPropertyValue('padding-bottom')).toBe('calc(12px + env(safe-area-inset-bottom, 0px))');
    expect(header.getPropertyValue('flex-shrink')).toBe('0');
    expect(footer.getPropertyValue('flex-shrink')).toBe('0');
    const close = getComputedStyle(screen.getByRole('button', {name: 'Закрыть ИИ-помощника'}));
    expect(close.width).toBe('44px');
    expect(close.height).toBe('44px');
    expect(close.flexShrink).toBe('0');
    expect(rule('.ai-assistant-messages').getPropertyValue('min-height')).toBe('0');
    expect(rule('.ai-assistant-messages').getPropertyValue('overflow-y')).toBe('auto');
    // On phones the safe area belongs to the backdrop: the smaller card
    // stays inside it without adding the same inset to its header twice.
    const mobile = Array.from(style.sheet.cssRules).find(item => item.media?.mediaText === '(max-width: 640px)');
    const mobileRule = selector => Array.from(mobile.cssRules).find(item => item.selectorText === selector)?.style;
    expect(mobileRule('.ai-assistant-overlay').getPropertyValue('padding-top')).toBe('calc(12px + env(safe-area-inset-top, 0px))');
    expect(mobileRule('.ai-assistant-overlay').getPropertyValue('padding-bottom')).toBe('calc(12px + env(safe-area-inset-bottom, 0px))');
    expect(mobileRule('.ai-assistant-panel').getPropertyValue('height')).toBe('min(72dvh, 640px)');
    expect(mobileRule('.ai-assistant-panel').getPropertyValue('max-height')).toBe('100%');
    expect(mobileRule('.ai-assistant-header').getPropertyValue('padding')).toBe('6px 8px 6px 14px');
  } finally {
    style.remove();
  }
});
