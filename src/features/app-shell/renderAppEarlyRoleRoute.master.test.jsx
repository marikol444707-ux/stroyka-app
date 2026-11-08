import {renderAppEarlyRoleRoute} from './renderAppEarlyRoleRoute';

test.each(['мастер', 'бригадир', 'субподрядчик'])('%s receives selected hidden act and signature setter through the actual role route', role => {
  const editingAct = {id: 51, signedSubcontractor: 'Локальная подпись'};
  const setEditingAct = jest.fn();
  const route = renderAppEarlyRoleRoute({data: {
    user: {id: 11, role}, appMainState: {editingAct, setEditingAct},
    actions: {}, builders: {}, materialRuntime: {}, paymentUiState: {},
    projectRuntime: {}, supplyWorkflowState: {}, authEntryState: {},
  }});
  expect(route.props.data.editingAct).toBe(editingAct);
  expect(route.props.actions.setEditingAct).toBe(setEditingAct);
});

// Exercise both prop boundaries: app action groups → role route → cabinet.
import {buildAppRenderContext} from './buildAppRenderContext';

test.each(['мастер', 'бригадир', 'субподрядчик'])('%s can cancel a supply request through the complete cabinet route', async role => {
  const cancelSupply = jest.fn().mockResolvedValue(undefined);
  const {earlyRoleRoute} = buildAppRenderContext({
    actionGroups: {
      documentActions: {}, personnelActions: {}, pricelistActions: {},
      projectCrudActions: {}, projectOperationActions: {}, supplyActions: {cancelSupply},
      supplyPlanningUi: {}, userAccessActions: {}, warehouseActions: {}, workJournalActions: {},
    },
    appCoreRuntime: {myNotifications: () => []},
    companyContext: {mode: 'company', selectedCompanyId: 4},
    user: {id: 7, role},
  });
  const cabinet = earlyRoleRoute.type(earlyRoleRoute.props).props.children;
  expect(cabinet.props.cancelSupply).toBe(cancelSupply);
  await cabinet.props.cancelSupply(19);
  expect(cancelSupply).toHaveBeenCalledWith(19);
});
