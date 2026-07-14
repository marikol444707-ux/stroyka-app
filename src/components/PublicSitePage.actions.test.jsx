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

  test('collects plot details for the request without changing the estimate', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);
    const initialEstimate = document.querySelector('.public-result-main strong').textContent;

    fireEvent.change(screen.getByRole('combobox', { name: 'Статус участка' }), { target: { value: 'owned' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Подъезд для техники' }), { target: { value: 'good' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Рельеф' }), { target: { value: 'flat' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Коммуникации' }), { target: { value: 'boundary' } });
    fireEvent.click(screen.getByRole('checkbox', { name: 'Геология уже есть' }));
    fireEvent.click(screen.getByRole('checkbox', { name: 'Геодезия уже есть' }));

    expect(screen.getByRole('region', { name: 'Предварительная проверка участка' })).toHaveTextContent('Основные данные указаны');
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Участок: заполнено 6 из 6 · проверить пунктов: 0');
    expect(document.querySelector('.public-result-main strong').textContent.replace(/\s/g, ' '))
      .toBe(initialEstimate.replace(/\s/g, ' '));
  });

  test('selects a house package and carries it into the calculator and request', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);
    const initialEstimate = document.querySelector('.public-project-cost-panel strong').textContent;

    expect(screen.getAllByRole('radio', { name: /Коробка|Тёплый контур|Под ключ/ })).toHaveLength(3);
    fireEvent.click(screen.getByRole('radio', { name: /Тёплый контур/ }));
    flushActions();

    expect(screen.getByRole('radio', { name: /Тёплый контур/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByRole('combobox', { name: 'Комплектация' })).toHaveValue('warm');
    expect(document.querySelector('.public-project-cost-panel strong')).not.toHaveTextContent(initialEstimate);
    expect(screen.getByLabelText('Комментарий').value).toContain('Комплектация: Тёплый контур');
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Тёплый контур');
    expect(screen.getByRole('status')).toHaveTextContent('Выбрана комплектация «Тёплый контур»');
    expect(screen.getByRole('region', { name: 'Примерный график этапов и платежей' })).toHaveTextContent('5 этапов');

    fireEvent.change(screen.getByRole('combobox', { name: 'Комплектация' }), { target: { value: 'box' } });
    expect(screen.getByRole('radio', { name: /Коробка/ })).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText('Комментарий').value).toContain('Комплектация: Коробка');
    expect(screen.getByRole('region', { name: 'Примерный график этапов и платежей' })).toHaveTextContent('4 этапа');
  });

  test('keeps the mirrored variant when the project is sent to the calculator', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Показать зеркальный вариант' }));
    fireEvent.click(screen.getByRole('button', { name: /Рассчитать такой проект/ }));
    flushActions();

    expect(screen.getByRole('button', { name: 'Вернуть обычный вариант' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByLabelText('Комментарий').value).toContain('Вариант: зеркальный');
    expect(document.getElementById('calculator').scrollIntoView).toHaveBeenCalled();
  });

  test('keeps layout preferences when the mirrored variant changes', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить планировку в заявке' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Спален' }), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить в заявку' }));
    flushActions();

    fireEvent.click(screen.getByRole('button', { name: 'Показать зеркальный вариант' }));
    flushActions();

    expect(screen.getByLabelText('Комментарий').value).toContain('4 спальни');
    expect(screen.getByLabelText('Комментарий').value).toContain('Вариант: зеркальный');
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Зеркальный вариант · 4 спальни');
  });

  test('resets project-specific options when a similar project is selected', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить планировку в заявке' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Спален' }), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить в заявку' }));
    flushActions();
    fireEvent.click(screen.getByRole('button', { name: 'Показать зеркальный вариант' }));
    fireEvent.click(screen.getByRole('button', { name: /Похожие по виду/ }));
    flushActions();

    expect(screen.getByRole('button', { name: 'Показать зеркальный вариант' })).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByLabelText('Комментарий').value).not.toContain('Вариант: зеркальный');
    expect(document.querySelector('.public-request-selected')).not.toHaveTextContent('4 спальни');
  });

  test('reopens the layout editor with the saved preferences', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Изменить планировку в заявке' }));
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Спален' }), { target: { value: '5' } });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Санузлов' }), { target: { value: '3' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Дополнительные пожелания' }), {
      target: { value: 'Кабинет рядом со входом' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить в заявку' }));
    flushActions();

    fireEvent.click(screen.getByRole('button', { name: 'Изменить планировку в заявке' }));

    expect(screen.getByRole('spinbutton', { name: 'Спален' })).toHaveValue(5);
    expect(screen.getByRole('spinbutton', { name: 'Санузлов' })).toHaveValue(3);
    expect(screen.getByRole('textbox', { name: 'Дополнительные пожелания' })).toHaveValue('Кабинет рядом со входом');
  });
});
