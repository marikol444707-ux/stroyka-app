import { isLeadershipUser, isProrabUser, roleColorForRole } from '../../utils/accessUtils';
import { createFileSrc, daysInMonth, matchSearchFields } from '../../utils/appRuntimeUtils';
import { calcStaffSalary, workedDaysForStaff } from '../../utils/payrollUtils';
import { projectFactSpentValue } from '../../utils/projectEconomyUtils';
import {
  formatSignedRubValue,
  projectPaymentIncomingAmount,
  projectPaymentSignedAmountValue,
} from '../../utils/projectPaymentUtils';

export function unreadCompanyMessagesCount(companyMessages, user) {
  return (companyMessages || []).filter(message => {
    const readBy = message.readBy || [];
    return user && !readBy.includes(user.id) && message.author_id !== user.id;
  }).length;
}

export function createAppRoleRuntime({ piecework, timesheet, user, users }) {
  return {
    canUseDirectorAgent: () => ['директор', 'system_owner'].includes(user ? user.role : ''),
    calcSalary: staff => calcStaffSalary(staff, timesheet, piecework, daysInMonth),
    financeUsers: (users || []).filter(item => ['директор', 'зам_директора', 'бухгалтер'].includes(item.role)),
    formatSignedRub: amount => formatSignedRubValue(amount),
    isDirector: () => (user ? user.role : '') === 'директор',
    isLeadership: () => isLeadershipUser(user),
    isMasterRole: () => ['мастер', 'субподрядчик', 'бригадир'].includes(user ? user.role : ''),
    isProrab: () => isProrabUser(user),
    projectPaymentInAmount: pay => projectPaymentIncomingAmount(pay),
    projectPaymentSignedAmount: pay => projectPaymentSignedAmountValue(pay),
    roleColor: role => roleColorForRole(role),
    workedDays: id => workedDaysForStaff(id, timesheet, daysInMonth),
  };
}

export function createAppUtilityRuntime({
  API,
  allBrigadeItems,
  estimatesList,
  materials,
  nextEstimateVersionForFromList,
  workJournal,
}) {
  return {
    fileSrc: createFileSrc(API),
    lowStockFor: rows => (rows || []).filter(m => m.minQuantity && m.quantity < m.minQuantity),
    matchSearch: (q, ...fields) => matchSearchFields(q, ...fields),
    nextEstimateVersionFor: (draft, sourceEstimates = estimatesList) => nextEstimateVersionForFromList(draft, sourceEstimates),
    projectFactSpent: project => projectFactSpentValue({
      project,
      workJournal,
      allBrigadeItems,
      materials,
    }),
  };
}
