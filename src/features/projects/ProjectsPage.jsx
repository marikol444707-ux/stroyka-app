import React from 'react';
import {
  createInspectionOrderForm,
  createWarrantyDefectForm,
} from '../project-operations/projectOperationInitialForms';
import ProjectAiControlTab from './ProjectAiControlTab';
import ProjectChecklistsTab from './ProjectChecklistsTab';
import ProjectChatTab from './ProjectChatTab';
import ProjectFinanceTab from './ProjectFinanceTab';
import ProjectJournalsHubTab from './ProjectJournalsHubTab';
import ProjectInspectionOrdersTab from './ProjectInspectionOrdersTab';
import ProjectMaterialInspectionTab from './ProjectMaterialInspectionTab';
import ProjectCableJournalTab from './ProjectCableJournalTab';
import ProjectMeasurementSourcesTab from './ProjectMeasurementSourcesTab';
import ProjectOverviewTab from './ProjectOverviewTab';
import ProjectPrintDocumentCard from './ProjectPrintDocumentCard';
import ProjectRoomsTab from './ProjectRoomsTab';
import ProjectScheduleTab from './ProjectScheduleTab';
import ProjectStagesTab from './ProjectStagesTab';
import ProjectSupervisorActsTab from './ProjectSupervisorActsTab';
import ProjectWeatherTab from './ProjectWeatherTab';
import ProjectWarrantyTab from './ProjectWarrantyTab';
import { createProjectForm } from './projectInitialForms';
import { createMaterialTransferForm } from '../warehouse/warehouseInitialForms';

