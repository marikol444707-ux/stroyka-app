export const QUICK_ACTION_IDS = {
  ASSIGNMENTS: 'assignments',
  RECEIVE_WAREHOUSE: 'receive_warehouse',
  TRANSFER_MATERIAL: 'transfer_material',
  OBJECT_EXPENSE: 'object_expense',
  OWN_EXPENSE: 'own_expense',
  CHAT: 'chat',
  WEATHER: 'weather',
  PROJECTS: 'projects',
  WAREHOUSE: 'warehouse',
  AI: 'ai',
};

const ASSIGNMENT_ROLES = [
  'директор',
  'зам_директора',
  'главный_инженер',
  'прораб',
  'кладовщик',
  'бухгалтер',
  'снабженец',
  'стройконтроль',
  'сметчик',
  'субподрядчик',
  'мастер',
  'бригадир',
  'технадзор',
];

export const QUICK_ACTION_DEFINITIONS = [
  {
    id: QUICK_ACTION_IDS.ASSIGNMENTS,
    label: 'Поручения',
    color: '#f97316',
    roles: ASSIGNMENT_ROLES,
    appPage: 'assignments',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.RECEIVE_WAREHOUSE,
    label: 'Принять на склад',
    color: '#3b82f6',
    roles: ['директор', 'зам_директора', 'прораб', 'кладовщик', 'снабженец'],
    appPage: 'warehouse',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.TRANSFER_MATERIAL,
    label: 'Передать материал',
    color: '#10b981',
    roles: ['директор', 'зам_директора', 'прораб', 'кладовщик'],
    appPage: 'warehouse',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.OBJECT_EXPENSE,
    label: 'Расход по объекту',
    color: '#8b5cf6',
    roles: ['директор', 'зам_директора', 'бухгалтер'],
    appPage: 'accounting',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.OWN_EXPENSE,
    label: 'Мои траты',
    color: '#22c55e',
    appPage: 'myexpenses',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.CHAT,
    label: 'Чат',
    color: '#3b82f6',
    appPage: 'companychat',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.WEATHER,
    label: 'Погода',
    color: '#06b6d4',
    roles: ['прораб', 'главный_инженер'],
    appPage: 'weather',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.PROJECTS,
    label: 'Объекты',
    color: '#f59e0b',
    roles: ['директор', 'зам_директора', 'главный_инженер', 'прораб', 'стройконтроль', 'технадзор', 'сметчик'],
    appPage: 'projects',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.WAREHOUSE,
    label: 'Склад',
    color: '#10b981',
    roles: ['директор', 'зам_директора', 'кладовщик', 'снабженец'],
    appPage: 'warehouse',
    surfaces: ['web', 'max'],
  },
  {
    id: QUICK_ACTION_IDS.AI,
    label: 'ИИ',
    color: '#f97316',
    appPage: 'dashboard',
    surfaces: ['web', 'max'],
  },
];

export function isQuickActionAllowed(action, userOrRole, surface = 'web') {
  const role = typeof userOrRole === 'string' ? userOrRole : userOrRole?.role;
  if (Array.isArray(action.surfaces) && !action.surfaces.includes(surface)) return false;
  if (!Array.isArray(action.roles) || action.roles.length === 0) return true;
  return Boolean(role && action.roles.includes(role));
}

export function getQuickActionsForUser(userOrRole, options = {}) {
  const surface = options.surface || 'web';
  return QUICK_ACTION_DEFINITIONS.filter(action => isQuickActionAllowed(action, userOrRole, surface));
}

export function getQuickActionById(actionId) {
  return QUICK_ACTION_DEFINITIONS.find(action => action.id === actionId) || null;
}

export function quickActionPageFor(actionId) {
  return getQuickActionById(actionId)?.appPage || '';
}
