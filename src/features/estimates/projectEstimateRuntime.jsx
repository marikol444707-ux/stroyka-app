import React from 'react';
import EstimateReconciliationsPanel from '../../components/EstimateReconciliationsPanel';
import EstimateMeasurementComparisonPanel from '../../components/EstimateMeasurementComparisonPanel';
import WorkJournalEstimateReconciliationPanel from '../../components/WorkJournalEstimateReconciliationPanel';
import {
  activeEstimateFromList,
  estimateKind,
  estimatePackage,
  estimateSectionsOf,
  estimateTotal,
  estimateUpdatedTs,
  estimateWorkKeyForItem,
  isArchivedEstimate,
  isGlobalEstimateTemplate,
  normalizeEstimateItemType,
} from '../../utils/estimateUtils';
import {
  estimateMeasurementComparisonSummaryFor,
  projectMeasurementBasisTotalsFor,
} from '../../utils/estimateMeasurementComparisonUtils';
import {
  buildEstimateMeasurementComparisonDocContent,
  buildWorkJournalEstimateReconciliationDocContent,
} from '../../utils/printDocumentBuilders';
import {
  estimateItemOptionsFromActiveEstimates,
  ks2ItemsFromActiveEstimates,
  projectPlanDoneFor,
} from '../../utils/projectEstimateItemsUtils';
import { workJournalEstimateSummaryFor } from '../../utils/workJournalEstimateReconciliationUtils';
import {
  estimateChangeRowsForDocsFromList,
  estimateChangesForNewEstimateFromList,
  includableEstimateChangesForProject,
} from '../../utils/estimateChangeUtils';
import { isLeadershipUser } from '../../utils/accessUtils';

