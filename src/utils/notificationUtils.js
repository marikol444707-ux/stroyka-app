const NOTIFICATION_PAGE_BY_TYPE = {
  work: 'projects',
  material: 'warehouse',
  stock: 'warehouse',
  supply: 'supply',
  delivery: 'supply',
  invoice: 'accounting',
  act: 'accounting',
  contract: 'accounting',
  unexpected: 'dashboard',
  prescription: 'projects',
  project: 'projects',
  crm: 'crm',
};

export const notificationPageForType = (type) => NOTIFICATION_PAGE_BY_TYPE[type] || 'dashboard';

export const notificationsForUser = (notifications = [], user = null) => {
  const rows = notifications || [];
  if (!user) return rows;
  if (['директор', 'зам_директора'].includes(user.role)) return rows;
  if (user.role === 'прораб') return rows.filter(item => ['work', 'material', 'unexpected', 'prescription', 'supply'].includes(item.type));
  if (['мастер', 'субподрядчик', 'бригадир'].includes(user.role)) {
    return rows.filter(item => item.text && item.text.includes(user.name));
  }
  if (user.role === 'бухгалтер') return rows.filter(item => ['invoice', 'act', 'contract', 'pay', 'expreport', 'ownexp', 'supplyinv'].includes(item.type));
  if (['кладовщик', 'снабженец'].includes(user.role)) return rows.filter(item => ['stock', 'supply', 'delivery', 'supplyinv'].includes(item.type));
  return rows;
};

export const buildComputedNotifications = ({
  user,
  expenseReports = [],
  ownExpenses = [],
  supplierInvoices = [],
  unexpectedWorksList = [],
  hiddenActs = [],
  prescriptionsList = [],
  accountablePayments = [],
  today = new Date().toISOString().split('T')[0],
} = {}) => {
  if (!user) return [];
  const out = [];

  if (user.role === 'бухгалтер' || user.role === 'директор' || user.role === 'зам_директора') {
    (expenseReports || []).filter(report => report.status === 'На утверждении' || report.status === 'Подано' || !report.status).slice(0, 5).forEach(report => {
      out.push({
        type: 'expreport',
        title: 'Авансовый отчёт на утверждение',
        text: (report.employeeName || '—') + ' · ' + Math.round(Number(report.totalAmount || 0)).toLocaleString('ru-RU') + ' ₽',
        icon: '💼',
        color: '#f59e0b',
      });
    });

    (ownExpenses || []).filter(expense => expense.status === 'Ожидает').slice(0, 5).forEach(expense => {
      out.push({
        type: 'ownexp',
        title: 'Возмещение «Мои траты»',
        text: (expense.employeeName || '—') + ' · ' + expense.description + ' · ' + Math.round(Number(expense.amount || 0)).toLocaleString('ru-RU') + ' ₽',
        icon: '💸',
        color: '#3b82f6',
      });
    });

    (supplierInvoices || []).filter(invoice => (
      invoice.status === 'На утверждении'
      || invoice.status === 'Утверждён'
      || invoice.status === 'Частично оплачен'
      || !invoice.status
    )).slice(0, 5).forEach(invoice => {
      const amount = Number(invoice.amount || invoice.totalAmount || 0);
      out.push({
        type: 'supplyinv',
        title: invoice.status === 'На утверждении' ? 'Счёт поставщика на утверждение' : 'Счёт поставщика к оплате',
        text: (invoice.supplierName || '—') + ' · ' + Math.round(amount).toLocaleString('ru-RU') + ' ₽',
        target: 'supply',
        icon: '📥',
        color: '#8b5cf6',
      });
    });
  }

  if (user.role === 'снабженец' || user.role === 'кладовщик') {
    (supplierInvoices || []).filter(invoice => invoice.status === 'На утверждении' || !invoice.status).slice(0, 5).forEach(invoice => {
      const amount = Number(invoice.amount || invoice.totalAmount || 0);
      out.push({
        type: 'supplyinv',
        title: 'Новый счёт от поставщика',
        text: (invoice.supplierName || '—') + ' · ' + Math.round(amount).toLocaleString('ru-RU') + ' ₽ — ждёт утверждения бухгалтером',
        target: 'supply',
        icon: '📥',
        color: '#8b5cf6',
      });
    });
  }

  if (user.role === 'заказчик') {
    (unexpectedWorksList || [])
      .filter(item => item.projectName === (user.project_name || user.projectName) && item.status === 'Ожидает согласования')
      .forEach(item => {
        out.push({
          type: 'unx',
          title: 'Изменение к смете на согласование',
          text: (item.changeType || 'Работа вне сметы') + ' · ' + item.description + ' · ' + (item.total || 0).toLocaleString('ru-RU') + ' ₽',
          icon: '🆕',
          color: '#fbbf24',
        });
      });
    (hiddenActs || []).filter(act => act.projectName === (user.project_name || user.projectName) && !act.signedCustomer).forEach(act => {
      out.push({ type: 'aosr', title: 'АОСР ждёт моей подписи', text: act.actNumber + ' · ' + act.workName, icon: '🔒', color: '#f97316' });
    });
  }

  if (user.role === 'технадзор') {
    (hiddenActs || []).filter(act => act.projectName === (user.project_name || user.projectName) && !act.signedSupervisor).forEach(act => {
      out.push({ type: 'aosr', title: 'АОСР ждёт моей подписи', text: act.actNumber + ' · ' + act.workName, icon: '🔒', color: '#f97316' });
    });
  }

  if (['прораб', 'мастер'].includes(user.role)) {
    (prescriptionsList || [])
      .filter(prescription => prescription.responsible === user.name && prescription.status === 'Открыто' && prescription.deadline && prescription.deadline < today)
      .forEach(prescription => {
        out.push({
          type: 'presc',
          title: 'Предписание просрочено',
          text: (prescription.violation || prescription.description || '').slice(0, 80),
          icon: '⚠️',
          color: '#ef4444',
        });
      });
  }

  (accountablePayments || [])
    .filter(payment => payment.givenTo === user.name && Number(payment.amount || 0) > Number(payment.spentAmount || 0))
    .forEach(payment => {
      const remaining = Number(payment.amount || 0) - Number(payment.spentAmount || 0);
      out.push({
        type: 'accreport',
        title: 'Отчитайся за подотчёт',
        text: 'Осталось отчитаться: ' + Math.round(remaining).toLocaleString('ru-RU') + ' ₽ · ' + (payment.projectName || '') + (payment.purpose ? ' · ' + payment.purpose : ''),
        icon: '💵',
        color: '#f59e0b',
        accountableId: payment.id,
      });
    });

  return out;
};