export default function ProjectsPage({ ctx }) {
  const {
    API, Archive, Bot, C, CHECKLIST_TEMPLATES, Calculator, Check, ChevronDown,
    ChevronUp, DIRECTOR_MAP_FEATURE_ENABLED, EMPTY_ESTIMATE_CHANGE, ESTIMATE_CHANGE_TYPES, ESTIMATE_CHANGE_VISIBLE_STATUSES, ESTIMATE_PACKAGES,
    EXPENSE_CATEGORIES, Eye, FileText, FolderKanban, GitBranch, MapPin,
    Package, Plus, ProjectBrigadeCalculationTab, ProjectCardHeader, ProjectDirectorMapPanel,
    ProjectDocumentsRegistryPanel, ProjectFinancePanel, ProjectHiddenWorksActsPanel, ProjectLaunchPanel, ProjectLettersPanel, ProjectMaterialsControlPanel, ProjectMaterialsStockPanel,
    ProjectMaterialsTransferPanel, ProjectPrescriptionsPanel, ProjectSafetyJournalPanel, ProjectScheduleSummaryPanel, ProjectTabsNav, ProjectWorkJournalPanel,
    STAGE_STATUSES, Search, TB_INSTRUCTIONS, TB_TYPES_GOST, Trash2, UNITS,
    Upload, X, _normalizeUnit, acceptMaterialAliasTask, accountablePayments, activeEstimatesForProject,
    activeProjectTab, activeTabGroup, aiFindingsForProject, aiSeverityMeta, aiTasksForProject, appendPhotos, approveUnexpectedWork,
    badge, brigadeCoef, brigadeContractItems, brigadeContracts, brigadePayments, btnB, btnG, btnGr,
    btnO, btnR, buildCableJournalContent, buildHiddenActContent, buildJPRContent, buildKS3Content, buildM15Content, buildMaterialInspectionContent,
    buildMaterialRequirementContent, buildPassportContent, buildSupplementaryAgreementContent, buildTBContent, cableJournal, cableTypeOf,
    card, checklistItems, checklists, companyName, companyRequisites, convertUnits,
    createBatchSupplyRequestFromMaterialControl, deleteBrigadePayment, deleteStage,
    denormalizeMeasure, directorMapActionTarget, directorMapContractForProject, editProject, editingItem,
    estimateChangesForNewEstimate, estimateItemOptionsForProject, estimateKind, estimatePackage,
    estimateReconciliationsForProject, estimateSearch, estimateWorkNormRequirementRows, estimatesList, expByCategory, expandedProject, fileSrc,
    fmtMeasure, formatSignedRub, generateAiFindingsForProject, getActStatusForJournal, hiddenActs, history, includableEstimateChanges,
    includeChangesInNewEstimate, inp, inspectionOrders, isApprovedEstimateChangeStatus, isEstimatePricelist, isFinanceRole,
    isCableName, isLeadership, isMobile, isProrab, listSearch, loadAll, loadChecklistItems, loadProjectChat, loadWorkJournalPage,
    manualExpenses, masterProfiles, matchSearch, materialControlStatus, materialControlSummaryForProject, materialInspections, materialNameKey, materialNormControlSummaryForProject,
    materialReconciliationRows, materialTransfers, materials, navigateTo,
    newBrigadeContract, newBrigadeItem, newChecklist, newChecklistItem, newInspOrder, newLetter,
    newParticipant, newPrescription, newProject, newProjectDoc, newStage, newTbEntry,
    newTransfer, newUnexpected, newWarrantyDefect, normalizeMeasure, openAiTaskAction, openBrigadeContract, openConfirmModal,
    openEstimateDetail, ownExpenses, parseAiTaskPayload, prescriptionsList, pricelists, projectAiSummaries, projectBudgetSpent, projectChatMessage,
    projectChatMessages, projectDocuments, projectEconomy, projectLetters, projectPaymentInAmount, projectPaymentSignedAmount,
    projectPayments, projectPlanDone, projectRealProgress, projectStages, projects, refreshData, renderEstimateChangeReconcileTask,
    renderEstimateReconciliationsPanel, renderMaterialAliasControls, renderMaterialSupplyAction, renderWorkJournalEstimateReconciliationPanel, roleColor,
    saveChecklist, savePrescription, saveProject, saveProjectStage,
    saveTbEntry, saveUnexpectedWork, selectedBrigadeContract, selectedChecklist, sendProjectChatMessage, setActiveProjectTab, setActiveTabGroup,
    setAddExpenseProject, setBrigadeCoef, setBrigadeContractItems, setBrigadeContracts, setBrigadePayments, setEditingAct,
    setEditingCable, setEditingInspection, setEditingItem, setEditingJournal, setEstimateSearch, setExpandedProject,
    setHiddenActs, setListSearch, setMaterialTransfers, setMaterials, setNewAccountable,
    setNewBrigadeContract, setNewBrigadeItem, setNewBrigadePayment, setNewChecklist, setNewChecklistItem, setNewInspOrder, setNewLetter,
    setNewManualExpense, setNewParticipant, setNewPrescription, setNewProject, setNewProjectDoc, setNewStage,
    setNewTbEntry, setNewTransfer, setNewUnexpected, setNewWarrantyDefect, setProjectAiSummaries, setProjectChatMessage,
    setRejectingEntry, setSelectedBrigadeContract, setSelectedChecklist, setShowAccountableForm, setShowArchive, setShowBalanceDetails,
    setShowBrigadeForm, setShowBrigadePayModal, setShowDocForm, setShowForm, setShowJournalTableModal, setShowLetterForm, setShowPhotoModal,
    setShowTransferForm, setUploadingDoc, setUploadingLetter, setWarehouseMain, setWarrantyEditForm,
    showArchive, showBalanceDetails, showBrigadeForm, showDocForm, showForm, showKS2, showLetterForm,
    showPreview, showTransferForm, signedEstimateChangeTotal, staff, supervisorActs, supplierInvoices, supplyRequests,
    tbJournal, tbl, tblC, tblH, toNum, toggleChecklistItem, unexpectedWorksList, updateAiFinding,
    updateAiTask, updateStage, uploadPhoto, uploadingDoc, uploadingLetter,
    user, users, visibleActiveProjects, visibleEstimatesForCurrentUser, visibleProjects, warehouseMain, warrantyDefects, warrantyEditForm,
    weatherLog, workJournal, workJournalPage,
  } = ctx;

  const journalPackage = (row = {}) => String(row.workPackage || row.work_package || '').trim() || 'Основная';
  const journalMaterialKey = (name, unit, workPackage) => [
    materialNameKey ? materialNameKey(name || '') : String(name || '').toLowerCase().trim(),
    _normalizeUnit ? _normalizeUnit(unit || '') : String(unit || '').toLowerCase().trim(),
    String(workPackage || 'Основная').trim() || 'Основная',
  ].join('|');
  const journalNamePackageKey = (name, workPackage) => [
    materialNameKey ? materialNameKey(name || '') : String(name || '').toLowerCase().trim(),
    String(workPackage || 'Основная').trim() || 'Основная',
  ].join('|');
  const projectJournalDiagnostics = (projectName) => {
    const projectStock = (materials || []).filter(m => m.project === projectName && toNum(m.quantity) > 0);
    const inspections = (materialInspections || []).filter(mi => mi.projectName === projectName);
    const inspectionKeys = new Set(inspections.map(mi => journalMaterialKey(mi.materialName, mi.unit, journalPackage(mi))));
    const stockWithoutInspection = projectStock.filter(m => !inspectionKeys.has(journalMaterialKey(m.name, m.unit, journalPackage(m))));
    const cableStock = projectStock.filter(m => isCableName ? isCableName(m.name) : false);
    const cables = (cableJournal || []).filter(c => c.projectName === projectName);
    const cableKeys = new Set(cables.map(c => journalNamePackageKey(c.cableBrand, journalPackage(c))));
    const cableWithoutJournal = cableStock.filter(m => !cableKeys.has(journalNamePackageKey(m.name, journalPackage(m))));
    const reconciliationRows = (materialReconciliationRows(projectName) || []);
    const smetaRows = reconciliationRows.filter(r => (r.supplied || 0) > 0 || (r.stock || 0) > 0 || (r.received || 0) > 0);
    const smetaInPlanRows = smetaRows.filter(r => (r.estimatePlanQty || 0) > 0);
    const smetaOverRows = smetaRows.filter(r => (r.controlPlanQty || 0) > 0 && (r.over || 0) > 0);
    const smetaOutsideRows = smetaRows.filter(r => r.isOutsideEstimate);
    const aliasNeededRows = smetaOutsideRows.filter(r => !(r.aliasIds || []).length);
    return {
      projectStock,
      inspections,
      stockWithoutInspection,
      cableStock,
      cables,
      cableWithoutJournal,
      smetaRows,
      smetaInPlanRows,
      smetaOverRows,
      smetaOutsideRows,
      aliasNeededRows,
    };
  };
  const [journalDiagnosticMode, setJournalDiagnosticMode] = React.useState('all');

  return (
<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                {isLeadership()&&<button onClick={()=>{setShowForm(showForm===true?false:true);setEditingItem(null);setNewProject(createProjectForm());}} style={btnO}><Plus size={14}/>Новый проект</button>}
                {projects.some(pr=>pr.archived)&&<button onClick={()=>setShowArchive(!showArchive)} style={btnG}><Archive size={14}/>{showArchive?'Активные':'Архив'}</button>}
              </div>
            </div>
            {showArchive&&<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{margin:0,color:C.text,fontSize:'12px'}}>📦 <b>Архив закрытых объектов.</b> Здесь хранятся завершённые объекты со всеми документами, перепиской и актами только для просмотра.</p></div>}
            {showForm===true&&isLeadership()&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
              <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать проект':'Новый проект'}</h3>
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px'}}>
                <input placeholder="Название *" value={newProject.name} onChange={e=>setNewProject({...newProject,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Заказчик (название)" value={newProject.client} onChange={e=>setNewProject({...newProject,client:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Email заказчика (для доступа в кабинет)" value={newProject.clientEmail||''} onChange={e=>setNewProject({...newProject,clientEmail:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Пароль заказчика" value={newProject.clientPassword||''} onChange={e=>setNewProject({...newProject,clientPassword:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newProject.status} onChange={e=>setNewProject({...newProject,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Планирование','В работе','Заморожен'].map(s=><option key={s}>{s}</option>)}</select>
                <input placeholder="Бюджет" type="number" step="any" inputMode="decimal" value={newProject.budget} onChange={e=>setNewProject({...newProject,budget:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Дедлайн" type="date" value={newProject.deadline} onChange={e=>setNewProject({...newProject,deadline:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newProject.pricelistId||''} onChange={e=>setNewProject({...newProject,pricelistId:e.target.value?Number(e.target.value):null})} style={{...inp,marginBottom:0}}><option value="">Прайс-лист</option>{pricelists.filter(pl=>!isEstimatePricelist(pl)||Number(pl.id)===Number(newProject.pricelistId)).map(pl=><option key={pl.id} value={pl.id}>{pl.name}</option>)}</select>
                <input placeholder="Этажей (например: 3)" type="number" step="any" inputMode="decimal" value={newProject.floors||''} onChange={e=>setNewProject({...newProject,floors:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Литеры (например: А,Б,В)" value={newProject.liters||''} onChange={e=>setNewProject({...newProject,liters:e.target.value})} style={{...inp,marginBottom:0}}/>
              </div>
              <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveProject} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
            </div>)}
            {visibleProjects((showArchive?projects.filter(pr=>pr.archived):projects.filter(pr=>!pr.archived))).map(p=>{
              const _bs=projectBudgetSpent(p);const total=_bs.total;
              const isOpen=expandedProject===p.id;
              const shouldRenderProjectOverview=isOpen&&activeProjectTab==='Общее';
              const cat=shouldRenderProjectOverview&&isFinanceRole()?expByCategory(p.name):{};
              const economy=shouldRenderProjectOverview&&isFinanceRole()?projectEconomy(p):null;
              const statusColors={'Планирование':[C.info,C.infoLight,C.infoBorder],'В работе':[C.success,C.successLight,C.successBorder],'Завершён':[C.textSec,C.bgGray,C.border],'Заморожен':[C.warning,C.warningLight,C.warningBorder]};
              return(<div key={p.id} style={{...card,marginBottom:'12px',overflow:'visible'}}>
                <ProjectCardHeader
                  C={C}
                  btnG={btnG}
                  badge={badge}
                  project={p}
                  statusColors={statusColors}
                  isOpen={isOpen}
                  total={total}
                  canSeeFinance={isFinanceRole()}
                  canManage={isLeadership()}
                  onToggle={async()=>{if(isOpen){setExpandedProject(null);}else{setExpandedProject(p.id);setActiveProjectTab('Общее');if(user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&!projectAiSummaries[p.name]){try{const r=await fetch(API+'/project-ai-summary/'+encodeURIComponent(p.name));const d=await r.json();if(d&&d.exists)setProjectAiSummaries(prev=>({...prev,[p.name]:d}));}catch(e){}}}}}
                  onEdit={()=>editProject(p)}
                />
                {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border}}>
                  <div style={{borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,padding:'18px 16px 10px'}}>
                    <ProjectTabsNav
                      C={C}
                      role={user.role}
                      activeProjectTab={activeProjectTab}
                      activeTabGroup={activeTabGroup}
                      setActiveProjectTab={setActiveProjectTab}
                      setActiveTabGroup={setActiveTabGroup}
                    />
                  </div>
                  <div style={{padding:isMobile?'12px':'20px',overflowX:'hidden'}}>
                    {activeProjectTab==='Общее'&&(
                      <ProjectOverviewTab
                        ctx={ctx}
                        project={p}
                        cat={cat}
                        economy={economy}
                        total={total}
                        budgetSpent={_bs}
                      />
                    )}

                    {activeProjectTab==='ИИ-контроль'&&(
                      <ProjectAiControlTab
                        C={C}
                        Bot={Bot}
                        Calculator={Calculator}
                        Check={Check}
                        Eye={Eye}
                        FileText={FileText}
                        GitBranch={GitBranch}
                        MapPin={MapPin}
                        Package={Package}
                        _normalizeUnit={_normalizeUnit}
                        acceptMaterialAliasTask={acceptMaterialAliasTask}
                        aiFindingsForProject={aiFindingsForProject}
                        aiSeverityMeta={aiSeverityMeta}
                        aiTasksForProject={aiTasksForProject}
                        badge={badge}
                        btnB={btnB}
                        btnG={btnG}
                        btnGr={btnGr}
                        btnO={btnO}
                        btnR={btnR}
                        card={card}
                        generateAiFindingsForProject={generateAiFindingsForProject}
                        isMobile={isMobile}
                        materialNameKey={materialNameKey}
                        materialReconciliationRows={materialReconciliationRows}
                        openAiTaskAction={openAiTaskAction}
                        parseAiTaskPayload={parseAiTaskPayload}
                        project={p}
                        renderEstimateChangeReconcileTask={renderEstimateChangeReconcileTask}
                        renderMaterialSupplyAction={renderMaterialSupplyAction}
                        toNum={toNum}
                        updateAiFinding={updateAiFinding}
                        updateAiTask={updateAiTask}
                        user={user}
                      />
                    )}

                    {activeProjectTab==='Проект / Обмеры'&&(
                      <ProjectMeasurementSourcesTab ctx={ctx} project={p} />
                    )}

                    {activeProjectTab==='Этапы'&&(
                      <ProjectStagesTab
                        C={C}
                        Check={Check}
                        Plus={Plus}
                        STAGE_STATUSES={STAGE_STATUSES}
                        Trash2={Trash2}
                        X={X}
                        badge={badge}
                        btnG={btnG}
                        btnO={btnO}
                        btnR={btnR}
                        card={card}
                        inp={inp}
                        isProrab={isProrab}
                        newStage={newStage}
                        project={p}
                        projectStages={projectStages}
                        saveProjectStage={saveProjectStage}
                        setNewStage={setNewStage}
                        setShowForm={setShowForm}
                        showForm={showForm}
                        updateStage={updateStage}
                        deleteStage={deleteStage}
                      />
                    )}

                    {activeProjectTab==='График'&&(
                      <ProjectScheduleTab
                        C={C}
                        ProjectScheduleSummaryPanel={ProjectScheduleSummaryPanel}
                        card={card}
                        isMobile={isMobile}
                        materialControlSummaryForProject={materialControlSummaryForProject}
                        project={p}
                        projectPayments={projectPayments}
                        projectPlanDone={projectPlanDone}
                        projectRealProgress={projectRealProgress}
                        projectStages={projectStages}
                        setActiveProjectTab={setActiveProjectTab}
                        supplierInvoices={supplierInvoices}
                        workJournal={workJournal}
                      />
                    )}

                    {DIRECTOR_MAP_FEATURE_ENABLED&&activeProjectTab==='Карта руководителя'&&(
                      <ProjectDirectorMapPanel
                        sandbox={false}
                        contract={directorMapContractForProject(p)}
                        onOpenStages={()=>setActiveProjectTab('Этапы')}
                        onAction={({ item, action }) => {
                          const targetTab = directorMapActionTarget({ item, action });
                          if (targetTab) setActiveProjectTab(targetTab);
                        }}
                      />
                    )}

                    {activeProjectTab==='Запуск объекта'&&(
                      <ProjectLaunchPanel
                        API={API}
                        C={C}
                        card={card}
                        btnB={btnB}
                        btnG={btnG}
                        btnO={btnO}
                        btnR={btnR}
                        project={p}
                        projectDocuments={(projectDocuments||[]).filter(doc=>(doc.projectName||doc.project_name)===p.name||Number(doc.projectId||doc.project_id)===Number(p.id))}
                        estimates={visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id))}
                        isMobile={isMobile}
                        onOpenDocuments={()=>setActiveProjectTab('📁 Реестр')}
                        onOpenEstimate={()=>setActiveProjectTab('Смета')}
                      />
                    )}

	                    {activeProjectTab==='Смета'&&(<div>
	                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>Смета проекта</b>
                      <div style={{marginBottom:'14px',position:'relative'}}>
                        <Search size={15} style={{position:'absolute',left:'12px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
                        <input placeholder='🔍 Поиск по позициям сметы (например: «демонтаж»)' value={estimateSearch||''} onChange={e=>setEstimateSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'34px'}}/>
                      </div>
                      {estimateSearch&&estimateSearch.trim().length>=2&&(()=>{
                        const q=estimateSearch.toLowerCase().trim();
                        const projEstimates=visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name);
                        const results=[];
                        projEstimates.forEach(est=>{const sects=(est.sections||(typeof est.sectionsJson==='string'?(()=>{try{return JSON.parse(est.sectionsJson||'[]')}catch(_){return []}})():est.sectionsJson)||[]);sects.forEach(sec=>{(sec.items||[]).forEach(it=>{if(String(it.name||'').toLowerCase().includes(q)) results.push({estimate:est,section:sec,item:it});});});});
                        return(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.bg}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                            <b style={{color:C.text,fontSize:'12px'}}>Найдено: {results.length} позиций</b>
                            <button onClick={()=>setEstimateSearch('')} style={{...btnG,padding:'3px 8px',fontSize:'10px'}}>×</button>
                          </div>
                          {results.length===0?<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'8px'}}>Ничего не найдено</p>:<div style={{maxHeight:'300px',overflowY:'auto'}}>{results.slice(0,100).map((r,i)=>(<div key={i} style={{padding:'8px 10px',borderRadius:'6px',marginBottom:'4px',backgroundColor:C.bgWhite,border:'1px solid '+C.border}}>
                            <b style={{fontSize:'12px',color:C.text,display:'block'}}>{r.item.name}</b>
                            <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'10px'}}>{'📂 '+r.section.name+' · '+fmtMeasure(r.item.quantity,r.item.unit)+(r.item.doneQuantity>0?' · сделано '+fmtMeasure(r.item.doneQuantity,r.item.unit):'')}</p>
                          </div>))}</div>}
                        </div>);
                      })()}
                      {(()=>{
                        const projEstimates=visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name);
                        if(projEstimates.length===0) return(<div style={{textAlign:'center',padding:'30px',color:C.textMuted}}><p>Смета не привязана</p><button onClick={()=>navigateTo('estimates')} style={btnO}>Перейти в Сметы</button></div>);
                        return projEstimates.map(est=>(<div key={est.id} style={{...card,padding:'14px',marginBottom:'10px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{est.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{estimateKind(est)+' · 📁 '+estimatePackage(est)+' · v'+est.version}</p></div>
                            <div style={{display:'flex',gap:'6px'}}>
                              <button onClick={()=>{openEstimateDetail(est);navigateTo('estimates');}} style={btnB}><Eye size={13}/>Открыть</button>
                            </div>
                          </div>
                        </div>));
	                      })()}
	                  </div>)}

	                    {activeProjectTab==='Сверка ЖПР'&&renderWorkJournalEstimateReconciliationPanel(p)}

	                    {activeProjectTab==='Производство работ'&&(
                      <ProjectWorkJournalPanel
                        project={p}
                        workJournal={workJournal}
                        workJournalPage={workJournalPage}
                        loadWorkJournalPage={loadWorkJournalPage}
                        weatherLog={weatherLog}
                        listSearch={listSearch}
                        setListSearch={setListSearch}
                        matchSearch={matchSearch}
                        setShowJournalTableModal={setShowJournalTableModal}
                        showPreview={showPreview}
                        buildJPRContent={buildJPRContent}
                        showKS2={showKS2}
                        setEditingJournal={setEditingJournal}
                        getActStatusForJournal={getActStatusForJournal}
                        setEditingAct={setEditingAct}
                        openConfirmModal={openConfirmModal}
                        setRejectingEntry={setRejectingEntry}
                        canConfirm={isProrab()}
                        showCustomerTotals={['директор','зам_директора','бухгалтер','сметчик','главный_инженер','прораб'].includes(user?.role)}
                        fileSrc={fileSrc}
                        setShowPhotoModal={setShowPhotoModal}
                        C={C}
                        inp={inp}
                        btnB={btnB}
                        btnG={btnG}
                        btnGr={btnGr}
                        btnR={btnR}
                        badge={badge}
                      />
                    )}

                    {activeProjectTab==='Помещения'&&(
                      <ProjectRoomsTab ctx={ctx} project={p} />
                    )}

                    {activeProjectTab==='Чек-листы'&&(
                      <ProjectChecklistsTab
                        API={API}
                        C={C}
                        CHECKLIST_TEMPLATES={CHECKLIST_TEMPLATES}
                        Check={Check}
                        ChevronDown={ChevronDown}
                        ChevronUp={ChevronUp}
                        Plus={Plus}
                        X={X}
                        btnG={btnG}
                        btnO={btnO}
                        card={card}
                        checklistItems={checklistItems}
                        checklists={checklists}
                        inp={inp}
                        isProrab={isProrab}
                        loadChecklistItems={loadChecklistItems}
                        newChecklist={newChecklist}
                        newChecklistItem={newChecklistItem}
                        project={p}
                        saveChecklist={saveChecklist}
                        selectedChecklist={selectedChecklist}
                        setNewChecklist={setNewChecklist}
                        setNewChecklistItem={setNewChecklistItem}
                        setSelectedChecklist={setSelectedChecklist}
                        setShowForm={setShowForm}
                        showForm={showForm}
                        toggleChecklistItem={toggleChecklistItem}
                      />
                    )}

                    {activeProjectTab==='Изменения к смете'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Изменения к смете</b>
                        <button onClick={()=>setShowForm(showForm==='unexpected'?false:'unexpected')} style={btnO}><Plus size={14}/>Создать изменение</button>
                      </div>
                      {(()=>{const budget=Number(p.budget||0);if(budget<=0) return null;const approved=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status)&&u.changeType!=='Исключение объёма'&&!u.includedInEstimateId).reduce((s,u)=>s+Number(u.total||0),0);const pending=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&u.status==='Ожидает согласования'&&u.changeType!=='Исключение объёма').reduce((s,u)=>s+Number(u.total||0),0);const pct=Math.round(approved/budget*100*10)/10;const LIMIT=10;const overLimit=pct>LIMIT;if(approved===0&&pending===0) return null;return(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:overLimit?C.dangerLight:pct>LIMIT*0.7?C.warningLight:C.bg,border:'1.5px solid '+(overLimit?C.dangerBorder:pct>LIMIT*0.7?C.warningBorder:C.border)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                          <div>
                            <b style={{color:C.text,fontSize:'13px'}}>📊 Изменения отдельной допработой: {pct}% от бюджета (контрольный порог {LIMIT}%)</b>
                            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждено: {Math.round(approved).toLocaleString('ru-RU')+' ₽'} {pending>0?'· Ждут: '+Math.round(pending).toLocaleString('ru-RU')+' ₽':''}</p>
                          </div>
                          {overLimit&&<span style={{padding:'4px 10px',backgroundColor:C.danger,color:'white',borderRadius:'10px',fontSize:'11px',fontWeight:'700'}}>⚠️ ПРЕВЫШЕН ЛИМИТ</span>}
                        </div>
                        {overLimit&&<p style={{color:C.danger,margin:'8px 0 0',fontSize:'11px',lineHeight:1.4}}>Сумма изменений превысила 10% бюджета. Это не блокировка, но стоит выпустить доп.соглашение или новую редакцию сметы, чтобы КС не задвоились.</p>}
                      </div>);})()}
                      {(()=>{const all=includableEstimateChanges(p.name);if(all.length===0) return null;const activeEsts=activeEstimatesForProject(p,'Заказчик');const unlinked=all.filter(u=>!u.estimateId);if(activeEsts.length===0) return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><b style={{color:C.warning,fontSize:'13px'}}>📐 Есть утверждённые изменения, но нет активной сметы заказчика</b><p style={{color:C.textSec,margin:'3px 0 0',fontSize:'11px'}}>Создайте или активируйте смету заказчика, чтобы включить изменения в новую версию без задвоения КС.</p></div>);return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'8px'}}>
                          <div>
                            <b style={{color:C.info,fontSize:'13px'}}>📐 Включение изменений в новую смету</b>
                            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждённые изменения можно перенести в новую активную версию сметы. После этого они не пойдут в КС отдельными строками.</p>
                          </div>
                          <span style={badge(C.info,C.bgWhite,C.infoBorder)}>{all.length+' изм.'}</span>
                        </div>
                        {activeEsts.map(est=>{const rows=estimateChangesForNewEstimate(p,est);if(rows.length===0) return null;const signed=signedEstimateChangeTotal(rows);return(<div key={est.id} style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border,marginTop:'8px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{minWidth:'220px',flex:1}}>
                            <b style={{color:C.text,fontSize:'12px'}}>{est.name+' · v'+(est.version||'1.0')}</b>
                            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>{estimatePackage(est)+' · '+rows.length+' изм. · влияние '+(signed>0?'+':'')+Math.round(signed).toLocaleString('ru-RU')+' ₽'}</p>
                          </div>
                          <button onClick={()=>includeChangesInNewEstimate(p,est,rows)} style={{...btnB,padding:'6px 12px',fontSize:'12px'}}><GitBranch size={13}/>В новую смету</button>
                        </div>);})}
                        {activeEsts.length>1&&unlinked.length>0&&<p style={{color:C.warning,margin:'8px 0 0',fontSize:'11px'}}>Есть изменения без привязки к строке сметы: {unlinked.length}. При нескольких активных пакетах их нужно привязать вручную, чтобы не включить не туда.</p>}
                      </div>);})()}
                      {(()=>{const recs=estimateReconciliationsForProject(p.name);if(recs.length===0)return null;const openChecks=recs.reduce((s,r)=>s+Number(r.reviewCount||0),0);return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.bg,border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                        <div>
                          <b style={{color:C.text,fontSize:'13px'}}>Связанные сверки смет: {recs.length}</b>
                          <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Спорных строк к проверке: {openChecks}. Сверка фиксирует, что вошло в новую смету, а что остаётся отдельной допработой.</p>
                        </div>
                        <button onClick={()=>{setActiveProjectTab('Сверки смет');setActiveTabGroup('work');}} style={{...btnB,padding:'6px 12px',fontSize:'12px'}}><FileText size={13}/>Открыть сверки</button>
                      </div>);})()}
                      {showForm==='unexpected'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                          <select value={newUnexpected.changeType} onChange={e=>setNewUnexpected({...EMPTY_ESTIMATE_CHANGE,changeType:e.target.value,price:newUnexpected.price})} style={{...inp,marginBottom:0}}>
                            {ESTIMATE_CHANGE_TYPES.map(t=><option key={t}>{t}</option>)}
                          </select>
                          {(()=>{const opts=estimateItemOptionsForProject(p);return(<select value={[newUnexpected.estimateId||'',newUnexpected.sectionName||'',newUnexpected.estimateItemName||''].join('|')} disabled={newUnexpected.changeType!=='Дополнительный объём к строке сметы'||opts.length===0} onChange={e=>{const o=opts.find(x=>[x.estimateId,x.sectionName,x.name].join('|')===e.target.value);if(!o)return;setNewUnexpected({...newUnexpected,estimateId:o.estimateId,sectionName:o.sectionName,estimateItemName:o.name,description:o.name,unit:o.unit,baseQuantity:o.quantity,quantity:'',newRequiredQuantity:'',deltaQuantity:'',price:Math.round(o.pricePerUnit||0)});}} style={{...inp,marginBottom:0}}>
                            <option value=''>{opts.length?'Привязать строку сметы':'Активная смета не найдена'}</option>
                            {opts.map(o=><option key={o.key} value={[o.estimateId,o.sectionName,o.name].join('|')}>{(o.sectionName?o.sectionName+' / ':'')+o.name+' · '+fmtMeasure(o.quantity,o.unit)}</option>)}
                          </select>);})()}
                        </div>
                        {newUnexpected.changeType==='Дополнительный объём к строке сметы'&&(<div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px',marginBottom:'8px',padding:'10px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                          <div><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>По активной смете</p><b style={{fontSize:'12px',color:C.text}}>{fmtMeasure(toNum(newUnexpected.baseQuantity),newUnexpected.unit)}</b></div>
                          <input placeholder="Фактически нужно всего" type="number" step="any" inputMode="decimal" value={newUnexpected.newRequiredQuantity?normalizeMeasure(toNum(newUnexpected.newRequiredQuantity),newUnexpected.unit).qty:''} onChange={e=>{const raw=denormalizeMeasure(e.target.value,newUnexpected.unit);const delta=Math.max(0,raw-toNum(newUnexpected.baseQuantity));setNewUnexpected({...newUnexpected,newRequiredQuantity:raw,deltaQuantity:delta,quantity:delta});}} style={{...inp,marginBottom:0}}/>
                          <div><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>Доп.объём</p><b style={{fontSize:'12px',color:toNum(newUnexpected.deltaQuantity)>0?C.warning:C.textMuted}}>{fmtMeasure(toNum(newUnexpected.deltaQuantity),newUnexpected.unit)}</b></div>
                        </div>)}
                        <textarea placeholder="Описание изменения *" value={newUnexpected.description} onChange={e=>setNewUnexpected({...newUnexpected,description:e.target.value})} style={{...inp,height:'80px',resize:'vertical'}}/>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
                          <input placeholder="Кол-во" type="number" step="any" inputMode="decimal" disabled={newUnexpected.changeType==='Дополнительный объём к строке сметы'} value={newUnexpected.quantity} onChange={e=>setNewUnexpected({...newUnexpected,quantity:e.target.value,deltaQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newUnexpected.unit} onChange={e=>setNewUnexpected({...newUnexpected,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                          <input placeholder="Цена (₽)" type="number" step="any" inputMode="decimal" value={newUnexpected.price} onChange={e=>setNewUnexpected({...newUnexpected,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <textarea placeholder="Причина изменения (ошибка объёма, решение заказчика, фактические условия)" value={newUnexpected.reason} onChange={e=>setNewUnexpected({...newUnexpected,reason:e.target.value})} style={{...inp,height:'56px',resize:'vertical',marginTop:'8px'}}/>
                        <div style={{display:'flex',gap:'8px',marginTop:'6px',flexWrap:'wrap'}}>
                          <button disabled={!newUnexpected.description||!!newUnexpected.__aiLoading} onClick={async()=>{
                            setNewUnexpected(prev=>({...prev,__aiLoading:true}));
                            try {
                              // Создаём временную запись чтобы AI имел id
                              const tmpRes = await fetch(API+'/unexpected-works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,description:newUnexpected.description,unit:newUnexpected.unit||'шт',quantity:Number(newUnexpected.quantity||0),changeType:newUnexpected.changeType,price:0,total:0,addedBy:user.name,addedByRole:user.role,status:'_ai_temp_'})});
                              const tmp = await tmpRes.json();
                              const aiRes = await fetch(API+'/unexpected-works/'+tmp.id+'/ai-estimate',{method:'POST'});
                              if(!aiRes.ok){const e=await aiRes.json().catch(()=>({}));throw new Error(e.detail||'Ошибка');}
                              const d = await aiRes.json();
                              // Удаляем временную
                              await fetch(API+'/unexpected-works/'+tmp.id,{method:'DELETE'}).catch(()=>{});
                              setNewUnexpected(prev=>({...prev,price:Math.round(d.pricePerUnit),__aiLoading:false,__aiNote:d.justification}));
                            } catch(e){alert('AI: '+e.message);setNewUnexpected(prev=>({...prev,__aiLoading:false}));}
                          }} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',fontSize:'12px',padding:'7px 12px',opacity:newUnexpected.__aiLoading?0.6:1}}><Bot size={13}/>{newUnexpected.__aiLoading?'…':'🤖 Оценить через ИИ'}</button>
                          {newUnexpected.__aiNote&&<span style={{fontSize:'11px',color:C.textSec,flex:1,fontStyle:'italic'}}>{newUnexpected.__aiNote}</span>}
                        </div>
                        <div style={{marginTop:'8px'}}>
                          <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
                            <label style={{...btnB,padding:'8px 12px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>📷 Прикрепить фото (можно несколько)<input type='file' accept='image/*' multiple style={{display:'none'}} onChange={async e=>{if(e.target.files&&e.target.files.length>0){const csv=await appendPhotos(newUnexpected.photoUrl,e.target.files,{projectName:p.name,context:'estimate-changes'});setNewUnexpected({...newUnexpected,photoUrl:csv});e.target.value='';}}}/></label>
                            {(newUnexpected.photoUrl||'').split(',').filter(Boolean).length>0&&<span style={{fontSize:'11px',color:C.success,fontWeight:'600'}}>📷 {(newUnexpected.photoUrl||'').split(',').filter(Boolean).length} фото</span>}
                          </div>
                          {(()=>{const urls=(newUnexpected.photoUrl||'').split(',').filter(Boolean);if(urls.length===0) return null;return (<div style={{display:'flex',gap:'4px',flexWrap:'wrap'}}>{urls.map((u,i)=>(<div key={i} style={{position:'relative'}}><img src={fileSrc(u)} alt='' onClick={()=>setShowPhotoModal(fileSrc(u))} style={{width:'60px',height:'60px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',border:'1px solid '+C.border}}/><button type='button' onClick={(ev)=>{ev.preventDefault();ev.stopPropagation();setNewUnexpected({...newUnexpected,photoUrl:urls.filter((_,j)=>j!==i).join(',')});}} style={{position:'absolute',top:'-4px',right:'-4px',background:'rgba(220,38,38,0.9)',color:'white',border:'none',borderRadius:'50%',width:'18px',height:'18px',cursor:'pointer',fontSize:'10px',lineHeight:'1',padding:0}}>×</button></div>))}</div>);})()}
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={()=>saveUnexpectedWork(p.name)} style={btnO}><Check size={14}/>Отправить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {(()=>{const approvedAll=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status));const ver=approvedAll.length+1;const sumDS=approvedAll.reduce((s,u)=>s+Number(u.total||0),0);if(approvedAll.length===0) return null;return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                        <div>
                          <b style={{color:C.info,fontSize:'13px'}}>📜 Договор подряда — версия v{ver}</b>
                          <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждённых изменений: {approvedAll.length} на сумму {Math.round(sumDS).toLocaleString('ru-RU')+' ₽'}. Если их не включили в новую смету, они идут в КС отдельными разделами.</p>
                        </div>
                      </div>);})()}
                      {ESTIMATE_CHANGE_VISIBLE_STATUSES.map(status=>{ const items=unexpectedWorksList.filter(u=>u.projectName===p.name&&u.status===status); if(items.length===0) return null; return(<div key={status} style={{marginBottom:'16px'}}><b style={{color:isApprovedEstimateChangeStatus(status)?C.success:status==='Отклонено'?C.danger:status==='Включено в новую смету'?C.info:C.warning,fontSize:'12px',display:'block',marginBottom:'8px'}}>{status==='Ожидает согласования'?'⏳':isApprovedEstimateChangeStatus(status)?'✅':status==='Включено в новую смету'?'📐':'❌'} {status} ({items.length})</b>{items.map((u,idx)=>{const dsNum=isApprovedEstimateChangeStatus(status)?(()=>{const arr=(unexpectedWorksList||[]).filter(x=>x.projectName===p.name&&isApprovedEstimateChangeStatus(x.status));return arr.length-arr.findIndex(x=>x.id===u.id);})():null;return(<div key={u.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}><div style={{flex:1,minWidth:'200px'}}>{dsNum&&<b style={{fontSize:'11px',color:C.info,display:'block'}}>ДС № {dsNum} к договору подряда</b>}<span style={{display:'inline-block',padding:'2px 7px',borderRadius:'9px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,color:C.textSec,fontSize:'10px',marginBottom:'4px'}}>{u.changeType||'Работа вне сметы'}</span><b style={{fontSize:'13px',color:C.text,display:'block'}}>{u.description}</b>{u.estimateItemName&&<p style={{color:C.info,margin:'2px 0',fontSize:'11px'}}>{'Строка сметы: '+(u.sectionName?u.sectionName+' / ':'')+u.estimateItemName}</p>}<p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{fmtMeasure(u.deltaQuantity||u.quantity,u.unit)+(u.price>0?' · '+u.price.toLocaleString()+' ₽/'+u.unit:'')+(u.total>0?' · Итого: '+u.total.toLocaleString()+' ₽':'')}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{'Добавил: '+u.addedBy+(u.approvedAt?' · Утв.: '+u.approvedAt:'')+(u.reason?' · Причина: '+u.reason:'')}</p></div><div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap'}}>{isApprovedEstimateChangeStatus(u.status)&&<button onClick={()=>showPreview(buildSupplementaryAgreementContent(u,p),'Доп.соглашение № '+dsNum+' к договору подряда — '+p.name)} style={{...btnB,padding:'4px 8px',fontSize:'11px'}} title='Печать доп.соглашения'><Eye size={11}/>🖨️ ДС</button>}{isLeadership()&&u.status==='Ожидает согласования'&&(<><input placeholder="Цена ₽" type="number" step="any" inputMode="decimal" defaultValue={u.price||''} style={{width:'90px',padding:'4px 8px',border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px'}} onChange={e=>e.target.dataset.price=e.target.value}/><button onClick={e=>{approveUnexpectedWork(u,e.target.previousSibling.dataset.price||u.price||0);}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}><Check size={11}/>Утвердить</button><button onClick={async()=>{await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnR,padding:'4px 8px',fontSize:'11px'}}><X size={11}/>Откл.</button></>)}</div></div></div>);})}</div>);})}
                      {unexpectedWorksList.filter(u=>u.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Изменений к смете нет</p>}
                  </div>)}

                    {activeProjectTab==='Сверки смет'&&renderEstimateReconciliationsPanel(p)}

                    {activeProjectTab==='Расчёт с бригадой'&&(
                      <ProjectBrigadeCalculationTab
                        project={p}
                        brigadeContracts={brigadeContracts}
                        smetaTotal={projectPlanDone(p).plan}
                        showBrigadeForm={showBrigadeForm}
                        setShowBrigadeForm={setShowBrigadeForm}
                        newBrigadeContract={newBrigadeContract}
                        setNewBrigadeContract={setNewBrigadeContract}
                        staff={staff}
                        masterProfiles={masterProfiles}
                        users={users}
                        pricelists={pricelists}
                        setBrigadeContracts={setBrigadeContracts}
                        setSelectedBrigadeContract={setSelectedBrigadeContract}
                        setBrigadeContractItems={setBrigadeContractItems}
                        setBrigadePayments={setBrigadePayments}
                        selectedBrigadeContract={selectedBrigadeContract}
                        brigadeContractItems={brigadeContractItems}
                        brigadePayments={brigadePayments}
                        estimatesList={estimatesList}
                        newBrigadeItem={newBrigadeItem}
                        setNewBrigadeItem={setNewBrigadeItem}
                        UNITS={UNITS}
                        showLeadership={isLeadership()}
                        brigadeCoef={brigadeCoef}
                        setBrigadeCoef={setBrigadeCoef}
                        showFinance={isFinanceRole()}
                        companyRequisites={companyRequisites}
                        companyName={companyName}
                        normalizeMeasure={normalizeMeasure}
                        toNum={toNum}
                        fmtMeasure={fmtMeasure}
                        userName={user.name}
                        setNewBrigadePayment={setNewBrigadePayment}
                        setShowBrigadePayModal={setShowBrigadePayModal}
                        deleteBrigadePayment={deleteBrigadePayment}
                        showPreview={showPreview}
                        uploadPhoto={uploadPhoto}
                        fileSrc={fileSrc}
                        openBrigadeContract={openBrigadeContract}
                        C={C}
                        card={card}
                        inp={inp}
                        btnO={btnO}
                        btnG={btnG}
                        btnB={btnB}
                        btnR={btnR}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                      />
                    )}
                    {activeProjectTab==='Материалы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Материалы объекта</b>
	                        <div style={{display:'flex',gap:'8px'}}>
	                          {(isLeadership()||user.role==='прораб'||user.role==='кладовщик')&&(
                          <button onClick={async()=>{
                            const res=await fetch(API+'/material-transfers?project_name='+encodeURIComponent(p.name));
                            const data=await res.json();
                            setMaterialTransfers(Array.isArray(data)?data:[]);
                            setNewTransfer(createMaterialTransferForm({ fromLocation: p.name }));
                            setShowTransferForm(!showTransferForm);
                          }} style={btnO}><Plus size={14}/>Передать материал</button>)}
                        </div>
                      </div>
                      {(()=>{
                        const diag=projectJournalDiagnostics(p.name);
                        if(!diag.smetaOutsideRows.length&&!diag.smetaOverRows.length) return null;
                        return(<div style={{...card,padding:'12px',marginBottom:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
                          <b style={{color:C.warning,fontSize:'13px'}}>Сметная сверка требует внимания</b>
                          <p style={{color:C.textSec,fontSize:'11px',margin:'4px 0 0'}}>Вне сметы: {diag.smetaOutsideRows.length} · нужен алиас/решение: {diag.aliasNeededRows.length} · сверх плана: {diag.smetaOverRows.length}</p>
                          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'8px'}}>
                            {diag.aliasNeededRows.slice(0,6).map((r,idx)=><span key={(r.key||r.name||'a')+'-'+idx} style={badge(C.warning,C.warningLight,C.warningBorder)}>{r.name}</span>)}
                          </div>
                        </div>);
                      })()}
                      <ProjectMaterialsControlPanel
                        projectName={p.name}
                        rows={materialReconciliationRows(p.name)}
                        normRows={estimateWorkNormRequirementRows(p.name)}
                        normCtrl={materialNormControlSummaryForProject(p.name)}
                        buildRowsForPackage={(workPackage)=>materialReconciliationRows(p.name, workPackage)}
                        buildNormRowsForPackage={(workPackage)=>estimateWorkNormRequirementRows(p.name, workPackage)}
                        buildNormCtrlForPackage={(workPackage)=>materialNormControlSummaryForProject(p.name, workPackage)}
                        isMobile={isMobile}
                        C={C}
                        card={card}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                        btnB={btnB}
                        badge={badge}
                        fmtMeasure={fmtMeasure}
                        materialControlStatus={materialControlStatus}
                        renderMaterialSupplyAction={renderMaterialSupplyAction}
                        renderMaterialAliasControls={renderMaterialAliasControls}
	                        onCreateSupplyForRows={(rows)=>createBatchSupplyRequestFromMaterialControl(p.name, rows)}
	                        showPreview={showPreview}
	                        buildMaterialRequirementContent={buildMaterialRequirementContent}
	                        onIssueMaterial={(row)=>{
	                          setNewTransfer(createMaterialTransferForm({
	                            materialName: row.name || '',
	                            unit: row.unit || 'шт',
	                            workPackage: row.packageName || row.workPackage || '',
	                            fromLocation: p.name,
	                            notes: 'Выдача мастеру из контроля материалов',
	                          }));
	                          setShowTransferForm(true);
	                        }}
	                      />
                      <ProjectMaterialsStockPanel
                        projectName={p.name}
                        materials={materials}
                        warehouseMain={warehouseMain}
                        isMobile={isMobile}
                        C={C}
                        card={card}
                      />

                      <ProjectMaterialsTransferPanel
                        projectName={p.name}
                        showTransferForm={showTransferForm}
                        setShowTransferForm={setShowTransferForm}
                        newTransfer={newTransfer}
                        setNewTransfer={setNewTransfer}
                        materialTransfers={materialTransfers}
                        setMaterialTransfers={setMaterialTransfers}
                        warehouseMain={warehouseMain}
                        setWarehouseMain={setWarehouseMain}
                        materials={materials}
                        setMaterials={setMaterials}
                        visibleProjects={visibleActiveProjects(projects)}
                        supplyRequests={supplyRequests}
                        staff={staff}
                        brigadeContracts={brigadeContracts}
                        workJournal={workJournal}
                        history={history}
                        workPackageOptions={[...new Set([...(activeEstimatesForProject(p,'Заказчик')||[]).map(estimatePackage), ...ESTIMATE_PACKAGES].filter(Boolean))]}
                        user={user}
                        C={C}
                        card={card}
                        inp={inp}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                        btnO={btnO}
                        btnG={btnG}
                        btnGr={btnGr}
                        btnB={btnB}
                        btnR={btnR}
                        normalizeUnit={_normalizeUnit}
                        convertUnits={convertUnits}
                        fmtMeasure={fmtMeasure}
                        showPreview={showPreview}
                        buildM15Content={buildM15Content}
                      />
                  </div>)}
                    {activeProjectTab==='Чат'&&(
                      <ProjectChatTab
                        C={C}
                        btnG={btnG}
                        btnO={btnO}
                        fileSrc={fileSrc}
                        inp={inp}
                        loadProjectChat={loadProjectChat}
                        project={p}
                        projectChatMessage={projectChatMessage}
                        projectChatMessages={projectChatMessages}
                        roleColor={roleColor}
                        sendProjectChatMessage={sendProjectChatMessage}
                        setProjectChatMessage={setProjectChatMessage}
                        setShowPhotoModal={setShowPhotoModal}
                        user={user}
                      />
                    )}

                    {activeProjectTab==='Финансы'&&(
                      <ProjectFinanceTab
                        C={C}
                        EXPENSE_CATEGORIES={EXPENSE_CATEGORIES}
                        ProjectFinancePanel={ProjectFinancePanel}
                        accountablePayments={accountablePayments}
                        btnB={btnB}
                        btnG={btnG}
                        btnO={btnO}
                        btnR={btnR}
                        card={card}
                        expByCategory={expByCategory}
                        fileSrc={fileSrc}
                        formatSignedRub={formatSignedRub}
                        isFinanceRole={isFinanceRole()}
                        isLeadership={isLeadership()}
                        loadAll={loadAll}
                        manualExpenses={manualExpenses}
                        ownExpenses={ownExpenses}
                        project={p}
                        projectPaymentInAmount={projectPaymentInAmount}
                        projectPaymentSignedAmount={projectPaymentSignedAmount}
                        projectPayments={projectPayments}
                        setAddExpenseProject={setAddExpenseProject}
                        setNewAccountable={setNewAccountable}
                        setNewManualExpense={setNewManualExpense}
                        setShowAccountableForm={setShowAccountableForm}
                        setShowBalanceDetails={setShowBalanceDetails}
                        setShowPhotoModal={setShowPhotoModal}
                        showBalanceDetails={showBalanceDetails}
                        user={user}
                      />
                    )}
                    {activeProjectTab==='Предписания'&&(
                      <ProjectPrescriptionsPanel
                        projectName={p.name}
                        prescriptionsList={prescriptionsList}
                        showForm={showForm}
                        setShowForm={setShowForm}
                        newPrescription={newPrescription}
                        setNewPrescription={setNewPrescription}
                        savePrescription={savePrescription}
                        loadAll={loadAll}
                        canClose={isProrab()}
                        C={C}
                        card={card}
                        inp={inp}
                        btnO={btnO}
                        btnG={btnG}
                        btnGr={btnGr}
                        badge={badge}
                      />
                    )}

                    {activeProjectTab==='Журнал ТБ'&&(
                      <ProjectSafetyJournalPanel
                        projectName={p.name}
                        tbJournal={tbJournal}
                        showForm={showForm}
                        setShowForm={setShowForm}
                        newTbEntry={newTbEntry}
                        setNewTbEntry={setNewTbEntry}
                        newParticipant={newParticipant}
                        setNewParticipant={setNewParticipant}
                        listSearch={listSearch}
                        setListSearch={setListSearch}
                        tbTypes={TB_TYPES_GOST}
                        tbInstructions={TB_INSTRUCTIONS}
                        saveTbEntry={saveTbEntry}
                        matchSearch={matchSearch}
                        showPreview={showPreview}
                        buildTBContent={buildTBContent}
                        C={C}
                        card={card}
                        inp={inp}
                        btnO={btnO}
                        btnG={btnG}
                        btnB={btnB}
                        btnR={btnR}
                      />
                    )}
                    {activeProjectTab==='АОСР'&&(
                      <ProjectHiddenWorksActsPanel
                        projectName={p.name}
                        hiddenActs={hiddenActs}
                        setEditingAct={setEditingAct}
                        setHiddenActs={setHiddenActs}
                        showPreview={showPreview}
                        buildHiddenActContent={buildHiddenActContent}
                        showDelete={isLeadership()}
                        C={C}
                        card={card}
                        tbl={tbl}
                        tblH={tblH}
                        tblC={tblC}
                        btnB={btnB}
                        btnG={btnG}
                        btnR={btnR}
                      />
                    )}
                  {activeProjectTab==='Главный'&&(
                    <ProjectJournalsHubTab
                      C={C}
                      card={card}
                      hiddenActs={hiddenActs}
                      prescriptionsList={prescriptionsList}
                      project={p}
                      projectJournalDiagnostics={projectJournalDiagnostics}
                      setActiveProjectTab={setActiveProjectTab}
                      tbJournal={tbJournal}
                      weatherLog={weatherLog}
                      workJournal={workJournal}
                    />
                  )}
                  {activeProjectTab==='Погода'&&(
                    <ProjectWeatherTab
                      C={C}
                      card={card}
                      project={p}
                      weatherLog={weatherLog}
                    />
                  )}
                  {activeProjectTab==='📁 Реестр'&&(
                    <ProjectDocumentsRegistryPanel
                      projectName={p.name}
                      projectDocuments={projectDocuments}
                      newProjectDoc={newProjectDoc}
                      setNewProjectDoc={setNewProjectDoc}
                      showDocForm={showDocForm}
                      setShowDocForm={setShowDocForm}
                      uploadingDoc={uploadingDoc}
                      setUploadingDoc={setUploadingDoc}
                      uploadPhoto={uploadPhoto}
                      fileSrc={fileSrc}
                      loadAll={loadAll}
                      user={user}
                      C={C}
                      card={card}
                      inp={inp}
                      btnO={btnO}
                      btnG={btnG}
                      btnB={btnB}
                      btnR={btnR}
                    />
                  )}
                  {activeProjectTab==='✉️ Переписка'&&(
                    <ProjectLettersPanel
                      projectName={p.name}
                      projectLetters={projectLetters}
                      newLetter={newLetter}
                      setNewLetter={setNewLetter}
                      showLetterForm={showLetterForm}
                      setShowLetterForm={setShowLetterForm}
                      uploadingLetter={uploadingLetter}
                      setUploadingLetter={setUploadingLetter}
                      uploadPhoto={uploadPhoto}
                      fileSrc={fileSrc}
                      loadAll={loadAll}
                      user={user}
                      C={C}
                      card={card}
                      inp={inp}
                      btnO={btnO}
                      btnG={btnG}
                      btnB={btnB}
                      btnR={btnR}
                    />
                  )}
                  {activeProjectTab==='КС-2'&&(
                    <ProjectPrintDocumentCard
                      C={C}
                      Eye={Eye}
                      btnO={btnO}
                      card={card}
                      description="Унифицированная форма по ОКУД 0322005. Формируется из выполненных позиций активной сметы. Утверждённые изменения к смете выводятся отдельными разделами без задвоения."
                      icon="📄"
                      openLabel="КС-2"
                      onOpen={()=>showKS2(p)}
                      title="Акт о приёмке выполненных работ (КС-2)"
                    />
                  )}
                  {activeProjectTab==='КС-3'&&(
                    <ProjectPrintDocumentCard
                      C={C}
                      Eye={Eye}
                      btnO={btnO}
                      card={card}
                      description="Унифицированная форма по ОКУД 0322001. Подаётся вместе с КС-2 за отчётный период."
                      icon="📋"
                      openLabel="КС-3"
                      onOpen={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)}
                      title="Справка о стоимости выполненных работ (КС-3)"
                    />
                  )}
                  {activeProjectTab==='Паспорт'&&(
                    <ProjectPrintDocumentCard
                      C={C}
                      Eye={Eye}
                      btnO={btnO}
                      card={card}
                      description="Сводная карточка объекта с основными характеристиками и реквизитами."
                      icon="📘"
                      openLabel="Паспорт"
                      onOpen={()=>showPreview(buildPassportContent(p),'Паспорт — '+p.name)}
                      title="Паспорт объекта"
                    />
                  )}
                  {activeProjectTab==='Акты технадзора'&&(
                    <ProjectSupervisorActsTab
                      C={C}
                      card={card}
                      fileSrc={fileSrc}
                      project={p}
                      setShowPhotoModal={setShowPhotoModal}
                      supervisorActs={supervisorActs}
                    />
                  )}
                  {activeProjectTab==='Замечания ГСН'&&(
                    <ProjectInspectionOrdersTab
                      API={API}
                      C={C}
                      Check={Check}
                      Plus={Plus}
                      Trash2={Trash2}
                      badge={badge}
                      btnG={btnG}
                      btnGr={btnGr}
                      btnO={btnO}
                      btnR={btnR}
                      card={card}
                      createInspectionOrderForm={createInspectionOrderForm}
                      inp={inp}
                      inspectionOrders={inspectionOrders}
                      newInspOrder={newInspOrder}
                      project={p}
                      refreshData={refreshData}
                      setNewInspOrder={setNewInspOrder}
                      setShowForm={setShowForm}
                      showForm={showForm}
                    />
                  )}
                  {activeProjectTab==='Гарантия'&&(
                    <ProjectWarrantyTab
                      API={API}
                      C={C}
                      Check={Check}
                      Plus={Plus}
                      Trash2={Trash2}
                      badge={badge}
                      btnG={btnG}
                      btnGr={btnGr}
                      btnO={btnO}
                      btnR={btnR}
                      card={card}
                      createWarrantyDefectForm={createWarrantyDefectForm}
                      inp={inp}
                      newWarrantyDefect={newWarrantyDefect}
                      project={p}
                      refreshData={refreshData}
                      setNewWarrantyDefect={setNewWarrantyDefect}
                      setWarrantyEditForm={setWarrantyEditForm}
                      user={user}
                      warrantyDefects={warrantyDefects}
                      warrantyEditForm={warrantyEditForm}
                    />
                  )}
                  {activeProjectTab==='Входной контроль'&&(
                    <div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📦 Журнал входного контроля материалов</b>
                        <span style={{fontSize:'11px',color:C.textMuted}}>СП 48.13330.2019 · автозаполняется из накладных</span>
                      </div>
                      <ProjectMaterialInspectionTab
                        C={C}
                        Eye={Eye}
                        badge={badge}
                        btnB={btnB}
                        btnG={btnG}
                        buildMaterialInspectionContent={buildMaterialInspectionContent}
                        card={card}
                        journalDiagnosticMode={journalDiagnosticMode}
                        journalPackage={journalPackage}
                        materialInspections={materialInspections}
                        project={p}
                        projectJournalDiagnostics={projectJournalDiagnostics}
                        setEditingInspection={setEditingInspection}
                        setJournalDiagnosticMode={setJournalDiagnosticMode}
                        showPreview={showPreview}
                        tbl={tbl}
                        tblC={tblC}
                        tblH={tblH}
                        toNum={toNum}
                      />
                    </div>
                  )}
                  {activeProjectTab==='Кабельная продукция'&&(
                    <div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>⚡ Журнал кабельной продукции</b>
                        <span style={{fontSize:'11px',color:C.textMuted}}>Электрика · СКС · пожарка · слаботочка</span>
                      </div>
                      <ProjectCableJournalTab
                        C={C}
                        Eye={Eye}
                        badge={badge}
                        btnB={btnB}
                        btnG={btnG}
                        buildCableJournalContent={buildCableJournalContent}
                        cableJournal={cableJournal}
                        cableTypeOf={cableTypeOf}
                        card={card}
                        journalDiagnosticMode={journalDiagnosticMode}
                        journalPackage={journalPackage}
                        project={p}
                        projectJournalDiagnostics={projectJournalDiagnostics}
                        setEditingCable={setEditingCable}
                        setJournalDiagnosticMode={setJournalDiagnosticMode}
                        showPreview={showPreview}
                        tbl={tbl}
                        tblC={tblC}
                        tblH={tblH}
                        toNum={toNum}
                      />
                    </div>
                  )}
                  </div>
                </div>)}
              </div>);
            })}
            {projects.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><FolderKanban size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Проектов нет — создайте первый!</p></div>}
          </div>
  );
}