export function createProjectEstimateRuntime({
  ESTIMATE_PACKAGES,
  activeTabActions,
  approveEstimateReconciliation,
  createEstimateChangeFromComparisonRow,
  createEstimateReconciliation,
  estimateChangeForComparisonRow,
  estimateDiffBaseFor,
  estimateReconciliationsForProject,
  estimatesList,
  openEstimateReconciliationPreview,
  projects,
  rooms,
  roomDoors,
  roomWindows,
  showPreview,
  unexpectedWorksList,
  user,
  visibleEstimatesForCurrentUser,
  workJournal,
  workJournalEstimateStatusMeta,
}) {
  const activeEstimatesForProject = (p, kind = 'Заказчик', sourceEstimates = null) => {
    const groups = {};
    visibleEstimatesForCurrentUser(sourceEstimates || estimatesList || [])
      .filter(e => (
        (e.projectName === p.name || Number(e.projectId) === Number(p.id))
        && estimateKind(e) === kind
        && e.status === 'Активная'
        && !isArchivedEstimate(e)
      ))
      .forEach(e => {
        const k = estimatePackage(e);
        if (!groups[k]) groups[k] = [];
        groups[k].push(e);
      });
    return Object.values(groups)
      .map(items => activeEstimateFromList(items))
      .filter(Boolean);
  };

  const renderEstimateReconciliationsPanel = (p) => {
    const recs = estimateReconciliationsForProject(p.name);
    const projectEstimates = visibleEstimatesForCurrentUser(estimatesList)
      .filter(e => e.projectName === p.name && estimateKind(e) === 'Заказчик' && !isArchivedEstimate(e) && !isGlobalEstimateTemplate(e));
    return (
      <EstimateReconciliationsPanel
        project={p}
        reconciliations={recs}
        projectEstimates={projectEstimates}
        estimateDiffBaseFor={estimateDiffBaseFor}
        estimatePackage={estimatePackage}
        estimateTotal={estimateTotal}
        estimateUpdatedTs={estimateUpdatedTs}
        canApprove={isLeadershipUser(user)}
        onApprove={approveEstimateReconciliation}
        onCreate={createEstimateReconciliation}
        onOpenPreview={openEstimateReconciliationPreview}
      />
    );
  };

  const getProjectWorkPackageOptions = (projectName = '') => {
    const project = (projects || []).find(p => p.name === projectName);
    const activePackages = project
      ? activeEstimatesForProject(project, 'Заказчик').map(estimatePackage).filter(Boolean)
      : [];
    const fallback = ESTIMATE_PACKAGES.filter(Boolean);
    return [...new Set((activePackages.length ? activePackages : fallback).filter(Boolean))];
  };

  const getProjectEstimateWorkOptions = (projectName = '', workPackage = '') => {
    const project = (projects || []).find(p => p.name === projectName);
    if (!project) return [];
    const packageFilter = String(workPackage || '').trim();
    const seen = new Set();
    const out = [];
    activeEstimatesForProject(project, 'Заказчик')
      .filter(est => !packageFilter || estimatePackage(est) === packageFilter)
      .forEach(est => {
        const pkg = estimatePackage(est);
        estimateSectionsOf(est).forEach((section, sectionIdx) => {
          const sectionName = section?.name || '';
          (section?.items || []).forEach((item, itemIdx) => {
            if (normalizeEstimateItemType(item, sectionName) !== 'work') return;
            const key = item.workKey || estimateWorkKeyForItem(item, sectionName, itemIdx);
            const value = [est.id, sectionIdx, itemIdx, key].join(':');
            if (seen.has(value)) return;
            seen.add(value);
            out.push({
              value,
              estimateId: est.id,
              estimateName: est.name,
              estimateItemKey: key,
              parentWorkKey: key,
              parentWorkName: item.workName || item.name || '',
              parentWorkSourceCode: item.workSourceCode || item.sourceCode || item.obosn || '',
              sectionName,
              workPackage: pkg,
              label: (item.workName || item.name || '').slice(0, 140),
            });
          });
        });
      });
    return out;
  };

  const projectMeasurementBasisTotals = (projectName) => projectMeasurementBasisTotalsFor(projectName, {
    rooms,
    roomWindows,
    roomDoors,
  });

  const estimateMeasurementComparisonSummary = (project) => estimateMeasurementComparisonSummaryFor(project, {
    totals: projectMeasurementBasisTotals(project?.name || ''),
    activeEstimates: project ? activeEstimatesForProject(project, 'Заказчик') : [],
  });

  const buildEstimateMeasurementComparisonContent = (project) => buildEstimateMeasurementComparisonDocContent(
    project,
    estimateMeasurementComparisonSummary(project),
    projectMeasurementBasisTotals(project?.name || ''),
    { generatedBy: user?.name || '' },
  );

  const renderEstimateMeasurementComparisonPanel = (project) => {
    return (
      <EstimateMeasurementComparisonPanel
        project={project}
        summary={estimateMeasurementComparisonSummary(project)}
        totals={projectMeasurementBasisTotals(project?.name || '')}
        estimateChangeForComparisonRow={estimateChangeForComparisonRow}
        onCreateEstimateChange={createEstimateChangeFromComparisonRow}
        onOpenChangesTab={() => activeTabActions.openEstimateChanges()}
        onPrint={() => showPreview(buildEstimateMeasurementComparisonContent(project), 'Смета ↔ обмеры — ' + project.name)}
      />
    );
  };

  const projectPlanDone = (p) => projectPlanDoneFor(activeEstimatesForProject(p, 'Заказчик'));

  const workJournalEstimateSummary = (project) => workJournalEstimateSummaryFor(project, {
    activeEstimates: project ? activeEstimatesForProject(project, 'Заказчик') : [],
    workJournal,
    planDone: projectPlanDone(project || {}),
  });

  const buildWorkJournalEstimateReconciliationContent = (project) => buildWorkJournalEstimateReconciliationDocContent(
    project,
    workJournalEstimateSummary(project),
    { generatedBy: user?.name || '', statusMeta: workJournalEstimateStatusMeta },
  );

  const renderWorkJournalEstimateReconciliationPanel = (project) => {
    return (
      <WorkJournalEstimateReconciliationPanel
        project={project}
        summary={workJournalEstimateSummary(project)}
        onPrint={() => showPreview(buildWorkJournalEstimateReconciliationContent(project), 'Сверка ЖПР ↔ смета — ' + project.name)}
      />
    );
  };

  const ks2ItemsFromEstimate = (p) => ks2ItemsFromActiveEstimates({
    project: p,
    activeEstimates: activeEstimatesForProject(p, 'Заказчик'),
    workJournal,
  });

  const estimateItemOptionsForProject = (p) => estimateItemOptionsFromActiveEstimates(activeEstimatesForProject(p, 'Заказчик'));
  const includableEstimateChanges = (projectName) => includableEstimateChangesForProject(projectName, unexpectedWorksList);
  const estimateChangesForNewEstimate = (project, est) => estimateChangesForNewEstimateFromList({
    project,
    estimate: est,
    unexpectedWorksList,
    activeCustomerEstimates: project ? activeEstimatesForProject(project, 'Заказчик') : [],
  });
  const estimateChangeRowsForDocs = (projectName, kind) => estimateChangeRowsForDocsFromList(projectName, kind, unexpectedWorksList);

  return {
    activeEstimatesForProject,
    buildEstimateMeasurementComparisonContent,
    buildWorkJournalEstimateReconciliationContent,
    estimateChangeRowsForDocs,
    estimateChangesForNewEstimate,
    estimateItemOptionsForProject,
    estimateMeasurementComparisonSummary,
    getProjectEstimateWorkOptions,
    getProjectWorkPackageOptions,
    includableEstimateChanges,
    ks2ItemsFromEstimate,
    projectMeasurementBasisTotals,
    projectPlanDone,
    renderEstimateMeasurementComparisonPanel,
    renderEstimateReconciliationsPanel,
    renderWorkJournalEstimateReconciliationPanel,
    workJournalEstimateSummary,
  };
}
