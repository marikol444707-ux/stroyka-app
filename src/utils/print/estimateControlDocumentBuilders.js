import { docEsc } from '../documentFormatUtils';
import { estimateDiffChangedRows } from '../estimateDiffDocumentUtils';
import { fmtMeasure } from '../measureUtils';
import { companyTitle, directorDocStyles, fmtDocMoney } from '../printDocumentShared';

const ESTIMATE_IMPACT_TOLERANCE = 0.5;

const looksLikeEstimateAdjustment = (row = {}) => (
  row.itemType === 'adjustment'
  || /корректир|округлен|округлён|итог(?:овая|овый)?\s+(?:смет|файл)|до\s+всего/i.test(String(row.name || row.itemName || ''))
);

const estimateImpactReason = (row = {}) => {
  if (looksLikeEstimateAdjustment(row)) return 'Корректировка общего итога исходного файла';
  if (row.kind === 'added') return 'Позиция добавлена';
  if (row.kind === 'removed') return 'Позиция исключена';
  const quantityChanged = Math.abs(Number(row.nextQty || 0) - Number(row.baseQty || 0)) > 0.0001;
  const priceChanged = Math.abs(Number(row.nextUnitPrice || 0) - Number(row.baseUnitPrice || 0)) > 0.01;
  if (quantityChanged && priceChanged) return 'Изменились объём и цена';
  if (quantityChanged) return 'Изменился объём';
  if (priceChanged) return 'Изменилась цена';
  return 'Изменился итог строки или коэффициент';
};

const estimateImpactAnalysis = (rows = [], totalImpact = 0) => {
  const meaningfulRows = rows
    .filter((row) => row.kind === 'changed'
      || Math.abs(Number(row.baseQty || 0)) > 0.0001
      || Math.abs(Number(row.nextQty || 0)) > 0.0001
      || Math.abs(Number(row.baseSum || 0)) > 0.005
      || Math.abs(Number(row.nextSum || 0)) > 0.005
      || Math.abs(Number(row.impact || 0)) > 0.005)
    .map((row) => ({ ...row, reason: estimateImpactReason(row) }))
    .sort((left, right) => Math.abs(Number(right.impact || 0)) - Math.abs(Number(left.impact || 0)));
  const positive = meaningfulRows.reduce((sum, row) => sum + Math.max(0, Number(row.impact || 0)), 0);
  const negative = meaningfulRows.reduce((sum, row) => sum + Math.min(0, Number(row.impact || 0)), 0);
  const explained = positive + negative;
  return {
    rows: meaningfulRows,
    positive,
    negative,
    explained,
    residual: Number(totalImpact || 0) - explained,
  };
};

const reconciliationImpactRows = (items = []) => (items || [])
  .filter((item) => ['changed', 'added', 'removed'].includes(item.itemType))
  .map((item) => ({
    kind: item.itemType,
    section: item.sectionName,
    name: item.itemName,
    unit: item.unit,
    baseQty: item.baseQuantity,
    nextQty: item.nextQuantity,
    baseUnitPrice: item.baseUnitPrice,
    nextUnitPrice: item.nextUnitPrice,
    baseSum: item.baseTotal,
    nextSum: item.nextTotal,
    impact: item.impact,
    decision: item.decision,
  }));

const renderEstimateImpactAnalysis = ({ analysis, classPrefix, fmtMoney, fmtQty, signMoney, diffColor, showPackage = false, showImpactCards = true }) => {
  const quantityLabel = (row, side) => {
    const value = side === 'base' ? row.baseQty : row.nextQty;
    const missing = (row.kind === 'added' && side === 'base') || (row.kind === 'removed' && side === 'next');
    if (missing) return '—';
    return `${fmtQty(value)}${row.unit ? ` ${row.unit}` : ''}`;
  };
  const rowsHtml = analysis.rows.map((row) => '<tr>'
    + `<td style="color:${diffColor(row.impact)};font-weight:700">${row.impact > 0 ? 'Плюс' : row.impact < 0 ? 'Минус' : 'Без изменения суммы'}</td>`
    + (showPackage ? `<td>${docEsc(row.workPackage || '')}</td>` : '')
    + `<td>${docEsc(row.section || '')}</td>`
    + `<td>${docEsc(row.name || '')}</td>`
    + `<td>${docEsc(row.reason)}</td>`
    + `<td class="num">${docEsc(quantityLabel(row, 'base'))}</td>`
    + `<td class="num">${docEsc(quantityLabel(row, 'next'))}</td>`
    + `<td class="num">${fmtMoney(row.baseSum)}</td>`
    + `<td class="num">${fmtMoney(row.nextSum)}</td>`
    + `<td class="num" style="color:${diffColor(row.impact)};font-weight:700">${signMoney(row.impact)}</td>`
    + '</tr>').join('');
  const residualIsMaterial = Math.abs(analysis.residual) > ESTIMATE_IMPACT_TOLERANCE;
  const balanceHtml = residualIsMaterial
    ? `<div class="${classPrefix}-balance ${classPrefix}-balance-warn"><b>Не распределено по позициям: ${signMoney(analysis.residual)}</b><span>Проверьте итоговые строки, индексы, коэффициенты и округления исходного файла.</span></div>`
    : `<div class="${classPrefix}-balance ${classPrefix}-balance-ok"><b>Разница полностью объяснена позициями</b><span>Баланс строк: ${signMoney(analysis.explained)}.</span></div>`;
  const impactCards = showImpactCards
    ? `<div class="${classPrefix}-grid">`
      + `<div class="${classPrefix}-card"><span>Плюсовые изменения</span><b style="color:${diffColor(analysis.positive)}">${signMoney(analysis.positive)}</b></div>`
      + `<div class="${classPrefix}-card"><span>Минусовые изменения</span><b style="color:${diffColor(analysis.negative)}">${signMoney(analysis.negative)}</b></div>`
      + `<div class="${classPrefix}-card"><span>Баланс позиций</span><b style="color:${diffColor(analysis.explained)}">${signMoney(analysis.explained)}</b></div>`
      + '</div>'
    : '';
  return `<div class="${classPrefix}-h">Изменённые позиции. Почему изменилась сумма</div>`
    + impactCards
    + balanceHtml
    + `<table class="${classPrefix}-table"><tr><th>Знак</th>${showPackage ? '<th>Смета / пакет</th>' : ''}<th>Раздел</th><th>Позиция</th><th>Причина</th><th>Было объём</th><th>Стало объём</th><th>Было сумма</th><th>Стало сумма</th><th>Разница</th></tr>`
    + (rowsHtml || `<tr><td colspan="${showPackage ? 10 : 9}" style="text-align:center;color:#64748b">Изменённых позиций нет</td></tr>`)
    + '</table>';
};

