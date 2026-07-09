import { estimatePackage, estimateSectionsOf, isEstimateMaterialItem, isEstimateWorkItem } from './estimateUtils';
import { packageMatches } from './materialDocumentUtils';
import { _normalizeUnit, normalizeMeasure, toNum } from './measureUtils';
import {
  materialNoNormCoverageReason,
  materialNormMatchesMaterial,
  materialTitleForNormRule,
  roundNormQty,
  workNoMaterialNormReason,
} from './materialNormUtils';

export const buildMaterialNormDeviationRows = ({
  projectName,
  workPackage = '',
  workJournal = [],
  parseJournalMaterials,
  materialNameKey,
}) => {
  const rows = {};
  (workJournal || [])
    .filter(w => w.project === projectName && w.status !== 'Отклонено' && packageMatches(w.workPackage || w.work_package, workPackage))
    .forEach(w => parseJournalMaterials(w.materialsUsed !== undefined ? w.materialsUsed : w.materials_used).forEach(m => {
      const name = m.name || '';
      const key = materialNameKey(name) + '|' + _normalizeUnit(m.unit || 'шт');
      if (!materialNameKey(name)) return;
      const qty = toNum(m.quantity);
      const norm = toNum(m.normQuantity);
      const unit = m.unit || 'шт';
      const tolerance = norm > 0 ? Math.max(0.001, norm * 0.1) : 0;
      const diff = norm > 0 ? qty - norm : 0;
      if (!rows[key]) rows[key] = {
        key,
        name,
        unit,
        qty: 0,
        normQty: 0,
        overQty: 0,
        savedQty: 0,
        withoutNormQty: 0,
        records: 0,
        overRecords: 0,
        withoutNormRecords: 0,
        works: [],
        normSources: [],
      };
      const row = rows[key];
      row.qty += qty;
      row.records += 1;
      if (norm > 0) {
        row.normQty += norm;
        if (diff > tolerance) {
          row.overQty += diff;
          row.overRecords += 1;
        } else if (diff < -tolerance) {
          row.savedQty += Math.abs(diff);
        }
      } else if (qty > 0) {
        row.withoutNormQty += qty;
        row.withoutNormRecords += 1;
      }
      if (m.normSource && !row.normSources.includes(m.normSource)) row.normSources.push(m.normSource);
      row.works.push({
        workName: w.description || '',
        master: w.masterName || w.master_name || '',
        date: w.date || '',
        qty,
        norm,
        diff,
        unit,
        normSource: m.normSource || '',
        overNormReason: m.overNormReason || '',
      });
    }));
  return Object.values(rows)
    .map(r => ({ ...r, overPct: r.normQty > 0 ? Math.round(r.overQty / r.normQty * 100) : 0 }))
    .sort((a, b) => (b.overQty - a.overQty) || (b.withoutNormQty - a.withoutNormQty) || a.name.localeCompare(b.name, 'ru'));
};

export const buildMaterialNormControlSummary = (rows = []) => {
  const overRows = rows.filter(r => r.overQty > 0);
  const withoutNormRows = rows.filter(r => r.withoutNormQty > 0);
  const savedRows = rows.filter(r => r.savedQty > 0 && r.overQty === 0);
  return {
    rows,
    overRows,
    withoutNormRows,
    savedRows,
    totalOverRows: overRows.length,
    totalWithoutNormRows: withoutNormRows.length,
    totalOverRecords: rows.reduce((s, r) => s + r.overRecords, 0),
    totalWithoutNormRecords: rows.reduce((s, r) => s + r.withoutNormRecords, 0),
  };
};

