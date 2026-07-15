import { render, screen } from '@testing-library/react';
import EstimateSectionsEditor from './EstimateSectionsEditor';

describe('EstimateSectionsEditor', () => {
  it('keeps assignment fields out of the main estimate table', () => {
    render(
      <EstimateSectionsEditor
        selectedEstimate={{
          id: 25,
          projectName: 'Объект',
          sections: [{
            id: 1,
            name: 'Монтаж',
            items: [{
              id: 10,
              type: 'work',
              name: 'Монтаж шкафа',
              unit: 'шт',
              quantity: 5,
              priceWork: 2000,
              doneQuantity: 2,
              brigadeName: 'Старая бригада',
              executionPricePerUnit: 800,
            }],
          }],
        }}
        showEstimateIssuesOnly={false}
        mobileExpandedRenderLists={{}}
        setMobileExpandedRenderLists={jest.fn()}
        isMobile={false}
        estimateQualityRows={() => []}
        brigadeContracts={[]}
        userRole="директор"
        setSelectedEstimate={jest.fn()}
        setEstimatesList={jest.fn()}
        persistEstimate={jest.fn()}
        newEstimateItem={{sectionId: '', name: '', quantity: '', priceWork: '', priceMaterial: ''}}
        setNewEstimateItem={jest.fn()}
        estimateIssueFocusKey=""
      />
    );

    expect(screen.getByRole('columnheader', {name: 'Наименование'})).toBeInTheDocument();
    expect(screen.getByRole('columnheader', {name: 'План'})).toBeInTheDocument();
    expect(screen.getByRole('columnheader', {name: 'Цена'})).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', {name: 'Кому'})).not.toBeInTheDocument();
    expect(screen.queryByRole('columnheader', {name: 'Внутр.'})).not.toBeInTheDocument();
    const completedValue = screen.getByLabelText('Выполнено: Монтаж шкафа');
    expect(completedValue.tagName).toBe('SPAN');
    expect(completedValue).toHaveTextContent('2 шт');
  });
});
