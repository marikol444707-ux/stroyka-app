import { _normalizeUnit, fmtMeasure, normalizeMeasure, toNum } from './measureUtils';
import { materialLookupText } from './materialMatchUtils';

export const buildWarehouseInvoiceEstimateControl = ({
  inv,
  warehouseInvoiceItems,
  materialControlSummaryForProject,
  canonicalMaterialMeta,
  materialNameLookupKey = materialLookupText,
}) => {
  const sourcePackageOf = (item = {}, parent = {}) => item.workPackage || item.work_package || parent.workPackage || parent.work_package || '';
  const linkedWorkLabel = (item = {}) => item.parentWorkName || item.parent_work_name || item.estimateWorkName || item.estimate_work_name || item.workName || item.work_name || '';
  const invoiceRows = warehouseInvoiceItems(inv);
  const items = invoiceRows.items || [];
  const place = inv?.location === 'Основной склад' ? '' : (inv?.project || inv?.location || '');
  if (!place) {
    return items.map((item, index) => ({
      index,
      name: item.name || '',
      quantity: toNum(item.quantity),
      unit: item.unit || '',
      lineSum: Number(item.total || 0) || Number(item.quantity || 0) * Number(item.price || 0),
      status: 'Основной склад',
      severity: 'neutral',
      detail: 'Без привязки к объектной смете',
      planText: '—',
      beforeText: '—',
      afterText: '—',
      overText: '—',
    }));
  }

  const summary = materialControlSummaryForProject(place);
  const rowsByKey = new Map((summary.rows || []).map(row => [row.key, row]));
  const itemMeta = items.map(item => {
    const itemPackage = sourcePackageOf(item, inv);
    const meta = canonicalMaterialMeta(place, item.name, item.unit);
    const baseKey = materialNameLookupKey(meta.name || item.name);
    const key = baseKey ? baseKey + (itemPackage ? '|' + String(itemPackage).trim().toLowerCase() : '|__no_package__') : '';
    const norm = normalizeMeasure(item.quantity, item.unit);
    return { meta, key, qty: norm.qty, unit: norm.unit || item.unit || '', workPackage: itemPackage };
  });
  const invoiceQtyByKey = {};
  itemMeta.forEach(meta => {
    if (meta.key) invoiceQtyByKey[meta.key] = (invoiceQtyByKey[meta.key] || 0) + Number(meta.qty || 0);
  });
  const seenQtyByKey = {};

  return items.map((item, index) => {
    const meta = itemMeta[index] || {};
    const qty = Number(meta.qty || 0);
    const unit = meta.unit || item.unit || '';
    const lineSum = Number(item.total || 0) || Number(item.quantity || 0) * Number(item.price || 0);
    if (!item?.name) {
      return {
        index,
        name: '',
        quantity: 0,
        unit,
        lineSum: 0,
        status: 'Не заполнено',
        severity: 'neutral',
        detail: '',
        planText: '—',
        beforeText: '—',
        afterText: '—',
        overText: '—',
      };
    }

    const backendControl = item.estimateControl || item.estimate_control || {};
    const row = meta.key ? rowsByKey.get(meta.key) : null;
    const alreadySeen = seenQtyByKey[meta.key] || 0;
    seenQtyByKey[meta.key] = alreadySeen + qty;
    const workLabel = linkedWorkLabel(item);

    if (!row || Number(row.controlPlanQty || row.planQty || 0) <= 0) {
      if (Number(backendControl.matchedRows || 0) > 0) {
        const unitReview = Number(backendControl.matchedWithDifferentUnit || 0) > 0;
        return {
          index,
          name: item.name || '',
          projectName: place,
          canonicalName: item.name || '',
          workPackage: backendControl.workPackage || meta.workPackage || item.workPackage || item.work_package || '',
          quantity: qty,
          incomingQty: qty,
          unit,
          rowUnit: unit,
          lineSum,
          shortageQty: 0,
          overQty: 0,
          priceOverSum: 0,
          unitMismatch: unitReview,
          status: unitReview ? 'Ед. проверить' : 'По смете',
          severity: unitReview ? 'warning' : 'success',
          detail: unitReview ? 'Сервер сопоставил материал по семейству/словам, но единица отличается от сметы' : 'Сервер сопоставил материал по семейству/словам полного наименования',
          planText: backendControl.plannedQty ? fmtMeasure(backendControl.plannedQty, unit) : 'найдено в смете',
          beforeText: '—',
          afterText: fmtMeasure(qty, unit),
          overText: '—',
          shortageText: '—',
          lineSumText: lineSum ? lineSum.toLocaleString('ru-RU') + ' ₽' : '—',
          planPriceText: '—',
          invoicePriceText: qty > 0 && lineSum ? Math.round(lineSum / qty).toLocaleString('ru-RU') + ' ₽/' + (unit || 'ед.') : '—',
          priceOverText: '—',
        };
      }

      if (backendControl.status === 'consumable_outside_estimate' || backendControl.isConsumableOutsideEstimate) {
        return {
          index,
          name: item.name || '',
          projectName: place,
          canonicalName: item.name || '',
          workPackage: backendControl.workPackage || meta.workPackage || item.workPackage || item.work_package || '',
          quantity: qty,
          incomingQty: qty,
          unit,
          rowUnit: unit,
          lineSum,
          shortageQty: 0,
          overQty: 0,
          priceOverSum: 0,
          unitMismatch: false,
          status: 'Расходник вне сметы',
          severity: 'info',
          detail: backendControl.controlMessage || 'Расходник принят на склад объекта и оставлен в контроле как позиция вне сметной ресурсной строки',
          planText: 'расходник',
          beforeText: '—',
          afterText: fmtMeasure(qty, unit),
          overText: '—',
          shortageText: '—',
          lineSumText: lineSum ? lineSum.toLocaleString('ru-RU') + ' ₽' : '—',
          planPriceText: '—',
          invoicePriceText: qty > 0 && lineSum ? Math.round(lineSum / qty).toLocaleString('ru-RU') + ' ₽/' + (unit || 'ед.') : '—',
          priceOverText: '—',
        };
      }

      if (workLabel) {
        return {
          index,
          name: item.name || '',
          projectName: place,
          canonicalName: item.name || '',
          workPackage: meta.workPackage || item.workPackage || item.work_package || '',
          isCompositeWorkMaterial: true,
          quantity: qty,
          incomingQty: qty,
          unit,
          rowUnit: unit,
          lineSum,
          shortageQty: 0,
          overQty: 0,
          priceOverSum: 0,
          unitMismatch: false,
          status: 'Комплектация работы',
          severity: 'info',
          detail: 'Материал не выделен отдельной ресурсной строкой сметы, но привязан к укрупненной работе',
          planText: 'укрупненная работа',
          beforeText: '—',
          afterText: fmtMeasure(qty, unit),
          overText: '—',
          shortageText: '—',
          lineSumText: lineSum ? lineSum.toLocaleString('ru-RU') + ' ₽' : '—',
          planPriceText: '—',
          invoicePriceText: qty > 0 && lineSum ? Math.round(lineSum / qty).toLocaleString('ru-RU') + ' ₽/' + (unit || 'ед.') : '—',
          priceOverText: '—',
          workRefs: [workLabel],
          sectionsList: item.sectionName ? [item.sectionName] : [],
          estimateItemKey: item.estimateItemKey || item.estimate_item_key || item.parentWorkKey || item.parent_work_key || '',
        };
      }

      return {
        index,
        name: item.name || '',
        projectName: place,
        canonicalName: item.name || '',
        workPackage: meta.workPackage || '',
        quantity: qty,
        incomingQty: qty,
        unit,
        rowUnit: unit,
        lineSum,
        shortageQty: 0,
        overQty: qty,
        priceOverSum: 0,
        unitMismatch: false,
        status: 'Вне сметы',
        severity: 'danger',
        detail: 'Материал есть в накладной, но не найден в активной смете и нормах объекта',
        planText: 'нет в смете/нормах',
        beforeText: '—',
        afterText: fmtMeasure(qty, unit),
        overText: fmtMeasure(qty, unit),
        lineSumText: lineSum ? lineSum.toLocaleString('ru-RU') + ' ₽' : '—',
        planPriceText: '—',
        priceOverText: '—',
      };
    }

    const rowUnit = row.unit || unit;
    const unitMismatch = rowUnit && unit && _normalizeUnit(rowUnit) !== _normalizeUnit(unit);
    const invoiceQty = Number(invoiceQtyByKey[meta.key] || 0);
    const suppliedBeforeInvoice = inv?.id ? Math.max(0, Number(row.supplied || 0) - invoiceQty) : Number(row.supplied || 0);
    const afterQty = suppliedBeforeInvoice + alreadySeen + qty;
    const controlPlanQty = Number(row.controlPlanQty || row.planQty || 0);
    const overQty = Math.max(0, afterQty - controlPlanQty);
    const shortageQty = Math.max(0, controlPlanQty - afterQty);
    const beforeQty = suppliedBeforeInvoice + alreadySeen;
    const coveredByLineQty = Math.min(qty, Math.max(0, controlPlanQty - beforeQty));
    const planUnitPrice = Number(row.planQty || 0) > 0 ? Number(row.planSum || 0) / Number(row.planQty || 1) : 0;
    const invoiceUnitPrice = qty > 0 ? lineSum / qty : Number(item.price || 0);
    const priceOverSum = planUnitPrice > 0 ? Math.max(0, lineSum - planUnitPrice * qty) : 0;
    const priceOver = priceOverSum > 1;
    const severity = unitMismatch ? 'warning' : overQty > 0 ? 'danger' : priceOver ? 'warning' : 'success';
    const status = unitMismatch ? 'Ед. не совпала' : overQty > 0 ? 'Сверх сметы' : priceOver ? 'Цена выше плана' : 'По смете';

    return {
      index,
      name: item.name || '',
      projectName: place,
      canonicalName: row.name,
      workPackage: meta.workPackage || row.workPackage || '',
      planSourceCount: row.planSourceCount || (row.planDetails || []).length,
      planDetails: row.planDetails || [],
      sectionsList: row.sections || [],
      workRefs: row.workRefs || [],
      quantity: qty,
      incomingQty: qty,
      unit,
      rowUnit,
      lineSum,
      planQty: controlPlanQty,
      estimatePlanQty: Number(row.planQty || 0),
      normPlanQty: Number(row.normPlanQty || 0),
      beforeQty,
      afterQty,
      shortageQty,
      overQty,
      priceOverSum,
      unitMismatch,
      status,
      severity,
      detail: unitMismatch
        ? 'В смете ' + (rowUnit || '—') + ', в накладной ' + (unit || '—')
        : overQty > 0
          ? 'После этой строки будет превышение плана'
          : priceOver
            ? 'Сумма строки выше сметного ориентира'
            : shortageQty > 0
              ? 'Поставка закрывает часть сметной потребности'
              : 'Поставка закрывает сметную потребность',
      planText: fmtMeasure(controlPlanQty, rowUnit),
      estimatePlanText: Number(row.planQty || 0) > 0 ? fmtMeasure(row.planQty, rowUnit) : '—',
      normPlanText: Number(row.normPlanQty || 0) > 0 ? fmtMeasure(row.normPlanQty, rowUnit) : '—',
      incomingText: fmtMeasure(qty, rowUnit),
      coveredByLineText: fmtMeasure(coveredByLineQty, rowUnit),
      beforeText: fmtMeasure(beforeQty, rowUnit),
      afterText: fmtMeasure(afterQty, rowUnit),
      shortageText: shortageQty > 0 ? fmtMeasure(shortageQty, rowUnit) : '—',
      overText: overQty > 0 ? fmtMeasure(overQty, rowUnit) : '—',
      lineSumText: lineSum ? lineSum.toLocaleString('ru-RU') + ' ₽' : '—',
      planPriceText: planUnitPrice > 0 ? Math.round(planUnitPrice).toLocaleString('ru-RU') + ' ₽/' + (rowUnit || 'ед.') : '—',
      invoicePriceText: invoiceUnitPrice > 0 ? Math.round(invoiceUnitPrice).toLocaleString('ru-RU') + ' ₽/' + (rowUnit || 'ед.') : '—',
      priceOverText: priceOverSum > 1 ? Math.round(priceOverSum).toLocaleString('ru-RU') + ' ₽' : '—',
      sections: (row.sections || []).slice(0, 2).join(' · '),
    };
  });
};