export const buildPersonalMaterialRowsForProject = ({
  projectName,
  personName = '',
  personId = null,
  workPackage = '',
  materialTransfers = [],
  workJournal = [],
  history = [],
  canonicalMaterialMeta,
  parseJournalMaterials,
  materialNameKey,
}) => {
  const byName = {};
  const materialTransferKey = (name, packageName = '', unit = '') => {
    const meta = canonicalMaterialMeta(projectName, name, unit);
    const base = materialNameKey(meta.name);
    return base ? base + '|' + (packageName || '') + '|' + _normalizeUnit(meta.unit || unit || 'шт') : '';
  };
  const ensurePersonalMaterialRow = (key, source = {}) => {
    if (!key) return null;
    if (!byName[key]) {
      const meta = canonicalMaterialMeta(projectName, source.materialName || source.material || source.name || '', source.unit || 'шт');
      byName[key] = {
        id: key + '|' + projectName,
        key,
        name: meta.name || source.materialName || source.material || source.name || '',
        unit: meta.unit || source.unit || 'шт',
        workPackage: source.workPackage || source.work_package || '',
        quantity: 0,
        received: 0,
        used: 0,
        returned: 0,
        pending: 0,
        project: projectName,
        aliases: [],
        transfers: [],
        pendingTransfers: [],
      };
    }
    const rawName = source.materialName || source.material || source.name || '';
    if (rawName && materialNameKey(rawName) !== materialNameKey(byName[key].name) && !byName[key].aliases.includes(rawName)) byName[key].aliases.push(rawName);
    return byName[key];
  };
  const transferBelongsToPerson = (t) => {
    const transferUserId = t.toUserId || t.to_user_id;
    if (personId && transferUserId) return Number(transferUserId) === Number(personId);
    return !transferUserId && t.toPerson === personName;
  };
  (materialTransfers || [])
    .filter(t => t.projectName === projectName && transferBelongsToPerson(t) && t.signed && (t.status || 'Активна') !== 'Аннулирована' && packageMatches(t.workPackage || t.work_package, workPackage))
    .forEach(t => {
      const key = materialTransferKey(t.materialName, t.workPackage, t.unit);
      const row = ensurePersonalMaterialRow(key, t);
      if (!row) return;
      row.received += toNum(t.quantity);
      row.quantity += toNum(t.quantity);
      row.transfers.push(t);
    });
  (materialTransfers || [])
    .filter(t => t.projectName === projectName && transferBelongsToPerson(t) && !t.signed && (t.status || 'Активна') !== 'Аннулирована' && packageMatches(t.workPackage || t.work_package, workPackage))
    .forEach(t => {
      const key = materialTransferKey(t.materialName, t.workPackage, t.unit);
      const row = ensurePersonalMaterialRow(key, t);
      if (!row) return;
      row.pending += toNum(t.quantity);
      row.pendingTransfers.push(t);
    });
  (workJournal || [])
    .filter(w => w.project === projectName && w.status !== 'Отклонено' && packageMatches(w.workPackage || w.work_package, workPackage) && (Number(w.masterId || w.master_id) === Number(personId) || w.masterName === personName || w.master_name === personName))
    .forEach(w => parseJournalMaterials(w.materialsUsed !== undefined ? w.materialsUsed : w.materials_used).forEach(m => {
      const key = materialTransferKey(m.name, m.workPackage || w.workPackage || w.work_package, m.unit);
      const cur = byName[key] || byName[materialTransferKey(m.name, '', m.unit)];
      if (cur) {
        cur.used += toNum(m.quantity);
        cur.quantity -= toNum(m.quantity);
      }
    }));
  (history || [])
    .filter(h => h.project === projectName && h.type === 'возврат от мастера' && h.issuedBy === personName && packageMatches(h.workPackage || h.work_package, workPackage))
    .forEach(h => {
      const key = materialTransferKey(h.material, h.workPackage || h.work_package, h.unit);
      const cur = byName[key] || byName[materialTransferKey(h.material, '', h.unit)];
      if (cur) {
        cur.returned += toNum(h.quantity);
        cur.quantity -= toNum(h.quantity);
      }
    });
  return Object.values(byName)
    .filter(r => r.received > 0 || r.pending > 0)
    .map(r => ({ ...r, quantity: Math.max(0, r.quantity) }));
};

