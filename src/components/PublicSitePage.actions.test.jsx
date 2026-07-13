import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import PublicSitePage from './PublicSitePage';

describe('public project actions', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    Element.prototype.scrollIntoView = jest.fn();
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      json: async () => ({}),
    });
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  const flushActions = () => {
    act(() => {
      jest.runOnlyPendingTimers();
    });
  };

  test('shows a mirrored project result at the preview', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Показать зеркальный вариант' }));
    flushActions();

    expect(screen.getByRole('button', { name: 'Вернуть обычный вариант' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('status')).toHaveTextContent('Зеркальный вариант включён');
    expect(document.getElementById('selected-project-preview').scrollIntoView).toHaveBeenCalled();
  });

  test('opens the next similar project at the preview', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);
    const initialTitle = document.querySelector('.public-project-spec-column h3').textContent;

    fireEvent.click(screen.getByRole('button', { name: /Похожие по виду/ }));
    flushActions();

    expect(document.querySelector('.public-project-spec-column h3')).not.toHaveTextContent(initialTitle);
    expect(screen.getByRole('status')).toHaveTextContent('Открыт похожий проект');
    expect(document.getElementById('selected-project-preview').scrollIntoView).toHaveBeenCalled();
  });

  test('collects layout changes and opens a prefilled request', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить планировку в заявке' }));
    expect(screen.getByRole('region', { name: 'Пожелания к планировке' })).toBeInTheDocument();

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Спален' }), { target: { value: '4' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Санузлов' }), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Нужен гараж' }));
    fireEvent.change(screen.getByRole('textbox', { name: 'Дополнительные пожелания' }), {
      target: { value: 'Добавить постирочную рядом с санузлом' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить в заявку' }));
    flushActions();

    expect(document.getElementById('request').scrollIntoView).toHaveBeenCalled();
    expect(screen.getByLabelText('Комментарий').value).toContain('4 спальни');
    expect(screen.getByLabelText('Комментарий').value).toContain('2 санузла');
    expect(screen.getByLabelText('Комментарий').value).toContain('гараж нужен');
    expect(screen.getByLabelText('Комментарий').value).toContain('Добавить постирочную рядом с санузлом');
    expect(screen.queryByRole('region', { name: 'Пожелания к планировке' })).not.toBeInTheDocument();
  });

  test('opens the calculator with the selected project', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: /Рассчитать такой проект/ }));
    flushActions();

    expect(document.getElementById('calculator').scrollIntoView).toHaveBeenCalled();
    expect(screen.getByRole('status')).toHaveTextContent('Проект передан в калькулятор');
  });
});
