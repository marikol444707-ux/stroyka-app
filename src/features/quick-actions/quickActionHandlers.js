import { createManualExpenseForm } from '../payments/paymentInitialForms';
import { QUICK_ACTION_IDS } from './quickActionRegistry';

const noop = () => {};
const safeFn = (fn, fallback = noop) => (typeof fn === 'function' ? fn : fallback);

export function createQuickActionHandlers({
  API,
  close = noop,
  navigateTo,
  openReceiveInvoice,
  projects,
  setActivePage,
  setAddExpenseProject,
  setMaterialTransfers,
  setNewManualExpense,
  setSelectedWarehouseProject,
  setShowAiAssistant,
  setShowChatPanel,
  setShowOwnExpenseForm,
  setShowTransferForm,
  setWarehouseTab,
  visibleActiveProjects,
} = {}) {
  const closeAction = safeFn(close);
  const openPage = safeFn(navigateTo, safeFn(setActivePage));
  const listVisibleProjects = typeof visibleActiveProjects === 'function'
    ? visibleActiveProjects
    : (items) => (Array.isArray(items) ? items.filter((p) => !p?.archived) : []);

  return {
    [QUICK_ACTION_IDS.ASSIGNMENTS]: () => {
      closeAction();
      openPage('assignments');
    },
    [QUICK_ACTION_IDS.RECEIVE_WAREHOUSE]: () => {
      safeFn(openReceiveInvoice)('', {scanFirst:true});
      closeAction();
    },
    [QUICK_ACTION_IDS.TRANSFER_MATERIAL]: async () => {
      const visible = listVisibleProjects(projects);
      if (visible.length === 1) {
        const projectName = visible[0].name;
        try {
          const response = await fetch(API + '/material-transfers?project_name=' + encodeURIComponent(projectName));
          const data = await response.json();
          safeFn(setMaterialTransfers)(Array.isArray(data) ? data : []);
        } catch (_error) {
          safeFn(setMaterialTransfers)([]);
        }
        safeFn(setSelectedWarehouseProject)(projectName);
        safeFn(setWarehouseTab)('objects');
        openPage('warehouse');
        safeFn(setShowTransferForm)(true);
        closeAction();
        return;
      }
      closeAction();
      safeFn(setWarehouseTab)('objects');
      openPage('warehouse');
    },
    [QUICK_ACTION_IDS.OBJECT_EXPENSE]: () => {
      const visible = listVisibleProjects(projects);
      safeFn(setNewManualExpense)(createManualExpenseForm());
      safeFn(setAddExpenseProject)(visible.length === 1 ? visible[0].name : '__choose__');
      closeAction();
    },
    [QUICK_ACTION_IDS.OWN_EXPENSE]: () => {
      closeAction();
      safeFn(setShowOwnExpenseForm)(true);
    },
    [QUICK_ACTION_IDS.CHAT]: () => {
      closeAction();
      safeFn(setShowChatPanel)(true);
    },
    [QUICK_ACTION_IDS.WEATHER]: () => {
      closeAction();
      openPage('weather');
    },
    [QUICK_ACTION_IDS.PROJECTS]: () => {
      closeAction();
      openPage('projects');
    },
    [QUICK_ACTION_IDS.WAREHOUSE]: () => {
      closeAction();
      openPage('warehouse');
    },
    [QUICK_ACTION_IDS.AI]: () => {
      closeAction();
      safeFn(setShowAiAssistant)(true);
    },
  };
}