export const buildMaterialAvailabilityMap = ({
  rows = [],
  projectName,
  canonicalMaterialMeta,
  materialNameKey,
}) => {
  const byName = {};
  rows.forEach(m => {
    const meta = canonicalMaterialMeta(projectName, m.name, m.unit);
    const key = materialNameKey(meta.name);
    if (!key) return;
    if (!byName[key]) byName[key] = { name: meta.name, unit: meta.unit || m.unit || 'шт', quantity: 0, aliases: [] };
    byName[key].quantity += toNum(m.quantity);
    if (m.name && materialNameKey(m.name) !== key && !byName[key].aliases.includes(m.name)) byName[key].aliases.push(m.name);
    if (!byName[key].unit && (meta.unit || m.unit)) byName[key].unit = meta.unit || m.unit;
  });
  return byName;
};

export const buildMaterialSuggestionsForWork = ({
  projectName,
  workName,
  sectionName = '',
  workPackage = '',
  materialReconciliationRows,
  materialNameKey,
}) => {
  const rows = materialReconciliationRows(projectName, workPackage).filter(r => toNum(r.stock) > 0 || toNum(r.planQty) > 0);
  const stop = new Set(['работ', 'работа', 'монтаж', 'установка', 'устройство', 'демонтаж', 'прочее', 'раздел']);
  const tokens = materialNameKey(workName + ' ' + sectionName).split(' ').filter(w => w.length > 3 && !stop.has(w));
  return rows.map(r => {
    const text = materialNameKey([r.name, ...(r.sections || [])].join(' '));
    let score = 0;
    if (toNum(r.stock) > 0) score += 20;
    if (toNum(r.planQty) > 0) score += 12;
    if (toNum(r.toBuy) > 0) score -= 4;
    if (r.isOutsideEstimate) score -= 3;
    tokens.forEach(t => { if (text.includes(t)) score += 7; });
    if (sectionName && text.includes(materialNameKey(sectionName))) score += 10;
    return { ...r, score };
  }).sort((a, b) => (b.score - a.score) || (b.stock - a.stock) || (b.planQty - a.planQty) || a.name.localeCompare(b.name, 'ru')).slice(0, 8);
};

export const buildEstimateWorkNormRequirementRows = ({
  projectName,
  workPackage = '',
  projects = [],
  activeEstimatesForProject,
  normRequirementsForWork,
  materialNameKey,
}) => {
  const project = projects.find(pr => pr.name === projectName) || { name: projectName };
  const activeEstimates = activeEstimatesForProject(project, 'Заказчик');
  const rows = {};
  activeEstimates
    .filter(est => packageMatches(estimatePackage(est), workPackage))
    .forEach(est => estimateSectionsOf(est).forEach(s => (s.items || []).forEach(it => {
      if (!isEstimateWorkItem(it, s.name)) return;
      normRequirementsForWork(it.name, s.name, it.quantity, it.unit, { projectName, estimateId: est.id }).forEach(req => {
        const key = req.ruleId + '|' + materialNameKey(req.name) + '|' + _normalizeUnit(req.unit);
        if (!rows[key]) rows[key] = {
          key,
          name: req.name,
          unit: req.unit,
          planQty: 0,
          works: [],
          sections: [],
          normSources: [],
          packageNames: [],
          sourceType: 'norm_hint',
          procurementEligible: false,
        };
        rows[key].planQty += toNum(req.quantity);
        const packageName = estimatePackage(est);
        const sectionLabel = (estimatePackage(est) !== 'Основная' ? estimatePackage(est) + ' / ' : '') + (s.name || '');
        if (sectionLabel && !rows[key].sections.includes(sectionLabel)) rows[key].sections.push(sectionLabel);
        if (packageName && !rows[key].packageNames.includes(packageName)) rows[key].packageNames.push(packageName);
        if (req.normSource && !rows[key].normSources.includes(req.normSource)) rows[key].normSources.push(req.normSource);
        const thicknessBaseMm = toNum(req.rule?.thicknessBaseMm);
        const thicknessMm = thicknessBaseMm ? (toNum(req.rule?.defaultThicknessMm) || thicknessBaseMm) : 0;
        rows[key].works.push({
          estimateId: est.id,
          estimateName: est.name || '',
          itemId: it.id,
          name: it.name,
          section: s.name,
          quantity: it.quantity,
          unit: it.unit,
          source: req.normSource,
          packageName,
          requiredQty: toNum(req.quantity),
          requiredUnit: req.unit,
          ruleId: req.ruleId,
          ruleScope: req.scope || req.rule?.scope || 'base',
          formula: {
            workQty: toNum(it.quantity),
            workUnit: it.unit || '',
            qtyPerUnit: toNum(req.rule?.qtyPerUnit),
            materialUnit: req.rule?.materialUnit || req.unit || '',
            thicknessBaseMm,
            thicknessMm,
            requiredQty: toNum(req.quantity),
            requiredUnit: req.unit || '',
          },
        });
      });
    })));
  return Object.values(rows)
    .map(r => ({ ...r, planQty: roundNormQty(r.planQty) }))
    .sort((a, b) => b.planQty - a.planQty || a.name.localeCompare(b.name, 'ru'));
};

