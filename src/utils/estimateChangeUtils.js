import { ESTIMATE_CHANGE_APPROVED_STATUSES } from '../constants/catalogs';

export const EMPTY_ESTIMATE_CHANGE = {
  changeType: 'Работа вне сметы',
  estimateId: '',
  sectionName: '',
  estimateItemName: '',
  baseQuantity: '',
  newRequiredQuantity: '',
  deltaQuantity: '',
  description: '',
  unit: 'шт',
  quantity: '',
  price: '',
  notes: '',
  reason: '',
  photoUrl: '',
};

export const isApprovedEstimateChangeStatus = (status) => ESTIMATE_CHANGE_APPROVED_STATUSES.includes(status);

export const approvedEstimateChangesForProject = (projectName, unexpectedWorksList = []) => (unexpectedWorksList || []).filter(change =>
  change.projectName === projectName &&
  isApprovedEstimateChangeStatus(change.status) &&
  change.changeType !== 'Исключение объёма' &&
  !change.includedInEstimateId
);

export const includableEstimateChangesForProject = (projectName, unexpectedWorksList = []) => (unexpectedWorksList || []).filter(change =>
  change.projectName === projectName &&
  isApprovedEstimateChangeStatus(change.status) &&
  !change.includedInEstimateId
);

export const estimateChangesForNewEstimateFromList = ({
  project,
  estimate,
  unexpectedWorksList = [],
  activeCustomerEstimates = [],
} = {}) => {
  if (!project || !estimate) return [];
  return includableEstimateChangesForProject(project.name, unexpectedWorksList).filter(change => {
    if (change.estimateId) return Number(change.estimateId) === Number(estimate.id);
    return activeCustomerEstimates.length === 1;
  });
};

export const signedEstimateChangeTotal = (rows = []) => (rows || []).reduce((sum, change) =>
  sum + Number(change.total || 0) * (change.changeType === 'Исключение объёма' ? -1 : 1), 0);

export const estimateChangeRowsForDocsFromList = (projectName, kind, unexpectedWorksList = []) =>
  approvedEstimateChangesForProject(projectName, unexpectedWorksList)
    .filter(change => kind === 'additional'
      ? change.changeType === 'Дополнительный объём к строке сметы'
      : change.changeType !== 'Дополнительный объём к строке сметы')
    .map(change => {
      const quantity = Number(change.deltaQuantity || change.quantity || 0);
      const price = Number(change.price || 0) || (quantity > 0 ? Number(change.total || 0) / quantity : 0);
      return {
        description: change.description || change.estimateItemName || '',
        unit: change.unit || 'шт',
        quantity,
        pricePerUnit: price,
        total: Math.round(Number(change.total || quantity * price || 0)),
        changeType: change.changeType || 'Работа вне сметы',
      };
    });
