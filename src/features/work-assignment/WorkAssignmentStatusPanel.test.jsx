import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import WorkAssignmentStatusPanel from './WorkAssignmentStatusPanel';

describe('WorkAssignmentStatusPanel', () => {
  const colors = {
    text: '#111', textSec: '#555', textMuted: '#777', success: '#080',
    warning: '#b70', accent: '#08c', border: '#ddd', bg: '#f5f5f5',
    bgWhite: '#fff', warningBorder: '#db8', warningLight: '#fff8e6',
    successBorder: '#ada', successLight: '#f0fff0', danger: '#c00',
    dangerBorder: '#eaa', dangerLight: '#fff0f0',
  };

  const estimate = {id: 25, projectName: 'Объект', workPackage: 'Основная', sections: [{
    name: 'Монтаж', items: [
      {name: 'Монтаж шкафа', unit: 'шт', quantity: 1, priceWork: 2000, estimateItemKey: 'work-1'},
      {name: 'Прокладка кабеля', unit: 'м', quantity: 10, priceWork: 100, estimateItemKey: 'work-2'},
    ],
  }]};
  const assignedItem = {
    id: 701, contractId: 70, projectName: 'Объект', workPackage: 'Основная',
    estimateItemKey: 'work-1', name: 'Монтаж шкафа', unit: 'шт', quantity: 1,
    priceBrigade: 1200, doneQuantity: 0,
  };

  function renderAssigned(props = {}) {
    return render(<WorkAssignmentStatusPanel
      selectedEstimate={estimate}
      brigadeContracts={[{id: 70, projectName: 'Объект', workPackage: 'Основная', brigadeName: 'Мастер Иван'}]}
      brigadeContractItems={[assignedItem]}
      API="/api" loadAll={jest.fn()} C={colors} card={{}} btnG={{}} btnR={{}}
      isMobile={false} showLeadership {...props}
    />);
  }

  it('shows assignment status without a duplicate assign action', () => {
    render(
      <WorkAssignmentStatusPanel
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          sections: [{
            name: 'Монтаж',
            items: [{name: 'Монтаж шкафа', unit: 'шт', quantity: 1, priceWork: 2000}],
          }],
        }}
        brigadeContracts={[]}
        brigadeContractItems={[]}
        API="/api"
        loadAll={jest.fn()}
        C={{
          text: '#111',
          textSec: '#555',
          textMuted: '#777',
          success: '#080',
          warning: '#b70',
          accent: '#08c',
          border: '#ddd',
          bg: '#f5f5f5',
          bgWhite: '#fff',
          warningBorder: '#db8',
          warningLight: '#fff8e6',
          successBorder: '#ada',
          successLight: '#f0fff0',
          danger: '#c00',
          dangerBorder: '#eaa',
          dangerLight: '#fff0f0',
        }}
        card={{}}
        btnG={{}}
        btnR={{}}
        isMobile={false}
        showLeadership
      />
    );

    expect(screen.getByText('Назначенные работы')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Назначить'})).not.toBeInTheDocument();
    expect(screen.queryByText('Монтаж шкафа')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Показать работы (1)'}));

    expect(screen.getByText('Монтаж шкафа')).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Скрыть работы'})).toBeInTheDocument();
  });

  it('separates issued and remaining work in the opened list', () => {
    renderAssigned();
    fireEvent.click(screen.getByRole('button', {name: /Показать работы/}));

    expect(screen.getByText('Монтаж шкафа')).toBeInTheDocument();
    expect(screen.queryByText('Прокладка кабеля')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Не выдано (1)'}));
    expect(screen.getByText('Прокладка кабеля')).toBeInTheDocument();
    expect(screen.queryByText('Монтаж шкафа')).not.toBeInTheDocument();
  });

  it('confirms removal inside the row and explains a failed request', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockRejectedValueOnce(new Error('offline'));
    const loadAll = jest.fn();
    renderAssigned({loadAll});
    fireEvent.click(screen.getByRole('button', {name: /Показать работы/}));
    fireEvent.click(screen.getByRole('button', {name: /Снять назначение/}));
    expect(fetchMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', {name: 'Подтвердить снятие'}));
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Не удалось снять назначение'));
    expect(loadAll).not.toHaveBeenCalled();
    fetchMock.mockRestore();
  });

  it('keeps a completed removal hidden when the follow-up refresh fails', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValueOnce({ok: true, json: async () => ({ok: true})});
    renderAssigned({loadAll: jest.fn().mockRejectedValueOnce(new Error('refresh failed'))});
    fireEvent.click(screen.getByRole('button', {name: /Показать работы/}));
    fireEvent.click(screen.getByRole('button', {name: /Снять назначение/}));
    fireEvent.click(screen.getByRole('button', {name: 'Подтвердить снятие'}));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Обновите страницу'));
    expect(screen.queryByText('Мастер Иван')).not.toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith('/api/brigade-contract-items/701', {method: 'DELETE'});
    fetchMock.mockRestore();
  });

  it('explains why completed work cannot be removed', () => {
    renderAssigned({brigadeContractItems: [{...assignedItem, doneQuantity: 1}], isMobile: true});
    fireEvent.click(screen.getByRole('button', {name: /Показать работы/}));

    expect(screen.getByText('Снять нельзя: есть выполненный объём')).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: /Снять назначение/})).not.toBeInTheDocument();
  });

  it('shows the server reason when removal is blocked by linked work records', async () => {
    const fetchMock = jest.spyOn(global, 'fetch').mockResolvedValueOnce({
      ok: false,
      json: async () => ({detail: 'Позиция связана с фактическим расходом по работе и не может быть удалена'}),
    });
    renderAssigned();
    fireEvent.click(screen.getByRole('button', {name: /Показать работы/}));
    fireEvent.click(screen.getByRole('button', {name: /Снять назначение/}));
    fireEvent.click(screen.getByRole('button', {name: 'Подтвердить снятие'}));

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('фактическим расходом'));
    expect(screen.getByText('Мастер Иван')).toBeInTheDocument();
    fetchMock.mockRestore();
  });
});