export const buildEstimateNormCoverageRows = ({
  projectName,
  sourceEstimates = null,
  projects = [],
  activeEstimatesForProject,
  workNormRulesFor,
  normRequirementsForWork,
  materialNameKey,
}) => {
  const project = projects.find(pr => pr.name === projectName) || { name: projectName };
  const activeEstimates = activeEstimatesForProject(project, 'Заказчик', sourceEstimates);
  const rows = [];
  activeEstimates.forEach(est => estimateSectionsOf(est).forEach((section, sectionIdx) => {
    const items = section.items || [];
    const materialsInSection = items.filter(it => isEstimateMaterialItem(it, section.name) && !materialNoNormCoverageReason(it.name));
    const coveredMaterialKeys = new Set();
    items.forEach((it, itemIdx) => {
      if (!isEstimateWorkItem(it, section.name)) return;
      const workQty = toNum(it.quantity);
      const workUnit = it.unit || '';
      const rules = workNormRulesFor(it.name, section.name, projectName, est.id)
        .filter(rule => _normalizeUnit(normalizeMeasure(workQty, workUnit).unit) === _normalizeUnit(rule.workUnit));
      if (!rules.length) {
        const noMaterialReason = workNoMaterialNormReason(it.name, section.name);
        rows.push({ key: [est.id, section.name, itemIdx, 'no'].join('|'), projectName, estimateId: est.id, estimateName: est.name, packageName: estimatePackage(est), sectionIdx, itemIdx, itemId: it.id, sectionName: section.name || '', workName: it.name || '', workQty, workUnit, status: noMaterialReason ? 'Норма не нужна' : 'Нет нормы', severity: noMaterialReason ? 'info' : 'warning', message: noMaterialReason || 'Для работы не найдено правило расхода материала', rule: null, materialName: '', materialQty: 0, materialUnit: '' });
        return;
      }
      rules.forEach(rule => {
        const ruleKey = String(rule.ruleKey || rule.id || '');
        const skippedRules = new Set((Array.isArray(it.materialNormSkipRules) ? it.materialNormSkipRules : []).map(String));
        const req = normRequirementsForWork(it.name, section.name, workQty, workUnit, { projectName, estimateId: est.id }).find(r => String(r.ruleId) === String(rule.ruleKey || rule.id));
        if (it.materialNormNoMaterial === true || skippedRules.has(ruleKey)) {
          rows.push({ key: [est.id, section.name, itemIdx, rule.ruleKey || rule.id, 'skip'].join('|'), projectName, estimateId: est.id, estimateName: est.name, packageName: estimatePackage(est), sectionIdx, itemIdx, itemId: it.id, sectionName: section.name || '', workName: it.name || '', workQty, workUnit, status: 'Норма не нужна', severity: 'info', message: it.materialNormSkipReason || 'Помечено в смете: материал по этой норме не требуется', rule, materialName: materialTitleForNormRule(rule), materialQty: 0, materialUnit: rule.materialUnit || '', requiredQty: 0, requiredUnit: rule.materialUnit || '', qtyPerUnit: rule.qtyPerUnit });
          return;
        }
        const matchingMaterials = materialsInSection.filter(m => materialNormMatchesMaterial(rule, m.name, m.unit, it.name + ' ' + section.name));
        matchingMaterials.forEach(m => coveredMaterialKeys.add(materialNameKey(m.name)));
        const material = matchingMaterials[0];
        const positiveMaterialQty = matchingMaterials.reduce((sum, m) => sum + Math.max(0, toNum(m.quantity)), 0);
        const negativeMaterialQty = matchingMaterials.reduce((sum, m) => sum + Math.min(0, toNum(m.quantity)), 0);
        const materialQty = positiveMaterialQty || toNum(material?.quantity);
        const requiredQty = toNum(req?.quantity);
        const shortageQty = requiredQty > 0 ? Math.max(0, roundNormQty(requiredQty - positiveMaterialQty)) : 0;
        const hasPositiveMaterial = positiveMaterialQty > 0;
        const hasOnlyNegativeMaterial = matchingMaterials.length > 0 && !hasPositiveMaterial && negativeMaterialQty < 0;
        const materialStatus = material
          ? (hasOnlyNegativeMaterial ? 'Некорректное количество' : hasPositiveMaterial ? (shortageQty > 0 ? 'Нехватка материала по норме' : (rule.scope === 'estimate' ? 'Поправка сметы' : rule.scope === 'project' ? 'Поправка объекта' : 'Норма применена')) : 'Материал без количества')
          : 'Нет материала в смете';
        rows.push({
          key: [est.id, section.name, itemIdx, rule.ruleKey || rule.id].join('|'),
          projectName,
          estimateId: est.id,
          estimateName: est.name,
          packageName: estimatePackage(est),
          sectionIdx,
          itemIdx,
          itemId: it.id,
          sectionName: section.name || '',
          workName: it.name || '',
          workQty,
          workUnit,
          status: materialStatus,
          severity: material ? (shortageQty > 0 || hasOnlyNegativeMaterial || !hasPositiveMaterial ? 'warning' : 'success') : 'info',
          message: material
            ? (hasOnlyNegativeMaterial
              ? 'Материал найден в разделе сметы, но количество отрицательное — это корректировка, она не закрывает потребность по норме'
              : !hasPositiveMaterial
                ? 'Материал найден в разделе сметы, но количество не заполнено или равно 0'
                : shortageQty > 0
                  ? 'Материала в смете меньше, чем требуется по норме'
                  : 'Работа покрыта нормой и материал найден в разделе сметы')
            : 'Норма есть, но строка материала в этом разделе сметы не найдена',
          rule,
          hasEstimateMaterial: !!material,
          materialName: material?.name || materialTitleForNormRule(rule),
          materialQty,
          materialUnit: material?.unit || rule.materialUnit || '',
          requiredQty,
          requiredUnit: req?.unit || rule.materialUnit || '',
          shortageQty,
          qtyPerUnit: rule.qtyPerUnit,
        });
      });
    });
    materialsInSection.forEach((m, idx) => {
      const key = materialNameKey(m.name);
      if (!key || coveredMaterialKeys.has(key)) return;
      rows.push({ key: [est.id, section.name, 'mat', idx].join('|'), projectName, estimateId: est.id, estimateName: est.name, packageName: estimatePackage(est), sectionIdx, itemIdx: idx, itemId: m.id, sectionName: section.name || '', workName: '—', workQty: 0, workUnit: '', status: 'Материал без работы', severity: 'warning', message: 'Материал есть в смете, но система не связала его с работой раздела', rule: null, materialName: m.name || '', materialQty: toNum(m.quantity), materialUnit: m.unit || '' });
    });
  }));
  return rows;
};
