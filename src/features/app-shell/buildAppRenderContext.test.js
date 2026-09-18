import { buildAppRenderContext } from './buildAppRenderContext';
import { qualityJournalLoadIssue, qualityJournalScopeKey } from '../../utils/qualityJournalScope';
import { getQualityJournalRevision } from '../../utils/qualityJournalEvents';

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
    expect(appShellProps.projectsPageContext.companyContext).toBe(companyContext);
    expect(
      appShellProps.appOperationsPagesProps.state.companyContext,
    ).toBe(companyContext);
  });

  test('a confirmed company journal remains usable through the complete project page wiring', () => {
    const user = { id: 7, role: 'директор' };
    const companyContext = {
      mode: 'company', selectedCompanyId: 4,
      companies: [{ companyId: 4, role: 'директор', active: true }],
    };
    const project = { id: 11, companyId: 4, name: 'Школа' };
    const ready = {
      scopeKey: qualityJournalScopeKey(companyContext, user),
      revision: getQualityJournalRevision(), status: 'ready', complete: true,
    };
    const { appShellProps } = buildAppRenderContext({
      actionGroups: {
        documentActions: {}, personnelActions: {}, pricelistActions: {},
        projectCrudActions: {}, projectOperationActions: {}, supplyActions: {},
        supplyPlanningUi: {}, userAccessActions: {}, warehouseActions: {}, workJournalActions: {},
      },
      appCoreRuntime: { myNotifications: () => [] },
      appMainState: { qualityJournalLoadState: { inspections: ready, cables: ready } },
      companyContext, user,
    });
    const ctx = appShellProps.projectsPageContext;
    expect(qualityJournalLoadIssue(ctx.qualityJournalLoadState, project, ctx.companyContext, ctx.user)).toBe('');
    expect(qualityJournalLoadIssue(ctx.qualityJournalLoadState, { ...project, companyId: 5 }, ctx.companyContext, ctx.user)).not.toBe('');
    expect(qualityJournalLoadIssue(ctx.qualityJournalLoadState, project, { ...ctx.companyContext, mode: 'all_companies' }, ctx.user)).not.toBe('');
  });
});
