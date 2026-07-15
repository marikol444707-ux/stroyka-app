import { fireEvent, render, screen } from '@testing-library/react';
import EstimateDuplicateWorkSummaryPanel from './EstimateDuplicateWorkSummaryPanel';
import { buildEstimateMaterialSummary, buildEstimateWorkSummary, estimateIssueDomId } from '../utils/estimateUtils';

describe('EstimateDuplicateWorkSummaryPanel', () => {
  it('switches between repeated works and repeated materials', () => {
    const selectedEstimate = {
      id: 25,
      workPackage: 'Электрика',
      sections: [
        {
          name: 'Первый этаж',
          items: [
            {type: 'work', name: 'Монтаж шкафа', unit: 'шт', quantity: 1, priceWork: 2000},
            {type: 'material', name: 'Краска', unit: 'кг', quantity: 10, priceMaterial: 100},
          ],
        },
        {
          name: 'Второй этаж',
          items: [
            {type: 'work', name: 'Монтаж шкафа', unit: 'шт', quantity: 2, priceWork: 2000},
            {type: 'material', name: 'краска.', unit: 'кг', quantity: 5, priceMaterial: 100},
          ],
        },
      ],
    };

    render(
      <EstimateDuplicateWorkSummaryPanel
        selectedEstimate={selectedEstimate}
        userRole="директор"
        isMobile={false}
        showEstimateWorkSummary
        setShowEstimateWorkSummary={jest.fn()}
        setShowEstimateIssuesOnly={jest.fn()}
        setMobileExpandedRenderLists={jest.fn()}
        buildEstimateWorkSummary={buildEstimateWorkSummary}
        buildEstimateMaterialSummary={buildEstimateMaterialSummary}
        estimateIssueDomId={estimateIssueDomId}
      />
    );

    expect(screen.getByRole('button', {name: 'Работы (1)'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Материалы (1)'})).toBeInTheDocument();
    expect(screen.getByText('Монтаж шкафа')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Материалы (1)'}));

    expect(screen.getByText('Краска')).toBeInTheDocument();
    expect(screen.queryByText('Монтаж шкафа')).not.toBeInTheDocument();
  });
});
