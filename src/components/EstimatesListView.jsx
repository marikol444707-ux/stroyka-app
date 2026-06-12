import React from 'react';
import EstimateListEmptyStates from './EstimateListEmptyStates';
import EstimateListSummaryBar from './EstimateListSummaryBar';
import EstimateProjectGroupCard from './EstimateProjectGroupCard';
import EstimateTemplatesList from './EstimateTemplatesList';

export default function EstimatesListView({
  C,
  card,
  badge,
  btnB,
  btnG,
  btnGr,
  btnR,
  estimatesList,
  showArchivedEstimates,
  setShowArchivedEstimates,
  setSelectedEstimate,
  isGlobalEstimateTemplate,
  isArchivedEstimate,
  estimateGroupKey,
  activeEstimateFromList,
  estimateUpdatedTs,
  estimateTypeIcon,
  estimateKind,
  estimatePackage,
  estimateTotal,
  estimateStatusView,
  estimateDisplayVersion,
  estimateVersionChain,
  setEstimateStatusRemote,
  deleteEstimateRemote,
  showPreview,
  buildEstimateDiffContent,
  isLeadership,
}) {
  const normal = (estimatesList || []).filter(e => !isGlobalEstimateTemplate(e) || e.status === 'Активная');
  const templates = (estimatesList || []).filter(e => isGlobalEstimateTemplate(e) && e.status !== 'Активная');
  const groups = {};

  normal.forEach(e => {
    if (!showArchivedEstimates && isArchivedEstimate(e)) return;
    const key = estimateGroupKey(e);
    if (!groups[key]) groups[key] = [];
    groups[key].push(e);
  });

  const grouped = Object.entries(groups).sort((a, b) => {
    const aa = activeEstimateFromList(a[1]);
    const bb = activeEstimateFromList(b[1]);
    return (estimateUpdatedTs(bb) || Number(bb?.id || 0)) - (estimateUpdatedTs(aa) || Number(aa?.id || 0));
  });

  const projectGroups = {};
  grouped.forEach(([key, items]) => {
    const active = activeEstimateFromList(items);
    const projectName = active?.projectName || items[0]?.projectName || 'Без объекта';
    if (!projectGroups[projectName]) projectGroups[projectName] = [];
    projectGroups[projectName].push([key, items]);
  });

  const groupedByProject = Object.entries(projectGroups).sort((a, b) => {
    const aa = a[1].map(([, items]) => activeEstimateFromList(items)).filter(Boolean);
    const bb = b[1].map(([, items]) => activeEstimateFromList(items)).filter(Boolean);
    const at = Math.max(0, ...aa.map(e => estimateUpdatedTs(e) || Number(e.id || 0)));
    const bt = Math.max(0, ...bb.map(e => estimateUpdatedTs(e) || Number(e.id || 0)));
    return bt - at || a[0].localeCompare(b[0], 'ru');
  });

  return (
    <>
      <EstimateListSummaryBar
        C={C}
        card={card}
        badge={badge}
        btnG={btnG}
        activeCount={normal.filter(e => e.status === 'Активная').length}
        draftCount={normal.filter(e => (e.status || 'Черновик') === 'Черновик').length}
        archivedCount={normal.filter(isArchivedEstimate).length}
        templatesCount={templates.length}
        showArchivedEstimates={showArchivedEstimates}
        setShowArchivedEstimates={setShowArchivedEstimates}
      />
      {groupedByProject.map(([projectName, projectEstimateGroups]) => (
        <EstimateProjectGroupCard
          key={projectName}
          C={C}
          card={card}
          badge={badge}
          btnB={btnB}
          btnG={btnG}
          btnGr={btnGr}
          btnR={btnR}
          projectName={projectName}
          groups={projectEstimateGroups}
          setSelectedEstimate={setSelectedEstimate}
          estimateTypeIcon={estimateTypeIcon}
          estimateKind={estimateKind}
          estimatePackage={estimatePackage}
          estimateUpdatedTs={estimateUpdatedTs}
          activeEstimateFromList={activeEstimateFromList}
          estimateTotal={estimateTotal}
          estimateStatusView={estimateStatusView}
          estimateDisplayVersion={estimateDisplayVersion}
          estimateVersionChain={estimateVersionChain}
          isArchivedEstimate={isArchivedEstimate}
          setEstimateStatusRemote={setEstimateStatusRemote}
          deleteEstimateRemote={deleteEstimateRemote}
          showPreview={showPreview}
          buildEstimateDiffContent={buildEstimateDiffContent}
          isLeadership={isLeadership}
        />
      ))}
      <EstimateTemplatesList
        C={C}
        card={card}
        templates={templates}
        setSelectedEstimate={setSelectedEstimate}
        estimateKind={estimateKind}
        estimateTotal={estimateTotal}
      />
      <EstimateListEmptyStates
        C={C}
        card={card}
        normalCount={normal.length}
        templatesCount={templates.length}
        groupedCount={groupedByProject.length}
      />
    </>
  );
}
