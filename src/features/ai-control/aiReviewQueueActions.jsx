import EstimateChangeReconcileTask from './EstimateChangeReconcileTask';
import {
  closeStaleAiTasksByMarkerPrefix,
  queueAiControlDescriptor,
  upsertAiTaskByMarker,
} from './aiQueueUtils';
import { createEstimateChangeReconcileTaskActions } from '../estimates/estimateChangeReconcileTaskActions';
import {
  buildMaterialControlSignatureForProject,
  buildMaterialControlTaskDescriptorsForProject,
  buildRoomControlSignatureForProject,
  buildRoomControlTaskDescriptorsForProject,
} from '../../utils/aiControlTaskUtils';
import { parseAiTaskPayload } from '../../utils/aiControlDescriptionUtils';
import { estimateIssueDomId } from '../../utils/estimateUtils';

export function createAiReviewQueueActions({
  API,
  aiFindings,
  aiTasks,
  buildEstimateDiff,
  estimateChangeAutoDecision,
  estimateChangeReconcileDescription,
  estimateChangeReconcileMarker,
  estimateChangeReconcileQueuedRef,
  estimateDiffBaseFor,
  estimateDiffReviewDescription,
  estimateDiffReviewMarker,
  estimateDiffReviewQueuedRef,
  estimateKind,
  estimateNormCoverageRows,
  estimateNormReviewDescription,
  estimateNormReviewIssueStatuses,
  estimateNormReviewMarker,
  estimateNormReviewQueuedRef,
  estimatePackage,
  estimateQualityDescription,
  estimateQualityReviewMarker,
  estimateQualityReviewQueuedRef,
  estimateQualityRows,
  estimatesList,
  fmtMeasure,
  includableEstimateChanges,
  isArchivedEstimate,
  isGlobalEstimateTemplate,
  isOpenAiStatus,
  materialAliasCandidates,
  materialControlSummaryForProject,
  materialControlTaskQueuedRef,
  materialNameKey,
  materialNormControlSummaryForProject,
  openAiTaskAction,
  patchAiFindingSilent,
  patchAiTaskSilent,
  roomCompleteness,
  roomControlTaskQueuedRef,
  roomWorks,
  rooms,
  sameEstimateGroup,
  selectedEstimate,
  setAiTasks,
  setEstimateIssueFocusKey,
  setUnexpectedWorksList,
  staff,
  user,
  users,
  workJournal,
  fetchFn = fetch,
}) {
  const aiTaskByMarker = (marker) => (aiTasks || []).find(task =>
    isOpenAiStatus(task.status) && String(task.actionPayload || '').includes(marker)
  );

  const jumpToEstimateIssue = (row) => {
    if (!row || row.sectionIdx === undefined || row.itemIdx === undefined) return;
    const key = estimateIssueDomId(row.estimateId || selectedEstimate?.id, row.sectionIdx, row.itemIdx);
    setEstimateIssueFocusKey(key);
    setTimeout(() => {
      const el = document.getElementById(key);
      if (el) el.scrollIntoView({behavior: 'smooth', block: 'center'});
    }, 30);
    setTimeout(() => setEstimateIssueFocusKey(prev => prev === key ? '' : prev), 4500);
  };

  const hasActiveEstimator = () => {
    const roleOf = (value) => String(value || '').trim().toLowerCase();
    return (users || []).some(item => roleOf(item.role) === 'сметчик')
      || (staff || []).some(item => roleOf(item.systemRole || item.role) === 'сметчик' && roleOf(item.status || 'активен') !== 'уволен');
  };

  const queueEstimateQualityReviewTask = async (estimate, reason = 'Автопроверка сметы') => {
    if (!estimate?.id || !estimate.projectName) return;
    if (estimateKind(estimate) !== 'Заказчик' || isArchivedEstimate(estimate) || (estimate.status || 'Черновик') !== 'Активная') return;
    const marker = estimateQualityReviewMarker(estimate.id);
    const existingTask = aiTaskByMarker(marker);
    const rows = estimateQualityRows(estimate);
    const counts = rows.reduce((acc, row) => {
      acc[row.status] = (acc[row.status] || 0) + 1;
      return acc;
    }, {});
    if (!rows.length) {
      if (existingTask) await patchAiTaskSilent(existingTask.id, {status: 'Закрыто'});
      return;
    }
    await upsertAiTaskByMarker({
      API,
      marker,
      projectName: estimate.projectName,
      existingTask,
      queuedRef: estimateQualityReviewQueuedRef,
      setAiTasks,
      patchAiTaskSilent,
      patch: {
        title: 'Исправить данные сметы: ' + estimate.projectName + ' — ' + rows.length + ' ош.',
        description: estimateQualityDescription(estimate, rows, reason),
        assignedRole: hasActiveEstimator() ? 'сметчик' : 'директор',
        actionLabel: 'Открыть смету',
        actionPayload: JSON.stringify({
          type: 'estimate_quality_review',
          marker,
          estimateId: estimate.id,
          estimateName: estimate.name || '',
          projectName: estimate.projectName || '',
          workPackage: estimatePackage(estimate),
          reason,
          counts,
        }),
      },
    });
  };

  const estimateListWithUpdatedEstimate = (estimate) => {
    if (!estimate?.id) return estimatesList || [];
    let found = false;
    const mapped = (estimatesList || []).map(item => {
      if (Number(item.id) === Number(estimate.id)) {
        found = true;
        return estimate;
      }
      return item;
    });
    return found ? mapped : [...mapped, estimate];
  };

  const estimateNormReviewExistingTask = (marker) => aiTaskByMarker(marker);

  const queueEstimateDiffReviewTask = async (baseEstimate, nextEstimate, reason = 'Новая смета') => {
    if (!baseEstimate?.id || !nextEstimate?.id || Number(baseEstimate.id) === Number(nextEstimate.id)) return;
    if (!sameEstimateGroup(baseEstimate, nextEstimate) || isGlobalEstimateTemplate(nextEstimate) || (nextEstimate.status || 'Черновик') !== 'Активная') return;
    const diff = buildEstimateDiff(baseEstimate, nextEstimate);
    const changeCount = diff.changed.length + diff.added.length + diff.removed.length;
    const marker = estimateDiffReviewMarker(baseEstimate.id, nextEstimate.id);
    const existingTask = aiTaskByMarker(marker);
    if (!changeCount) {
      if (existingTask) await patchAiTaskSilent(existingTask.id, {status: 'Закрыто'});
      return;
    }
    await upsertAiTaskByMarker({
      API,
      marker,
      projectName: nextEstimate.projectName || baseEstimate.projectName || '',
      existingTask,
      queuedRef: estimateDiffReviewQueuedRef,
      setAiTasks,
      patchAiTaskSilent,
      patch: {
        title: 'Сверить разницу смет: ' + (nextEstimate.projectName || baseEstimate.projectName || '') + ' — ' + changeCount + ' изм.',
        description: estimateDiffReviewDescription(baseEstimate, nextEstimate, diff, reason),
        assignedRole: hasActiveEstimator() ? 'сметчик' : 'директор',
        actionLabel: 'Открыть ведомость смет',
        actionPayload: JSON.stringify({
          type: 'estimate_diff_review',
          marker,
          baseEstimateId: baseEstimate.id,
          nextEstimateId: nextEstimate.id,
          projectName: nextEstimate.projectName || baseEstimate.projectName || '',
          workPackage: estimatePackage(nextEstimate),
          reason,
          changed: diff.changed.length,
          added: diff.added.length,
          removed: diff.removed.length,
          impact: diff.impact,
        }),
      },
    });
  };

  const autoReconcileEstimateChanges = async (baseEstimate, nextEstimate, reason = 'Новая смета') => {
    if (!baseEstimate?.id || !nextEstimate?.id || Number(baseEstimate.id) === Number(nextEstimate.id)) return;
    if (!sameEstimateGroup(baseEstimate, nextEstimate) || isGlobalEstimateTemplate(nextEstimate) || estimateKind(nextEstimate) !== 'Заказчик' || (nextEstimate.status || 'Черновик') !== 'Активная') return;
    const marker = estimateChangeReconcileMarker(nextEstimate.id);
    const candidates = includableEstimateChanges(nextEstimate.projectName || baseEstimate.projectName || '');
    const existingTask = aiTaskByMarker(marker);
    if (!candidates.length) {
      if (existingTask) await patchAiTaskSilent(existingTask.id, {status: 'Закрыто'});
      return;
    }
    const diff = buildEstimateDiff(baseEstimate, nextEstimate);
    const decisions = candidates.map(change => estimateChangeAutoDecision(change, nextEstimate, diff));
    const autoIds = decisions.filter(decision => decision.autoInclude).map(decision => Number(decision.change.id)).filter(Boolean);
    let includedIds = [];
    if (autoIds.length) {
      try {
        const res = await fetchFn(API + '/estimates/' + nextEstimate.id + '/reconcile-changes', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({changeIds: autoIds, updatedBy: user.name}),
        });
        const data = await res.json().catch(() => ({}));
        if (res.ok) {
          includedIds = (data.includedChangeIds || []).map(Number);
          if (includedIds.length) {
            const includedSet = new Set(includedIds);
            setUnexpectedWorksList(prev => (prev || []).map(item => includedSet.has(Number(item.id))
              ? {
                  ...item,
                  status: 'Включено в новую смету',
                  includedInEstimateId: nextEstimate.id,
                  reason: item.reason || ('Автоматически сопоставлено с новой сметой №' + nextEstimate.id),
                }
              : item));
          }
        }
      } catch (e) {}
    }
    const includedSet = new Set(includedIds);
    const unresolved = decisions.filter(decision => !includedSet.has(Number(decision.change.id)));
    if (!unresolved.length) {
      if (existingTask) await patchAiTaskSilent(existingTask.id, {status: 'Закрыто'});
      return;
    }
    const payloadData = {
      type: 'estimate_change_reconcile',
      marker,
      baseEstimateId: baseEstimate.id,
      nextEstimateId: nextEstimate.id,
      projectName: nextEstimate.projectName || baseEstimate.projectName || '',
      workPackage: estimatePackage(nextEstimate),
      reason,
      included: includedIds.length,
      unresolved: unresolved.length,
    };
    await upsertAiTaskByMarker({
      API,
      marker,
      projectName: nextEstimate.projectName || baseEstimate.projectName || '',
      existingTask,
      queuedRef: estimateChangeReconcileQueuedRef,
      setAiTasks,
      patchAiTaskSilent,
      patch: {
        title: 'Проверить включение допработ: ' + (nextEstimate.projectName || baseEstimate.projectName || '') + ' — ' + unresolved.length + ' спорн.',
        description: estimateChangeReconcileDescription(baseEstimate, nextEstimate, unresolved, includedIds.length, reason),
        assignedRole: hasActiveEstimator() ? 'сметчик' : 'директор',
        actionPayload: JSON.stringify(payloadData),
        actionLabel: 'Открыть изменения к смете',
      },
    });
  };

  const {
    confirmEstimateChangeIncluded,
    estimateChangeReconcileEstimatesForTask,
    estimateChangeReconcileRowsForTask,
  } = createEstimateChangeReconcileTaskActions({
    API,
    user,
    estimatesList,
    estimateDiffBaseFor,
    buildEstimateDiff,
    includableEstimateChanges,
    estimateChangeAutoDecision,
    setUnexpectedWorksList,
    patchAiTaskSilent,
  });

  const renderEstimateChangeReconcileTask = (task) => {
    const {baseEstimate, nextEstimate} = estimateChangeReconcileEstimatesForTask(task);
    const rows = estimateChangeReconcileRowsForTask(task);
    return (
      <EstimateChangeReconcileTask
        task={task}
        baseEstimate={baseEstimate}
        nextEstimate={nextEstimate}
        rows={rows}
        fmtMeasure={fmtMeasure}
        onConfirmIncluded={confirmEstimateChangeIncluded}
        onOpenTask={openAiTaskAction}
      />
    );
  };

  const queueEstimateNormReviewTask = async (estimate, reason = 'Автопроверка сметы', sourceEstimates = null) => {
    if (!estimate?.id || !estimate.projectName) return;
    if (estimateKind(estimate) !== 'Заказчик' || isArchivedEstimate(estimate) || (estimate.status || 'Черновик') !== 'Активная') return;
    const marker = estimateNormReviewMarker(estimate.id);
    const existingTask = estimateNormReviewExistingTask(marker);
    const rows = estimateNormCoverageRows(estimate.projectName, sourceEstimates)
      .filter(row => Number(row.estimateId) === Number(estimate.id) && estimateNormReviewIssueStatuses.includes(row.status));
    const counts = estimateNormReviewIssueStatuses.reduce((acc, status) => {
      const count = rows.filter(row => row.status === status).length;
      if (count) acc[status] = count;
      return acc;
    }, {});
    if (!rows.length) {
      if (existingTask) await patchAiTaskSilent(existingTask.id, {status: 'Закрыто'});
      return;
    }
    await upsertAiTaskByMarker({
      API,
      marker,
      projectName: estimate.projectName,
      existingTask,
      queuedRef: estimateNormReviewQueuedRef,
      setAiTasks,
      patchAiTaskSilent,
      patch: {
        title: 'Проверить смету: ' + estimate.projectName + ' — ' + rows.length + ' замеч.',
        description: estimateNormReviewDescription(estimate, rows, reason),
        assignedRole: hasActiveEstimator() ? 'сметчик' : 'директор',
        actionLabel: 'Открыть проверку сметы',
        actionPayload: JSON.stringify({
          type: 'estimate_norm_review',
          marker,
          estimateId: estimate.id,
          estimateName: estimate.name || '',
          projectName: estimate.projectName || '',
          workPackage: estimatePackage(estimate),
          reason,
          counts,
        }),
      },
    });
  };

  const materialControlTaskDescriptorsForProject = (projectName, reason = 'Фоновая проверка материалов') => buildMaterialControlTaskDescriptorsForProject({
    projectName,
    reason,
    materialControlSummaryForProject,
    materialNormControlSummaryForProject,
    materialNameKey,
    materialAliasCandidates,
    hasActiveEstimator,
  });

  const materialControlSignatureForProject = (projectName) => buildMaterialControlSignatureForProject({
    projectName,
    materialControlSummaryForProject,
    materialNormControlSummaryForProject,
  });

  const roomControlTaskDescriptorsForProject = (projectName, reason = 'Фоновая проверка помещений') => buildRoomControlTaskDescriptorsForProject({
    projectName,
    reason,
    rooms,
    roomWorks,
    workJournal,
    roomCompleteness,
    materialNameKey,
  });

  const roomControlSignatureForProject = (projectName) => buildRoomControlSignatureForProject({
    projectName,
    rooms,
    roomWorks,
    workJournal,
    roomCompleteness,
    materialNameKey,
  });

  const queueMaterialControlTask = async (descriptor) => {
    await queueAiControlDescriptor({
      API,
      descriptor,
      aiTaskByMarker,
      queuedRef: materialControlTaskQueuedRef,
      setAiTasks,
      patchAiTaskSilent,
    });
  };

  const queueMaterialControlTasksForProject = async (projectName, reason = 'Фоновая проверка материалов') => {
    const descriptors = materialControlTaskDescriptorsForProject(projectName, reason);
    const activeMarkers = new Set(descriptors.map(descriptor => descriptor.marker));
    closeStaleAiTasksByMarkerPrefix({
      tasks: aiTasks,
      projectName,
      markerPrefix: 'MATERIAL_CONTROL:',
      activeMarkers,
      parsePayload: parseAiTaskPayload,
      isOpenStatus: isOpenAiStatus,
      patchTaskSilent: patchAiTaskSilent,
    });
    for (const descriptor of descriptors) {
      await queueMaterialControlTask(descriptor);
    }
  };

  const queueRoomControlTask = async (descriptor) => {
    await queueAiControlDescriptor({
      API,
      descriptor,
      aiTaskByMarker,
      queuedRef: roomControlTaskQueuedRef,
      setAiTasks,
      patchAiTaskSilent,
    });
  };

  const queueRoomControlTasksForProject = async (projectName, reason = 'Фоновая проверка помещений') => {
    const descriptors = roomControlTaskDescriptorsForProject(projectName, reason);
    const activeMarkers = new Set(descriptors.map(descriptor => descriptor.marker));
    const isLegacyRoomBinding = (item) => {
      const dedupe = String(item?.dedupeKey || item?.dedupe_key || '');
      const payload = String(item?.actionPayload || item?.action_payload || '');
      return (dedupe.startsWith('work_journal:') && dedupe.endsWith(':room_binding')) || payload.includes('room_binding');
    };
    (aiTasks || [])
      .filter(task => isOpenAiStatus(task.status) && (task.projectName || '') === projectName && isLegacyRoomBinding(task))
      .forEach(task => patchAiTaskSilent(task.id, {status: 'Закрыто'}));
    (aiFindings || [])
      .filter(finding => isOpenAiStatus(finding.status) && (finding.projectName || '') === projectName && isLegacyRoomBinding(finding))
      .forEach(finding => patchAiFindingSilent(finding.id, {status: 'Закрыто'}));
    closeStaleAiTasksByMarkerPrefix({
      tasks: aiTasks,
      projectName,
      markerPrefix: 'ROOM_CONTROL:',
      activeMarkers,
      parsePayload: parseAiTaskPayload,
      isOpenStatus: isOpenAiStatus,
      patchTaskSilent: patchAiTaskSilent,
    });
    for (const descriptor of descriptors) {
      await queueRoomControlTask(descriptor);
    }
  };

  return {
    aiTaskByMarker,
    autoReconcileEstimateChanges,
    estimateListWithUpdatedEstimate,
    estimateNormReviewExistingTask,
    hasActiveEstimator,
    jumpToEstimateIssue,
    materialControlSignatureForProject,
    materialControlTaskDescriptorsForProject,
    queueEstimateDiffReviewTask,
    queueEstimateNormReviewTask,
    queueEstimateQualityReviewTask,
    queueMaterialControlTask,
    queueMaterialControlTasksForProject,
    queueRoomControlTask,
    queueRoomControlTasksForProject,
    renderEstimateChangeReconcileTask,
    roomControlSignatureForProject,
    roomControlTaskDescriptorsForProject,
  };
}
