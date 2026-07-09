import { estimateImportedPlanMeasure, estimateItemMaterialSum, estimateMaterialPlanIssue, estimatePackage, estimateSectionsOf, isEstimateMaterialItem, normalizeEstimateWorkingItem } from './estimateUtils';
import { materialLookupText, materialNameMatchScore } from './materialMatchUtils';
import { normalizeMeasure, toNum, _normalizeUnit } from './measureUtils';
import { packageMatches } from './materialDocumentUtils';

const materialControlEstimatesForProject = (project, activeEstimatesForProject) => {
  if (typeof activeEstimatesForProject !== 'function') return [];
  const seen = new Set();
  return ['Заказчик', 'Материалы'].flatMap(kind => activeEstimatesForProject(project, kind) || [])
    .filter(est => {
      const key = est?.id || `${est?.name || ''}|${estimatePackage(est)}|${est?.smetaType || est?.smeta_type || ''}`;
      if (!key || seen.has(key)) return false;
      seen.add(key);
      return true;
    });
};

export const buildEstimateMaterialPlanRows = ({
  projectName,
  projects = [],
  activeEstimatesForProject,
  materialNameLookupKey = materialLookupText,
}) => {
  const project = projects.find(pr => pr.name === projectName) || { name: projectName };
  const rows = {};
  const ensure = (name, unit, sectionLabel = '') => {
    const key = materialNameLookupKey(name);
    if (!key) return null;
    if (!rows[key]) {
      rows[key] = {
        key,
        name: name || '',
        unit: normalizeMeasure(1, unit).unit || unit || '',
        sections: [],
        workRefs: [],
        planQty: 0,
        planSum: 0,
      };
    }
    if (sectionLabel && !rows[key].sections.includes(sectionLabel)) rows[key].sections.push(sectionLabel);
    return rows[key];
  };
  const activeEstimates = materialControlEstimatesForProject(project, activeEstimatesForProject);
  activeEstimates.forEach(est => estimateSectionsOf(est).forEach(s => (s.items || []).forEach(rawIt => {
    const it = normalizeEstimateWorkingItem(rawIt, s.name);
    if (!isEstimateMaterialItem(it, s.name)) return;
    if (toNum(estimateImportedPlanMeasure(it).qty) <= 0) return;
    if (estimateMaterialPlanIssue(it, s.name)) return;
    const sectionLabel = (estimatePackage(est) !== 'Основная' ? estimatePackage(est) + ' / ' : '') + (s.name || '');
    const planMeasure = estimateImportedPlanMeasure(it);
    const r = ensure(it.name, planMeasure.unit || it.unit, sectionLabel);
    if (!r) return;
    if (it.parentWorkName && !r.workRefs.includes(it.parentWorkName)) r.workRefs.push(it.parentWorkName);
    r.planQty += toNum(planMeasure.qty);
    r.planSum += estimateItemMaterialSum(it);
  })));
  return Object.values(rows).sort((a, b) => a.name.localeCompare(b.name, 'ru'));
};

export const buildMaterialAliasCandidates = ({
  projectName,
  row,
  estimateMaterialPlanRows,
  materialNameLookupKey = materialLookupText,
}) => {
  const sourceText = materialNameLookupKey([row?.name, ...(row?.aliases || [])].join(' '));
  const tokens = sourceText.split(' ').filter(t => t.length > 2);
  return estimateMaterialPlanRows(projectName)
    .filter(r => materialNameLookupKey(r.name) !== materialNameLookupKey(row?.name))
    .map(r => {
      const text = materialNameLookupKey(r.name + ' ' + (r.sections || []).join(' '));
      let score = 0;
      tokens.forEach(t => { if (text.includes(t)) score += 8; });
      if (row?.unit && r.unit && _normalizeUnit(row.unit) === _normalizeUnit(r.unit)) score += 5;
      if (text.includes(sourceText) || sourceText.includes(text)) score += 20;
      score = Math.max(score, Math.round(materialNameMatchScore(sourceText, text) * 100));
      return { ...r, score };
    })
    .filter(r => r.score > 0)
    .sort((a, b) => (b.score - a.score) || (b.planQty - a.planQty) || a.name.localeCompare(b.name, 'ru'))
    .slice(0, 4);
};

