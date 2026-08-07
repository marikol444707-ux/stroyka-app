import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import EstimateReconciliationsPanel from './EstimateReconciliationsPanel';

const estimate = (id, status, quantity) => ({
  id,
  projectId: 7,
  projectName: 'Лицей',
  smetaType: 'Заказчик',
  workPackage: 'Отделка',
  status,
  version: String(id),
  sections: [{name:'Стены',items:[{name:'Штукатурка',quantity}]}],
});

describe('EstimateReconciliationsPanel', () => {
  it('opens one project summary with the previous and active estimate revisions', () => {
    const onOpenProjectSummary = jest.fn();
    const base = estimate(1, 'Черновик', 80);
    const active = estimate(2, 'Активная', 90);

    render(
      <EstimateReconciliationsPanel
        project={{id:7,name:'Лицей'}}
        reconciliations={[]}
        projectEstimates={[base, active]}
        estimatePackage={row => row.workPackage}
        estimateTotal={row => row.sections[0].items[0].quantity}
        canApprove
        onApprove={jest.fn()}
        onCreate={jest.fn()}
        onOpenPreview={jest.fn()}
        onOpenProjectSummary={onOpenProjectSummary}
      />,
    );

    fireEvent.click(screen.getByRole('button', {name:/Свод изменений/}));

    expect(onOpenProjectSummary).toHaveBeenCalledWith('Лицей', [{base, next:active}]);
  });

  it('keeps reconciliation approval separate from budget adjustment approval', () => {
    const onApprove = jest.fn();
    const onLoadBudgetAdjustmentPreview = jest.fn();
    const draft = {
      id:8,
      status:'Черновик',
      baseEstimateId:1,
      nextEstimateId:2,
      baseEstimateName:'База',
      nextEstimateName:'Редакция',
    };

    render(
      <EstimateReconciliationsPanel
        project={{id:7,name:'Лицей'}}
        reconciliations={[draft]}
        projectEstimates={[]}
        estimatePackage={row => row.workPackage}
        estimateTotal={() => 0}
        canApprove
        canAdjustBudget
        onApprove={onApprove}
        onCreate={jest.fn()}
        onOpenPreview={jest.fn()}
        onOpenProjectSummary={jest.fn()}
        onLoadBudgetAdjustmentPreview={onLoadBudgetAdjustmentPreview}
        onApproveBudgetAdjustment={jest.fn()}
        onLoadBudgetAdjustmentHistory={jest.fn()}
        onBudgetAdjustmentApplied={jest.fn()}
      />,
    );

    fireEvent.click(screen.getByRole('button', {name:'Утвердить'}));

    expect(onApprove).toHaveBeenCalledWith(draft);
    expect(onLoadBudgetAdjustmentPreview).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', {name:/Рассчитать по сверке/})).not.toBeInTheDocument();
  });
});