export const buildEstimateReconciliationDocContent = (rec = {}) => {
  const items = rec?.items || [];
  const fmtMoney = (value) => `${(Math.round(Number(value || 0) * 100) / 100).toLocaleString('ru-RU')} ₽`;
  const signMoney = (value) => `${Number(value || 0) > 0 ? '+' : ''}${fmtMoney(value)}`;
  const fmtQty = (value) => {
    const quantity = Number(value || 0);
    return Math.abs(quantity - Math.round(quantity)) < 0.001
      ? String(Math.round(quantity))
      : quantity.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
  };
  const diffColor = (value) => {
    if (Number(value || 0) > 0) return '#b45309';
    if (Number(value || 0) < 0) return '#047857';
    return '#374151';
  };
  const impactAnalysis = estimateImpactAnalysis(reconciliationImpactRows(items), rec?.impact);
  const reviewCount = impactAnalysis.rows.filter((item) => (
    String(item.decision || '').startsWith('Проверить') || item.decision === 'На проверке'
  )).length;

  let html = '<style>'
    + '.erec-title{text-align:center;font-size:18px;font-weight:700;margin:0 0 4px}'
    + '.erec-sub{text-align:center;color:#555;font-size:11px;margin:0 0 14px}'
    + '.erec-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 14px}'
    + '.erec-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
    + '.erec-card span{display:block;color:#64748b;font-size:10px}.erec-card b{font-size:14px}'
    + '.erec-table{font-size:10px;table-layout:fixed}.erec-table th{font-size:9px}.erec-table td,.erec-table th{vertical-align:top;word-break:break-word}'
    + '.erec-table .num{text-align:right;white-space:nowrap}.erec-h{font-size:13px;font-weight:700;margin:16px 0 6px}'
    + '.erec-balance{display:flex;justify-content:space-between;gap:12px;border:1px solid;padding:8px;margin:0 0 8px;font-size:10px}.erec-balance span{color:#475569}'
    + '.erec-balance-ok{border-color:#86efac;background:#f0fdf4}.erec-balance-warn{border-color:#f59e0b;background:#fffbeb;color:#92400e}'
    + '</style>';
  html += `<div class="erec-title">АКТ / ВЕДОМОСТЬ СВЕРКИ СМЕТ № ${docEsc(rec?.id || '')}</div>`;
  html += `<div class="erec-sub">Объект: ${docEsc(rec?.projectName || '')} · Тип: ${docEsc(rec?.smetaType || 'Заказчик')} · Пакет: ${docEsc(rec?.workPackage || 'Основная')} · Статус: ${docEsc(rec?.status || 'Черновик')}</div>`;
  html += '<table>'
    + `<tr><th>Базовая смета</th><td>${docEsc((rec?.baseEstimateName || '') + ' v' + (rec?.baseVersion || ''))}</td></tr>`
    + `<tr><th>Новая смета</th><td>${docEsc((rec?.nextEstimateName || '') + ' v' + (rec?.nextVersion || ''))}</td></tr>`
    + `<tr><th>Дата создания</th><td>${docEsc(String(rec?.createdAt || '').slice(0, 10))}</td></tr>`
    + '</table>';
  html += '<div class="erec-grid">'
    + `<div class="erec-card"><span>Было</span><b>${fmtMoney(rec?.baseTotal)}</b></div>`
    + `<div class="erec-card"><span>Стало</span><b>${fmtMoney(rec?.nextTotal)}</b></div>`
    + `<div class="erec-card"><span>Разница</span><b style="color:${diffColor(rec?.impact)}">${signMoney(rec?.impact)}</b></div>`
    + `<div class="erec-card"><span>Спорные / проверить</span><b style="color:#b45309">${reviewCount}</b></div>`
    + '</div>';
  html += renderEstimateImpactAnalysis({ analysis: impactAnalysis, classPrefix: 'erec', fmtMoney, fmtQty, signMoney, diffColor });
  html += '<p style="font-size:10px;color:#555;margin-top:16px">Сверка фиксирует снимок старой и новой сметы. Строки со статусом проверки должны быть разобраны до закрытия КС, чтобы одна и та же работа не попала и в новую смету, и отдельной допработой.</p>';
  return html;
};

