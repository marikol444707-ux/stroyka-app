import { estimatePackage } from './estimateUtils';

const ROLE_COLORS = {
  директор: '#f97316',
  зам_директора: '#ea580c',
  главный_инженер: '#8b5cf6',
  прораб: '#3b82f6',
  кладовщик: '#10b981',
  снабженец: '#14b8a6',
  бухгалтер: '#6b7280',
  стройконтроль: '#06b6d4',
  менеджер_crm: '#8b5cf6',
  мастер: '#ec4899',
  субподрядчик: '#f59e0b',
  бригадир: '#ec4899',
  сметчик: '#3b82f6',
  заказчик: '#06b6d4',
  поставщик: '#f59e0b',
};

export const roleColorForRole = (role) => ROLE_COLORS[role] || '#6b7280';

export const canAccessRole = (user, page, roles = {}) => Boolean(user) && (roles[user.role] || []).includes(page);

export const isLeadershipUser = (user) => ['директор', 'зам_директора'].includes(user?.role || '');

export const isFinanceUser = (user) => ['директор', 'зам_директора', 'бухгалтер'].includes(user?.role || '');

export const isProrabUser = (user) => ['директор', 'зам_директора', 'прораб', 'главный_инженер'].includes(user?.role || '');

export const canEditMaterialNormsForUser = (user) => ['директор', 'зам_директора', 'прораб', 'главный_инженер', 'сметчик'].includes(user?.role || '');

export const canCreateSupplyRequestFromNormForUser = (user) => ['директор', 'зам_директора', 'прораб', 'снабженец', 'кладовщик', 'мастер', 'субподрядчик', 'бригадир'].includes(user?.role || '');

export const canCreateSupplyRequestFromControlForUser = (user) => ['директор', 'зам_директора', 'снабженец', 'кладовщик', 'прораб', 'мастер', 'субподрядчик', 'бригадир', 'бухгалтер'].includes(user?.role || '');

export const canCreateInvoiceControlReviewTaskForUser = (user) => ['директор', 'зам_директора', 'бухгалтер', 'прораб', 'главный_инженер', 'сметчик', 'снабженец', 'кладовщик'].includes(user?.role || '');

export const generateTempPassword = () => {
  const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%';
  const bytes = new Uint32Array(14);
  if (window.crypto?.getRandomValues) window.crypto.getRandomValues(bytes);
  else for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * chars.length);
  return Array.from(bytes, n => chars[n % chars.length]).join('');
};

export const roleFlagsForUser = (user) => {
  const role = user?.role || '';
  const isLeadershipRole = isLeadershipUser(user);
  const isFinanceRole = isFinanceUser(user);
  const isWarehouseRole = ['директор', 'зам_директора', 'кладовщик', 'снабженец', 'прораб', 'главный_инженер'].includes(role);
  const isSupplyRole = ['директор', 'зам_директора', 'снабженец', 'кладовщик', 'прораб', 'мастер', 'субподрядчик', 'бригадир', 'поставщик', 'бухгалтер'].includes(role);
  const canSeeSupplierInvoices = ['директор', 'зам_директора', 'бухгалтер', 'снабженец', 'кладовщик', 'прораб', 'поставщик'].includes(role);
  const isProjectRole = [
    'директор',
    'зам_директора',
    'бухгалтер',
    'прораб',
    'главный_инженер',
    'сметчик',
    'мастер',
    'субподрядчик',
    'бригадир',
    'кладовщик',
    'снабженец',
    'технадзор',
    'заказчик',
    'стройконтроль',
  ].includes(role);
  const isInternalRole = ['директор', 'зам_директора', 'бухгалтер', 'прораб', 'главный_инженер', 'сметчик', 'мастер', 'субподрядчик', 'бригадир', 'кладовщик', 'снабженец', 'менеджер_crm', 'стройконтроль'].includes(role);
  const canSeeProjectDocs = isProjectRole;
  return { role, isLeadershipRole, isFinanceRole, isWarehouseRole, isSupplyRole, canSeeSupplierInvoices, isProjectRole, isInternalRole, canSeeProjectDocs };
};

export const assignedProjectsForUser = (user) => {
  if (!user) return [];
  const assigned = user.assignedProjects || user.assigned_projects;
  if (Array.isArray(assigned) && assigned.length > 0) return assigned;
  const single = user.project_name || user.projectName;
  return single ? [single] : [];
};

export const assignedPackagesForUser = (user) => {
  if (!user) return [];
  const assigned = user.assignedPackages || user.assigned_packages;
  return Array.isArray(assigned) ? assigned.filter(Boolean) : [];
};

export const visibleProjectsForUser = (list, user) => {
  const rows = list || [];
  if (!user) return rows;
  if (['директор', 'зам_директора', 'бухгалтер', 'сметчик', 'главный_инженер'].includes(user.role)) return rows;
  if (['мастер', 'субподрядчик', 'бригадир'].includes(user.role)) {
    const mine = assignedProjectsForUser(user);
    return mine.length > 0 ? rows.filter(project => mine.includes(project.name)) : [];
  }
  if (['прораб', 'технадзор', 'стройконтроль'].includes(user.role)) {
    const mine = assignedProjectsForUser(user);
    if (mine.length > 0) return rows.filter(project => mine.includes(project.name));
  }
  return rows;
};

export const visibleEstimatesForUser = (list, user) => {
  const rows = list || [];
  if (!user) return rows;
  if (['директор', 'зам_директора', 'бухгалтер', 'сметчик', 'главный_инженер'].includes(user.role)) return rows;
  const projectNames = assignedProjectsForUser(user);
  const packageNames = assignedPackagesForUser(user);
  const restrictPackages = ['мастер', 'субподрядчик', 'бригадир'].includes(user.role);
  return rows.filter(estimate => {
    const projectOk = projectNames.length === 0 || projectNames.includes(estimate.projectName || estimate.project_name || estimate.project || '');
    const packageOk = !restrictPackages || (packageNames.length > 0 && packageNames.includes(estimatePackage(estimate)));
    return projectOk && packageOk;
  });
};

export const activeProjectsOnly = (list) => (list || []).filter(project => !project.archived && project.status !== 'Завершён');

export const selectableActiveProjectsForUser = (list, user) => visibleProjectsForUser(list || [], user)
  .filter(project => !project.archived && project.status !== 'Завершён');
