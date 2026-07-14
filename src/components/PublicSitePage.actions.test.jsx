import React from 'react';
import { act, fireEvent, render, screen } from '@testing-library/react';
import PublicSitePage from './PublicSitePage';

describe('public project actions', () => {
  beforeEach(() => {
    jest.useFakeTimers();
    window.history.replaceState({}, '', '/');
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
    delete navigator.share;
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

  test('compares projects and selects one for the calculation', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Добавить H1-01 к сравнению' }));
    fireEvent.click(screen.getByRole('button', { name: /H1-02.*Дом 116 м2 с кухней-гостиной/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Добавить H1-02 к сравнению' }));

    const comparison = screen.getByRole('region', { name: 'Сравнение проектов' });
    expect(comparison).toHaveTextContent('Одноэтажный кирпичный дом 110 м2');
    expect(comparison).toHaveTextContent('Дом 116 м2 с кухней-гостиной');
    expect(comparison).toHaveTextContent('2 из 3');
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Сравнивались: H1-01, H1-02');

    fireEvent.click(screen.getByRole('button', { name: 'Выбрать H1-01 для расчёта' }));
    expect(document.querySelector('.public-project-spec-column h3')).toHaveTextContent('Одноэтажный кирпичный дом 110 м2');
    expect(screen.getByRole('status')).toHaveTextContent('Выбран проект H1-01');
  });

  test('clears comparison when another project direction opens', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Добавить H1-01 к сравнению' }));
    expect(screen.getByRole('region', { name: 'Сравнение проектов' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /Одноэтажный дом из кирпича.*Смотреть проекты/ }));

    expect(screen.queryByRole('region', { name: 'Сравнение проектов' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Добавить B1-01 к сравнению' })).toBeInTheDocument();
  });

  test('opens the same project comparison from a shared URL', async () => {
    window.history.replaceState({}, '', '/?project=H1-02&compare=H1-01%2CH1-02#projects');

    render(<PublicSitePage onLogin={jest.fn()} />);

    const comparison = await screen.findByRole('region', { name: 'Сравнение проектов' });
    expect(comparison).toHaveTextContent('Одноэтажный кирпичный дом 110 м2');
    expect(comparison).toHaveTextContent('Дом 116 м2 с кухней-гостиной');
    expect(comparison).toHaveTextContent('2 из 3');
    expect(document.querySelector('.public-project-spec-column h3')).toHaveTextContent('Дом 116 м2 с кухней-гостиной');
  });

  test('shares the selected project and comparison list', async () => {
    const share = jest.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'share', { value: share, configurable: true });
    render(<PublicSitePage onLogin={jest.fn()} />);

    fireEvent.click(screen.getByRole('button', { name: 'Добавить H1-01 к сравнению' }));
    fireEvent.click(screen.getByRole('button', { name: /H1-02.*Дом 116 м2 с кухней-гостиной/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Добавить H1-02 к сравнению' }));
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Поделиться сравнением' }));
      await Promise.resolve();
    });

    expect(share).toHaveBeenCalledTimes(1);
    const sharedUrl = new URL(share.mock.calls[0][0].url);
    expect(sharedUrl.searchParams.get('project')).toBe('H1-02');
    expect(sharedUrl.searchParams.get('compare')).toBe('H1-01,H1-02');
    expect(sharedUrl.hash).toBe('#projects');
  }, 15000);

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

  test('adds a selected mortgage or installment scenario to the request', () => {
    render(<PublicSitePage onLogin={jest.fn()} />);

    const financing = screen.getByRole('region', { name: 'Ипотека и рассрочка' });
    expect(financing).toHaveTextContent('Предварительный платёж');
    expect(screen.getByRole('radio', { name: 'Ипотека' })).toHaveAttribute('aria-checked', 'true');

    fireEvent.change(screen.getByRole('spinbutton', { name: 'Первоначальный взнос, %' }), {
      target: { value: '25' },
    });
    fireEvent.change(screen.getByRole('spinbutton', { name: 'Примерная ставка, % годовых' }), {
      target: { value: '15' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Добавить ипотеку в заявку' }));

    expect(financing).toHaveTextContent('Ипотека добавлена в заявку');
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Ипотека на строительство');

    fireEvent.click(screen.getByRole('radio', { name: 'Рассрочка' }));
    expect(screen.queryByRole('spinbutton', { name: 'Примерная ставка, % годовых' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Добавить рассрочку в заявку' }));

    expect(financing).toHaveTextContent('Рассрочка добавлена в заявку');
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Рассрочка по договору');

    fireEvent.click(document.querySelector('.public-project-decision-actions .public-primary'));
    flushActions();

    expect(document.getElementById('request').scrollIntoView).toHaveBeenCalled();
    expect(document.querySelector('.public-request-selected')).toHaveTextContent('Рассрочка по договору');
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