export const buildMaterialPlanningReviewIssues = (row = {}) => {
  const issues = [];
  const invalidPlanCount = Number(row.invalidPlanCount ?? row.invalidPlanDetails?.length ?? 0);
  if (invalidPlanCount > 0) {
    issues.push({
      code: 'invalid_estimate_rows',
      label: 'Некорректные строки сметы: ' + invalidPlanCount,
      count: invalidPlanCount,
    });
  }
  if (row.unitMismatch) {
    issues.push({ code: 'unit_mismatch', label: 'Конфликт единиц измерения' });
  }
  if ((row.aliases || []).length > 0 && !(row.aliasIds || []).length) {
    issues.push({ code: 'unconfirmed_alias', label: 'Наименование не подтверждено алиасом' });
  }
  return issues;
};

export const buildMaterialReconciliationRows = ({
  projectName,
  workPackage = '',
  projects = [],
  invoices = [],
  supplyDeliveries = [],
  supplyHistory = [],
  warehouseMovements = [],
  materialTransfers = [],
  workJournal = [],
  history = [],
  materials = [],
  supplyRequests = [],
  activeEstimatesForProject,
  canonicalMaterialMeta,
  warehouseInvoiceItems,
  isSupplyDeliveryInvoice,
  estimateWorkNormRequirementRows,
  parseSupplyItems,
  materialNameLookupKey = materialLookupText,
}) => {
  const project = projects.find(pr => pr.name === projectName) || { name: projectName };
  const keyOf = materialNameLookupKey;
  const rows = {};
  const rowsByMaterialKey = {};
  const requiredPackage = String(workPackage || '').trim();
  const sourcePackageMatches = (value) => !requiredPackage || String(value || '').trim() === requiredPackage;
  const sourcePackageOf = (item = {}, parent = {}) => item.workPackage || item.work_package || parent.workPackage || parent.work_package || '';
  const materialUnit = (unit) => normalizeMeasure(1, unit).unit || unit || '';
  const materialQty = (qty, unit) => {
    const norm = normalizeMeasure(qty, unit);
    return { qty: norm.qty, unit: norm.unit || unit || '' };
  };
  const packageKeyPart = (pkg = '') => {
    const clean = String(pkg || '').trim();
    return requiredPackage ? '' : (clean ? '|' + clean.toLowerCase() : '|__no_package__');
  };
  const exactMatchedRow = (materialKey, sourcePackage = '') => {
    const cleanPackage = String(sourcePackage || '').trim();
    const candidates = (rowsByMaterialKey[materialKey] || []).filter(row => {
      if (requiredPackage || !cleanPackage) return true;
      const rowPackage = String(row.workPackage || '').trim();
      return !rowPackage || rowPackage === cleanPackage;
    });
    return candidates.length === 1 ? candidates[0] : null;
  };
  const ensure = (name, unit, sourcePackage = '') => {
    const rawName = name || '';
    const meta = canonicalMaterialMeta(projectName, rawName, unit);
    const baseKey = keyOf(meta.name);
    if (!baseKey) return null;
    const cleanPackage = String(sourcePackage || '').trim();
    const key = baseKey + packageKeyPart(cleanPackage);
    const cleanUnit = materialUnit(meta.unit || unit);
    let row = rows[key] || exactMatchedRow(baseKey, cleanPackage);
    if (!row) {
      row = {
        key,
        materialKey: baseKey,
        name: meta.name || '',
        unit: cleanUnit,
        workPackage: cleanPackage,
        sections: [],
        workRefs: [],
        aliases: [],
        aliasIds: [],
        holders: {},
        invoiceDetails: [],
        supplyDetails: [],
        movementDetails: [],
        planDetails: [],
        invalidPlanDetails: [],
        normDetails: [],
        normSections: [],
        normWorks: [],
        normSources: [],
        planQty: 0,
        normPlanQty: 0,
        planSum: 0,
        invoiceReceived: 0,
        supplyReceived: 0,
        received: 0,
        receivedSum: 0,
        movedIn: 0,
        movedOut: 0,
        issuedFromMain: 0,
        issued: 0,
        issuedSigned: 0,
        issuedPending: 0,
        returnedFromMasters: 0,
        used: 0,
        stock: 0,
        requested: 0,
        inTransit: 0,
        unitMismatch: false,
      };
      rows[key] = row;
      if (!rowsByMaterialKey[baseKey]) rowsByMaterialKey[baseKey] = [];
      rowsByMaterialKey[baseKey].push(row);
    }
    if (cleanPackage && !row.workPackage) row.workPackage = cleanPackage;
    if (rawName && keyOf(rawName) !== baseKey && !row.aliases.includes(rawName)) row.aliases.push(rawName);
    if (meta.alias?.id && !row.aliasIds.includes(meta.alias.id)) row.aliasIds.push(meta.alias.id);
    if (cleanUnit && row.unit && row.unit !== cleanUnit) row.unitMismatch = true;
    if (!row.unit && cleanUnit) row.unit = cleanUnit;
    return row;
  };
  const addQty = (row, field, qty, unit) => {
    if (!row) return;
    const converted = materialQty(qty, unit || row.unit);
    if (converted.unit && row.unit && converted.unit !== row.unit) row.unitMismatch = true;
    if (!row.unit && converted.unit) row.unit = converted.unit;
    row[field] += converted.qty;
  };
  const addHolderQty = (row, person, role, field, qty, unit, transfer) => {
    if (!row) return;
    const name = (person || 'Без ответственного').trim();
    const key = name.toLowerCase();
    const converted = materialQty(qty, unit || row.unit);
    if (converted.unit && row.unit && converted.unit !== row.unit) row.unitMismatch = true;
    if (!row.unit && converted.unit) row.unit = converted.unit;
    if (!row.holders[key]) row.holders[key] = { name, role: role || '', unit: row.unit || converted.unit || unit || '', issued: 0, pending: 0, used: 0, returned: 0, transfers: [] };
    row.holders[key][field] += converted.qty;
    if (transfer) row.holders[key].transfers.push(transfer);
  };

  const activeEstimates = materialControlEstimatesForProject(project, activeEstimatesForProject);
  activeEstimates
    .filter(est => packageMatches(estimatePackage(est), workPackage))
    .forEach(est => estimateSectionsOf(est).forEach(s => (s.items || []).forEach(rawIt => {
      const it = normalizeEstimateWorkingItem(rawIt, s.name);
      if (!isEstimateMaterialItem(it, s.name)) return;
      if (toNum(estimateImportedPlanMeasure(it).qty) <= 0) return;
      const r = ensure(it.name, it.unit, estimatePackage(est));
      if (!r) return;
      const planMeasure = estimateImportedPlanMeasure(it);
      const converted = materialQty(planMeasure.qty, planMeasure.unit || it.unit || r.unit);
      const planSum = estimateItemMaterialSum(it);
      const sectionLabel = (estimatePackage(est) !== 'Основная' ? estimatePackage(est) + ' / ' : '') + (s.name || '');
      if (sectionLabel && !r.sections.includes(sectionLabel)) r.sections.push(sectionLabel);
      if (it.parentWorkName && !r.workRefs.includes(it.parentWorkName)) r.workRefs.push(it.parentWorkName);
      const planIssue = estimateMaterialPlanIssue(it, s.name);
      const sourceQty = Number(it.quantity || 0);
      const sourceUnit = it.unit || '';
      const hasRawQty = it.rawQuantity !== undefined && it.rawQuantity !== null && it.rawQuantity !== '';
      const traceSourceQty = hasRawQty ? Number(it.rawQuantity || 0) : sourceQty;
      const traceSourceUnit = it.rawUnit || sourceUnit;
      const normalizedUnit = converted.unit || it.unit || r.unit;
      const trace = {
        sourceType: 'estimate_material',
        sourceQty,
        sourceUnit,
        normalizedQty: converted.qty,
        normalizedUnit,
        normalizationFactor: Number(planMeasure.factor || 1),
        conversionApplied: Number(planMeasure.factor || 1) !== 1
          || Math.abs(converted.qty - traceSourceQty) > 0.000001
          || _normalizeUnit(normalizedUnit) !== _normalizeUnit(traceSourceUnit),
      };
      if (planIssue) {
        r.invalidPlanDetails.push({
          ...trace,
          includedInProcurement: false,
          estimateId: est.id,
          estimateName: est.name || '',
          packageName: estimatePackage(est),
          sectionName: s.name || '',
          materialName: it.name || '',
          workName: it.parentWorkName || '',
          qty: converted.qty,
          unit: converted.unit || it.unit || r.unit,
          rawQty: it.rawQuantity,
          rawUnit: it.rawUnit,
          sum: planSum,
          reason: planIssue,
        });
        return;
      }
      addQty(r, 'planQty', planMeasure.qty, planMeasure.unit || it.unit);
      r.planSum += planSum;
      r.planDetails.push({
        ...trace,
        includedInProcurement: true,
        estimateId: est.id,
        estimateName: est.name || '',
        packageName: estimatePackage(est),
        sectionName: s.name || '',
        materialName: it.name || '',
        workName: it.parentWorkName || '',
        qty: converted.qty,
        unit: converted.unit || it.unit || r.unit,
        rawQty: it.rawQuantity,
        rawUnit: it.rawUnit,
        sum: planSum,
      });
    })));

  (invoices || []).filter(inv => {
    const invoiceStatus = String(inv.status || '').trim().toLowerCase();
    if (invoiceStatus === 'аннулирована' || invoiceStatus === 'аннулирован') return false;
    return !isSupplyDeliveryInvoice(inv) && ((inv.project || inv.location) === projectName || inv.location === projectName);
  }).forEach(inv => {
    warehouseInvoiceItems(inv).items.filter(it => sourcePackageMatches(sourcePackageOf(it, inv))).forEach(it => {
      const itemPackage = sourcePackageOf(it, inv);
      const r = ensure(it.name, it.unit, itemPackage);
      if (!r) return;
      const qty = Number(it.quantity || 0);
      const price = Number(it.price || 0);
      const converted = materialQty(qty, it.unit || r.unit);
      addQty(r, 'invoiceReceived', qty, it.unit);
      addQty(r, 'received', qty, it.unit);
      const total = Number(it.total || qty * price || 0);
      r.receivedSum += total;
      r.invoiceDetails.push({
        id: inv.id,
        number: inv.number || '',
        date: inv.date || '',
        supplierName: inv.supplierName || '',
        qty: converted.qty,
        unit: converted.unit || it.unit || r.unit,
        sourceUnit: it.unit || '',
        sourceQty: qty,
        total,
        workPackage: itemPackage,
      });
    });
  });

  const acceptedDeliveryKeys = new Set();
  const deliveryKey = (row, pkg = '') => (row?.key || '') + '|' + String(pkg || '').trim();
  (supplyDeliveries || [])
    .filter(d => d.project === projectName && sourcePackageMatches(sourcePackageOf({}, d)) && ['Принято', 'Проблема'].includes(d.status || '') && Number(d.receivedQuantity || 0) > 0)
    .forEach(d => {
      const deliveryPackage = sourcePackageOf({}, d);
      const r = ensure(d.materialName, d.unit, deliveryPackage);
      if (!r) return;
      const qty = Number(d.receivedQuantity || 0);
      const converted = materialQty(qty, d.unit || r.unit);
      addQty(r, 'supplyReceived', qty, d.unit);
      addQty(r, 'received', qty, d.unit);
      const total = Number(d.totalPrice || 0) || qty * Number(d.pricePerUnit || 0);
      r.receivedSum += total;
      r.supplyDetails.push({
        id: d.id,
        requestId: d.requestId,
        status: d.status || '',
        supplierName: d.supplierName || '',
        qty: converted.qty,
        unit: converted.unit || d.unit || r.unit,
        total,
        date: d.receivedAt || d.deliveryDate || d.plannedDate || '',
        workPackage: deliveryPackage,
      });
      acceptedDeliveryKeys.add(deliveryKey(r, deliveryPackage));
    });
  (supplyHistory || [])
    .filter(h => h.project === projectName && sourcePackageMatches(sourcePackageOf({}, h)) && ['Доставлено', 'Поставлено', 'Принято'].includes(h.status || ''))
    .forEach(h => {
      const historyPackage = sourcePackageOf({}, h);
      const r = ensure(h.materialName, h.unit, historyPackage);
      if (!r || acceptedDeliveryKeys.has(deliveryKey(r, historyPackage))) return;
      const qty = Number(h.quantity || 0);
      const converted = materialQty(qty, h.unit || r.unit);
      addQty(r, 'supplyReceived', qty, h.unit);
      addQty(r, 'received', qty, h.unit);
      const total = Number(h.totalPrice || 0) || qty * Number(h.pricePerUnit || 0);
      r.receivedSum += total;
      r.supplyDetails.push({
        id: h.id,
        status: h.status || '',
        supplierName: h.supplierName || '',
        qty: converted.qty,
        unit: converted.unit || h.unit || r.unit,
        total,
        date: h.date || h.createdAt || '',
        workPackage: historyPackage,
      });
    });

  (warehouseMovements || []).forEach(m => {
    const movementPackage = sourcePackageOf({}, m);
    if (!sourcePackageMatches(movementPackage)) return;
    const qty = Number(m.quantity || 0);
    if ((m.toLocation || '') === projectName) {
      const r = ensure(m.materialName, m.unit, movementPackage);
      addQty(r, 'movedIn', qty, m.unit);
      const converted = materialQty(qty, m.unit || r?.unit);
      if (r) r.movementDetails.push({ id: m.id, type: 'in', from: m.fromLocation || '', to: m.toLocation || '', qty: converted.qty, unit: converted.unit || m.unit || r.unit, date: m.date || m.createdAt || '', workPackage: movementPackage });
    }
    if ((m.fromLocation || '') === projectName) {
      const r = ensure(m.materialName, m.unit, movementPackage);
      addQty(r, 'movedOut', qty, m.unit);
      const converted = materialQty(qty, m.unit || r?.unit);
      if (r) r.movementDetails.push({ id: m.id, type: 'out', from: m.fromLocation || '', to: m.toLocation || '', qty: converted.qty, unit: converted.unit || m.unit || r.unit, date: m.date || m.createdAt || '', workPackage: movementPackage });
    }
  });
  (materialTransfers || []).filter(t => t.projectName === projectName && (t.status || 'Активна') !== 'Аннулирована' && sourcePackageMatches(t.workPackage || t.work_package)).forEach(t => {
    const transferPackage = t.workPackage || t.work_package || '';
    const r = ensure(t.materialName, t.unit, transferPackage);
    if ((t.fromLocation || '') === 'Основной склад') addQty(r, 'issuedFromMain', t.quantity, t.unit);
    addQty(r, 'issued', t.quantity, t.unit);
    if (t.signed) addQty(r, 'issuedSigned', t.quantity, t.unit);
    else addQty(r, 'issuedPending', t.quantity, t.unit);
    addHolderQty(r, t.toPerson, t.toPersonRole, t.signed ? 'issued' : 'pending', t.quantity, t.unit, t);
  });
  (workJournal || []).filter(w => w.project === projectName && !['Отклонено', 'Аннулировано', 'Удалено', 'Отменено'].includes(w.status || '') && sourcePackageMatches(w.workPackage || w.work_package)).forEach(w => {
    let mats = w.materialsUsed !== undefined ? w.materialsUsed : w.materials_used;
    if (typeof mats === 'string') {
      try { mats = JSON.parse(mats); } catch (_) { mats = []; }
    }
    if (!Array.isArray(mats)) return;
    mats.forEach(m => {
      const writeoffPackage = m.workPackage || m.work_package || w.workPackage || w.work_package || '';
      const r = ensure(m.name, m.unit, writeoffPackage);
      addQty(r, 'used', m.quantity, m.unit);
      addHolderQty(r, w.masterName || w.master_name || 'Без ответственного', '', 'used', m.quantity, m.unit);
    });
  });
  (history || [])
    .filter(h => h.project === projectName && h.type === 'возврат от мастера' && sourcePackageMatches(h.workPackage || h.work_package))
    .forEach(h => {
      const returnPackage = h.workPackage || h.work_package || '';
      const r = ensure(h.material, '', returnPackage);
      addQty(r, 'returnedFromMasters', h.quantity, r?.unit);
      addHolderQty(r, h.issuedBy || h.issued_by || 'Без ответственного', '', 'returned', h.quantity, r?.unit);
    });
  (materials || []).filter(m => m.project === projectName && sourcePackageMatches(sourcePackageOf({}, m))).forEach(m => {
    const stockPackage = sourcePackageOf({}, m);
    const r = ensure(m.name, m.unit, stockPackage);
    if (r) {
      addQty(r, 'stock', m.quantity, m.unit);
      if (!r.receivedSum && Number(m.price || 0) > 0) r.receivedSum += Number(m.quantity || 0) * Number(m.price || 0);
    }
  });

  const requestPipelineStatuses = new Set(['Новая', 'Подтверждена прорабом', 'Утверждена', 'КП запрошены']);
  (supplyRequests || [])
    .filter(req => req.project === projectName && requestPipelineStatuses.has(req.status || 'Новая'))
    .forEach(req => parseSupplyItems(req).filter(it => sourcePackageMatches(sourcePackageOf(it, req))).forEach(it => {
      const requestPackage = sourcePackageOf(it, req);
      const r = ensure(it.materialName, it.unit, requestPackage);
      addQty(r, 'requested', it.quantity, it.unit);
    }));
  (supplyDeliveries || [])
    .filter(d => d.project === projectName && sourcePackageMatches(sourcePackageOf({}, d)) && d.status === 'В пути')
    .forEach(d => {
      const transitPackage = sourcePackageOf({}, d);
      const r = ensure(d.materialName, d.unit, transitPackage);
      addQty(r, 'inTransit', d.shippedQuantity || d.plannedQuantity, d.unit);
    });

  (estimateWorkNormRequirementRows(projectName, workPackage) || []).forEach(n => {
    const normPackage = (n.packageNames || []).find(Boolean) || n.packageName || '';
    const r = ensure(n.name, n.unit, normPackage);
    if (!r) return;
    addQty(r, 'normPlanQty', n.planQty, n.unit);
    (n.sections || []).forEach(s => { if (s && !r.normSections.includes(s)) r.normSections.push(s); });
    (n.normSources || []).forEach(src => { if (src && !r.normSources.includes(src)) r.normSources.push(src); });
    (n.works || []).forEach(w => {
      const workName = w?.name || '';
      if (workName && !r.workRefs.includes(workName)) r.workRefs.push(workName);
      if (workName && !r.normWorks.some(x => x.name === workName && x.section === w.section)) r.normWorks.push(w);
    });
    r.normDetails.push(n);
  });

  const materialRowMatchesPackage = (row) => {
    if (!workPackage) return true;
    const planPackages = (row.planDetails || []).map(d => d.packageName).filter(Boolean);
    const invalidPackages = (row.invalidPlanDetails || []).map(d => d.packageName).filter(Boolean);
    const normPackages = (row.normDetails || []).flatMap(d => d.packageNames || []).filter(Boolean);
    const transferPackages = (row.holders ? Object.values(row.holders) : [])
      .flatMap(h => (h.transfers || []).map(t => t.workPackage || t.work_package).filter(Boolean));
    const hasStrictSourceActivity = (row.received || 0) || (row.stock || 0) || (row.requested || 0) ||
      (row.inTransit || 0) || (row.movedIn || 0) || (row.movedOut || 0) || (row.issued || 0) || (row.used || 0);
    if (hasStrictSourceActivity) return true;
    return [...planPackages, ...invalidPackages, ...normPackages, ...transferPackages].includes(workPackage);
  };

  return Object.values(rows).filter(materialRowMatchesPackage).map(r => {
    const detailPackages = [
      ...(r.planDetails || []).map(d => d.packageName),
      ...(r.invalidPlanDetails || []).map(d => d.packageName),
      ...(r.normDetails || []).flatMap(d => d.packageNames || []),
      ...(r.invoiceDetails || []).map(d => d.workPackage),
      ...(r.supplyDetails || []).map(d => d.workPackage),
      ...(r.movementDetails || []).map(d => d.workPackage),
    ].map(v => String(v || '').trim()).filter(Boolean);
    const rowPackage = requiredPackage || r.workPackage || detailPackages[0] || '';
    const movedNet = r.movedIn + r.issuedFromMain - r.movedOut;
    const supplied = r.received + movedNet;
    const estimatePlanQty = Number(r.planQty || 0);
    const normPlanQty = Number(r.normPlanQty || 0);
    const hasEstimatePlan = estimatePlanQty > 0;
    const controlPlanQty = hasEstimatePlan ? estimatePlanQty : normPlanQty;
    const normOverEstimateQty = estimatePlanQty > 0 ? Math.max(0, normPlanQty - estimatePlanQty) : normPlanQty;
    const normWithoutEstimateQty = !hasEstimatePlan ? normPlanQty : 0;
    const estimateOverNormQty = normPlanQty > 0 ? Math.max(0, estimatePlanQty - normPlanQty) : 0;
    const usedOverEstimateQty = estimatePlanQty > 0 ? Math.max(0, (r.used || 0) - estimatePlanQty) : 0;
    const invalidPlanCount = (r.invalidPlanDetails || []).length;
    const reviewIssues = buildMaterialPlanningReviewIssues({...r, invalidPlanCount});
    const reviewRequired = reviewIssues.length > 0;
    const procurementEligible = hasEstimatePlan && !reviewRequired;
    const toBuy = procurementEligible ? Math.max(0, estimatePlanQty - supplied - (r.requested || 0) - (r.inTransit || 0)) : 0;
    const coveredWithPipeline = supplied + (r.requested || 0) + (r.inTransit || 0);
    const hasMaterialActivity = coveredWithPipeline > 0 || (r.stock || 0) > 0 || (r.issued || 0) > 0 || (r.used || 0) > 0;
    const holders = Object.values(r.holders || {}).map(h => ({
      ...h,
      balance: Math.max(0, (h.issued || 0) - (h.used || 0) - (h.returned || 0)),
    })).filter(h => (h.issued || 0) > 0 || (h.pending || 0) > 0 || (h.used || 0) > 0)
      .sort((a, b) => (b.balance - a.balance) || (b.pending - a.pending) || a.name.localeCompare(b.name, 'ru'));
    const masterBalance = holders.reduce((sum, h) => sum + (h.balance || 0), 0);
    const pendingAtMasters = holders.reduce((sum, h) => sum + (h.pending || 0), 0);
    const usedWithoutIssue = Math.max(0, (r.used || 0) - (r.issuedSigned || 0));
    const expectedStock = supplied - (r.issued || 0) + (r.returnedFromMasters || 0) - usedWithoutIssue;
    const stockDiff = (r.stock || 0) - expectedStock;
    return {
      ...r,
      workPackage: rowPackage,
      packageName: rowPackage,
      planSourceCount: (r.planDetails || []).length,
      invalidPlanCount,
      reviewIssues,
      reviewReasons: reviewIssues.map(issue => issue.label),
      reviewRequired,
      procurementEligible,
      procurementBlockedReason: reviewRequired ? reviewIssues.map(issue => issue.label).join('; ') : '',
      identityStatus: (r.aliasIds || []).length > 0 ? 'confirmed_alias' : (r.aliases || []).length > 0 ? 'unconfirmed_alias' : 'exact',
      planningSource: hasEstimatePlan ? 'estimate' : normPlanQty > 0 ? 'norm_hint' : 'activity',
      movedNet,
      supplied,
      holders,
      masterBalance,
      pendingAtMasters,
      usedWithoutIssue,
      expectedStock,
      stockDiff,
      stockMismatch: Math.abs(stockDiff) > 0.0001,
      estimatePlanQty,
      normPlanQty,
      controlPlanQty,
      procurementPlanQty: hasEstimatePlan ? estimatePlanQty : 0,
      eligibleProcurementPlanQty: procurementEligible ? estimatePlanQty : 0,
      normWithoutEstimateQty,
      normSourceCount: (r.normDetails || []).length,
      normOverEstimateQty,
      estimateOverNormQty,
      usedOverEstimateQty,
      usedOverControlQty: controlPlanQty > 0 ? Math.max(0, (r.used || 0) - controlPlanQty) : 0,
      usedOverNormQty: normPlanQty > 0 ? Math.max(0, (r.used || 0) - normPlanQty) : 0,
      spendPct: controlPlanQty > 0 ? Math.min(999, Math.round((r.used || 0) / controlPlanQty * 100)) : 0,
      shortage: hasEstimatePlan ? Math.max(0, estimatePlanQty - supplied) : 0,
      toBuy,
      coveredWithPipeline,
      over: controlPlanQty > 0 ? Math.max(0, supplied - controlPlanQty) : coveredWithPipeline,
      isOutsideEstimate: !estimatePlanQty && !normPlanQty && hasMaterialActivity,
      coveragePct: controlPlanQty > 0 ? Math.min(999, Math.round(supplied / controlPlanQty * 100)) : 0,
    };
  }).sort((a, b) => (b.toBuy - a.toBuy) || (b.shortage - a.shortage) || (b.isOutsideEstimate - a.isOutsideEstimate) || a.name.localeCompare(b.name, 'ru'));
};

