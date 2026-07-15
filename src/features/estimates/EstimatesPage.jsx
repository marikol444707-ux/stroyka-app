import React from 'react';
import { canManageEstimateForContext, estimateRoleForContext } from './estimateAccess';

export default function EstimatesPage({ ctx }) {
  const {
    acceptMaterialNormSuggestion, acceptMaterialNormSuggestionAsOverride, activeEstimateFromList, activeMaterialNormSuggestions, addEstimateMaterialFromCoverage, allBrigadeItems, API, applyEstimateActivationState,
    autoReconcileEstimateChanges, badge, brigadeContracts, btnB, btnG, btnGr, btnO, btnR,
    btnState, buildEstimateDiffContent, buildEstimateWorkSummary, buildMaterialNormCoverageContent, C, canCreateSupplyRequestFromNorm, canEditMaterialNorms, card,
    createBatchSupplyRequestFromNormCoverage, createEstimateFromNormSuggestions, createEstimateReconciliation, createMaterialNormCoverageTask, createSupplyRequestFromNormCoverage, createTaskFromMaterialNormSuggestion, deleteEstimateRemote, disableMaterialNorm,
    editingMaterialNormId, editMaterialNorm, enrichEstimateMeasurementBasis, ESTIMATE_PACKAGES, EstimateAddSectionForm, EstimateCreateActions, EstimateCreateFormFields, estimateDiffBaseFor,
    estimateDisplayVersion, EstimateDuplicateWorkSummaryPanel, estimateGroupKey, EstimateImportValidationBanner, EstimateImportView, estimateIssueDomId, estimateIssueFocusKey,
    estimateItemTotal, estimateKind, estimateNormCoverageRows, estimatePackage, estimateProjectFilter, estimateQualityRows, estimateSearch, EstimateSearchResults,
    EstimateSectionsEditor, EstimateSelectedToolbar, estimatesList, EstimatesListToolbar, EstimatesListView, estimatesPage, estimatesTab, EstimatesTabsNav,
    estimateStatusView, estimateTotal, EstimateTotalCard, estimateTypeIcon, estimateUpdatedTs, estimateVersionChain, exportToExcel,
    fmtMeasure, generateMaterialNormSuggestions, handleDetectEstimateHiddenWorks, handleEstimateAiAnalysis, handleEstimateImportFile, handleExportSelectedEstimate, handleNormalizeSelectedEstimateImport,
    handleOpenEstimateDistribute, handleOpenSelectedEstimateHistory, handleOpenWorkAssignment, handlePreviewSelectedEstimate, handleShowSelectedEstimateDiff, handleToggleSelectedEstimateTemplate, importValidating,
    importValidationWarnings, inp, isArchivedEstimate, isGlobalEstimateTemplate, isMobile, jumpToEstimateIssue,
    loadAll, loadMaterialNormsPage, markEstimateWorkNoMaterialFromCoverage, materialNormCanCreateSupply, materialNormCoverageComment, materialNormCoverageDisplayRows, materialNormCoverageExportRows, materialNormCoverageMeta,
    materialNormCoverageProject, MaterialNormCoverageSection, MaterialNormFormPanel, materialNormNotice, MaterialNormNotice, materialNormOverrides, MaterialNormOverridesPanel, materialNormPreviewSuggestions,
    materialNormRuleForCalc, materialNorms, materialNormSearch, MaterialNormsHeader, MaterialNormsListPanel, materialNormsPage, materialNormSuggestionLoading, MaterialNormSuggestionsPanel,
    materialNormSupplyRequestExists, materialTitleForNormRule, mobileExpandedRenderLists, newEstimate, newEstimateItem, newEstimateSection, newMaterialNorm, nextEstimateVersionFor,
    openEstimateDetail, persistEstimate, projects, queueEstimateDiffReviewTask, queueEstimateNormReviewTask, queueEstimateQualityReviewTask, readApiResult, refreshData,
    rejectMaterialNormSuggestion, resetMaterialNormForm, sameEstimateGroup, saveMaterialNorm, saveMaterialNormOverrideFromCoverage, selectedEstimate, setActivePage,
    setEstimateProjectFilter, setEstimateSearch, setEstimatesList, setEstimatesTab, setEstimateStatusRemote, setGenerateForm, setImportValidationWarnings,
    setMaterialNormCoverageProject, setMaterialNormNotice, setMaterialNormPreviewSuggestions, setMaterialNormSearch, setMobileExpandedRenderLists, setNewEstimate, setNewEstimateItem, setNewEstimateSection,
    setNewMaterialNorm, setSelectedEstimate, setShowArchivedEstimates, setShowEstimateIssuesOnly, setShowEstimateWorkSummary, setShowForm, setShowGenerateEstimate, showArchivedEstimates,
    companyContext, showEstimateIssuesOnly, showEstimateWorkSummary, showForm, showPreview, user, visibleActiveProjects, visibleEstimatesForCurrentUser, WORK_MATERIAL_NORM_RULES,
    WorkAssignmentStatusPanel,
  } = ctx;
  const effectiveUserRole = estimateRoleForContext(user, companyContext);
  const isLeadershipUser = canManageEstimateForContext(user, companyContext);

  return (
<div>
            <EstimatesTabsNav
              estimatesTab={estimatesTab}
              setEstimatesTab={setEstimatesTab}
              setActivePage={setActivePage}
              btnO={btnO}
              btnG={btnG}
            />

            {estimatesTab==='list'&&(<div>
              {(()=>{const visibleEstimateList=visibleEstimatesForCurrentUser(estimatesList);const estimateProjectOptions=Array.from(new Set((visibleEstimateList||[]).filter(e=>!isGlobalEstimateTemplate(e)).map(e=>e.projectName||e.project||'Без объекта').filter(Boolean))).sort((a,b)=>a.localeCompare(b,'ru'));const filteredEstimateList=estimateProjectFilter?visibleEstimateList.filter(e=>(e.projectName||e.project||'Без объекта')===estimateProjectFilter):visibleEstimateList;return(<>
              <EstimatesListToolbar
                C={C}
                btnB={btnB}
                btnO={btnO}
                inp={inp}
                showForm={showForm}
                setShowForm={setShowForm}
                setGenerateForm={setGenerateForm}
                setShowGenerateEstimate={setShowGenerateEstimate}
                estimateSearch={estimateSearch}
                setEstimateSearch={setEstimateSearch}
                projectOptions={estimateProjectOptions}
                projectFilter={estimateProjectFilter}
                setProjectFilter={setEstimateProjectFilter}
                showLeadership={isLeadershipUser}
              />
              <EstimateSearchResults
                C={C}
                card={card}
                btnG={btnG}
                estimateSearch={estimateSearch}
                estimatesList={filteredEstimateList}
                setEstimateSearch={setEstimateSearch}
                setSelectedEstimate={openEstimateDetail}
                fmtMeasure={fmtMeasure}
                estimateItemTotal={estimateItemTotal}
              />
              {showForm&&(<div style={{...card,padding:'20px',marginBottom:'16px'}}>
                <EstimateCreateFormFields
                  inp={inp}
                  projects={projects}
                  newEstimate={newEstimate}
                  setNewEstimate={setNewEstimate}
                  nextEstimateVersionFor={nextEstimateVersionFor}
                  estimatePackages={ESTIMATE_PACKAGES}
                  templates={estimatesList.filter(isGlobalEstimateTemplate)}
                />
                <EstimateCreateActions btnO={btnO} btnG={btnG} onCreate={async()=>{
                  if(!newEstimate.name) return;
                  let sections=[];
                  if(newEstimate.templateId){
                    const tmpl=estimatesList.find(e=>String(e.id)===String(newEstimate.templateId));
                    if(tmpl) sections=enrichEstimateMeasurementBasis((tmpl.sections||[]).map(s=>({...s,id:Date.now()+Math.random(),items:(s.items||[]).map(i=>({...i,id:Date.now()+Math.random()}))})));
                  }
                  const estimateStatus=isLeadershipUser?(newEstimate.status||'Активная'):'Черновик';
                  const estimatePayload={...newEstimate,status:estimateStatus,sections};
                  const est=await readApiResult(await fetch(API+'/estimates',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(estimatePayload)}));
                  const newEst={...newEstimate,id:est.id,sections,smetaType:newEstimate.smetaType||'Заказчик',workPackage:newEstimate.workPackage||'Основная',status:estimateStatus};
                  const diffBase=activeEstimateFromList((estimatesList||[]).filter(e=>newEst.status==='Активная'&&!isGlobalEstimateTemplate(e)&&sameEstimateGroup(e,newEst)&&e.status==='Активная'));
	                  const nextEstimates=applyEstimateActivationState([...(estimatesList||[]),newEst], newEst);
                  setEstimatesList(nextEstimates);
                  setSelectedEstimate(newEst);
                  setShowForm(false);
                  setNewEstimate({projectId:'',projectName:'',name:'',version:'1.0',smetaType:'Заказчик',workPackage:'Основная',status:'Активная',templateId:''});
                  if(diffBase) {
                    await queueEstimateDiffReviewTask(diffBase,newEst,'Смета создана');
                    await autoReconcileEstimateChanges(diffBase,newEst,'Смета создана');
                    await createEstimateReconciliation(diffBase,newEst,{silent:true});
                  }
                  await queueEstimateQualityReviewTask(newEst, 'Смета создана');
                  await queueEstimateNormReviewTask(newEst, 'Смета создана', nextEstimates);
                }} onCancel={()=>setShowForm(false)} />
              </div>)}
              {selectedEstimate?(<div>
                <EstimateImportValidationBanner
                  C={C}
                  card={card}
                  importValidating={importValidating}
                  importValidationWarnings={importValidationWarnings}
                  setImportValidationWarnings={setImportValidationWarnings}
                  estimateIssues={estimateQualityRows(selectedEstimate)}
                  onJumpToIssue={jumpToEstimateIssue}
                />
                <EstimateSelectedToolbar
                  C={C}
                  badge={badge}
                  btnB={btnB}
                  btnG={btnG}
                  btnGr={btnGr}
                  btnO={btnO}
                  estimateKind={estimateKind}
                  estimatePackage={estimatePackage}
                  estimateStatusView={estimateStatusView}
                  estimateTypeIcon={estimateTypeIcon}
                  estimatesList={estimatesList}
                  hasDiff={Boolean(estimateDiffBaseFor(selectedEstimate))}
                  issueCount={estimateQualityRows(selectedEstimate).length}
                  onAiAnalysis={handleEstimateAiAnalysis}
                  onBack={()=>setSelectedEstimate(null)}
                  onDetectHiddenWorks={handleDetectEstimateHiddenWorks}
                  onExport={handleExportSelectedEstimate}
                  onHistory={handleOpenSelectedEstimateHistory}
                  onNormalize={handleNormalizeSelectedEstimateImport}
                  onOpenDistribute={handleOpenEstimateDistribute}
                  onOpenWorkAssignment={handleOpenWorkAssignment}
                  onCreateReconciliation={()=>{const base=estimateDiffBaseFor(selectedEstimate);if(base)createEstimateReconciliation(base,selectedEstimate);}}
                  onPreview={handlePreviewSelectedEstimate}
                  onShowDiff={handleShowSelectedEstimateDiff}
                  onToggleIssuesOnly={()=>estimateQualityRows(selectedEstimate).length&&setShowEstimateIssuesOnly(v=>!v)}
                  onToggleTemplate={handleToggleSelectedEstimateTemplate}
                  sameEstimateGroup={sameEstimateGroup}
                  selectedEstimate={selectedEstimate}
                  setEstimateStatusRemote={setEstimateStatusRemote}
                  showLeadership={isLeadershipUser}
	                  showEstimateIssuesOnly={showEstimateIssuesOnly}
	                />
                <WorkAssignmentStatusPanel
                  selectedEstimate={selectedEstimate}
                  brigadeContracts={brigadeContracts}
                  brigadeContractItems={allBrigadeItems}
                  API={API}
                  loadAll={loadAll}
                  C={C}
                  card={card}
                  btnG={btnG}
                  btnR={btnR}
                  isMobile={isMobile}
                  showLeadership={isLeadershipUser}
                />
                <EstimateDuplicateWorkSummaryPanel
                  selectedEstimate={selectedEstimate}
                  userRole={effectiveUserRole}
                  isMobile={isMobile}
                  showEstimateWorkSummary={showEstimateWorkSummary}
                  setShowEstimateWorkSummary={setShowEstimateWorkSummary}
                  setShowEstimateIssuesOnly={setShowEstimateIssuesOnly}
                  setMobileExpandedRenderLists={setMobileExpandedRenderLists}
                  buildEstimateWorkSummary={buildEstimateWorkSummary}
                  estimateIssueDomId={estimateIssueDomId}
                />
	                <EstimateAddSectionForm
	                  card={card}
	                  inp={inp}
                  btnO={btnO}
                  newEstimateSection={newEstimateSection}
                  setNewEstimateSection={setNewEstimateSection}
                  onAdd={()=>{if(!newEstimateSection.name) return;const section={id:Date.now(),name:newEstimateSection.name,items:[]};const updated={...selectedEstimate,sections:[...(selectedEstimate.sections||[]),section]};setSelectedEstimate(updated);setEstimatesList(prev=>prev.map(e=>e.id===updated.id?updated:e));setNewEstimateSection({name:''});}}
                />
                <EstimateSectionsEditor
                  selectedEstimate={selectedEstimate}
                  showEstimateIssuesOnly={showEstimateIssuesOnly}
                  mobileExpandedRenderLists={mobileExpandedRenderLists}
                  setMobileExpandedRenderLists={setMobileExpandedRenderLists}
                  isMobile={isMobile}
                  estimateQualityRows={estimateQualityRows}
                  brigadeContracts={brigadeContracts}
                  userRole={effectiveUserRole}
                  setSelectedEstimate={setSelectedEstimate}
                  setEstimatesList={setEstimatesList}
                  persistEstimate={persistEstimate}
                  newEstimateItem={newEstimateItem}
                  setNewEstimateItem={setNewEstimateItem}
                  estimateIssueFocusKey={estimateIssueFocusKey}
                />
                <EstimateTotalCard C={C} card={card} total={(selectedEstimate.sections||[]).flatMap(s=>s.items||[]).reduce((sum,i)=>sum+estimateItemTotal(i),0)} />
              </div>):(<div>
                <EstimatesListView
                  C={C}
                  card={card}
                  badge={badge}
                  btnB={btnB}
                  btnG={btnG}
                  btnGr={btnGr}
                  btnO={btnO}
                  btnR={btnR}
                  estimatesList={filteredEstimateList}
                  estimatesPage={estimatesPage}
                  onRetryEstimates={() => refreshData('estimates')}
                  projectFilter={estimateProjectFilter}
                  showArchivedEstimates={showArchivedEstimates}
                  setShowArchivedEstimates={setShowArchivedEstimates}
                  setSelectedEstimate={openEstimateDetail}
                  isGlobalEstimateTemplate={isGlobalEstimateTemplate}
                  isArchivedEstimate={isArchivedEstimate}
                  estimateGroupKey={estimateGroupKey}
                  activeEstimateFromList={activeEstimateFromList}
                  estimateUpdatedTs={estimateUpdatedTs}
                  estimateTypeIcon={estimateTypeIcon}
                  estimateKind={estimateKind}
                  estimatePackage={estimatePackage}
                  estimateTotal={estimateTotal}
                  estimateStatusView={estimateStatusView}
                  estimateDisplayVersion={estimateDisplayVersion}
                  estimateVersionChain={estimateVersionChain}
                  setEstimateStatusRemote={setEstimateStatusRemote}
                  deleteEstimateRemote={deleteEstimateRemote}
                  showPreview={showPreview}
                  buildEstimateDiffContent={buildEstimateDiffContent}
                  onCreateReconciliation={createEstimateReconciliation}
                  isLeadership={isLeadershipUser}
                  canHardDeleteEstimate={effectiveUserRole === 'директор'}
                />
              </div>)}
              </>);})()}
            </div>)}

            {estimatesTab==='import'&&(
              <EstimateImportView
                C={C}
                card={card}
                inp={inp}
                projects={projects}
                newEstimate={newEstimate}
                setNewEstimate={setNewEstimate}
                nextEstimateVersionFor={nextEstimateVersionFor}
                estimatePackages={ESTIMATE_PACKAGES}
                onFileChange={handleEstimateImportFile}
              />
            )}

            {estimatesTab==='norms'&&(<div>
              <MaterialNormsHeader
                C={C}
                badge={badge}
                btnG={btnG}
                btnO={btnO}
                btnState={btnState}
                materialNorms={materialNorms}
                materialNormOverrides={materialNormOverrides}
                materialNormPreviewSuggestions={materialNormPreviewSuggestions}
                setMaterialNormPreviewSuggestions={setMaterialNormPreviewSuggestions}
                materialNormSuggestionLoading={materialNormSuggestionLoading}
                canEditMaterialNorms={canEditMaterialNorms}
                generateMaterialNormSuggestions={generateMaterialNormSuggestions}
                activeSuggestionCount={activeMaterialNormSuggestions().length}
                fallbackNormsCount={WORK_MATERIAL_NORM_RULES.length}
              />
              <MaterialNormNotice
                C={C}
                card={card}
                btnG={btnG}
                materialNormNotice={materialNormNotice}
                setMaterialNormNotice={setMaterialNormNotice}
              />
              <MaterialNormCoverageSection
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
                  projects={projects}
                  materialNormCoverageProject={materialNormCoverageProject}
	                setMaterialNormCoverageProject={setMaterialNormCoverageProject}
                  visibleActiveProjects={visibleActiveProjects}
                  estimateNormCoverageRows={estimateNormCoverageRows}
                  materialNormCoverageDisplayRows={materialNormCoverageDisplayRows}
                  mobileExpandedRenderLists={mobileExpandedRenderLists}
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
              <MaterialNormSuggestionsPanel
                C={C}
                badge={badge}
                btnB={btnB}
                btnG={btnG}
                btnGr={btnGr}
                btnO={btnO}
                btnR={btnR}
                btnState={btnState}
                card={card}
                inp={inp}
                isMobile={isMobile}
                suggestions={activeMaterialNormSuggestions()}
                materialNormSuggestionLoading={materialNormSuggestionLoading}
                generateMaterialNormSuggestions={generateMaterialNormSuggestions}
                canEditMaterialNorms={canEditMaterialNorms}
                createEstimateFromNormSuggestions={createEstimateFromNormSuggestions}
                acceptMaterialNormSuggestion={acceptMaterialNormSuggestion}
                acceptMaterialNormSuggestionAsOverride={acceptMaterialNormSuggestionAsOverride}
                createTaskFromMaterialNormSuggestion={createTaskFromMaterialNormSuggestion}
                rejectMaterialNormSuggestion={rejectMaterialNormSuggestion}
              />
              <MaterialNormOverridesPanel
                selectedProject={materialNormCoverageProject||visibleActiveProjects(projects||[])[0]?.name||''}
                materialNormOverrides={materialNormOverrides}
                isMobile={isMobile}
              />
              {canEditMaterialNorms()&&(
                <MaterialNormFormPanel
                  editingMaterialNormId={editingMaterialNormId}
                  newMaterialNorm={newMaterialNorm}
                  setNewMaterialNorm={setNewMaterialNorm}
                  saveMaterialNorm={saveMaterialNorm}
                  resetMaterialNormForm={resetMaterialNormForm}
                  isMobile={isMobile}
                />
              )}
              <MaterialNormsListPanel
                materialNormSearch={materialNormSearch}
                setMaterialNormSearch={setMaterialNormSearch}
                materialNorms={materialNorms}
                materialNormsPage={materialNormsPage}
                loadMaterialNormsPage={loadMaterialNormsPage}
                materialNormRuleForCalc={materialNormRuleForCalc}
                materialTitleForNormRule={materialTitleForNormRule}
                canEditMaterialNorms={canEditMaterialNorms}
                editMaterialNorm={editMaterialNorm}
                disableMaterialNorm={disableMaterialNorm}
                isMobile={isMobile}
              />
            </div>)}
          </div>
  );
}
