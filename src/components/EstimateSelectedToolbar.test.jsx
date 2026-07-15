import { render, screen } from '@testing-library/react';
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
    expect(screen.getByRole('button', { name: 'Назначить исполнителю' })).toBeInTheDocument();
  });
});