export const buildMaterialControlSummary = (rows = []) => {
  const planRows = rows.filter(r => r.planQty > 0);
  const suppliedRows = rows.filter(r => r.supplied > 0);
  const invoiceRows = rows.filter(r => r.invoiceReceived > 0);
  const deliveryRows = rows.filter(r => r.supplyReceived > 0);
  const movedRows = rows.filter(r => r.movedNet !== 0);
  const toBuyRows = rows.filter(r => r.toBuy > 0);
  const outsideRows = rows.filter(r => r.isOutsideEstimate);
  const overRows = rows.filter(r => r.over > 0);
  const mismatchRows = rows.filter(r => r.unitMismatch);
  const stockMismatchRows = rows.filter(r => r.stockMismatch);
  const masterBalanceRows = rows.filter(r => r.masterBalance > 0);
  const usedWithoutIssueRows = rows.filter(r => r.issued > 0 && r.usedWithoutIssue > 0);
  const invalidPlanRows = rows.filter(r => r.invalidPlanCount > 0);
  const reviewRows = rows.filter(r => r.reviewRequired);
  const normRows = rows.filter(r => r.normPlanQty > 0);
  const normOverEstimateRows = rows.filter(r => r.normOverEstimateQty > 0);
  const normWithoutEstimateRows = rows.filter(r => r.normWithoutEstimateQty > 0);
  const usedOverControlRows = rows.filter(r => r.usedOverControlQty > 0);
  const usedOverEstimateRows = rows.filter(r => r.usedOverEstimateQty > 0);
  const planSum = rows.reduce((s, r) => s + Number(r.planSum || 0), 0);
  const suppliedSum = rows.reduce((s, r) => s + Number(r.receivedSum || 0), 0);
  return {
    rows,
    planRows,
    suppliedRows,
    invoiceRows,
    deliveryRows,
    movedRows,
    toBuyRows,
    outsideRows,
    overRows,
    mismatchRows,
    stockMismatchRows,
    masterBalanceRows,
    usedWithoutIssueRows,
    invalidPlanRows,
    reviewRows,
    normRows,
    normOverEstimateRows,
    normWithoutEstimateRows,
    usedOverControlRows,
    usedOverEstimateRows,
    planSum,
    suppliedSum,
  };
};
