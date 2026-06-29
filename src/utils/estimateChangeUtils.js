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
