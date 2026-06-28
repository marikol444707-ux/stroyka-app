const FINISHED_STATUSES = new Set(['Завершен', 'Завершён', 'Закрыт', 'Подписан']);
const REJECTED_STATUSES = new Set(['Отклонено', 'Аннулировано', 'Удалено', 'Отменено']);
const PENDING_WORK_STATUSES = new Set(['', 'На проверке', 'Автоматически из сметы']);
const SUPPLY_PIPELINE_STATUSES = new Set(['Новая', 'Подтверждена прорабом', 'Утверждена', 'КП запрошены']);

const norm = value => String(value || '').toLowerCase().replace(/ё/g, 'е').replace(/[.,;:()«»"']/g, ' ').replace(/\s+/g, ' ').trim();
const toNumber = value => Number.isFinite(Number(value)) ? Number(value) : 0;
const unique = rows => [...new Set(rows.filter(Boolean))];
const rowProject = row => row?.projectName || row?.project_name || row?.project || row?.location || '';
const rowPackage = row => String(row?.workPackage || row?.work_package || row?.package || '').trim();

function projectRows(list = [], project = {}) {
  const name = project.name || '';
  const id = Number(project.id || 0);
  return (list || []).filter(row => rowProject(row) === name || (id && Number(row?.projectId || row?.project_id) === id));
}

function packageMatches(row, workPackage) {
  const pkg = String(workPackage || '').trim();
  const rowPkg = rowPackage(row);
  if (!pkg || pkg === 'Основная') return !rowPkg || rowPkg === pkg;
  if (!rowPkg) return false;
  return rowPkg === pkg;
}

function textMatches(row, title) {
  const titleKey = norm(title);
  if (!titleKey) return false;
  const haystack = [
    row?.name,
    row?.title,
    row?.description,
    row?.workName,
    row?.work_name,
    row?.estimateItemName,
    row?.estimate_item_name,
    row?.notes,
    row?.comment,
  ].map(norm).join(' ');
  return haystack.includes(titleKey) || titleKey.split(' ').some(token => token.length >= 5 && haystack.includes(token));
}

function inferPackage(stage, packages) {
  const stageText = norm([stage?.name, stage?.title, stage?.notes].join(' '));
  const matched = packages.find(pkg => {
    const key = norm(pkg);
    return key && (stageText.includes(key) || key.includes(stageText));
  });
  return matched || rowPackage(stage) || 'Основная';
}

function dateMs(value) {
  if (!value) return null;
  const date = new Date(String(value).slice(0, 10) + 'T00:00:00');
  return Number.isNaN(date.getTime()) ? null : date.getTime();
}

function timelineFor(stage, allStages) {
  const dated = allStages
    .flatMap(item => [dateMs(item.startDate || item.start_date), dateMs(item.endDate || item.end_date)])
    .filter(Boolean)
    .sort((a, b) => a - b);
  if (!dated.length) return { startPercent: 0, widthPercent: 18 };
  const min = dated[0];
  const max = dated[dated.length - 1];
  const start = dateMs(stage.startDate || stage.start_date) || min;
  const end = dateMs(stage.endDate || stage.end_date) || start;
  const span = Math.max(1, max - min);
  return {
    startPercent: Math.max(0, Math.min(92, Math.round(((start - min) / span) * 100))),
    widthPercent: Math.max(10, Math.min(36, Math.round(((Math.max(end, start) - start) / span) * 100) || 14)),
  };
}

function statusForRows(rows, goodText, missingText = 'нет связи') {
  if (!rows.length) return { status: 'missing', label: missingText };
  return { status: 'confirmed', label: goodText };
}

function estimatePackageName(estimate) {
  return String(estimate?.workPackage || estimate?.work_package || estimate?.packageName || estimate?.package_name || estimate?.package || estimate?.name || 'Основная').trim();
}

function rowsForPackage(rows, workPackage, title = '') {
  const direct = rows.filter(row => packageMatches(row, workPackage));
  if (direct.length) return direct;
  return rows.filter(row => textMatches(row, title));
}

function materialIssueRows(materialSummary, workPackage) {
  const issueLists = [
    materialSummary?.toBuyRows,
    materialSummary?.outsideRows,
    materialSummary?.mismatchRows,
    materialSummary?.stockMismatchRows,
    materialSummary?.usedOverControlRows,
  ].filter(Array.isArray);
  const rows = issueLists.flat();
  if (!workPackage || workPackage === 'Основная') return rows;
  return rows.filter(row => !rowPackage(row) || rowPackage(row) === workPackage);
}

function buildSupplyChain({ workPackage, materialIssues, requests, deliveries, invoices, warehouseInvoices, inspections, materials, works }) {
  if (!materialIssues.length && !requests.length && !deliveries.length && !invoices.length) return [];
  const issue = materialIssues[0] || {};
  const request = requests[0] || {};
  const delivery = deliveries[0] || {};
  const invoice = invoices[0] || {};
  const warehouseInvoice = warehouseInvoices[0] || {};
  const inspection = inspections[0] || {};
  const stock = materials.reduce((sum, row) => sum + toNumber(row.quantity), 0);
  const plannedQty = toNumber(delivery.plannedQuantity || delivery.planned_quantity || request.quantity || issue.toBuy || issue.shortage);
  const shippedQty = toNumber(delivery.shippedQuantity || delivery.shipped_quantity);
  const receivedQty = toNumber(delivery.receivedQuantity || delivery.received_quantity);
  const shortageQty = toNumber(delivery.shortageQuantity || delivery.shortage_quantity || issue.toBuy || issue.shortage);
  const unit = delivery.unit || request.unit || issue.unit || materials[0]?.unit || '';
  const moneyStatus = toNumber(invoice.amount || invoice.totalAmount) > toNumber(invoice.paidAmount || invoice.paid_amount) ? 'warning' : 'info';
  const qualityDone = inspection.inspected || inspection.status === 'Закрыта' || inspection.status === 'Принята';

  return [
    { step: 'need', title: 'Потребность', status: materialIssues.length ? 'danger' : 'info', value: materialIssues.length ? `нужно проверить ${workPackage}` : 'по текущему этапу' },
    { step: 'request', title: 'Заявка', status: requests.length ? 'ok' : 'warning', value: requests.length ? `заявка ${request.status || 'есть'}` : 'заявки нет' },
    { step: 'offer', title: 'КП', status: invoice.offerId || invoice.offer_id ? 'ok' : 'info', value: invoice.offerId || invoice.offer_id ? 'КП связано' : 'КП не видно' },
    { step: 'invoice', title: 'Счет', status: moneyStatus, value: invoices.length ? (invoice.status || 'счет есть') : 'счета нет' },
    { step: 'shipment', title: 'Отгрузка', status: shortageQty > 0 ? 'danger' : (deliveries.length ? 'ok' : 'info'), value: deliveries.length ? `${shippedQty || plannedQty || 0} ${unit}`.trim() : 'нет данных' },
    { step: 'acceptance', title: 'Приемка', status: shortageQty > 0 ? 'danger' : (receivedQty ? 'ok' : 'info'), value: shortageQty > 0 ? `недостача ${shortageQty} ${unit}`.trim() : `${receivedQty || 0} ${unit}`.trim() },
    { step: 'primary_document', title: 'Накладная', status: warehouseInvoices.length ? 'ok' : 'warning', value: warehouseInvoice.number ? `№ ${warehouseInvoice.number}` : (warehouseInvoices.length ? 'есть' : 'не связана') },
    { step: 'quality_control', title: 'Входной контроль', status: qualityDone ? 'ok' : 'warning', value: qualityDone ? 'проверен' : 'не закрыт' },
    { step: 'warehouse', title: 'Склад', status: stock > 0 ? 'info' : 'warning', value: stock > 0 ? `${stock} ${unit || materials[0]?.unit || ''}`.trim() : 'остатка нет' },
    { step: 'work_journal', title: 'ЖПР', status: works.length ? 'info' : 'warning', value: works.length ? `${works.length} записей` : 'факта нет' },
  ];
}

function buildSignals({ pendingWorks, worksWithoutRoom, materialIssues, deliveries, invoices, hiddenActs, inspections }) {
  const signals = [];
  const deliveryShortage = deliveries.find(row => toNumber(row.shortageQuantity || row.shortage_quantity) > 0 || (toNumber(row.plannedQuantity || row.planned_quantity) > 0 && toNumber(row.receivedQuantity || row.received_quantity) < toNumber(row.plannedQuantity || row.planned_quantity)));
  if (materialIssues.length || deliveryShortage) {
    signals.push({
      type: 'material',
      severity: 'red',
      title: deliveryShortage ? 'Поставка принята не полностью' : 'Есть материальный риск',
      explanation: deliveryShortage ? 'План поставки больше фактически принятого объема.' : 'Контроль материалов показывает строки на проверку или докупку.',
      nextAction: { type: 'open_source', label: 'Открыть материалы', enabledInSandbox: false },
    });
  }
  if (pendingWorks.length) {
    signals.push({
      type: 'link_quality',
      severity: 'yellow',
      title: `ЖПР на проверке: ${pendingWorks.length}`,
      explanation: 'Неподтвержденный ЖПР не считается закрытым фактом.',
      nextAction: { type: 'review_link', label: 'Открыть ЖПР', enabledInSandbox: false },
    });
  }
  if (worksWithoutRoom.length) {
    signals.push({
      type: 'link_quality',
      severity: 'yellow',
      title: `ЖПР без помещения/зоны: ${worksWithoutRoom.length}`,
      explanation: 'Факт есть, но связь с зоной требует проверки.',
      nextAction: { type: 'review_link', label: 'Проверить связь', enabledInSandbox: false },
    });
  }
  const openActs = hiddenActs.filter(row => !FINISHED_STATUSES.has(row.status || '') || !row.signedCustomer || !row.signedSupervisor);
  if (openActs.length) {
    signals.push({
      type: 'document',
      severity: 'yellow',
      title: `АОСР/документы на проверке: ${openActs.length}`,
      explanation: 'Карта только показывает документальный риск и не подписывает документы.',
      nextAction: { type: 'open_source', label: 'Открыть АОСР', enabledInSandbox: false },
    });
  }
  const pendingInspections = inspections.filter(row => !row.inspected && row.status !== 'Закрыта');
  if (pendingInspections.length) {
    signals.push({
      type: 'document',
      severity: 'yellow',
      title: `Входной контроль не закрыт: ${pendingInspections.length}`,
      explanation: 'Материал виден, но качество/сертификаты требуют проверки.',
      nextAction: { type: 'open_source', label: 'Открыть входной контроль', enabledInSandbox: false },
    });
  }
  const payableInvoices = invoices.filter(row => !FINISHED_STATUSES.has(row.status || '') || toNumber(row.amount || row.totalAmount) > toNumber(row.paidAmount || row.paid_amount));
  if (payableInvoices.length) {
    signals.push({
      type: 'money',
      severity: 'yellow',
      title: `Счета/обязательства: ${payableInvoices.length}`,
      explanation: 'Счет виден как обязательство, факт денег считается только из project_payments.',
      nextAction: { type: 'open_source', label: 'Открыть финансы', enabledInSandbox: false },
    });
  }
  return signals;
}

function fallbackStagesFromPackages({ project, packages, workRows, supplyRows }) {
  const sourcePackages = unique([
    ...packages,
    ...workRows.map(rowPackage),
    ...supplyRows.map(rowPackage),
  ]);
  if (sourcePackages.length) {
    return sourcePackages.map((pkg, index) => ({
      id: `package:${pkg || 'main'}`,
      name: pkg || 'Основная',
      status: index === 0 ? 'В работе' : 'На проверке',
      progress: 0,
      responsible: project.responsible || '',
      workPackage: pkg || 'Основная',
    }));
  }
  return [{
    id: `project:${project.id || project.name}`,
    name: project.name || 'Объект',
    status: project.status || 'В работе',
    progress: toNumber(project.progress),
    responsible: project.responsible || '',
    workPackage: 'Основная',
  }];
}

export function buildDirectorMapContract({
  project,
  stages = [],
  estimates = [],
  workJournal = [],
  materials = [],
  supplyRequests = [],
  supplyDeliveries = [],
  supplierInvoices = [],
  warehouseInvoices = [],
  materialInspections = [],
  hiddenActs = [],
  projectPayments = [],
  materialSummary = null,
  planDone = null,
  projectProgress = null,
} = {}) {
  if (!project) {
    return {
      contractVersion: 'director-map.v1',
      mode: 'read_only',
      project: { id: '', name: 'Объект не выбран', status: '', deadline: '', directorViewTitle: 'Карта руководителя' },
      summary: {},
      items: [],
      guards: [],
    };
  }

  const projectName = project.name || '';
  const projectStages = projectRows(stages, project);
  const workRows = projectRows(workJournal, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const supplyRows = projectRows(supplyRequests, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const deliveryRows = projectRows(supplyDeliveries, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const invoiceRows = projectRows(supplierInvoices, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const warehouseInvoiceRows = projectRows(warehouseInvoices, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const inspectionRows = projectRows(materialInspections, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const actRows = projectRows(hiddenActs, project).filter(row => !REJECTED_STATUSES.has(row.status || ''));
  const paymentRows = projectRows(projectPayments, project);
  const materialRows = projectRows(materials, project);
  const estimatePackages = unique(estimates.map(estimatePackageName));
  const sourceStages = projectStages.length ? projectStages : fallbackStagesFromPackages({
    project,
    packages: estimatePackages,
    workRows,
    supplyRows: [...supplyRows, ...deliveryRows],
  });

  const items = sourceStages.map((stage, index) => {
    const workPackage = rowPackage(stage) || inferPackage(stage, estimatePackages);
    const title = stage.name || stage.title || workPackage || 'Этап';
    const estimateRows = estimates.filter(est => !workPackage || estimatePackageName(est) === workPackage || norm(estimatePackageName(est)).includes(norm(workPackage)));
    const works = rowsForPackage(workRows, workPackage, title);
    const confirmedWorks = works.filter(row => row.status === 'Подтверждено');
    const pendingWorks = works.filter(row => PENDING_WORK_STATUSES.has(row.status || ''));
    const worksWithoutRoom = works.filter(row => !(row.roomName || row.room_name || row.zone || '').trim());
    const requests = rowsForPackage(supplyRows, workPackage, title).filter(row => SUPPLY_PIPELINE_STATUSES.has(row.status || 'Новая'));
    const deliveries = rowsForPackage(deliveryRows, workPackage, title);
    const invoices = rowsForPackage(invoiceRows, workPackage, title);
    const warehouseRows = rowsForPackage(warehouseInvoiceRows, workPackage, title);
    const inspections = rowsForPackage(inspectionRows, workPackage, title);
    const acts = rowsForPackage(actRows, workPackage, title);
    const nodeMaterials = rowsForPackage(materialRows, workPackage, title);
    const payments = rowsForPackage(paymentRows, workPackage, title);
    const issues = materialIssueRows(materialSummary, workPackage);
    const plannedProgress = toNumber(stage.progress || stage.plannedProgress || project.progress || 0);
    const factFromWorks = works.length ? Math.round((confirmedWorks.length / works.length) * 100) : 0;
    const factProgress = Math.max(factFromWorks, toNumber(stage.progress || 0));
    const moneyFact = payments.reduce((sum, row) => sum + toNumber(row.amount), 0);
    const moneyObligations = invoices.reduce((sum, row) => {
      const amount = toNumber(row.amount || row.totalAmount);
      const paid = toNumber(row.paidAmount || row.paid_amount);
      return sum + Math.max(0, amount - paid);
    }, 0);
    const signals = buildSignals({ pendingWorks, worksWithoutRoom, materialIssues: issues, deliveries, invoices, hiddenActs: acts, inspections });
    const hasReview = signals.length || pendingWorks.length || worksWithoutRoom.length;

    return {
      id: String(stage.id || `${workPackage || 'stage'}-${index}`),
      type: 'work_node',
      title,
      workPackage,
      zone: stage.zone || stage.roomName || stage.room_name || 'Объект',
      status: stage.status || (confirmedWorks.length ? 'В работе' : 'На проверке'),
      priority: signals.some(signal => signal.severity === 'red') ? 'high' : 'normal',
      startDate: stage.startDate || stage.start_date || '',
      endDate: stage.endDate || stage.end_date || '',
      responsible: stage.responsible || project.responsible || 'Не назначен',
      plannedProgress,
      factProgress,
      reviewState: hasReview ? 'needs_review' : 'ok',
      money: {
        plan: toNumber(stage.budget || 0),
        fact: moneyFact,
        obligations: moneyObligations,
        factSourceRule: 'project_payments_only',
      },
      timeline: timelineFor(stage, sourceStages),
      sourceRefs: {
        stage: { status: 'confirmed', label: stage.status || 'этап' },
        estimate: statusForRows(estimateRows, `смет: ${estimateRows.length}`),
        workJournal: statusForRows(works, confirmedWorks.length ? `ЖПР ${confirmedWorks.length}/${works.length}` : `ЖПР ${works.length}`),
        supply: statusForRows([...requests, ...deliveries], deliveries.length ? `поставок: ${deliveries.length}` : `заявок: ${requests.length}`),
        warehouse: statusForRows([...warehouseRows, ...nodeMaterials], nodeMaterials.length ? `остатков: ${nodeMaterials.length}` : `накладных: ${warehouseRows.length}`),
        documents: statusForRows([...acts, ...inspections], acts.length ? `АОСР: ${acts.length}` : `контроль: ${inspections.length}`),
        payments: statusForRows([...payments, ...invoices], moneyFact ? `${moneyFact.toLocaleString('ru-RU')} ₽ факт` : `обязательства: ${moneyObligations.toLocaleString('ru-RU')} ₽`),
      },
      signals,
      supplyChain: buildSupplyChain({
        workPackage,
        materialIssues: issues,
        requests,
        deliveries,
        invoices,
        warehouseInvoices: warehouseRows,
        inspections,
        materials: nodeMaterials,
        works,
      }),
    };
  });

  const allSignals = items.flatMap(item => item.signals || []);
  const moneyFact = paymentRows.reduce((sum, row) => sum + toNumber(row.amount), 0);
  const moneyObligations = invoiceRows.reduce((sum, row) => {
    const amount = toNumber(row.amount || row.totalAmount);
    const paid = toNumber(row.paidAmount || row.paid_amount);
    return sum + Math.max(0, amount - paid);
  }, 0);
  const plannedProgress = items.length ? Math.round(items.reduce((sum, item) => sum + toNumber(item.plannedProgress), 0) / items.length) : toNumber(project.progress);
  const factProgress = Number.isFinite(Number(projectProgress))
    ? Math.round(Number(projectProgress))
    : (planDone?.plan ? Math.round((toNumber(planDone.done) / Math.max(1, toNumber(planDone.plan))) * 100) : plannedProgress);

  return {
    contractVersion: 'director-map.v1',
    mode: 'read_only',
    integrationPolicy: {
      readOnly: true,
      writesToAccounting: false,
      writesToWarehouse: false,
      writesToWorkJournal: false,
      autoScheduleShift: false,
      autoLinkThreshold: 90,
      uncertainState: 'needs_review',
    },
    project: {
      id: project.id || projectName,
      name: projectName,
      status: project.status || '',
      deadline: project.deadline || '',
      directorViewTitle: 'Карта руководителя',
    },
    summary: {
      plannedProgress,
      factProgress,
      lagPercent: Math.max(0, plannedProgress - factProgress),
      redSignals: allSignals.filter(signal => signal.severity === 'red').length,
      yellowSignals: allSignals.filter(signal => signal.severity !== 'red').length,
      reviewItems: items.filter(item => item.reviewState === 'needs_review').length,
      moneyFact,
      moneyObligations,
    },
    items,
    unlinked: {
      workJournal: workRows.filter(row => !rowPackage(row)),
      materials: materialRows.filter(row => !rowPackage(row)),
      documents: [...actRows, ...inspectionRows].filter(row => !rowPackage(row)),
      payments: paymentRows.filter(row => !rowPackage(row)),
    },
    guards: [
      'no_fact_money_outside_project_payments',
      'no_warehouse_changes_from_director_map',
      'no_work_journal_confirmation_from_director_map',
      'no_auto_date_shift',
      'all_low_confidence_links_go_to_needs_review',
    ],
  };
}
