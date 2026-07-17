import { materialAutoMatchSafe, materialLookupText, materialNameMatchScore } from './materialMatchUtils';
import { _normalizeUnit, toNum } from './measureUtils';
import { isActiveSupplyRequestStatus, supplyRequestOrigin } from './supplyUtils';

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

const packageIdentity = value => materialLookupText(value || 'Основная');

const requestItems = (request, parseSupplyItems) => {
  let parsed = [];
  try {
    parsed = typeof parseSupplyItems === 'function' ? parseSupplyItems(request) : [];
  } catch (_) {
    parsed = [];
  }
  if (Array.isArray(parsed) && parsed.length) return parsed;
  return [{
    materialName: request.materialName || '',
    quantity: request.quantity,
    unit: request.unit || '',
    workPackage: request.workPackage || request.work_package || '',
  }];
};

const stablePositiveDecimalId = value => {
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string' && typeof value !== 'number') return null;
  if (typeof value === 'number' && (!Number.isSafeInteger(value) || value <= 0)) return null;
  const normalized = String(value).trim();
  if (!/^[1-9]\d*$/.test(normalized)) return null;
  const numeric = Number(normalized);
  return Number.isSafeInteger(numeric) ? numeric : normalized;
};

const stableRequestId = request => stablePositiveDecimalId(request?.id);

const stableProjectName = value => {
  if (typeof value !== 'string') return null;
  const normalized = value.trim();
  return normalized || null;
};

const requestHasProjectionLineage = (request, parseSupplyItems) => {
  if (supplyRequestOrigin(request)) return true;
  const lineageFields = ['estimateId', 'estimate_id', 'sourceEstimateId', 'source_estimate_id'];
  if (lineageFields.some(field => stablePositiveDecimalId(request?.[field]) !== null)) return true;
  return requestItems(request, parseSupplyItems).some(item => (
    lineageFields.some(field => stablePositiveDecimalId(item?.[field]) !== null)
    || Boolean(item?.estimateControl || item?.estimate_control)
  ));
};

const requestValueSignature = value => {
  if (value === undefined) return 'undefined';
  if (value === null) return 'null';
  if (typeof value === 'string') return `string:${value.trim()}`;
  if (typeof value === 'number') return Number.isFinite(value) ? `number:${value}` : `number:${String(value)}`;
  if (typeof value === 'boolean') return `boolean:${value}`;
  return `${typeof value}:${String(value)}`;
};

const requestDuplicateSignature = (request, parseSupplyItems) => JSON.stringify({
  project: requestValueSignature(request?.project),
  status: requestValueSignature(request?.status),
  notes: requestValueSignature(request?.notes),
  items: requestItems(request, parseSupplyItems).map(item => ({
    materialName: requestValueSignature(item?.materialName || item?.material_name || item?.name || request?.materialName),
    quantity: requestValueSignature(item?.quantity ?? item?.qty ?? request?.quantity),
    unit: requestValueSignature(item?.unit || request?.unit),
    workPackage: requestValueSignature(item?.workPackage || item?.work_package || request?.workPackage || request?.work_package),
  })),
});

const uniqueRequestEntries = (projectInputs = [], parseSupplyItems) => {
  const missingEntries = [];
  const groups = new Map();
  let missingIndex = 0;
  let order = 0;

  (projectInputs || []).forEach(input => (input.requests || []).forEach(request => {
    if (!request) return;
    const requestId = stableRequestId(request);
    if (requestId !== null) {
      const requestKey = `id:${String(requestId).trim()}`;
      const group = groups.get(requestKey) || {requestKey, firstOrder: order, occurrences: []};
      group.occurrences.push({request, signature: requestDuplicateSignature(request, parseSupplyItems)});
      groups.set(requestKey, group);
      order += 1;
      return;
    }
    missingEntries.push({request, requestKey: `missing:${missingIndex}`, firstOrder: order});
    missingIndex += 1;
    order += 1;
  }));

  const groupedEntries = [...groups.values()].map(group => {
    const occurrences = [...group.occurrences].sort((left, right) => left.signature.localeCompare(right.signature));
    const distinctSignatures = new Set(occurrences.map(occurrence => occurrence.signature));
    return {
      request: occurrences[0].request,
      requestKey: group.requestKey,
      firstOrder: group.firstOrder,
      conflict: distinctSignatures.size > 1,
      conflictingRequests: distinctSignatures.size > 1 ? occurrences.map(occurrence => occurrence.request) : [],
    };
  });

  return [...missingEntries, ...groupedEntries]
    .sort((left, right) => left.firstOrder - right.firstOrder)
    .map(({firstOrder, ...entry}) => entry);
};

