import { fireEvent, render, screen } from '@testing-library/react';
import EstimateSelectedToolbar from './EstimateSelectedToolbar';

const style = {};

describe('EstimateSelectedToolbar', () => {
  it('does not show the unused estimate chat action', () => {
    render(
      <EstimateSelectedToolbar
        C={{ bg: '#fff', danger: '#c00', dangerBorder: '#c00' }}
        badge={() => style}
        btnB={style}
        btnG={style}
        btnGr={style}
        btnO={style}
        estimateKind={() => ({ label: 'Смета' })}
        estimatePackage={() => 'Общестрой'}
        estimateStatusView={() => ({ label: 'Активная' })}
        estimateTypeIcon={() => null}
        estimatesList={[]}
        hasDiff={false}
        issueCount={0}
        sameEstimateGroup={() => false}
        selectedEstimate={{ name: 'Тестовая смета', status: 'Активная' }}
        showLeadership
      />,
    );

    expect(screen.queryByRole('button', { name: 'Чат' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Назначить работы' })).toBeInTheDocument();
  });

  it('keeps primary actions visible and moves service actions into the more menu', () => {
    const onExport = jest.fn();
    const setEstimateStatusRemote = jest.fn();
    const selectedEstimate = { name: 'Тестовая смета', status: 'Активная' };
    render(
      <EstimateSelectedToolbar
        C={{ bg: '#fff', bgWhite: '#fff', border: '#ddd', text: '#111', danger: '#c00', dangerBorder: '#c00' }}
        badge={() => style}
        btnB={style}
        btnG={style}
        btnGr={style}
        btnO={style}
        estimateKind={() => ({ label: 'Смета' })}
        estimatePackage={() => 'Общестрой'}
        estimateStatusView={() => ({ label: 'Активная' })}
        estimateTypeIcon={() => null}
        estimatesList={[]}
        hasDiff
        issueCount={3}
        onAiAnalysis={jest.fn()}
        onBack={jest.fn()}
        onDetectHiddenWorks={jest.fn()}
        onExport={onExport}
        onHistory={jest.fn()}
        onNormalize={jest.fn()}
        onOpenDistribute={jest.fn()}
        onOpenWorkAssignment={jest.fn()}
        onPreview={jest.fn()}
        onCreateReconciliation={jest.fn()}
        onShowDiff={jest.fn()}
        onToggleIssuesOnly={jest.fn()}
        onToggleTemplate={jest.fn()}
        sameEstimateGroup={() => false}
        selectedEstimate={selectedEstimate}
        setEstimateStatusRemote={setEstimateStatusRemote}
        showLeadership
      />,
    );

    expect(screen.getByRole('button', {name: 'Проблемы: 3'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Просмотр'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Назначить работы'})).toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Excel'})).not.toBeInTheDocument();
    expect(screen.queryByRole('button', {name: 'Расширенное распределение'})).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Ещё'}));

    expect(screen.getByRole('button', {name: 'Excel'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'Расширенное распределение'})).toBeInTheDocument();
    expect(screen.getByRole('button', {name: 'ИИ-анализ'})).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Excel'}));
    expect(onExport).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', {name: 'Excel'})).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', {name: 'Ещё'}));
    fireEvent.click(screen.getByRole('button', {name: 'Снять активность'}));
    expect(setEstimateStatusRemote).toHaveBeenCalledWith(selectedEstimate, 'Черновик');
    expect(screen.queryByRole('button', {name: 'Снять активность'})).not.toBeInTheDocument();
  });
});
