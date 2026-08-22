import React from 'react';
import { render, screen } from '@testing-library/react';

import WarehousePage from './WarehousePage';

jest.mock('../features/human-approved-actions/HumanApprovedActionReviewPanel', () => props => (
  <div data-testid="human-action-panel">
    {props.API}|{props.companyMode}|{props.selectedCompanyId}|{props.user?.role}|{props.projects?.length}
  </div>
));
jest.mock('./WarehouseMaterialControlOverview', () => () => <div>material-control</div>);
jest.mock('./WarehouseTabsNav', () => () => <div>tabs</div>);
jest.mock('./WarehouseInvoicesPanel', () => () => null);
jest.mock('./WarehouseMainStockPanel', () => () => null);
jest.mock('./WarehouseCompanyWarehousesPanel', () => () => null);
jest.mock('./WarehouseHistoryPanel', () => () => null);
jest.mock('./WarehouseOperationsPanel', () => () => null);
jest.mock('./WarehouseObjectsPanel', () => () => null);

test('mounts the default-off human review panel only in warehouse control with exact company context', () => {
  const props = {
    API: '/api',
    C: {},
    card: {},
    companyContext: { mode: 'company', selectedCompanyId: 4 },
    projects: [{ id: 17, companyId: 4, name: 'Школа' }],
    user: { role: 'директор' },
    visibleActiveProjects: value => value,
    warehouseTab: 'control',
  };
  const view = render(<WarehousePage {...props} />);

  expect(screen.getByTestId('human-action-panel')).toHaveTextContent(
    '/api|company|4|директор|1',
  );
  view.rerender(<WarehousePage {...props} warehouseTab="invoices" />);
  expect(screen.queryByTestId('human-action-panel')).not.toBeInTheDocument();
});
