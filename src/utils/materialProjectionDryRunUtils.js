import { materialAutoMatchSafe, materialLookupText, materialNameMatchScore } from './materialMatchUtils';
import { _normalizeUnit, toNum } from './measureUtils';

const rowIdentity = (row = {}) => [
  materialLookupText(row.materialKey || row.name || ''),
  materialLookupText(row.workPackage || row.work_package || ''),
  _normalizeUnit(row.unit || ''),
].join('|');

const sourceIdentity = (detail = {}) => [
  detail.estimateId || '',
  materialLookupText(detail.packageName || detail.workPackage || ''),
  materialLookupText(detail.sectionName || ''),
  materialLookupText(detail.materialName || detail.name || ''),
  materialLookupText(detail.workName || ''),
].join('|');

const sourceIdentities = (row = {}) => new Set(
  (row.planDetails || []).map(sourceIdentity).filter(key => key.split('|').some(Boolean)),
);

const hasSourceOverlap = (left, right) => {
  const leftSources = sourceIdentities(left);
  if (!leftSources.size) return false;
  return [...sourceIdentities(right)].some(key => leftSources.has(key));
};

const publicRow = (row = {}) => ({
  key: rowIdentity(row),
  name: row.name || '',
  unit: row.unit || '',
  workPackage: row.workPackage || row.work_package || '',
  qty: toNum(row.planQty),
});

export const buildLegacyMaterialProjection = (correctedRows = []) => {
  const sourceRows = (correctedRows || []).flatMap(row => {
    const details = (row.planDetails || []).filter(detail => detail.includedInProcurement !== false);
    if (!details.length && toNum(row.planQty) > 0) {
      return [{
        name: row.name || '',
        unit: row.unit || '',
        workPackage: row.workPackage || row.work_package || '',
        qty: toNum(row.planQty),
        detail: null,
      }];
    }
    return details.map(detail => ({
      name: detail.materialName || row.name || '',
      unit: detail.normalizedUnit || detail.unit || row.unit || '',
      workPackage: detail.packageName || row.workPackage || row.work_package || '',
      qty: toNum(detail.normalizedQty ?? detail.qty),
      detail,
    }));
  }).filter(source => source.name && source.qty > 0);
  const legacyRows = [];

  sourceRows.forEach(source => {
    const sourcePackage = String(source.workPackage || '').trim();
    const sourceUnit = _normalizeUnit(source.unit || '');
    let best = null;
    legacyRows.forEach(row => {
      const rowPackage = String(row.workPackage || '').trim();
      if (rowPackage && sourcePackage && rowPackage !== sourcePackage) return;
      if (sourceUnit && row.unit && _normalizeUnit(row.unit) !== sourceUnit) return;
      const names = [row.name, ...(row.aliases || [])].filter(Boolean);
      const score = Math.max(...names.map(name => materialNameMatchScore(source.name, name)), 0);
      if (!materialAutoMatchSafe(source.name, names.join(' '), score)) return;
      if (!best || score > best.score) best = {row, score};
    });
    let target = best?.row;
    if (!target) {
      target = {
        materialKey: materialLookupText(source.name),
        name: source.name,
        unit: source.unit,
        workPackage: sourcePackage,
        planQty: 0,
        planDetails: [],
        aliases: [],
      };
      legacyRows.push(target);
    } else if (materialLookupText(source.name) !== materialLookupText(target.name) && !target.aliases.includes(source.name)) {
      target.aliases.push(source.name);
    }
    target.planQty += source.qty;
    if (source.detail) target.planDetails.push(source.detail);
  });

  return legacyRows;
};

const compareProject = ({projectId = null, projectName = '', legacyRows = [], correctedRows = []} = {}) => {
  const legacy = legacyRows.map((row, index) => ({row, index, identity: rowIdentity(row)}));
  const corrected = correctedRows.map((row, index) => ({row, index, identity: rowIdentity(row)}));
  const correctedByIdentity = new Map(corrected.map(item => [item.identity, item]));
  const usedLegacy = new Set();
  const usedCorrected = new Set();
  const changes = [];
  const counts = {unchanged: 0, quantityChanged: 0, legacyOnly: 0, correctedOnly: 0, splitRows: 0};

  legacy.forEach(oldItem => {
    const splitItems = corrected.filter(item => (
      !usedCorrected.has(item.index) && hasSourceOverlap(oldItem.row, item.row)
    ));
    if (splitItems.length < 2) return;
    usedLegacy.add(oldItem.index);
    splitItems.forEach(item => usedCorrected.add(item.index));
    counts.splitRows += 1;
    changes.push({
      status: 'split',
      legacyKey: oldItem.identity,
      legacyName: oldItem.row.name || '',
      unit: oldItem.row.unit || '',
      legacyQty: toNum(oldItem.row.planQty),
      correctedNames: splitItems.map(item => item.row.name || '').sort((a, b) => a.localeCompare(b, 'ru')),
      correctedRows: splitItems.map(item => publicRow(item.row)).sort((a, b) => a.name.localeCompare(b.name, 'ru')),
      correctedQty: splitItems.reduce((sum, item) => sum + toNum(item.row.planQty), 0),
    });
  });

  legacy.forEach(oldItem => {
    if (usedLegacy.has(oldItem.index)) return;
    const newItem = correctedByIdentity.get(oldItem.identity);
    if (!newItem || usedCorrected.has(newItem.index)) return;
    usedLegacy.add(oldItem.index);
    usedCorrected.add(newItem.index);
    const legacyQty = toNum(oldItem.row.planQty);
    const correctedQty = toNum(newItem.row.planQty);
    const deltaQty = correctedQty - legacyQty;
    if (Math.abs(deltaQty) < 0.000001) {
      counts.unchanged += 1;
      return;
    }
    counts.quantityChanged += 1;
    changes.push({
      status: 'quantity_changed',
      ...publicRow(newItem.row),
      legacyQty,
      correctedQty,
      deltaQty,
    });
  });

  corrected.filter(item => !usedCorrected.has(item.index)).forEach(item => {
    counts.correctedOnly += 1;
    const row = publicRow(item.row);
    changes.push({status: 'corrected_only', ...row, correctedQty: row.qty});
  });
  legacy.filter(item => !usedLegacy.has(item.index)).forEach(item => {
    counts.legacyOnly += 1;
    const row = publicRow(item.row);
    changes.push({status: 'legacy_only', ...row, legacyQty: row.qty});
  });

  return {
    projectId,
    projectName,
    summary: {legacyRows: legacy.length, correctedRows: corrected.length, ...counts},
    changes,
  };
};

export const buildMaterialProjectionDryRun = (projectInputs = []) => {
  const projects = (projectInputs || []).map(compareProject);
  const summary = projects.reduce((totals, project) => {
    totals.projects += 1;
    Object.keys(project.summary).forEach(key => { totals[key] += project.summary[key]; });
    return totals;
  }, {
    projects: 0,
    legacyRows: 0,
    correctedRows: 0,
    unchanged: 0,
    quantityChanged: 0,
    legacyOnly: 0,
    correctedOnly: 0,
    splitRows: 0,
  });
  return {ok: true, dryRun: true, writesAttempted: 0, summary, projects};
};
