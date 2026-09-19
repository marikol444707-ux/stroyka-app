import React from 'react';
import { render, screen } from '@testing-library/react';
import WarehousePage from './WarehousePage';

jest.mock('../features/inventory-reconciliation/InventoryWorkspace', () => ({
  __esModule: true,
  default: props => <div data-testid="inventory-workspace">{props.API}|{props.companyContext?.selectedCompanyId}|{props.user?.role}</div>,
  inventoryReconciliationEnabled: () => process.env.REACT_APP_INVENTORY_RECONCILIATION_ENABLED === '1',
}));
jest.mock('./WarehouseTabsNav', () => () => <div data-testid="warehouse-tabs">Общие вкладки склада</div>);
jest.mock('./WarehouseOperationsPanel', () => () => <div data-testid="legacy-operations">Прежний склад</div>);
jest.mock('../features/tool-custody/ToolsWorkspace', () => () => null);
jest.mock('../features/warehouse/WarehouseDistributionPanel', () => () => null);
jest.mock('../features/human-approved-actions/HumanApprovedActionReviewPanel', () => () => null);
jest.mock('./WarehouseMaterialControlOverview', () => () => null);
jest.mock('./WarehouseInvoicesPanel', () => () => null);
jest.mock('./WarehouseMainStockPanel', () => () => <div data-testid="main-stock">Основной склад</div>);
jest.mock('./WarehouseCompanyWarehousesPanel', () => () => null);
jest.mock('./WarehouseHistoryPanel', () => () => null);
jest.mock('./WarehouseObjectsPanel', () => () => null);

const flag = 'REACT_APP_INVENTORY_RECONCILIATION_ENABLED';
const originalFlag = process.env[flag];

function restoreFlag() {
  if (originalFlag === undefined) delete process.env[flag];
  else process.env[flag] = originalFlag;
}

afterEach(restoreFlag);

test('foreman warehouse navigation exists only while inventory reconciliation is enabled', () => {
  let enabledRoles;
  let disabledRoles;
  process.env[flag] = '1';
  jest.isolateModules(() => { enabledRoles = require('../constants/roles').ROLES; });
  process.env[flag] = '0';
  jest.isolateModules(() => { disabledRoles = require('../constants/roles').ROLES; });

  expect(enabledRoles.прораб).toContain('warehouse');
  expect(disabledRoles.прораб).not.toContain('warehouse');
});

test('enabled foreman route renders only project inventory workspace even if the old warehouse tab is main stock', () => {
  process.env[flag] = '1';
  render(<WarehousePage
    API="/api"
    C={{}}
    companyContext={{ mode: 'company', selectedCompanyId: 2 }}
    projects={[{ id: 11, name: 'Назначенный объект' }]}
    refreshData={jest.fn()}
    showPreview={jest.fn()}
    user={{ id: 17, role: 'прораб', name: 'Прораб' }}
    visibleActiveProjects={value => value}
    warehouseTab="main"
  />);

  expect(screen.getByTestId('inventory-workspace')).toHaveTextContent('/api|2|прораб');
  expect(screen.queryByTestId('warehouse-tabs')).not.toBeInTheDocument();
  expect(screen.queryByTestId('main-stock')).not.toBeInTheDocument();
  expect(screen.queryByTestId('legacy-operations')).not.toBeInTheDocument();
});
