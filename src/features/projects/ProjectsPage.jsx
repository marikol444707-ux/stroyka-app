import React from 'react';
import {
  createInspectionOrderForm,
  createWarrantyDefectForm,
} from '../project-operations/projectOperationInitialForms';
import ProjectAiControlTab from './ProjectAiControlTab';
import ProjectChecklistsTab from './ProjectChecklistsTab';
import ProjectChatTab from './ProjectChatTab';
import ProjectEstimateChangesTab from './ProjectEstimateChangesTab';
import ProjectFinanceTab from './ProjectFinanceTab';
import ProjectJournalsHubTab from './ProjectJournalsHubTab';
import ProjectInspectionOrdersTab from './ProjectInspectionOrdersTab';
import ProjectMaterialsTab from './ProjectMaterialsTab';
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

export default function ProjectsPage({ ctx }) {
  const {
    API, Archive, Bot, C, CHECKLIST_TEMPLATES, Calculator, Check, ChevronDown,
    ChevronUp, DIRECTOR_MAP_FEATURE_ENABLED,
    EXPENSE_CATEGORIES, Eye, FileText, FolderKanban, GitBranch, MapPin,
    Package, Plus, ProjectBrigadeCalculationTab, ProjectCardHeader, ProjectDirectorMapPanel,
    ProjectDocumentsRegistryPanel, ProjectFinancePanel, ProjectHiddenWorksActsPanel, ProjectLaunchPanel, ProjectLettersPanel,
    ProjectPrescriptionsPanel, ProjectSafetyJournalPanel, ProjectScheduleSummaryPanel, ProjectTabsNav, ProjectWorkJournalPanel,
    STAGE_STATUSES, Search, TB_INSTRUCTIONS, TB_TYPES_GOST, Trash2, UNITS,
    X, _normalizeUnit, acceptMaterialAliasTask, accountablePayments,
    activeProjectTab, activeTabGroup, aiFindingsForProject, aiSeverityMeta, aiTasksForProject,
    badge, brigadeCoef, brigadeContractItems, brigadeContracts, brigadePayments, btnB, btnG, btnGr,
    btnO, btnR, buildCableJournalContent, buildHiddenActContent, buildJPRContent, buildKS3Content, buildMaterialInspectionContent,
    buildPassportContent, buildTBContent, cableJournal, cableTypeOf,
    card, checklistItems, checklists, companyName, companyRequisites,
    deleteBrigadePayment, deleteStage,
    directorMapActionTarget, directorMapContractForProject, editProject, editingItem,
    estimateKind, estimatePackage,
    estimateSearch, estimatesList, expByCategory, expandedProject, fileSrc,
    fmtMeasure, formatSignedRub, generateAiFindingsForProject, getActStatusForJournal, hiddenActs,
    inp, inspectionOrders, isEstimatePricelist, isFinanceRole,
    isCableName, isLeadership, isMobile, isProrab, listSearch, loadAll, loadChecklistItems, loadProjectChat, loadWorkJournalPage,
    manualExpenses, masterProfiles, matchSearch, materialControlSummaryForProject, materialInspections, materialNameKey,
    materialReconciliationRows, materials, navigateTo,
    newBrigadeContract, newBrigadeItem, newChecklist, newChecklistItem, newInspOrder, newLetter,
    newParticipant, newPrescription, newProject, newProjectDoc, newStage, newTbEntry,
    newWarrantyDefect, normalizeMeasure, openAiTaskAction, openBrigadeContract, openConfirmModal,
    openEstimateDetail, ownExpenses, parseAiTaskPayload, prescriptionsList, pricelists, projectAiSummaries, projectBudgetSpent, projectChatMessage,
    projectChatMessages, projectDocuments, projectEconomy, projectLetters, projectPaymentInAmount, projectPaymentSignedAmount,
    projectPayments, projectPlanDone, projectRealProgress, projectStages, projects, refreshData, renderEstimateChangeReconcileTask,
    renderEstimateReconciliationsPanel, renderMaterialSupplyAction, renderWorkJournalEstimateReconciliationPanel, roleColor,
    saveChecklist, savePrescription, saveProject, saveProjectStage,
    saveTbEntry, selectedBrigadeContract, selectedChecklist, sendProjectChatMessage, setActiveProjectTab, setActiveTabGroup,
    setAddExpenseProject, setBrigadeCoef, setBrigadeContractItems, setBrigadeContracts, setBrigadePayments, setEditingAct,
    setEditingCable, setEditingInspection, setEditingItem, setEditingJournal, setEstimateSearch, setExpandedProject,
    setHiddenActs, setListSearch, setNewAccountable,
    setNewBrigadeContract, setNewBrigadeItem, setNewBrigadePayment, setNewChecklist, setNewChecklistItem, setNewInspOrder, setNewLetter,
    setNewManualExpense, setNewParticipant, setNewPrescription, setNewProject, setNewProjectDoc, setNewStage,
    setNewTbEntry, setNewWarrantyDefect, setProjectAiSummaries, setProjectChatMessage,
    setRejectingEntry, setSelectedBrigadeContract, setSelectedChecklist, setShowAccountableForm, setShowArchive, setShowBalanceDetails,
    setShowBrigadeForm, setShowBrigadePayModal, setShowDocForm, setShowForm, setShowJournalTableModal, setShowLetterForm, setShowPhotoModal,
    setUploadingDoc, setUploadingLetter, setWarrantyEditForm,
    showArchive, showBalanceDetails, showBrigadeForm, showDocForm, showForm, showKS2, showLetterForm,
    showPreview, staff, submitAiTaskReport, supervisorActs, supplierInvoices,
    tbJournal, tbl, tblC, tblH, toNum, toggleChecklistItem, updateAiFinding,
    updateAiTask, updateStage, uploadPhoto, uploadingDoc, uploadingLetter,
    user, users, visibleEstimatesForCurrentUser, visibleProjects, warrantyDefects, warrantyEditForm,
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
  const currentUser = user || {};
  const currentRole = currentUser.role || '';
  const isLeadershipUser = typeof isLeadership === 'function' ? isLeadership() : Boolean(isLeadership);
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);

  return (
<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                {isLeadershipUser&&<button onClick={()=>{setShowForm(showForm===true?false:true);setEditingItem(null);setNewProject(createProjectForm());}} style={btnO}><Plus size={14}/>Новый проект</button>}
                {projects.some(pr=>pr.archived)&&<button onClick={()=>setShowArchive(!showArchive)} style={btnG}><Archive size={14}/>{showArchive?'Активные':'Архив'}</button>}
              </div>
            </div>
            {showArchive&&<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{margin:0,color:C.text,fontSize:'12px'}}>📦 <b>Архив закрытых объектов.</b> Здесь хранятся завершённые объекты со всеми документами, перепиской и актами только для просмотра.</p></div>}
            {showForm===true&&isLeadershipUser&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
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
              const cat=shouldRenderProjectOverview&&isFinanceUser?expByCategory(p.name):{};
              const economy=shouldRenderProjectOverview&&isFinanceUser?projectEconomy(p):null;
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
                  canSeeFinance={isFinanceUser}
                  canManage={isLeadershipUser}
                  onToggle={async()=>{if(isOpen){setExpandedProject(null);}else{setExpandedProject(p.id);setActiveProjectTab('Общее');if(user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&!projectAiSummaries[p.name]){try{const r=await fetch(API+'/project-ai-summary/'+encodeURIComponent(p.name));const d=await r.json();if(d&&d.exists)setProjectAiSummaries(prev=>({...prev,[p.name]:d}));}catch(e){}}}}}
                  onEdit={()=>editProject(p)}
                />
                {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border}}>
                  <div style={{borderBottom:'1.5px solid '+C.border,backgroundColor:C.bg,padding:'18px 16px 10px'}}>
                    <ProjectTabsNav
                      C={C}
                    role={currentRole}
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
                        submitAiTaskReport={submitAiTaskReport}
                        toNum={toNum}
                        updateAiFinding={updateAiFinding}
                        updateAiTask={updateAiTask}
                        uploadPhoto={uploadPhoto}
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

                    {activeProjectTab==='Изменения к смете'&&(
                      <ProjectEstimateChangesTab ctx={ctx} project={p} />
                    )}

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
                        showLeadership={isLeadershipUser}
                        brigadeCoef={brigadeCoef}
                        setBrigadeCoef={setBrigadeCoef}
                        showFinance={isFinanceUser}
                        companyRequisites={companyRequisites}
                        companyName={companyName}
                        normalizeMeasure={normalizeMeasure}
                        toNum={toNum}
                        fmtMeasure={fmtMeasure}
                        userName={currentUser.name || ''}
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
                    {activeProjectTab==='Материалы'&&(
                      <ProjectMaterialsTab ctx={ctx} project={p} projectJournalDiagnostics={projectJournalDiagnostics} />
                    )}

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
                        isFinanceRole={isFinanceUser}
                        isLeadership={isLeadershipUser}
                        inp={inp}
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
                        showDelete={isLeadershipUser}
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
                      projectId={p.id}
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
