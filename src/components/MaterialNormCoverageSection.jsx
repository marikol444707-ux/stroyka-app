import React from 'react';
import MaterialNormCoveragePanel from './MaterialNormCoveragePanel';

export default function MaterialNormCoverageSection({
  C,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnState,
  card,
  inp,
  isMobile,
  projects,
  materialNormCoverageProject,
  setMaterialNormCoverageProject,
  visibleActiveProjects,
  estimateNormCoverageRows,
  materialNormCoverageDisplayRows,
  mobileExpandedRenderLists,
  setMobileExpandedRenderLists,
  canEditMaterialNorms,
  canCreateSupplyRequestFromNorm,
  materialNormCanCreateSupply,
  materialNormSupplyRequestExists,
  materialNormCoverageMeta,
  materialNormCoverageComment,
  fmtMeasure,
  buildMaterialNormCoverageContent,
  showPreview,
  exportToExcel,
  materialNormCoverageExportRows,
  createBatchSupplyRequestFromNormCoverage,
  createSupplyRequestFromNormCoverage,
  addEstimateMaterialFromCoverage,
  markEstimateWorkNoMaterialFromCoverage,
  createMaterialNormCoverageTask,
  saveMaterialNormOverrideFromCoverage,
}) {
  const projectOptions = visibleActiveProjects(projects || []);
  const selectedProject = materialNormCoverageProject || projectOptions[0]?.name || '';
  const rows = selectedProject ? estimateNormCoverageRows(selectedProject) : [];
  const displayRows = materialNormCoverageDisplayRows(rows);
  const coverageKey = ['material-norm-coverage', selectedProject].join(':');
  const coverageLimit = isMobile ? 80 : 160;
  const visibleCoverageRows = mobileExpandedRenderLists[coverageKey] ? displayRows : displayRows.slice(0, coverageLimit);
  const hiddenCoverageRows = displayRows.length - visibleCoverageRows.length;

  return (
    <MaterialNormCoveragePanel
      C={C}
      badge={badge}
      btnB={btnB}
      btnG={btnG}
      btnGr={btnGr}
      btnO={btnO}
      btnState={btnState}
      card={card}
      inp={inp}
      isMobile={isMobile}
      projectOptions={projectOptions}
      selectedProject={selectedProject}
      setMaterialNormCoverageProject={setMaterialNormCoverageProject}
      rows={rows}
      displayRows={displayRows}
      visibleCoverageRows={visibleCoverageRows}
      hiddenCoverageRows={hiddenCoverageRows}
      coverageKey={coverageKey}
      setMobileExpandedRenderLists={setMobileExpandedRenderLists}
      canEditMaterialNorms={canEditMaterialNorms}
      canCreateSupplyRequestFromNorm={canCreateSupplyRequestFromNorm}
      materialNormCanCreateSupply={materialNormCanCreateSupply}
      materialNormSupplyRequestExists={materialNormSupplyRequestExists}
      materialNormCoverageMeta={materialNormCoverageMeta}
      materialNormCoverageComment={materialNormCoverageComment}
      fmtMeasure={fmtMeasure}
      buildMaterialNormCoverageContent={buildMaterialNormCoverageContent}
      showPreview={showPreview}
      exportToExcel={exportToExcel}
      materialNormCoverageExportRows={materialNormCoverageExportRows}
      createBatchSupplyRequestFromNormCoverage={createBatchSupplyRequestFromNormCoverage}
      createSupplyRequestFromNormCoverage={createSupplyRequestFromNormCoverage}
      addEstimateMaterialFromCoverage={addEstimateMaterialFromCoverage}
      markEstimateWorkNoMaterialFromCoverage={markEstimateWorkNoMaterialFromCoverage}
      createMaterialNormCoverageTask={createMaterialNormCoverageTask}
      saveMaterialNormOverrideFromCoverage={saveMaterialNormOverrideFromCoverage}
    />
  );
}
