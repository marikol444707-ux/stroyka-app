import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BudgetAdjustmentClientError } from '../features/estimates/projectBudgetAdjustmentActions';
import ProjectBudgetAdjustmentPanel from './ProjectBudgetAdjustmentPanel';

const HASH = 'a'.repeat(64);
const approvedReconciliations = [{
  id:15,
  status:'Утверждена',
  workPackage:'Отделка',
  baseEstimateName:'База',
  nextEstimateName:'Редакция',
}];

const preview = {
  reconciliationId:15,
  companyId:4,
  projectId:14,
  baseEstimateId:100,
  nextEstimateId:101,
  projectBudgetBefore:'1000000.00',
  estimateBaseTotal:'250000.00',
  estimateNextTotal:'275000.00',
  adjustmentAmount:'25000.00',
  projectBudgetAfter:'1025000.00',
  planSha256:HASH,
  readyForApproval:true,
  blockers:[],
};

const receipt = {
  id:9,
  ...preview,
  approvedByUserId:7,
  approvedByName:'Николай',
  approvedByRole:'директор',
  approvedAt:'2026-08-07T12:00:00+03:00',
  createdAt:'2026-08-07T12:00:00+03:00',
  idempotent:false,
};
delete receipt.readyForApproval;
delete receipt.blockers;

const renderPanel = (overrides = {}) => {
  const props = {
    project:{id:14,name:'Лицей'},
    approvedReconciliations,
    canManage:true,
    onLoadPreview:jest.fn().mockResolvedValue(preview),
    onApprove:jest.fn().mockResolvedValue(receipt),
    onLoadHistory:jest.fn().mockResolvedValue({projectId:14,items:[],nextBeforeId:null}),
    onApplied:jest.fn(),
    ...overrides,
  };
  render(<ProjectBudgetAdjustmentPanel {...props}/>);
  return props;
};

describe('ProjectBudgetAdjustmentPanel', () => {
  it('is absent for a user without effective leadership in the selected company', () => {
    renderPanel({canManage:false});

    expect(screen.queryByText('Изменение бюджета')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {name:/Рассчитать/})).not.toBeInTheDocument();
  });

  it('shows exact before, delta and after values before one explicit approval', async () => {
    const props = renderPanel();

    fireEvent.click(screen.getByRole('button', {name:/Рассчитать по сверке № 15/}));

    expect(await screen.findByText(/1.000.000,00 ₽/)).toBeInTheDocument();
    expect(screen.getByText(/\+25.000,00 ₽/)).toBeInTheDocument();
    expect(screen.getByText(/1.025.000,00 ₽/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name:'Подтвердить изменение бюджета'}));

    await waitFor(() => expect(props.onApprove).toHaveBeenCalledWith(15, HASH));
    expect(props.onApprove).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(props.onApplied).toHaveBeenCalledWith(receipt));
    expect(screen.queryByRole('button', {name:'Подтвердить изменение бюджета'})).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Бюджет изменён');
  });

  it('exposes loading state while the preview is requested', async () => {
    let resolvePreview;
    const onLoadPreview = jest.fn(() => new Promise(resolve => { resolvePreview = resolve; }));
    renderPanel({onLoadPreview});

    fireEvent.click(screen.getByRole('button', {name:/Рассчитать по сверке № 15/}));

    expect(screen.getByRole('button', {name:'Расчёт…'})).toBeDisabled();
    expect(screen.getByLabelText('Изменение бюджета')).toHaveAttribute('aria-busy', 'true');
    resolvePreview(preview);
    expect(await screen.findByRole('button', {name:'Подтвердить изменение бюджета'})).toBeInTheDocument();
  });

  it('forces a new preview after a stale approval and never mutates the displayed project', async () => {
    const project = {id:14,name:'Лицей',budget:'1000000.00'};
    const props = renderPanel({
      project,
      onApprove:jest.fn().mockRejectedValue(
        new BudgetAdjustmentClientError('budget_adjustment_plan_stale', 409),
      ),
    });

    fireEvent.click(screen.getByRole('button', {name:/Рассчитать по сверке № 15/}));
    fireEvent.click(await screen.findByRole('button', {name:'Подтвердить изменение бюджета'}));

    expect(await screen.findByRole('alert')).toHaveTextContent('Расчёт устарел');
    expect(screen.queryByRole('button', {name:'Подтвердить изменение бюджета'})).not.toBeInTheDocument();
    expect(screen.getByRole('button', {name:/Рассчитать по сверке № 15/})).toBeInTheDocument();
    expect(project.budget).toBe('1000000.00');
    expect(props.onApplied).not.toHaveBeenCalled();
  });

  it('loads immutable history only when the leader opens it', async () => {
    const onLoadHistory = jest.fn().mockResolvedValue({
      projectId:14,
      items:[receipt],
      nextBeforeId:null,
    });
    renderPanel({onLoadHistory});

    expect(onLoadHistory).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', {name:'Показать историю'}));

    expect(await screen.findByText('Николай · директор')).toBeInTheDocument();
    expect(screen.getByText(/\+25.000,00 ₽/)).toBeInTheDocument();
    expect(onLoadHistory).toHaveBeenCalledWith(14, {limit:25});
  });
});
