import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorkAssignmentModal, { performerRows } from './WorkAssignmentModal';

describe('work assignment performers', () => {
  it('offers a subcontractor as an estimate work assignee', () => {
    const rows = performerRows([], [
      { id: 11, name: 'ИП Исполнитель', role: 'субподрядчик' },
      { id: 12, name: 'Бухгалтер', role: 'бухгалтер' },
    ]);

    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({
      contractorId: 11,
      name: 'ИП Исполнитель',
      employmentType: 'субподрядчик',
    });
  });
});

describe('work assignment prices', () => {
  beforeEach(() => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ok: true, brigadeName: 'Бригада', items: [{}, {}], contractId: 77}),
    });
    Storage.prototype.getItem = jest.fn(() => 'token');
    window.alert = jest.fn();
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('applies the coefficient to all rows and sends one edited row as a manual price', async () => {
    render(
      <WorkAssignmentModal
        show
        onClose={jest.fn()}
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          sections: [{
            name: 'Монтаж',
            items: [
              {name: 'Блок управления', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
              {name: 'Прокладка кабеля', unit: 'м', quantity: 10, priceWork: 100, estimateItemKey: 'work-2'},
            ],
          }],
        }}
        staff={[]}
        users={[]}
        API="/api"
        loadAll={jest.fn()}
        C={{}}
        card={{}}
        inp={{}}
        btnO={{}}
        btnG={{}}
        btnB={{}}
        isMobile={false}
      />
    );

    fireEvent.change(screen.getByPlaceholderText('Или название бригады'), {target: {value: 'Бригада'}});
    fireEvent.change(screen.getByLabelText('Коэффициент'), {target: {value: '0.4'}});
    fireEvent.click(screen.getByRole('button', {name: 'Выбрать все'}));
    fireEvent.change(screen.getByLabelText('Цена исполнителю: Блок управления'), {target: {value: '1000'}});
    fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const request = global.fetch.mock.calls[0][1];
    const payload = JSON.parse(request.body);

    expect(payload.coefficient).toBe(0.4);
    expect(payload.items).toEqual([
      expect.objectContaining({estimateItemKey: 'work-1', priceMode: 'manual', manualPrice: 1000}),
      expect.objectContaining({estimateItemKey: 'work-2', priceMode: 'coefficient'}),
    ]);
    expect(payload.items[1].manualPrice).toBeUndefined();
  });
});
