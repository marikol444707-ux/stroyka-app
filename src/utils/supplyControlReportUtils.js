import { toNum } from './measureUtils';

export const buildSupplyControlIssues = ({
  lowMainStock = [],
  lowStock = [],
  supplyRequests = [],
  supplierInvoices = [],
  invoices = [],
  activeProjects = [],
  warehouseInvoiceEstimateControl,
  invoiceControlNeedsReview,
  invoiceControlProjectName,
  invoiceControlMaterialName,
  invoiceControlReviewReason,
  materialReconciliationRows,
  materialNormControlSummaryForProject,
  fmtMeasure,
  fmtMoney,
} = {}) => {
  const issues = [];
  lowMainStock.forEach(material => issues.push({
    severity: 'Внимание',
    project: 'Основной склад',
    where: material.name,
    problem: 'Остаток ниже минимума: ' + fmtMeasure(material.quantity, material.unit),
    action: 'Пополнить склад',
  }));
  lowStock.forEach(material => issues.push({
    severity: 'Внимание',
    project: material.project || 'Объект',
    where: material.name,
    problem: 'Остаток ниже минимума: ' + fmtMeasure(material.quantity, material.unit),
    action: 'Создать заявку или перемещение',
  }));
  (supplyRequests || [])
    .filter(request => request.status === 'Новая' || request.status === 'Подтверждена прорабом')
    .forEach(request => issues.push({
      severity: request.status === 'Новая' ? 'Внимание' : 'Критично',
      project: request.project || '',
      where: request.materialName || 'Заявка #' + request.id,
      problem: 'Заявка ждёт решения: ' + (request.status || 'Новая'),
      action: 'Открыть снабжение',
    }));
  (supplierInvoices || [])
    .filter(invoice => invoice.status === 'На утверждении' || !invoice.status)
    .forEach(invoice => issues.push({
      severity: 'Критично',
      project: invoice.projectName || invoice.project || '',
      where: invoice.supplierName || 'Поставщик',
      problem: 'Счёт ждёт утверждения: ' + fmtMoney(invoice.amount || invoice.totalAmount),
      action: 'Утвердить или отклонить',
    }));
  (invoices || [])
    .filter(invoice => (invoice.location || '') !== 'Основной склад')
    .slice(0, 80)
    .forEach(invoice => {
      warehouseInvoiceEstimateControl(invoice)
        .filter(invoiceControlNeedsReview)
        .slice(0, 4)
        .forEach(control => {
          const severe = control.status === 'Вне сметы' || toNum(control.overQty) > 0;
          issues.push({
            severity: severe ? 'Критично' : 'Внимание',
            project: invoiceControlProjectName(invoice, control),
            where: invoiceControlMaterialName(control, control) || ('Накладная #' + (invoice.id || invoice.number || '')),
            problem: 'Накладная №' + (invoice.number || invoice.id || '') + ': ' + invoiceControlReviewReason(control),
            action: 'Создать/открыть задачу сметчику или директору',
          });
        });
    });
  activeProjects.slice(0, 12).forEach(project => {
    const materialRows = materialReconciliationRows(project.name);
    materialRows.filter(row => row.toBuy > 0).slice(0, 3).forEach(row => issues.push({
      severity: 'Внимание',
      project: project.name,
      where: row.name,
      problem: 'К закупке по плану: ' + fmtMeasure(row.toBuy, row.unit),
      action: 'Проверить заявку/поставку',
    }));
    materialRows.filter(row => row.issued > 0 && row.usedWithoutIssue > 0).slice(0, 2).forEach(row => issues.push({
      severity: 'Критично',
      project: project.name,
      where: row.name,
      problem: 'Списано больше выданного: +' + fmtMeasure(row.usedWithoutIssue, row.unit),
      action: 'Проверить выдачу и журнал работ',
    }));
    const normControl = materialNormControlSummaryForProject(project.name);
    normControl.overRows.slice(0, 2).forEach(row => issues.push({
      severity: 'Критично',
      project: project.name,
      where: row.name,
      problem: 'Перерасход по норме: +' + fmtMeasure(row.overQty, row.unit),
      action: 'Проверить списание мастера и норму',
    }));
    normControl.withoutNormRows.slice(0, 2).forEach(row => issues.push({
      severity: 'Внимание',
      project: project.name,
      where: row.name,
      problem: 'Материал списан без нормы: ' + fmtMeasure(row.withoutNormQty, row.unit),
      action: 'Добавить норму или уточнить списание',
    }));
  });
  return issues.sort((a, b) => (a.severity === 'Критично' ? -1 : 1) - (b.severity === 'Критично' ? -1 : 1));
};

export const buildSupplyControlReportData = ({
  issues = [],
  supplyRequests = [],
  supplierOffers = [],
  supplierInvoices = [],
} = {}) => {
  const inWorkRequests = (supplyRequests || []).filter(request =>
    ['Новая', 'Подтверждена прорабом', 'Утверждена', 'КП запрошены'].includes(request.status || 'Новая')
  );
  const offersToReview = (supplierOffers || []).filter(offer => offer.status === 'Получено');
  const invoicesToPay = (supplierInvoices || []).filter(invoice =>
    invoice.status === 'На утверждении' ||
    invoice.status === 'Утверждён' ||
    invoice.status === 'Частично оплачен' ||
    !invoice.status
  );
  const debt = invoicesToPay.reduce((sum, invoice) =>
    sum + Math.max(0, Number(invoice.amount || invoice.totalAmount || 0) - Number(invoice.paidAmount || 0)), 0);
  return { issues, inWorkRequests, offersToReview, invoicesToPay, debt };
};
