import React from 'react';
import {act, fireEvent, render, screen} from '@testing-library/react';
import {readFileSync} from 'fs';
import AiAssistantDrawer from './AiAssistantDrawer';

const props = () => ({showAiAssistant: true, setShowAiAssistant: jest.fn(), C: {}, inp: {fontSize: '13px'}, btnG: {}, btnO: {},
  aiChat: [], aiLoading: false, aiMessage: '10 мм', setAiMessage: jest.fn(), sendAiMessage: jest.fn(), chatEndRef: {current: null}});
let originalViewport;
beforeEach(() => {originalViewport = window.visualViewport;});
afterEach(() => Object.defineProperty(window, 'visualViewport', {configurable: true, value: originalViewport}));

function mockViewport() {
  const listeners = {};
  const viewport = {height: 844, offsetTop: 0, scale: 1,
    addEventListener: jest.fn((name, fn) => {listeners[name] = fn;}),
    removeEventListener: jest.fn((name) => {delete listeners[name];})};
  Object.defineProperty(window, 'visualViewport', {configurable: true, value: viewport});
  return {viewport, resize: () => act(() => listeners.resize?.()), scroll: () => act(() => listeners.scroll?.())};
}

test('follows keyboard visual viewport height/offset and cleans up on close and reopen', () => {
  const {viewport, resize, scroll} = mockViewport();
  const inputProps = props();
  const {container, rerender, unmount} = render(<AiAssistantDrawer {...inputProps}/>);
  const overlay = container.querySelector('.ai-assistant-overlay');
  expect(overlay.style.height).toBe('844px');
  viewport.height = 420; viewport.offsetTop = 37; resize();
  expect(overlay.style.height).toBe('420px');
  expect(overlay.style.top).toBe('37px');
  viewport.offsetTop = 42; scroll();
  expect(overlay.style.top).toBe('42px');
  viewport.scale = 2; viewport.height = 200; resize();
  expect(overlay.style.height).toBe('420px');
  fireEvent.click(screen.getByRole('button', {name: 'Закрыть помощника'}));
  expect(inputProps.setShowAiAssistant).toHaveBeenCalledWith(false);
  rerender(<AiAssistantDrawer {...inputProps} showAiAssistant={false}/>);
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  expect(viewport.removeEventListener).toHaveBeenCalledTimes(2);
  viewport.scale = 1; viewport.height = 844; viewport.offsetTop = 0;
  rerender(<AiAssistantDrawer {...inputProps}/>);
  expect(container.querySelector('.ai-assistant-overlay').style.height).toBe('844px');
  unmount();
  expect(viewport.removeEventListener).toHaveBeenCalledTimes(4);
});

test('CSS fallback supports safe areas, dynamic height and a scrollable flex body without touching global styles', () => {
  Object.defineProperty(window, 'visualViewport', {configurable: true, value: undefined});
  const {container} = render(<AiAssistantDrawer {...props()}/>);
  expect(container.querySelector('.ai-assistant-overlay').style.height).toBe('');
  const css = readFileSync(`${__dirname}/AiAssistantDrawer.css`, 'utf8');
  expect(css).toMatch(/height: 100vh;\s*height: 100dvh/);
  expect(css).toContain('env(safe-area-inset-top, 0px)');
  expect(css).toContain('env(safe-area-inset-bottom, 0px)');
  expect(css).toMatch(/\.ai-assistant-messages\s*\{[^}]*min-height: 0;[^}]*overflow-y: auto;/);
  expect(css).toMatch(/\.ai-assistant-composer\s*\{[^}]*flex-shrink: 0;/);
  expect(css).toContain('.ai-assistant-input { font-size: 16px; }');
  expect(css).not.toMatch(/(^|\})\s*(body|html|input|button)\s*\{/);
});

test('input prevents IME sends, enforces request limit and offers accessible close/send controls', () => {
  const inputProps = props();
  const {rerender} = render(<AiAssistantDrawer {...inputProps}/>);
  const input = screen.getByRole('textbox', {name: 'Вопрос помощнику'});
  expect(screen.getByText('Материалы, работы и данные вашей компании')).toBeInTheDocument();
  expect(screen.queryByText('Знает нормы СНиП, расценки, материалы')).not.toBeInTheDocument();
  expect(input).toHaveAttribute('maxlength', '8000');
  expect(input.style.fontSize).toBe('');
  fireEvent.keyDown(input, {key: 'Enter', isComposing: true});
  expect(inputProps.sendAiMessage).not.toHaveBeenCalled();
  fireEvent.keyDown(input, {key: 'Enter'});
  expect(inputProps.sendAiMessage).toHaveBeenCalledTimes(1);
  rerender(<AiAssistantDrawer {...inputProps} aiLoading/>);
  expect(input).toBeDisabled();
  expect(screen.getByRole('button', {name: 'Отправить вопрос'})).toBeDisabled();
  rerender(<AiAssistantDrawer {...inputProps} aiMessage="   "/>);
  expect(screen.getByRole('button', {name: 'Отправить вопрос'})).toBeDisabled();
});
