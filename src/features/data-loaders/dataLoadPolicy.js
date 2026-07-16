export const ESTIMATES_SUMMARY_PATH = '/estimates?summary=true';

const PEOPLE_DATA_ROLES = new Set([
  'директор', 'зам_директора', 'бухгалтер', 'прораб', 'главный_инженер', 'сметчик', 'кладовщик', 'снабженец', 'стройконтроль',
]);
const USER_DIRECTORY_ROLES = new Set([
  'директор', 'зам_директора', 'бухгалтер', 'прораб', 'главный_инженер', 'сметчик',
]);
const ACCOUNTING_DATA_ROLES = new Set([
  'директор', 'зам_директора', 'бухгалтер', 'прораб', 'главный_инженер',
]);
const SYSTEM_ASSIGNMENT_ROLES = new Set(['директор', 'зам_директора']);
const WORKER_DATA_ROLES = new Set(['мастер', 'субподрядчик', 'бригадир']);

export const createDataLoadPolicy = ({ flags = {}, canAccessEstimates = false } = {}) => {
  const role = flags.role || '';
  const isWorkerRole = WORKER_DATA_ROLES.has(role);
  const canLoadPeopleData = PEOPLE_DATA_ROLES.has(role);
  const canLoadUserDirectory = USER_DIRECTORY_ROLES.has(role) || Boolean(flags.isLeadershipRole);
  const canLoadAccountingData = ACCOUNTING_DATA_ROLES.has(role) || Boolean(flags.isFinanceRole);

  return {
    ...flags,
    role,
    isWorkerRole,
    canLoadPeopleData,
    canLoadUserDirectory,
    canLoadAccountingData,
    canLoadBrigadeData: canLoadPeopleData || canLoadAccountingData || isWorkerRole,
    canLoadBrigadePayments: Boolean(flags.isFinanceRole) || isWorkerRole,
    canLoadEstimates: Boolean(flags.canSeeProjectDocs) || Boolean(canAccessEstimates),
    estimatesLoadPath: isWorkerRole ? '/estimates' : ESTIMATES_SUMMARY_PATH,
    assignmentsPath: SYSTEM_ASSIGNMENT_ROLES.has(role)
      ? '/assignments?include_system=true'
      : '/assignments',
  };
};