export const buildEstimateMeasurementComparisonDocContent = (project = {}, summary = {}, totals = {}, context = {}) => {
  const { generatedBy = '' } = context;
  const rows = summary.rows || [];
  const overRows = summary.overRows || [];
  const missingRows = summary.missingRows || [];
  const manualRows = summary.manualRows || [];
  const money = (value) => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`;
  const qty = (value, unit) => fmtMeasure(value, unit || '');

  let html = '<style>'
    + '.emc-title{text-align:center;font-size:18px;font-weight:800;margin:0 0 4px}'
    + '.emc-sub{text-align:center;color:#64748b;font-size:11px;margin:0 0 14px}'
    + '.emc-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}'
    + '.emc-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
    + '.emc-card span{display:block;color:#64748b;font-size:10px}.emc-card b{font-size:14px}'
    + '.emc-table{font-size:10px;table-layout:fixed}.emc-table th{font-size:9px}.emc-table td,.emc-table th{vertical-align:top;word-break:break-word}'
    + '.emc-num{text-align:right;white-space:nowrap}'
    + '@media print{.emc-grid{grid-template-columns:repeat(4,1fr)}.emc-table{font-size:9px}}'
    + '</style>';
  html += '<div class="emc-title">СМЕТА ↔ ОБМЕРЫ ПОМЕЩЕНИЙ</div>';
  html += `<div class="emc-sub">Объект: ${docEsc(project?.name || '')} · ${new Date().toLocaleDateString('ru-RU')} · сформировал: ${docEsc(generatedBy)}</div>`;
  html += '<div class="emc-grid">'
    + `<div class="emc-card"><span>Строк проверено</span><b>${rows.length}</b></div>`
    + `<div class="emc-card"><span>Сверх сметы</span><b style="color:#dc2626">${overRows.length}</b></div>`
    + `<div class="emc-card"><span>Нет обмера/ед. изм.</span><b style="color:#b45309">${missingRows.length + manualRows.length}</b></div>`
    + `<div class="emc-card"><span>Оценка доп. объёма</span><b>${money(summary.overSum)}</b></div>`
    + '</div>';
  html += '<table>'
    + `<tr><th>Помещений</th><td>${totals.roomCount || 0}</td><th>Стены общие</th><td>${qty(totals.wall_gross_area, 'м2')}</td><th>Минус окна</th><td>${qty(totals.window_area, 'м2')}</td></tr>`
    + `<tr><th>Минус двери</th><td>${qty(totals.door_area, 'м2')}</td><th>Стены чистые</th><td>${qty(totals.wall_net_area, 'м2')}</td><th>Пол</th><td>${qty(totals.floor_area, 'м2')}</td></tr>`
    + `<tr><th>Потолок</th><td>${qty(totals.ceiling_area, 'м2')}</td><th>Откосы</th><td>${qty(Number(totals.window_reveals || 0) + Number(totals.door_reveals || 0), 'м2')}</td><th>Формула стен</th><td>${qty(totals.wall_gross_area, 'м2')} - ${qty(totals.openings_area, 'м2')} = ${qty(totals.wall_net_area, 'м2')}</td></tr>`
    + '</table>';
  html += '<table class="emc-table"><tr><th>Статус</th><th>Пакет</th><th>Раздел</th><th>Позиция</th><th>Основание</th><th>Смета</th><th>Обмер</th><th>Разница</th><th>Оценка</th></tr>';
  html += rows.map((row) => {
    const color = row.status === 'Сверх сметы' ? '#dc2626' : row.status === 'Сходится' ? '#059669' : '#b45309';
    const unit = row.expectedUnit || row.planUnit;
    return '<tr>'
      + `<td style="color:${color};font-weight:700">${docEsc(row.status)}</td>`
      + `<td>${docEsc(row.packageName)}</td>`
      + `<td>${docEsc(row.sectionName)}</td>`
      + `<td>${docEsc(row.itemName)}</td>`
      + `<td>${docEsc(row.basisLabel)}</td>`
      + `<td class="emc-num">${docEsc(qty(row.planQty, row.planUnit))}</td>`
      + `<td class="emc-num">${row.supported && row.unitOk ? docEsc(qty(row.measuredQty, unit)) : '—'}</td>`
      + `<td class="emc-num">${row.supported && row.unitOk ? docEsc(`${row.diff > 0 ? '+' : ''}${qty(row.diff, unit)}`) : '—'}</td>`
      + `<td class="emc-num">${row.overSum > 0 ? money(row.overSum) : '—'}</td>`
      + '</tr>';
  }).join('');
  if (!rows.length) {
    html += '<tr><td colspan="9" style="text-align:center;color:#64748b">Нет активной сметы заказчика или рабочих строк для сравнения</td></tr>';
  }
  html += '</table><p style="font-size:10px;color:#64748b;margin-top:12px">Отчёт не создаёт допработы автоматически. Он показывает, где фактическое основание объёма из помещений отличается от активной сметы заказчика.</p>';
  return html;
};

export const buildWorkJournalEstimateReconciliationDocContent = (project = {}, summary = {}, context = {}) => {
  const {
    generatedBy = '',
    statusMeta = () => ({ color: '#334155' }),
  } = context;
  const rows = summary.rows || [];
  const linkedRows = summary.linkedRows || [];
  const outsideRows = summary.outsideRows || [];
  const reviewRows = summary.reviewRows || [];
  const overRows = summary.overRows || [];
  const money = (value) => `${Math.round(Number(value || 0)).toLocaleString('ru-RU')} ₽`;
  const pct = Number(summary.estimatePlan || 0) > 0
    ? Math.round((Number(summary.estimateDone || 0) / Number(summary.estimatePlan || 0)) * 1000) / 10
    : 0;

  let html = '<style>'
    + '.wjr-title{text-align:center;font-size:18px;font-weight:800;margin:0 0 4px}'
    + '.wjr-sub{text-align:center;color:#64748b;font-size:11px;margin:0 0 14px}'
    + '.wjr-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0}'
    + '.wjr-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
    + '.wjr-card span{display:block;color:#64748b;font-size:10px}.wjr-card b{font-size:14px}'
    + '.wjr-table{font-size:10px;table-layout:fixed}.wjr-table th{font-size:9px}.wjr-table td,.wjr-table th{vertical-align:top;word-break:break-word}'
    + '.wjr-num{text-align:right;white-space:nowrap}'
    + '@media print{.wjr-grid{grid-template-columns:repeat(4,1fr)}.wjr-table{font-size:9px}}'
    + '</style>';
  html += '<div class="wjr-title">СВЕРКА ЖПР ↔ АКТИВНАЯ СМЕТА</div>';
  html += `<div class="wjr-sub">Объект: ${docEsc(project?.name || '')} · ${new Date().toLocaleDateString('ru-RU')} · сформировал: ${docEsc(generatedBy)}</div>`;
  html += '<div class="wjr-grid">'
    + `<div class="wjr-card"><span>Строк ЖПР</span><b>${rows.length}</b></div>`
    + `<div class="wjr-card"><span>Найдено в смете</span><b style="color:#047857">${linkedRows.length}</b></div>`
    + `<div class="wjr-card"><span>Вне сметы / проверка</span><b style="color:#b45309">${outsideRows.length + reviewRows.length}</b></div>`
    + `<div class="wjr-card"><span>Превышение объёма</span><b style="color:#dc2626">${overRows.length}</b></div>`
    + '</div>';
  html += '<div class="wjr-grid">'
    + `<div class="wjr-card"><span>Активная смета</span><b>${money(summary.estimatePlan)}</b></div>`
    + `<div class="wjr-card"><span>Закрыто в смете</span><b>${money(summary.estimateDone)} · ${pct}%</b></div>`
    + `<div class="wjr-card"><span>Сумма ЖПР</span><b>${money(summary.journalTotal)}</b></div>`
    + `<div class="wjr-card"><span>ЖПР вне сметы</span><b style="color:#dc2626">${money(summary.outsideTotal)}</b></div>`
    + '</div>';
  html += '<table class="wjr-table"><tr><th>Статус</th><th>Дата</th><th>ЖПР / исполнитель</th><th>Объём ЖПР</th><th>Сумма ЖПР</th><th>Строка сметы</th><th>План сметы</th><th>Сделано в смете</th><th>Оценка по смете</th><th>Увер.</th></tr>';
  html += rows.map((row) => {
    const meta = statusMeta(row.status);
    const match = row.match;
    const estimateName = match
      ? `${match.packageName && match.packageName !== 'Основная' ? `${match.packageName} / ` : ''}${match.sectionName} / ${match.itemName}`
      : '—';
    return '<tr>'
      + `<td style="color:${meta.color};font-weight:700">${docEsc(row.status)}</td>`
      + `<td>${docEsc(row.work?.date || '')}</td>`
      + `<td><b>${docEsc(row.work?.description || '')}</b><div style="color:#64748b">${docEsc(row.work?.masterName || '')}</div></td>`
      + `<td class="wjr-num">${docEsc(fmtMeasure(row.workQty, row.workUnit))}</td>`
      + `<td class="wjr-num">${money(row.work?.total)}</td>`
      + `<td>${docEsc(estimateName)}</td>`
      + `<td class="wjr-num">${docEsc(match ? fmtMeasure(match.planQty, match.unit) : '—')}</td>`
      + `<td class="wjr-num">${docEsc(match ? fmtMeasure(match.doneQty, match.unit) : '—')}</td>`
      + `<td class="wjr-num">${row.estimateValue ? money(row.estimateValue) : '—'}</td>`
      + `<td class="wjr-num">${row.score ? `${Math.round(row.score * 100)}%` : '—'}</td>`
      + '</tr>';
  }).join('');
  if (!rows.length) {
    html += '<tr><td colspan="10" style="text-align:center;color:#64748b">Записей ЖПР для сверки нет</td></tr>';
  }
  html += '</table><p style="font-size:10px;color:#64748b;margin-top:12px">Сумма ЖПР — внутренняя сумма по исполнителю. Оценка по смете считается по активной смете заказчика и нужна только для контроля соответствия факта строкам сметы.</p>';
  return html;
};

export const buildMaterialNormCoverageDocContent = (projectName = '', rows = [], context = {}) => {
  const {
    companyRequisites = {},
    companyName = '',
    materialTitleForNormRule = () => '',
    materialNormCoverageComment = () => '',
  } = context;
  const okCount = rows.filter((row) => ['Норма применена', 'Поправка объекта', 'Поправка сметы'].includes(row.status)).length;
  const skippedCount = rows.filter((row) => row.status === 'Норма не нужна').length;
  const missingCount = rows.filter((row) => row.status === 'Нет нормы').length;
  const unlinkedCount = rows.filter((row) => row.status === 'Материал без работы').length;
  const shortageCount = rows.filter((row) => row.status === 'Нехватка материала по норме').length;
  const infoCount = rows.filter((row) => row.status === 'Нет материала в смете').length;
  const zeroQtyCount = rows.filter((row) => row.status === 'Материал без количества').length;
  const invalidQtyCount = rows.filter((row) => row.status === 'Некорректное количество').length;
  const orgName = companyTitle(companyRequisites, companyName);
  const statusClass = (status) => {
    if (['Норма применена', 'Поправка объекта', 'Поправка сметы'].includes(status)) return 'mn-ok';
    if (status === 'Норма не нужна') return 'mn-skip';
    if (status === 'Некорректное количество') return 'mn-danger';
    if (status === 'Нет материала в смете') return 'mn-info';
    return 'mn-warn';
  };

  let html = '<style>.mn-tbl{border-collapse:collapse;width:100%;font-size:10.5px;margin:8px 0}.mn-tbl th,.mn-tbl td{border:1px solid #333;padding:5px 6px;vertical-align:top}.mn-tbl th{background:#f3f4f6}.mn-ok{background:#dcfce7}.mn-info{background:#dbeafe}.mn-skip{background:#f3f4f6}.mn-warn{background:#fef3c7}.mn-danger{background:#fee2e2}.mn-note{font-size:10px;color:#555}.mn-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(90px,1fr));gap:8px;margin:10px 0}.mn-summary div{border:1px solid #333;padding:6px;text-align:center}.mn-summary b{display:block;font-size:14px}</style>';
  html += '<h2 style="text-align:center;margin:6px 0">ВЕДОМОСТЬ ПОКРЫТИЯ СМЕТЫ НОРМАМИ МАТЕРИАЛОВ</h2>';
  html += '<p style="text-align:center;font-size:11px;color:#444">контроль связки: работа сметы → норма расхода → материал сметы</p>';
  html += `<p style="font-size:12px"><b>Объект:</b> ${docEsc(projectName || '')} · <b>Организация:</b> ${docEsc(orgName)} · <b>Дата:</b> ${new Date().toLocaleDateString('ru-RU')}</p>`;
  html += '<div class="mn-summary">'
    + `<div><span>Покрыто</span><b>${okCount}</b></div>`
    + `<div><span>Без материалов</span><b>${skippedCount}</b></div>`
    + `<div><span>Нет нормы</span><b>${missingCount}</b></div>`
    + `<div><span>Нехватка</span><b>${shortageCount}</b></div>`
    + `<div><span>Материал без работы</span><b>${unlinkedCount}</b></div>`
    + `<div><span>Некорректно</span><b>${invalidQtyCount}</b></div>`
    + `<div><span>Без количества</span><b>${zeroQtyCount}</b></div>`
    + `<div><span>Нет материала</span><b>${infoCount}</b></div>`
    + `<div><span>Всего</span><b>${rows.length}</b></div>`
    + '</div>';
  if (!rows.length) {
    html += '<p style="text-align:center;color:#888;font-size:12px;padding:16px">Нет активной сметы заказчика или нет строк для проверки.</p>';
    return html;
  }
  html += '<table class="mn-tbl"><tr><th>№</th><th>Статус</th><th>Смета / раздел</th><th>Работа</th><th>Объём</th><th>Материал / норма</th><th>Потребность</th><th>В смете</th><th>Комментарий</th></tr>';
  rows.forEach((row, index) => {
    html += `<tr class="${statusClass(row.status)}">`
      + `<td>${index + 1}</td>`
      + `<td><b>${docEsc(row.status || '')}</b></td>`
      + `<td>${docEsc((row.estimateName || '') + ' / ' + (row.packageName || ''))}<div class="mn-note">${docEsc(row.sectionName || '')}</div></td>`
      + `<td>${docEsc(row.workName || '')}</td>`
      + `<td>${docEsc(row.workQty ? fmtMeasure(row.workQty, row.workUnit) : '')}</td>`
      + `<td>${docEsc(row.materialName || materialTitleForNormRule(row.rule) || '')}<div class="mn-note">${docEsc(row.rule?.label || row.rule?.ruleKey || '')}</div></td>`
      + `<td>${docEsc(row.requiredQty ? fmtMeasure(row.requiredQty, row.requiredUnit) : '')}</td>`
      + `<td>${docEsc(row.hasEstimateMaterial ? fmtMeasure(row.materialQty, row.materialUnit) : '')}</td>`
      + `<td>${docEsc(materialNormCoverageComment(row))}</td>`
      + '</tr>';
  });
  html += '</table>';
  html += '<div style="margin-top:24px;display:grid;grid-template-columns:1fr 1fr;gap:20px"><div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Сметчик:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div><div><div style="font-size:11px;font-weight:600;margin-bottom:30px">Прораб / главный инженер:</div><div style="border-bottom:1px solid #333;min-height:18px"></div></div></div>';
  html += '<p style="margin-top:16px;font-size:10px;color:#666;text-align:center">Строки `Некорректное количество` и `Материал без количества` сначала исправляются в смете. Строки `Нет материала в смете` сначала добавляются в смету/доп. смету. После этого снабжение создаёт заявку по утверждённой потребности.</p>';
  return html;
};

export const buildSupplyControlReportDocContent = (data = {}, context = {}) => {
  const {
    issues = [],
    inWorkRequests = [],
    offersToReview = [],
    invoicesToPay = [],
    debt = 0,
  } = data;
  const {
    companyName = '',
    generatedBy = '',
  } = context;

  let html = directorDocStyles();
  html += '<div class="dir-title">КОНТРОЛЬ СНАБЖЕНИЯ И СКЛАДА</div>';
  html += `<div class="dir-sub">${docEsc(companyName || 'СтройКа')} · ${new Date().toLocaleDateString('ru-RU')} · сформировал: ${docEsc(generatedBy)}</div>`;
  html += '<div class="dir-grid">';
  html += `<div class="dir-card"><span>Заявки в работе</span><b>${inWorkRequests.length}</b></div>`;
  html += `<div class="dir-card"><span>КП на выбор</span><b>${offersToReview.length}</b></div>`;
  html += `<div class="dir-card"><span>Счета к оплате</span><b>${invoicesToPay.length}</b></div>`;
  html += `<div class="dir-card"><span>Долг по счетам</span><b>${fmtDocMoney(debt)}</b></div>`;
  html += '</div>';
  html += '<div class="dir-section"><h3>Замечания</h3>';
  if (issues.length) {
    html += '<table class="dir-table"><tr><th>N</th><th>Приоритет</th><th>Объект/склад</th><th>Позиция</th><th>Проблема</th><th>Действие</th></tr>';
    issues.slice(0, 45).forEach((row, index) => {
      html += '<tr>'
        + `<td>${index + 1}</td>`
        + `<td>${docEsc(row.severity)}</td>`
        + `<td>${docEsc(row.project)}</td>`
        + `<td>${docEsc(row.where)}</td>`
        + `<td>${docEsc(row.problem)}</td>`
        + `<td>${docEsc(row.action)}</td>`
        + '</tr>';
    });
    html += '</table>';
  } else {
    html += '<div class="dir-ok">По снабжению и складу критичных замечаний не найдено.</div>';
  }
  html += '</div>';
  return html;
};

export const buildEstimateControlReportDocContent = (data = {}, context = {}) => {
  const {
    estimates = [],
    activeEstimates = [],
    issues = [],
    topItems = [],
    activeTotal = 0,
  } = data;
  const {
    companyName = '',
    generatedBy = '',
  } = context;

  let html = directorDocStyles();
  html += '<div class="dir-title">ПРОВЕРКА СМЕТ ДИРЕКТОРА</div>';
  html += `<div class="dir-sub">${docEsc(companyName || 'СтройКа')} · ${new Date().toLocaleDateString('ru-RU')} · сформировал: ${docEsc(generatedBy)}</div>`;
  html += '<div class="dir-grid">';
  html += `<div class="dir-card"><span>Всего смет</span><b>${estimates.length}</b></div>`;
  html += `<div class="dir-card"><span>Активных</span><b>${activeEstimates.length}</b></div>`;
  html += `<div class="dir-card"><span>Замечаний</span><b>${issues.length}</b></div>`;
  html += `<div class="dir-card"><span>Активная сумма</span><b>${fmtDocMoney(activeTotal)}</b></div>`;
  html += '</div>';
  html += '<div class="dir-section"><h3>Замечания</h3>';
  if (issues.length) {
    html += '<table class="dir-table"><tr><th>N</th><th>Приоритет</th><th>Объект</th><th>Смета</th><th>Где</th><th>Проблема</th><th>Действие</th></tr>';
    issues.slice(0, 40).forEach((row, index) => {
      html += '<tr>'
        + `<td>${index + 1}</td>`
        + `<td>${docEsc(row.severity)}</td>`
        + `<td>${docEsc(row.project)}</td>`
        + `<td>${docEsc(row.estimate)}</td>`
        + `<td>${docEsc(row.where)}</td>`
        + `<td>${docEsc(row.problem)}</td>`
        + `<td>${docEsc(row.action)}</td>`
        + '</tr>';
    });
    html += '</table>';
  } else {
    html += '<div class="dir-ok">По активным и рабочим сметам критичных замечаний не найдено.</div>';
  }
  html += '</div>';
  html += '<div class="dir-section"><h3>Самые дорогие позиции активных смет</h3>';
  if (topItems.length) {
    html += '<table class="dir-table"><tr><th>N</th><th>Объект</th><th>Смета</th><th>Раздел</th><th>Позиция</th><th>Кол-во</th><th>Сумма</th></tr>';
    topItems.forEach((item, index) => {
      html += '<tr>'
        + `<td>${index + 1}</td>`
        + `<td>${docEsc(item.project)}</td>`
        + `<td>${docEsc(item.estimate)}</td>`
        + `<td>${docEsc(item.section)}</td>`
        + `<td>${docEsc(item.name)}</td>`
        + `<td>${docEsc(fmtMeasure(item.qty, item.unit))}</td>`
        + `<td>${fmtDocMoney(item.sum)}</td>`
        + '</tr>';
    });
    html += '</table>';
  } else {
    html += '<div class="dir-risk">Активных позиций со стоимостью пока нет.</div>';
  }
  html += '</div>';
  return html;
};

export const buildEstimateDiffDocContent = (data = {}) => {
  const {
    baseMeta = '',
    nextMeta = '',
    projectName = '',
    estimateType = '',
    workPackage = '',
    diff = { added: [], removed: [], changed: [], baseTotal: 0, nextTotal: 0, impact: 0 },
  } = data;
  const fmtMoney = (value) => `${(Math.round(Number(value || 0) * 100) / 100).toLocaleString('ru-RU')} ₽`;
  const fmtQty = (value) => {
    const quantity = Number(value || 0);
    return Math.abs(quantity - Math.round(quantity)) < 0.001
      ? String(Math.round(quantity))
      : quantity.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
  };
  const signMoney = (value) => `${Number(value || 0) > 0 ? '+' : ''}${fmtMoney(value)}`;
  const diffColor = (value) => {
    if (Number(value || 0) > 0) return '#b45309';
    if (Number(value || 0) < 0) return '#047857';
    return '#374151';
  };
  const changedPositionRows = estimateDiffChangedRows(diff);
  const impactAnalysis = estimateImpactAnalysis(changedPositionRows, diff.impact);

  let html = '<style>'
    + '.ediff-title{text-align:center;font-size:18px;font-weight:700;margin:0 0 4px}'
    + '.ediff-sub{text-align:center;color:#555;font-size:11px;margin:0 0 14px}'
    + '.ediff-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0 14px}'
    + '.ediff-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
    + '.ediff-card span{display:block;color:#64748b;font-size:10px}.ediff-card b{font-size:14px}'
    + '.ediff-table{font-size:10px;table-layout:fixed}.ediff-table th{font-size:9px}.ediff-table td,.ediff-table th{vertical-align:top;word-break:break-word}'
    + '.ediff-table .num{text-align:right;white-space:nowrap}'
    + '.ediff-h{font-size:13px;font-weight:700;margin:16px 0 6px}'
    + '.ediff-balance{display:flex;justify-content:space-between;gap:12px;border:1px solid;padding:8px;margin:0 0 8px;font-size:10px}.ediff-balance span{color:#475569}'
    + '.ediff-balance-ok{border-color:#86efac;background:#f0fdf4}.ediff-balance-warn{border-color:#f59e0b;background:#fffbeb;color:#92400e}'
    + '@media print{.ediff-grid{grid-template-columns:repeat(3,1fr)}.ediff-table{font-size:9px}}'
    + '</style>';
  html += '<div class="ediff-title">СОПОСТАВИТЕЛЬНАЯ ВЕДОМОСТЬ СМЕТ</div>';
  html += `<div class="ediff-sub">Объект: ${docEsc(projectName)} · Тип: ${docEsc(estimateType)} · Пакет: ${docEsc(workPackage)}</div>`;
  html += `<table><tr><th>База сравнения</th><td>${docEsc(baseMeta)}</td></tr><tr><th>Новая / выбранная смета</th><td>${docEsc(nextMeta)}</td></tr></table>`;
  html += '<div class="ediff-grid">'
    + `<div class="ediff-card"><span>Было</span><b>${fmtMoney(diff.baseTotal)}</b></div>`
    + `<div class="ediff-card"><span>Стало</span><b>${fmtMoney(diff.nextTotal)}</b></div>`
    + `<div class="ediff-card"><span>Разница</span><b style="color:${diffColor(diff.impact)}">${signMoney(diff.impact)}</b></div>`
    + '</div>';
  html += '<div class="ediff-grid">'
    + `<div class="ediff-card"><span>Изменено позиций</span><b>${changedPositionRows.filter(row => row.kind === 'changed').length}</b></div>`
    + `<div class="ediff-card"><span>Добавлено позиций</span><b>${changedPositionRows.filter(row => row.kind === 'added').length}</b></div>`
    + `<div class="ediff-card"><span>Исключено позиций</span><b>${changedPositionRows.filter(row => row.kind === 'removed').length}</b></div>`
    + '</div>';
  html += renderEstimateImpactAnalysis({ analysis: impactAnalysis, classPrefix: 'ediff', fmtMoney, fmtQty, signMoney, diffColor });
  html += '<p style="font-size:10px;color:#555;margin-top:16px">Документ показывает только позиции, которые изменились между выбранными редакциями сметы. Неизменённые и пустые технические строки не выводятся.</p>';
  return html;
};

export const buildProjectEstimateDiffSummaryDocContent = (data = {}) => {
  const {
    projectName = '',
    packageCount = 0,
    changedPackageCount = 0,
    baseTotal = 0,
    nextTotal = 0,
    impact = 0,
    rows = [],
  } = data;
  const fmtMoney = (value) => `${(Math.round(Number(value || 0) * 100) / 100).toLocaleString('ru-RU')} ₽`;
  const signMoney = (value) => `${Number(value || 0) > 0 ? '+' : ''}${fmtMoney(value)}`;
  const fmtQty = (value) => {
    const quantity = Number(value || 0);
    return Math.abs(quantity - Math.round(quantity)) < 0.001
      ? String(Math.round(quantity))
      : quantity.toLocaleString('ru-RU', { maximumFractionDigits: 3 });
  };
  const diffColor = (value) => {
    if (Number(value || 0) > 0) return '#b45309';
    if (Number(value || 0) < 0) return '#047857';
    return '#374151';
  };
  const analysis = estimateImpactAnalysis(rows, impact);
  let html = '<style>'
    + '.eps-title{text-align:center;font-size:18px;font-weight:700;margin:0 0 4px}'
    + '.eps-sub{text-align:center;color:#555;font-size:11px;margin:0 0 14px}'
    + '.eps-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:12px 0 14px}'
    + '.eps-card{border:1px solid #cbd5e1;border-radius:8px;padding:8px;background:#f8fafc}'
    + '.eps-card span{display:block;color:#64748b;font-size:10px}.eps-card b{font-size:14px}'
    + '.eps-table{font-size:9px;table-layout:fixed}.eps-table th{font-size:8px}.eps-table td,.eps-table th{vertical-align:top;word-break:break-word}'
    + '.eps-table .num{text-align:right;white-space:nowrap}.eps-h{font-size:13px;font-weight:700;margin:16px 0 6px}'
    + '.eps-balance{display:flex;justify-content:space-between;gap:12px;border:1px solid;padding:8px;margin:0 0 8px;font-size:10px}.eps-balance span{color:#475569}'
    + '.eps-balance-ok{border-color:#86efac;background:#f0fdf4}.eps-balance-warn{border-color:#f59e0b;background:#fffbeb;color:#92400e}'
    + '@media print{.eps-grid{grid-template-columns:repeat(4,1fr)}.eps-table{font-size:8px}}'
    + '</style>';
  html += '<div class="eps-title">СВОД ИЗМЕНЕНИЙ СМЕТ ПО ОБЪЕКТУ</div>';
  html += `<div class="eps-sub">Объект: ${docEsc(projectName)} · сравниваются предыдущие и активные редакции каждого пакета</div>`;
  html += '<div class="eps-grid">'
    + `<div class="eps-card"><span>Пакетов сравнено</span><b>${packageCount}</b></div>`
    + `<div class="eps-card"><span>Пакетов с изменениями</span><b>${changedPackageCount}</b></div>`
    + `<div class="eps-card"><span>Изменённых позиций</span><b>${rows.length}</b></div>`
    + `<div class="eps-card"><span>Общая разница</span><b style="color:${diffColor(impact)}">${signMoney(impact)}</b></div>`
    + '</div>';
  html += '<div class="eps-grid">'
    + `<div class="eps-card"><span>Было по пакетам</span><b>${fmtMoney(baseTotal)}</b></div>`
    + `<div class="eps-card"><span>Стало по пакетам</span><b>${fmtMoney(nextTotal)}</b></div>`
    + `<div class="eps-card"><span>Плюсовые позиции</span><b style="color:${diffColor(analysis.positive)}">${signMoney(analysis.positive)}</b></div>`
    + `<div class="eps-card"><span>Минусовые позиции</span><b style="color:${diffColor(analysis.negative)}">${signMoney(analysis.negative)}</b></div>`
    + '</div>';
  html += renderEstimateImpactAnalysis({ analysis, classPrefix: 'eps', fmtMoney, fmtQty, signMoney, diffColor, showPackage: true, showImpactCards: false });
  html += '<p style="font-size:10px;color:#555;margin-top:16px">В свод входят только позиции, изменившиеся между предыдущей и активной редакциями каждого пакета смет объекта. Неизменённые пакеты и пустые технические строки в таблицу не попадают.</p>';
  return html;
};
