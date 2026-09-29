import React from 'react';
import { render, screen } from '@testing-library/react';
import WarehousePage from './WarehousePage';

jest.mock('./WarehouseOperationsPanel', () => props => <div data-testid="legacy-operations">{props.warehouseTab}</div>);
jest.mock('../features/warehouse/WarehouseDistributionPanel', () => () => <div data-testid="distributions" />);
jest.mock('../features/human-approved-actions/HumanApprovedActionReviewPanel', () => () => null);
jest.mock('./WarehouseMaterialControlOverview', () => () => null);
jest.mock('./WarehouseTabsNav', () => () => null);
jest.mock('./WarehouseInvoicesPanel', () => () => null);
jest.mock('./WarehouseMainStockPanel', () => () => null);
jest.mock('./WarehouseCompanyWarehousesPanel', () => () => null);
jest.mock('./WarehouseHistoryPanel', () => () => null);
jest.mock('./WarehouseObjectsPanel', () => () => null);

const distributionFlag = 'REACT_APP_WAREHOUSE_DISTRIBUTION_ENABLED';
const transferFlag = 'REACT_APP_WAREHOUSE_DISTRIBUTION_TRANSFERS_ENABLED';
const original = { [distributionFlag]: process.env[distributionFlag], [transferFlag]: process.env[transferFlag] };
function setFlag(name, value) {
  if (value === undefined) delete process.env[name];
  else process.env[name] = value;
}
afterEach(() => Object.entries(original).forEach(([name, value]) => setFlag(name, value)));

describe.each([
  [undefined, undefined],
  ['false', 'false'],
  ['true', 'false'],
  ['false', 'true'],
  ['1', 'true'],
  ['true', 'true'],
])('distribution=%s transfer=%s', (distribution, transfer) => {
  test.each(['move', 'tools', 'inventory'])('%s hides legacy only for two-stage movements', warehouseTab => {
    setFlag(distributionFlag, distribution); setFlag(transferFlag, transfer);
    render(<WarehousePage warehouseTab={warehouseTab} C={{}} card={{}} projects={[]}
      companyContext={{ mode: 'company', selectedCompanyId: 2 }} user={{ role: 'директор' }} visibleActiveProjects={value => value} />);
    const hideLegacy = warehouseTab === 'move' && distribution === 'true' && transfer === 'true';
    expect(screen.queryAllByTestId('legacy-operations')).toHaveLength(hideLegacy ? 0 : 1);
    expect(screen.queryByTestId('legacy-operations')?.textContent ?? null).toBe(hideLegacy ? null : warehouseTab);
    expect(screen.queryAllByTestId('distributions')).toHaveLength(warehouseTab === 'move' ? 1 : 0);
  });
});
