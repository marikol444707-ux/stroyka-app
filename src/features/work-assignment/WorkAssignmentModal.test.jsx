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

  it('offers an existing brigade contract without forcing manual typing', () => {
    const rows = performerRows([], [], [
      { id: 70, brigadeName: 'Бригада Север', contractorType: 'Своя бригада' },
    ]);

    expect(rows).toEqual([
      expect.objectContaining({
        optionId: 'contract:70',
        contractorId: '',
        name: 'Бригада Север',
      }),
    ]);
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
    fireEvent.click(screen.getByRole('button', {name: 'Настроить цену'}));
    fireEvent.change(screen.getByLabelText('Коэффициент'), {target: {value: '0.4'}});
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

  it('selects only unassigned work by default and sends it in one action', async () => {
    render(
      <WorkAssignmentModal
        show
        onClose={jest.fn()}
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          workPackage: 'Основная',
          sections: [{
            name: 'Монтаж',
            items: [
              {name: 'Уже выданная работа', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
              {name: 'Новая работа', unit: 'м', quantity: 10, priceWork: 100, estimateItemKey: 'work-2'},
            ],
          }],
        }}
        brigadeContracts={[{id: 70, projectName: 'Объект', workPackage: 'Основная', brigadeName: 'Бригада 1'}]}
        brigadeContractItems={[{
          id: 701,
          contractId: 70,
          projectName: 'Объект',
          workPackage: 'Основная',
          estimateItemKey: 'work-1',
        }]}
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

    expect(screen.queryByText('Уже выданная работа')).not.toBeInTheDocument();
    expect(screen.getByText('Новая работа')).toBeInTheDocument();
    expect(screen.getByText('Уже назначено: 1')).toBeInTheDocument();
    expect(screen.getByText('Выбрано: 1 из 1')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Настроить цену'})).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Ручная'})).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Или название бригады'), {target: {value: 'Бригада 2'}});
    fireEvent.click(screen.getByRole('button', {name: 'Выдать в работу'}));

    await waitFor(() => expect(global.fetch).toHaveBeenCalledTimes(1));
    const payload = JSON.parse(global.fetch.mock.calls[0][1].body);
    expect(payload.items).toEqual([
      expect.objectContaining({estimateItemKey: 'work-2'}),
    ]);
  });

  it('explains when every estimate row is already assigned', () => {
    render(
      <WorkAssignmentModal
        show
        onClose={jest.fn()}
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          workPackage: 'Основная',
          sections: [{name: 'Монтаж', items: [
            {name: 'Монтаж шкафа', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
          ]}],
        }}
        brigadeContracts={[{id: 70, projectName: 'Объект', workPackage: 'Основная', brigadeName: 'Бригада 1'}]}
        brigadeContractItems={[{
          id: 701,
          contractId: 70,
          projectName: 'Объект',
          workPackage: 'Основная',
          estimateItemKey: 'work-1',
        }]}
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

    expect(screen.getByText('Все работы этой сметы уже назначены')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Снять все'})).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Выдать в работу'})).toBeDisabled();
  });
});
