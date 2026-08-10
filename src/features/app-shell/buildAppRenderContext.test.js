import { buildAppRenderContext } from './buildAppRenderContext';

describe('buildAppRenderContext company context wiring', () => {
  test('passes the received company context to operations page state', () => {
    const companyContext = {
      mode: 'company',
      selectedCompanyId: 4,
      selectedCompany: { companyId: 4, role: 'директор' },
    };

    const { appShellProps, earlyRoleRoute } = buildAppRenderContext({
      actionGroups: {
        documentActions: {},
        personnelActions: {},
        pricelistActions: {},
        projectCrudActions: {},
        projectOperationActions: {},
        supplyActions: {},
        supplyPlanningUi: {},
        userAccessActions: {},
        warehouseActions: {},
        workJournalActions: {},
      },
      appCoreRuntime: { myNotifications: () => [] },
      companyContext,
      user: { id: 7, role: 'директор' },
    });

    expect(earlyRoleRoute).toBeNull();
    expect(
      appShellProps.appOperationsPagesProps.state.companyContext,
    ).toBe(companyContext);
  });
});