const conflictingRequestReviewItem = (entry, parseSupplyItems) => {
  const requests = entry.conflictingRequests || [entry.request];
  const projectNames = [...new Set(requests.map(request => stableProjectName(request?.project)).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, 'ru'));
  const candidateNames = [...new Set(requests.flatMap(request => requestItems(request, parseSupplyItems).map(item => (
    item?.materialName || item?.material_name || item?.name || request?.materialName || ''
  ))).filter(Boolean))].sort((left, right) => left.localeCompare(right, 'ru'));
  const statuses = [...new Set(requests.map(request => stableProjectName(request?.status)).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, 'ru'));
  return {
    projectId: null,
    projectName: projectNames.length === 1 ? projectNames[0] : (projectNames.length ? `Конфликт: ${projectNames.join(' / ')}` : ''),
    requestId: stableRequestId(entry.request),
    requestKey: entry.requestKey,
    requestStatus: statuses.join('; ') || 'Новая',
    itemIndex: 0,
    materialName: candidateNames.join('; ') || 'Данные заявки расходятся',
    quantity: 0,
    unit: '',
    workPackage: '',
    status: 'needs_review',
    reason: 'conflicting_request_duplicates',
    candidateNames,
    candidateProjectIds: [],
  };
};

export const buildSupplyRequestProjectionReview = ({
  projectName = '',
  requests = [],
  correctedRows = [],
  parseSupplyItems,
} = {}) => {
  const currentRows = (correctedRows || []).filter(row => toNum(row.planQty) > 0);
  const legacyRows = buildLegacyMaterialProjection(currentRows);
  const projection = buildMaterialProjectionDryRun([{projectName, legacyRows, correctedRows: currentRows}]);
  const splitChanges = (projection.projects[0]?.changes || []).filter(change => change.status === 'split');
  const activeRequests = uniqueRequestEntries([{
    requests: (requests || []).filter(request => (
      request?.project === projectName && isActiveSupplyRequestStatus(request?.status)
    )),
  }], parseSupplyItems).map((entry, requestIndex) => ({...entry, requestIndex}));
  const ready = [];
  const needsReview = [];
  const counts = {legacyAggregate: 0, unmatched: 0, ambiguous: 0, unitMismatch: 0, packageMismatch: 0, missingId: 0, conflictingDuplicate: 0};

  activeRequests.forEach(entry => {
    if (entry.conflict) {
      counts.conflictingDuplicate += 1;
      needsReview.push(conflictingRequestReviewItem(entry, parseSupplyItems));
      return;
    }
    const {request, requestIndex, requestKey} = entry;
    requestItems(request, parseSupplyItems).forEach((item, itemIndex) => {
    const materialName = item?.materialName || item?.material_name || item?.name || request.materialName || '';
    const materialKey = materialLookupText(materialName);
    const unit = item?.unit || request.unit || '';
    const unitKey = _normalizeUnit(unit);
    const workPackage = item?.workPackage || item?.work_package || request.workPackage || request.work_package || '';
    const packageKey = packageIdentity(workPackage);
    const quantity = toNum(item?.quantity ?? item?.qty ?? request.quantity);
    const requestId = stableRequestId(request);
    const hasRequestId = requestId !== null;
    const base = {
      requestId,
      requestKey: requestKey || (hasRequestId ? `id:${String(requestId).trim()}` : `missing:${requestIndex}`),
      requestStatus: request.status || 'Новая',
      itemIndex,
      materialName,
      quantity,
      unit,
      workPackage,
    };
    if (!hasRequestId) {
      counts.missingId += 1;
      needsReview.push({...base, status: 'needs_review', reason: 'missing_request_id', candidateNames: []});
      return;
    }
    const nameMatches = currentRows.filter(row => {
      const exact = materialLookupText(row.materialKey || row.name) === materialKey;
      const confirmedAlias = (row.aliasIds || []).length > 0 && (row.aliases || []).some(alias => materialLookupText(alias) === materialKey);
      return exact || confirmedAlias;
    });
    const exactMatches = nameMatches.filter(row => (
      packageIdentity(row.workPackage || row.packageName) === packageKey
      && (!unitKey || !_normalizeUnit(row.unit) || _normalizeUnit(row.unit) === unitKey)
    ));
    const split = splitChanges.find(change => (
      materialLookupText(change.legacyName) === materialKey
      && packageIdentity(change.correctedRows?.[0]?.workPackage) === packageKey
      && (!unitKey || !_normalizeUnit(change.unit) || _normalizeUnit(change.unit) === unitKey)
    ));
    const fromMaterialControl = String(request.notes || '').includes('Создано из контроля материалов');
    const exceedsExactPlan = exactMatches.length === 1 && quantity > toNum(exactMatches[0].planQty) + 0.0001;
    if (split && (fromMaterialControl || exceedsExactPlan)) {
      counts.legacyAggregate += 1;
      needsReview.push({...base, status: 'needs_review', reason: 'legacy_aggregate_split', candidateNames: split.correctedNames || []});
      return;
    }
    if (exactMatches.length === 1) {
      ready.push({...base, status: 'ready', reason: 'exact_projection_identity', projectionName: exactMatches[0].name});
      return;
    }
    if (nameMatches.length) {
      const samePackage = nameMatches.filter(row => packageIdentity(row.workPackage || row.packageName) === packageKey);
      const reason = samePackage.length ? 'unit_mismatch' : 'package_mismatch';
      counts[reason === 'unit_mismatch' ? 'unitMismatch' : 'packageMismatch'] += 1;
      needsReview.push({...base, status: 'needs_review', reason, candidateNames: nameMatches.map(row => row.name)});
      return;
    }
    const fuzzyMatches = currentRows.filter(row => {
      if (packageIdentity(row.workPackage || row.packageName) !== packageKey) return false;
      if (unitKey && _normalizeUnit(row.unit) && _normalizeUnit(row.unit) !== unitKey) return false;
      const score = materialNameMatchScore(materialName, row.name);
      return materialAutoMatchSafe(materialName, row.name, score);
    });
    if (fuzzyMatches.length) {
      counts.ambiguous += 1;
      needsReview.push({...base, status: 'needs_review', reason: 'ambiguous_material_identity', candidateNames: fuzzyMatches.map(row => row.name)});
      return;
    }
    counts.unmatched += 1;
    needsReview.push({...base, status: 'needs_review', reason: 'material_not_in_projection', candidateNames: []});
    });
  });

  return {
    ok: true,
    dryRun: true,
    writesAttempted: 0,
    summary: {
      activeRequests: activeRequests.length,
      items: ready.length + needsReview.length,
      ready: ready.length,
      needsReview: needsReview.length,
      ...counts,
    },
    ready,
    needsReview,
  };
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

export const buildAllProjectsMaterialProjectionReview = (
  projectInputs = [],
  parseSupplyItems,
  projectIdentityCandidates = null,
  requestSource = null,
) => {
  const inputs = (Array.isArray(projectInputs) ? projectInputs : []).filter(input => input && typeof input === 'object');
  const identityInputs = Array.isArray(projectIdentityCandidates) ? projectIdentityCandidates : inputs;
  const projectCandidatesByName = identityInputs.reduce((result, input) => {
    if (!input || typeof input !== 'object') return result;
    const projectName = stableProjectName(input.projectName);
    if (!projectName) return result;
    const candidates = result.get(projectName) || [];
    const projectId = stablePositiveDecimalId(input.projectId);
    candidates.push({projectId, projectName});
    result.set(projectName, candidates);
    return result;
  }, new Map());
  const requestInputs = (Array.isArray(requestSource) ? [{requests: requestSource}] : inputs).map(input => ({
    ...input,
    requests: (Array.isArray(input.requests) ? input.requests : []).filter(request => (
      isActiveSupplyRequestStatus(request?.status)
      && requestHasProjectionLineage(request, parseSupplyItems)
    )),
  }));
  const uniqueRequests = uniqueRequestEntries(requestInputs, parseSupplyItems);
  const activeRequests = uniqueRequests;
  const resolvedProjectIdByName = new Map();
  projectCandidatesByName.forEach((candidates, projectName) => {
    if (candidates.length !== 1 || candidates[0].projectId === null) return;
    const candidateId = candidates[0].projectId;
    const activeMatches = inputs.filter(input => (
      stableProjectName(input.projectName) === projectName
      && stablePositiveDecimalId(input.projectId) !== null
      && String(stablePositiveDecimalId(input.projectId)) === String(candidateId)
    ));
    if (activeMatches.length === 1) resolvedProjectIdByName.set(projectName, candidateId);
  });
  const unresolvedReviewItems = activeRequests.flatMap(entry => {
    if (entry.conflict) {
      const item = conflictingRequestReviewItem(entry, parseSupplyItems);
      item.candidateProjectIds = [...new Set((entry.conflictingRequests || []).flatMap(request => {
        const projectName = stableProjectName(request?.project);
        return projectName ? (projectCandidatesByName.get(projectName) || []).map(candidate => candidate.projectId).filter(id => id !== null) : [];
      }))];
      return [item];
    }
    const {request, requestKey} = entry;
    const projectName = stableProjectName(request?.project);
    const hasValidProjectName = projectName !== null;
    const candidates = projectCandidatesByName.get(projectName) || [];
    if (hasValidProjectName && resolvedProjectIdByName.has(projectName)) return [];
    const requestId = stableRequestId(request);
    const candidateProjectIds = candidates
      .map(candidate => candidate.projectId)
      .filter(projectId => projectId !== null && projectId !== undefined);
    return requestItems(request, parseSupplyItems).map((item, itemIndex) => ({
      projectId: null,
      projectName: projectName || '',
      requestId,
      requestKey,
      requestStatus: request.status || 'Новая',
      itemIndex,
      materialName: item?.materialName || item?.material_name || item?.name || request.materialName || '',
      quantity: toNum(item?.quantity ?? item?.qty ?? request.quantity),
      unit: item?.unit || request.unit || '',
      workPackage: item?.workPackage || item?.work_package || request.workPackage || request.work_package || '',
      status: 'needs_review',
      reason: requestId === null
        ? 'missing_request_id'
        : (!hasValidProjectName
          ? 'project_identity_invalid'
          : (candidates.length > 1
          ? 'ambiguous_project_identity'
          : (candidates.length === 0
            ? 'project_not_found'
            : (candidates[0].projectId === null ? 'project_identity_invalid' : 'project_inactive')))),
      candidateNames: [],
      candidateProjectIds,
    }));
  });
  const normalizedRequests = uniqueRequests.filter(entry => !entry.conflict).map(({request}) => request);

  const projects = inputs.map(input => {
    const projectName = stableProjectName(input.projectName) || '';
    const correctedRows = (input.correctedRows || []).filter(row => toNum(row.planQty) > 0);
    const legacyRows = buildLegacyMaterialProjection(correctedRows);
    const projection = buildMaterialProjectionDryRun([{
      projectId: stablePositiveDecimalId(input.projectId),
      projectName,
      legacyRows,
      correctedRows,
    }]).projects[0];
    const resolvedProjectId = resolvedProjectIdByName.get(projectName);
    const projectIsResolved = resolvedProjectId !== undefined
      && stablePositiveDecimalId(input.projectId) !== null
      && String(stablePositiveDecimalId(input.projectId)) === String(resolvedProjectId);
    const requestReview = buildSupplyRequestProjectionReview({
      projectName,
      requests: projectIsResolved ? normalizedRequests : [],
      correctedRows,
      parseSupplyItems,
    });
    const projectionChanges = (projection.changes || []).length;
    const requestItemsNeedingReview = requestReview.summary.needsReview || 0;
    return {
      projectId: stablePositiveDecimalId(input.projectId),
      projectName,
      projectionChanges,
      requestItemsNeedingReview,
      activeRequests: requestReview.summary.activeRequests || 0,
      requestItems: requestReview.summary.items || 0,
      requestItemsReady: requestReview.summary.ready || 0,
      splitRows: projection.summary.splitRows || 0,
      quantityChanged: projection.summary.quantityChanged || 0,
      correctedOnly: projection.summary.correctedOnly || 0,
      legacyOnly: projection.summary.legacyOnly || 0,
      needsReview: projectionChanges > 0 || requestItemsNeedingReview > 0,
      requestReviewItems: (requestReview.needsReview || []).map(item => ({
        ...item,
        projectId: stablePositiveDecimalId(input.projectId),
        projectName,
      })),
    };
  }).sort((left, right) => (
    Number(right.needsReview) - Number(left.needsReview)
    || right.requestItemsNeedingReview - left.requestItemsNeedingReview
    || right.projectionChanges - left.projectionChanges
    || left.projectName.localeCompare(right.projectName, 'ru')
  ));

  const reviewItems = [
    ...projects.flatMap(project => project.requestReviewItems || []),
    ...unresolvedReviewItems,
  ].sort((left, right) => (
    String(left.projectName || '').localeCompare(String(right.projectName || ''), 'ru')
    || String(left.requestKey || '').localeCompare(String(right.requestKey || ''), 'ru', {numeric: true})
    || left.itemIndex - right.itemIndex
  ));
  const reviewRequestKeys = new Set(reviewItems.map(item => (
    String(item.requestKey || '').startsWith('id:')
      ? item.requestKey
      : `${item.projectName}|${item.requestKey}`
  )));
  const requestItemCount = activeRequests.reduce((total, entry) => (
    total + (entry.conflict ? 1 : requestItems(entry.request, parseSupplyItems).length)
  ), 0);

  const summary = projects.reduce((totals, project) => {
    totals.projects += 1;
    totals.projectsNeedingReview += Number(project.needsReview);
    totals.projectionChanges += project.projectionChanges;
    totals.splitRows += project.splitRows;
    return totals;
  }, {
    projects: 0,
    projectsNeedingReview: 0,
    projectionChanges: 0,
    activeRequests: activeRequests.length,
    requestItems: requestItemCount,
    requestItemsReady: Math.max(0, requestItemCount - reviewItems.length),
    requestsNeedingReview: reviewRequestKeys.size,
    requestItemsNeedingReview: reviewItems.length,
    splitRows: 0,
  });

  return {ok: true, dryRun: true, writesAttempted: 0, summary, projects, reviewItems};
};
