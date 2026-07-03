import React from 'react';

export default function ProjectsPage({ ctx }) {
  const {
    API, Archive, Bot, C, CHECKLIST_TEMPLATES, Calculator, Check, ChevronDown,
    ChevronUp, DIRECTOR_MAP_FEATURE_ENABLED, DOOR_PURPOSES, DOOR_TYPES, EMPTY_ESTIMATE_CHANGE, ESTIMATE_CHANGE_TYPES, ESTIMATE_CHANGE_VISIBLE_STATUSES, ESTIMATE_PACKAGES,
    EXPENSE_CATEGORIES, Edit2, Eye, FileText, FolderKanban, GitBranch, MapPin, PROJECT_MEASUREMENT_DOC_TYPES,
    PROJECT_MEASUREMENT_SOURCE_TYPES, PROJECT_MEASUREMENT_STATUSES, Package, PhotoAttachmentField, Plus, ProjectBrigadeCalculationTab, ProjectCardHeader, ProjectDirectorMapPanel,
    ProjectDocumentsRegistryPanel, ProjectEconomyPanel, ProjectFinancePanel, ProjectHiddenWorksActsPanel, ProjectLaunchPanel, ProjectLettersPanel, ProjectMaterialsControlPanel, ProjectMaterialsStockPanel,
    ProjectMaterialsTransferPanel, ProjectObjectLinksPanel, ProjectPrescriptionsPanel, ProjectSafetyJournalPanel, ProjectScheduleSummaryPanel, ProjectTabsNav, ProjectWorkJournalPanel, QrCode,
    REVEAL_MATERIALS, STAGE_STATUSES, ScrollText, Search, TB_INSTRUCTIONS, TB_TYPES_GOST, Trash2, UNITS,
    Upload, WINDOW_TYPES, X, _normalizeUnit, _sectionsOfEst, acceptMaterialAliasTask, accountablePayments, activeEstimatesForProject,
    activeProjectTab, activeTabGroup, addTask, aiFindingsForProject, aiSeverityMeta, aiTasksForProject, appendPhotos, approveUnexpectedWork,
    badge, brigadeCoef, brigadeContractItems, brigadeContracts, brigadePayments, btnB, btnG, btnGr,
    btnO, btnR, buildCableJournalContent, buildHiddenActContent, buildJPRContent, buildKS3Content, buildM15Content, buildMaterialInspectionContent,
    buildMaterialRequirementContent, buildPassportContent, buildSupplementaryAgreementContent, buildTBContent, cableJournal, cableTypeOf, calcDoorArea, calcDoorReveals,
    calcWindowArea, calcWindowReveals, card, checklistItems, checklists, companyName, companyRequisites, convertUnits,
    createBatchSupplyRequestFromMaterialControl, createProjectMeasurementActions, customRoomTypes, deleteBrigadePayment, deleteDoor, deleteRoom, deleteStage, deleteWindow,
    denormalizeMeasure, directorMapActionTarget, directorMapContractForProject, draftRoomDoors, draftRoomWindows, editProject, editingDoor, editingItem,
    editingWindow, estimateChangesForNewEstimate, estimateImportedPlanMeasure, estimateItemOptionsForProject, estimateItemTotal, estimateKind, estimateMaterialPlanIssue, estimatePackage,
    estimateReconciliationsForProject, estimateSearch, estimateWorkNormRequirementRows, estimatesList, expByCategory, expandedProject, expandedRoom, fileSrc,
    fmtMeasure, formatSignedRub, generateAiFindingsForProject, getActStatusForJournal, getRoomNetWall, hiddenActs, history, includableEstimateChanges,
    includeChangesInNewEstimate, inp, inspectionOrders, isApprovedEstimateChangeStatus, isEstimateMaterialItem, isEstimatePricelist, isEstimateWorkItem, isFinanceRole,
    isLeadership, isMobile, isProrab, listSearch, loadAll, loadChecklistItems, loadProjectChat, loadWorkJournalPage,
    manualExpenses, masterProfiles, matchSearch, materialControlStatus, materialControlSummaryForProject, materialInspections, materialNameKey, materialNormControlSummaryForProject,
    materialReconciliationRows, materialTransfers, materials, measurementDraftLoadingId, measurementRoomDrafts, mobileExpandedRenderLists, navigateTo, newAccountable,
    newBrigadeContract, newBrigadeItem, newChecklist, newChecklistItem, newDoor, newInspOrder, newLetter, newMeasurementDoc,
    newParticipant, newPrescription, newProject, newProjectDoc, newRoom, newStage, newTask, newTbEntry,
    newTransfer, newUnexpected, newWarrantyDefect, newWindow, normalizeMeasure, openAiTaskAction, openBrigadeContract, openConfirmModal,
    openEstimateDetail, ownExpenses, parseAiTaskPayload, prescriptionsList, pricelists, projectAiSummaries, projectBudgetSpent, projectChatMessage,
    projectChatMessages, projectDocuments, projectEconomy, projectLetters, projectMeasurements, projectObjectLinks, projectPaymentInAmount, projectPaymentSignedAmount,
    projectPayments, projectPlanDone, projectRealProgress, projectStages, projects, refreshData, removeTask, renderEstimateChangeReconcileTask,
    renderEstimateMeasurementComparisonPanel, renderEstimateReconciliationsPanel, renderMaterialAliasControls, renderMaterialSupplyAction, renderWorkJournalEstimateReconciliationPanel, roleColor, roomCompleteness, roomDoors,
    roomWindows, rooms, saveChecklist, saveDoor, savePrescription, saveProject, saveProjectStage, saveRoom,
    saveTbEntry, saveUnexpectedWork, saveWindow, selectedBrigadeContract, selectedChecklist, sendProjectChatMessage, setActiveProjectTab, setActiveTabGroup,
    setAddExpenseProject, setBrigadeCoef, setBrigadeContractItems, setBrigadeContracts, setBrigadePayments, setDraftRoomDoors, setDraftRoomWindows, setEditingAct,
    setEditingCable, setEditingDoor, setEditingInspection, setEditingItem, setEditingJournal, setEditingWindow, setEstimateSearch, setExpandedProject,
    setExpandedRoom, setHiddenActs, setListSearch, setMaterialTransfers, setMaterials, setMeasurementDraftLoadingId, setMobileExpandedRenderLists, setNewAccountable,
    setNewBrigadeContract, setNewBrigadeItem, setNewBrigadePayment, setNewChecklist, setNewChecklistItem, setNewDoor, setNewInspOrder, setNewLetter,
    setNewManualExpense, setNewMeasurementDoc, setNewParticipant, setNewPrescription, setNewProject, setNewProjectDoc, setNewRoom, setNewStage,
    setNewTask, setNewTbEntry, setNewTransfer, setNewUnexpected, setNewWarrantyDefect, setNewWindow, setProjectAiSummaries, setProjectChatMessage,
    setRejectingEntry, setRoomDoors, setRoomWindows, setSelectedBrigadeContract, setSelectedChecklist, setShowAccountableForm, setShowArchive, setShowBalanceDetails,
    setShowBrigadeForm, setShowBrigadePayModal, setShowDocForm, setShowForm, setShowJournalTableModal, setShowLetterForm, setShowMeasurementForm, setShowPhotoModal,
    setShowQRModal, setShowRoomForm, setShowTransferForm, setUploadingDoc, setUploadingLetter, setUploadingMeasurementDoc, setWarehouseMain, setWarrantyEditForm,
    showArchive, showBalanceDetails, showBrigadeForm, showDocForm, showForm, showKS2, showLetterForm, showMeasurementForm,
    showPreview, showRoomForm, showTransferForm, signedEstimateChangeTotal, staff, supervisorActs, supplierInvoices, supplyRequests,
    tbJournal, tbl, tblC, tblH, toNum, toggleChecklistItem, unexpectedWorksList, updateAiFinding,
    updateAiTask, updateDoor, updateStage, updateWindow, uploadPhoto, uploadingDoc, uploadingLetter, uploadingMeasurementDoc,
    user, users, visibleActiveProjects, visibleEstimatesForCurrentUser, visibleProjects, warehouseMain, warrantyDefects, warrantyEditForm,
    weatherLog, workExecutionTotal, workJournal, workJournalPage,
  } = ctx;

  return (
<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                {isLeadership()&&<button onClick={()=>{setShowForm(showForm===true?false:true);setEditingItem(null);setNewProject({name:'',client:'',status:'Планирование',budget:'',deadline:'',progress:0,tasks:[],pricelistId:null});}} style={btnO}><Plus size={14}/>Новый проект</button>}
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
	                    {activeProjectTab==='Общее'&&(<div>
		                      {isFinanceRole()&&(<div style={{display:'grid',gridTemplateColumns:isMobile?'repeat(2,minmax(0,1fr))':'1fr 1fr 1fr',gap:isMobile?'8px':'12px',marginBottom:'16px'}}>
		                        {EXPENSE_CATEGORIES.map(c=>(<div key={c.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'10px',border:'1.5px solid '+C.border}}><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>{c.label}</p><b style={{fontSize:'14px',color:c.color}}>{(cat[c.id]||0).toLocaleString()+' ₽'}</b></div>))}
		                      </div>)}
		                      {isFinanceRole()&&<ProjectEconomyPanel C={C} card={card} btnB={btnB} btnG={btnG} btnO={btnO} project={p} economy={economy} isMobile={isMobile} onOpenFinance={()=>setActiveProjectTab('Финансы')} onOpenJournal={()=>setActiveProjectTab('Производство работ')} onOpenMaterials={()=>setActiveProjectTab('Материалы')} onOpenEstimate={()=>setActiveProjectTab('Смета')} showPreview={showPreview} />}
		                      {(()=>{const linksKey=['project-object-links',p.id||p.name].join(':');const showLinks=!isMobile||mobileExpandedRenderLists[linksKey];if(!showLinks){return(<div style={{...card,padding:'14px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                                <div>
                                  <b style={{color:C.text,fontSize:'14px'}}>🧭 Связи объекта</b>
                                  <p style={{margin:'4px 0 0',color:C.textSec,fontSize:'12px',lineHeight:1.4}}>Сметы, журналы, материалы и документы загружаются по запросу.</p>
                                </div>
                                <button type="button" onClick={()=>setMobileExpandedRenderLists(prev=>({...prev,[linksKey]:true}))} style={{...btnB,padding:'8px 12px',fontSize:'12px'}}>Показать</button>
                              </div>
                            </div>);}return <ProjectObjectLinksPanel C={C} card={card} items={projectObjectLinks(p)} isMobile={isMobile} onOpen={(tab)=>tab&&setActiveProjectTab(tab)} />;})()}
		                      {(()=>{const wj=(workJournal||[]).filter(w=>w.project===p.name);const pending=wj.filter(w=>!w.status||w.status==='На проверке'||w.status==='Автоматически из сметы');const confirmed=wj.filter(w=>w.status==='Подтверждено');const rejected=wj.filter(w=>w.status==='Отклонено');const last7=wj.filter(w=>{if(!w.date) return false;const d=new Date(w.date);return (Date.now()-d.getTime())<7*24*3600*1000;});const sumConfirmed=confirmed.reduce((s,w)=>s+workExecutionTotal(w),0);return(<div style={{...card,padding:'14px',marginBottom:'12px',backgroundColor:pending.length>0?C.warningLight:C.bg,border:'1.5px solid '+(pending.length>0?C.warningBorder:C.border)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px',flexWrap:'wrap',gap:'8px'}}>
                          <b style={{color:C.text,fontSize:'13px'}}>👷 Работы от мастеров {pending.length>0&&<span style={{padding:'2px 8px',borderRadius:'8px',backgroundColor:C.warning,color:'white',fontSize:'11px',marginLeft:'4px'}}>{pending.length+' на проверке'}</span>}</b>
                          <button onClick={()=>setActiveProjectTab('Производство работ')} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>📜 Открыть журнал</button>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'8px'}}>
                          <div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>За 7 дней</p><b style={{color:C.text,fontSize:'15px'}}>{last7.length}</b></div>
                          <div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>Подтверждено</p><b style={{color:C.success,fontSize:'15px'}}>{confirmed.length}</b></div>
                          <div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>На проверке</p><b style={{color:C.warning,fontSize:'15px'}}>{pending.length}</b></div>
                          {rejected.length>0&&<div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>Отклонено</p><b style={{color:C.danger,fontSize:'15px'}}>{rejected.length}</b></div>}
	                          {isFinanceRole()&&<div style={{padding:'8px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,gridColumn:'span 2'}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 2px'}}>К оплате исполнителям</p><b style={{color:C.accent,fontSize:'15px'}}>{Math.round(sumConfirmed).toLocaleString('ru-RU')+' ₽'}</b></div>}
                        </div>
                      </div>);})()}
                      <div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}>
                        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'12px'}}>📊 Бригады и выполнение</b>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Бригад</p><b style={{color:C.text,fontSize:'18px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).length}</b></div>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>По договорам</p><b style={{color:C.accent,fontSize:'16px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).reduce((s,bc)=>s+Number(bc.totalAmount||0),0).toLocaleString()+' ₽'}</b></div>
                          <div style={{textAlign:'center'}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Смет</p><b style={{color:C.text,fontSize:'18px'}}>{visibleEstimatesForCurrentUser(estimatesList).filter(e=>e.projectName===p.name||Number(e.projectId)===Number(p.id)).length}</b></div>
                        </div>
                        <div style={{marginBottom:'12px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
                            <b style={{fontSize:'12px',color:C.text}}>Выполнение работ бригадами</b>
                            <span style={{fontSize:'12px',color:C.textSec}}>{(()=>{
                              const pBrigades=brigadeContracts.filter(bc=>bc.projectName===p.name);
                              if(!pBrigades.length) return '0%';
                              const totalSmeta=pBrigades.reduce((s,bc)=>s+Number(bc.totalAmount||0),0);
                              const totalDone=pBrigades.reduce((s,bc)=>s+Number(bc.doneAmount||0),0);
                              return totalSmeta>0?Math.min(100,Math.round(totalDone/totalSmeta*100))+'%':'0%';
                            })()}</span>
                          </div>
                          <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}>
                            <div style={{backgroundColor:C.success,width:(()=>{const pBrigades=brigadeContracts.filter(bc=>bc.projectName===p.name);const totalSmeta=pBrigades.reduce((s,bc)=>s+Number(bc.totalAmount||0),0);const totalDone=pBrigades.reduce((s,bc)=>s+Number(bc.doneAmount||0),0);return Math.min(100,totalSmeta>0?Math.round(totalDone/totalSmeta*100):0)+'%';})(),height:'100%',borderRadius:'6px'}}/>
                          </div>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(2,1fr)',gap:'10px'}}>
                          <div style={{backgroundColor:C.successLight,padding:'10px',borderRadius:'8px',border:'1px solid '+C.successBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Смета заказчика</p><b style={{color:C.success,fontSize:'14px'}}>{Math.round(projectPlanDone(p).plan).toLocaleString('ru-RU')+' ₽'}</b></div>
                          <div style={{backgroundColor:C.warningLight,padding:'10px',borderRadius:'8px',border:'1px solid '+C.warningBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Подрядчикам</p><b style={{color:C.warning,fontSize:'14px'}}>{brigadeContracts.filter(bc=>bc.projectName===p.name).reduce((s,bc)=>s+Number(bc.totalAmount||0),0).toLocaleString()+' ₽'}</b></div>
                        </div>
                      </div>
                      <div style={{backgroundColor:C.bg,borderRadius:'10px',padding:'14px',border:'1.5px solid '+C.border,marginBottom:'12px'}}>
                        {isFinanceRole()&&(<><div style={{display:'flex',justifyContent:'space-between',marginBottom:'8px'}}><b style={{color:C.text,fontSize:'13px'}}>Прогресс бюджета</b><span style={{fontSize:'13px',color:total>p.budget?C.danger:C.success}}>{Math.round(total).toLocaleString('ru-RU')+' из '+p.budget.toLocaleString()+' ₽'}</span></div>
                        <div style={{backgroundColor:C.bgGray,borderRadius:'6px',height:'10px'}}><div style={{backgroundColor:total>p.budget?C.danger:total>p.budget*0.8?C.warning:C.success,width:Math.min(100,p.budget>0?total/p.budget*100:0)+'%',height:'100%',borderRadius:'6px',transition:'width 0.3s'}}/></div>
                        <div style={{display:'flex',gap:'12px',flexWrap:'wrap',marginTop:'8px',fontSize:'11px',color:C.textSec}}>
                          <span>🔨 Работы/Бригады: <b style={{color:C.text}}>{Math.round(_bs.works).toLocaleString('ru-RU')+' ₽'}</b></span>
                          <span>📦 Материалы: <b style={{color:C.text}}>{Math.round(_bs.materials).toLocaleString('ru-RU')+' ₽'}</b></span>
                          {_bs.unexpected>0&&<span>🆕 Изменения к смете: <b style={{color:C.warning}}>{Math.round(_bs.unexpected).toLocaleString('ru-RU')+' ₽'}</b></span>}
                          {_bs.other>0&&<span>⚙️ Прочие затраты: <b style={{color:C.text}}>{Math.round(_bs.other).toLocaleString('ru-RU')+' ₽'}</b></span>}
                        </div>
                        <p style={{margin:'6px 0 0',fontSize:'10px',color:C.textMuted,fontStyle:'italic'}}>Себестоимость = всё что мы потратили (наши затраты), а не бюджет заказчика</p></>)}
                      </div>
                      <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginBottom:'16px'}}>
                        <button onClick={()=>showPreview(buildPassportContent(p),'Паспорт объекта — '+p.name)} style={btnB}><FileText size={14}/>Паспорт</button>
                        <button onClick={()=>showKS2(p)} style={btnG}><FileText size={14}/>КС-2</button>
                        <button onClick={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)} style={btnG}><FileText size={14}/>КС-3</button>
                        <button onClick={()=>showPreview(buildJPRContent(p.name),'ЖПР — '+p.name)} style={btnG}><ScrollText size={14}/>ЖПР</button>
                        <button onClick={()=>setShowQRModal({title:'QR — '+p.name,data:window.location.origin+'/?project='+encodeURIComponent(p.name)})} style={btnG}><QrCode size={14}/>QR</button>
                      </div>
                      <div>
                        <b style={{color:C.text,fontSize:'13px'}}>Задачи:</b>
                        {isLeadership()&&<div style={{display:'flex',gap:'8px',marginTop:'8px',marginBottom:'10px'}}>
                          <input placeholder="Новая задача..." value={newTask} onChange={e=>setNewTask(e.target.value)} onKeyDown={e=>e.key==='Enter'&&addTask(p)} style={{...inp,marginBottom:0,flex:1,fontSize:'13px'}}/>
                          <button onClick={()=>addTask(p)} style={btnO}><Plus size={14}/></button>
                        </div>}
                        {(p.tasks||[]).map((t,i)=>(<div key={i} style={{display:'flex',justifyContent:'space-between',alignItems:'center',padding:'8px 10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><span style={{fontSize:'13px',color:C.text}}>{'• '+t}</span>{isLeadership()&&<button onClick={()=>removeTask(p,i)} style={{...btnR,padding:'3px 7px',fontSize:'10px'}}><X size={10}/></button>}</div>))}
                      </div>

                      {user&&['директор','зам_директора','бухгалтер','прораб'].includes(user.role)&&(()=>{
                        const smetaItems=activeEstimatesForProject(p,'Заказчик').flatMap(est=>(_sectionsOfEst(est)||[]).flatMap(s=>(s.items||[]).map(i=>({...i,section:s.name,workPackage:estimatePackage(est)}))));
                        const norm=(s)=>(s||'').toLowerCase().replace(/[.,;:()«»"'-]/g,' ').replace(/\s+/g,' ').trim();
                        const matchScore=(a,b)=>{const aw=norm(a).split(' ').filter(w=>w.length>=3);const bw=new Set(norm(b).split(' ').filter(w=>w.length>=3));if(!aw.length||!bw.size) return 0;const common=aw.filter(w=>bw.has(w)).length;return common/Math.max(aw.length,1);};
                        const projMaterials=materials.filter(m=>m.project===p.name);
                        const projTransfers=materialTransfers.filter(t=>t.projectName===p.name);
                        const workProgress=smetaItems.filter(it=>isEstimateWorkItem(it,it.section)).map(it=>{
                          const plan=Number(it.quantity||0);
                          const done=Number(it.doneQuantity||0);
                          const left=Math.max(0,plan-done);
                          const pct=plan>0?Math.min(100,Math.round(done/plan*100)):0;
                          return {name:it.name,section:it.section,unit:it.unit,plan,done,left,pct};
                        });
                        const matPlan=smetaItems.filter(i=>isEstimateMaterialItem(i,i.section)&&!estimateMaterialPlanIssue(i,i.section)&&toNum(estimateImportedPlanMeasure(i).qty)>0).map(it=>{
                          const planMeasure=estimateImportedPlanMeasure(it);
                          const plan=toNum(planMeasure.qty);
                          const bought=projMaterials.filter(m=>matchScore(m.name,it.name)>=0.4).reduce((s,m)=>s+Number(m.quantity||0),0);
                          return {name:it.name,unit:planMeasure.unit||it.unit,plan,bought,need:Math.max(0,plan-bought)};
                        });
                        const fmt=(n)=>Number(n||0).toLocaleString('ru-RU');
                        const payload={
                          project:p.name,
                          total:smetaItems.reduce((s,i)=>s+estimateItemTotal(i),0),
                          workProgress:workProgress.filter(w=>w.plan>0),
                          materials:matPlan,
                          stock:projMaterials.map(m=>({name:m.name,qty:Number(m.quantity||0),unit:m.unit})),
                          transfers:projTransfers.slice(0,20).map(t=>({name:t.materialName,qty:Number(t.quantity||0),unit:t.unit,to:t.toPerson,date:t.transferDate}))
                        };
                        const payloadStr=JSON.stringify(payload);
                        let _h=0;for(let i=0;i<payloadStr.length;i++){_h=((_h*31)+payloadStr.charCodeAt(i))|0;}
                        const currentHash=(_h>>>0).toString(16);
                        const cached=projectAiSummaries[p.name];
                        const isFresh=cached&&cached.payloadHash===currentHash;
                        const fmtAgo=(iso)=>{if(!iso) return '';const d=new Date(iso);const m=Math.floor((Date.now()-d.getTime())/60000);if(m<1) return 'только что';if(m<60) return m+' мин назад';const h=Math.floor(m/60);if(h<24) return h+' ч назад';return Math.floor(h/24)+' дн назад';};
                        const runAiSummary=async()=>{
                          const prompt='Объект "'+p.name+'". Проанализируй прогресс и материальный учёт. Данные ниже.\n\n'+JSON.stringify(payload,null,1)+'\n\nОТВЕТЬ СТРОГО JSON (без markdown):\n{\n  "summary":"одна-две фразы общего впечатления",\n  "progress":[{"what":"что","status":"в норме|отставание|опережение","note":"что заметил"}],\n  "materials":[{"what":"материал","problem":"нехватка|избыток|пропажа|норма","action":"что сделать","amount":число_или_0}],\n  "alerts":[{"type":"критично|внимание|совет","text":"что"}]\n}\nИспользуй только данные из payload. Если данных мало — пиши "недостаточно данных".';
                          // Показываем загрузку прямо в карточке (без открытия панели чата)
                          setProjectAiSummaries(prev=>({...prev,[p.name]:{...(prev[p.name]||{}),loading:true}}));
                          try{
                            const res=await fetch(API+'/ai-chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({messages:[{role:'user',content:prompt}],jsonOnly:true})});
                            const data=await res.json();
                            const raw=(data.response||data.error||'').trim();
                            let parsed=null;
                            try{const clean=raw.replace(/^```(?:json)?/i,'').replace(/```$/,'').trim();const s=clean.indexOf('{'),e=clean.lastIndexOf('}');if(s>=0&&e>s) parsed=JSON.parse(clean.slice(s,e+1));}catch(e){}
                            let out;
                            if(parsed){
                              const ln=[];
                              if(parsed.summary) ln.push('📋 '+parsed.summary,'');
                              if(Array.isArray(parsed.alerts)&&parsed.alerts.length){ln.push('🚨 ВНИМАНИЕ');parsed.alerts.forEach((a,n)=>ln.push((n+1)+'. ['+(a.type||'')+'] '+(a.text||'')));ln.push('');}
                              if(Array.isArray(parsed.progress)&&parsed.progress.length){ln.push('🔨 РАБОТЫ');parsed.progress.forEach((q,n)=>ln.push((n+1)+'. '+(q.what||'?')+' — '+(q.status||'?')+(q.note?': '+q.note:'')));ln.push('');}
                              if(Array.isArray(parsed.materials)&&parsed.materials.length){ln.push('📦 МАТЕРИАЛЫ');parsed.materials.forEach((m,n)=>ln.push((n+1)+'. '+(m.what||'?')+' — '+(m.problem||'?')+(m.action?' → '+m.action:'')+(m.amount?' ('+fmt(m.amount)+')':'')));}
                              out=ln.join('\n');
                            }else out=raw||'Ошибка ответа ИИ';
                            try{await fetch(API+'/project-ai-summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,payloadHash:currentHash,summary:out})});}catch(e){}
                            setProjectAiSummaries(prev=>({...prev,[p.name]:{exists:true,payloadHash:currentHash,summary:out,updatedAt:new Date().toISOString(),loading:false}}));
                          }catch(e){
                            setProjectAiSummaries(prev=>({...prev,[p.name]:{...(prev[p.name]||{}),loading:false,error:'Ошибка соединения с AI'}}));
                          }
                        };
                        return(<div style={{...card,padding:'16px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.accentBorder}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'14px'}}>📊 Контроль объекта</b>
                            <button onClick={runAiSummary} disabled={cached&&cached.loading} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',fontSize:'12px',opacity:(cached&&cached.loading)?0.6:1}}><Bot size={13}/>{cached&&cached.loading?'AI думает...':cached&&cached.summary?'Обновить ИИ':'AI-сводка'}</button>
                          </div>
                          {cached&&cached.loading&&(<div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,textAlign:'center'}}>
                            <p style={{margin:0,fontSize:'13px',color:C.info}}>⏳ AI анализирует объект... (15-40 сек)</p>
                          </div>)}
                          {cached&&cached.error&&(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:C.dangerLight,border:'1.5px solid '+C.dangerBorder}}>
                            <p style={{margin:0,fontSize:'13px',color:C.danger}}>❌ {cached.error}</p>
                          </div>)}
                          {cached&&cached.summary&&!cached.loading&&(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:isFresh?C.successLight:C.warningLight,border:'1.5px solid '+(isFresh?C.successBorder:C.warningBorder)}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px'}}>
                              <b style={{fontSize:'12px',color:isFresh?C.success:C.warning}}>🤖 {isFresh?'AI-сводка актуальна':'⚠️ Данные изменились — нужно обновить'}</b>
                              <span style={{fontSize:'11px',color:C.textSec}}>{fmtAgo(cached.updatedAt)}</span>
                            </div>
                            <div style={{fontSize:'12px',color:C.text,whiteSpace:'pre-wrap',lineHeight:'1.5'}}>{cached.summary}</div>
                          </div>)}
                          {(!cached||(!cached.summary&&!cached.loading&&!cached.error))&&<p style={{fontSize:'12px',color:C.textMuted,marginBottom:'12px',padding:'8px',backgroundColor:C.bg,borderRadius:'8px'}}>💡 AI-сводка ещё не делалась. Нажмите «AI-сводка» — анализ сохранится в системе.</p>}
                          {smetaItems.length===0&&<p style={{color:C.textMuted,fontSize:'12px',padding:'10px',textAlign:'center'}}>У объекта нет сметы — нечего сравнивать. Добавьте смету в разделе «Сметы».</p>}
                          {smetaItems.length>0&&(<>
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📋 Прогресс по смете (работы)</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Позиция</th><th style={tblH}>План</th><th style={tblH}>Выполнено</th><th style={tblH}>Осталось</th><th style={tblH}>%</th></tr></thead><tbody>
                              {workProgress.filter(w=>w.plan>0).slice(0,15).map((w,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{w.name}</td><td style={{...tblC,fontSize:'11px'}}>{fmtMeasure(w.plan,w.unit)}</td><td style={{...tblC,fontSize:'11px',color:w.done>0?C.success:C.textMuted}}>{fmtMeasure(w.done,w.unit)}</td><td style={{...tblC,fontSize:'11px',color:w.left>0?C.warning:C.success}}>{fmtMeasure(w.left,w.unit)}</td><td style={{...tblC,fontSize:'11px',fontWeight:'600',color:w.pct>=100?C.success:w.pct>=50?C.info:C.warning}}>{w.pct}%</td></tr>))}
                            </tbody></table>
                            {!workProgress.filter(w=>w.plan>0).length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>В смете нет позиций работ</p>}
                          </div>
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📥 Материалы — план vs закуплено</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>По смете</th><th style={tblH}>Закуплено</th><th style={tblH}>Не хватает</th></tr></thead><tbody>
                              {matPlan.slice(0,15).map((m,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{m.name}</td><td style={{...tblC,fontSize:'11px'}}>{m.plan} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:m.bought>=m.plan?C.success:C.info}}>{m.bought} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:m.need>0?C.danger:C.success}}>{m.need>0?m.need+' '+m.unit:'✅'}</td></tr>))}
                            </tbody></table>
                            {!matPlan.length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>В смете нет материалов</p>}
                          </div>
                          </>)}
                          <div style={{marginBottom:'14px'}}>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>📤 Выдачи мастерам ({projTransfers.length})</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Кол-во</th><th style={tblH}>Кому</th><th style={tblH}>Дата</th></tr></thead><tbody>
                              {projTransfers.slice(0,10).map((t,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{t.materialName}</td><td style={{...tblC,fontSize:'11px'}}>{t.quantity} {t.unit}</td><td style={{...tblC,fontSize:'11px'}}>{t.toPerson}</td><td style={{...tblC,fontSize:'11px'}}>{t.transferDate}</td></tr>))}
                            </tbody></table>
                            {!projTransfers.length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>Передач ещё не было</p>}
                          </div>
                          <div>
                            <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>🏬 Остатки на складе объекта ({projMaterials.filter(m=>Number(m.quantity||0)>0).length})</b>
                            <table style={{...tbl,fontSize:'11px'}}><thead><tr><th style={tblH}>Материал</th><th style={tblH}>Остаток</th><th style={tblH}>Категория</th></tr></thead><tbody>
                              {projMaterials.filter(m=>Number(m.quantity||0)>0).slice(0,15).map((m,i)=>(<tr key={i}><td style={{...tblC,fontSize:'11px'}}>{m.name}</td><td style={{...tblC,fontSize:'11px',fontWeight:'600',color:C.success}}>{m.quantity} {m.unit}</td><td style={{...tblC,fontSize:'11px',color:C.textSec}}>{m.category||''}</td></tr>))}
                            </tbody></table>
                            {!projMaterials.filter(m=>Number(m.quantity||0)>0).length&&<p style={{color:C.textMuted,fontSize:'11px',padding:'8px'}}>Склад объекта пуст</p>}
                          </div>
                        </div>);
                      })()}

                  </div>)}

                    {activeProjectTab==='ИИ-контроль'&&(()=> {
                      const projectFindings = aiFindingsForProject(p.name);
                      const projectTasks = aiTasksForProject(p.name);
                      const standaloneTasks = projectTasks.filter(t=>!t.findingId);
                      const byCategory = projectFindings.reduce((acc,f)=>{const k=f.category||'Общее';if(!acc[k])acc[k]=[];acc[k].push(f);return acc;},{});
                      const importantCount = projectFindings.filter(f=>f.severity==='Критично'||f.severity==='Не хватает данных').length;
                      const canRunAiControl = user&&['директор','зам_директора','прораб','главный_инженер','сметчик','технадзор','стройконтроль'].includes(user.role);
                      const taskTypeMeta = (task) => {
                        const type = parseAiTaskPayload(task).type;
                        if (['material_purchase_review','material_outside_estimate_review','material_writeoff_review','material_norm_over_review','material_without_norm_review','material_transfer_sign_review'].includes(type)) return {key:'materials',label:'Материалы',icon:<Package size={13}/>,color:C.info,bg:C.infoLight,border:C.infoBorder};
                        if (['room_measurement_review','work_room_link_review'].includes(type)) return {key:'rooms',label:'Помещения',icon:<MapPin size={13}/>,color:C.success,bg:C.successLight,border:C.successBorder};
                        if (['estimate_quality_review','estimate_norm_review','material_norm_coverage'].includes(type)) return {key:'estimate',label:'Смета и нормы',icon:<Calculator size={13}/>,color:C.accent,bg:C.accentLight,border:C.accentBorder};
                        if (['estimate_diff_review','estimate_change_reconcile'].includes(type)) return {key:'changes',label:'Изменения к смете',icon:<GitBranch size={13}/>,color:C.warning,bg:C.warningLight,border:C.warningBorder};
                        return {key:'other',label:'Прочее',icon:<Eye size={13}/>,color:C.textSec,bg:C.bgGray,border:C.border};
                      };
                      const groupedStandaloneTasks = standaloneTasks.reduce((acc,task)=>{
                        const meta = taskTypeMeta(task);
                        if (!acc[meta.key]) acc[meta.key] = {meta,tasks:[]};
                        acc[meta.key].tasks.push(task);
                        return acc;
                      },{});
                      const standaloneTaskGroups = ['materials','rooms','estimate','changes','other'].map(k=>groupedStandaloneTasks[k]).filter(Boolean);
                      return (<div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
                          <div>
                            <b style={{color:C.text,fontSize:'15px'}}>🤖 ИИ-контроль объекта</b>
                            <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Фоновый контроль обмеров, ЖПР, смет, норм, материалов и поручений.</p>
                          </div>
                          <button onClick={()=>generateAiFindingsForProject(p.name)} disabled={!canRunAiControl} style={{...btnO,opacity:canRunAiControl?1:.55}}><Bot size={14}/>Обновить контроль</button>
                        </div>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(4,1fr)',gap:'10px',marginBottom:'14px'}}>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Открыто</p><b style={{color:C.text,fontSize:'20px'}}>{projectFindings.length}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:importantCount?C.warningLight:C.successLight,border:'1.5px solid '+(importantCount?C.warningBorder:C.successBorder)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Важные</p><b style={{color:importantCount?C.warning:C.success,fontSize:'20px'}}>{importantCount}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Поручения</p><b style={{color:C.accent,fontSize:'20px'}}>{projectTasks.length}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Категорий</p><b style={{color:C.text,fontSize:'20px'}}>{Object.keys(byCategory).length}</b></div>
                        </div>
                        {projectFindings.length===0&&standaloneTasks.length===0&&(<div style={{...card,padding:'18px',textAlign:'center',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}>
                          <b style={{color:C.success,fontSize:'14px'}}>Замечаний пока нет</b>
                          <p style={{color:C.textSec,fontSize:'12px',margin:'6px 0 12px'}}>Система обновляет контроль после ключевых событий, а эту кнопку можно использовать для ручного пересчёта.</p>
                          <button onClick={()=>generateAiFindingsForProject(p.name)} disabled={!canRunAiControl} style={{...btnGr,opacity:canRunAiControl?1:.55}}><Bot size={14}/>Обновить контроль</button>
                        </div>)}
                        {standaloneTasks.length>0&&(<div style={{...card,padding:'14px',marginBottom:'12px'}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',marginBottom:'10px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>Поручения</b>
                            <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{standaloneTasks.length}</span>
                          </div>
                          {standaloneTaskGroups.map(group=>(
                            <div key={group.meta.key} style={{marginBottom:'12px'}}>
                              <div style={{display:'flex',alignItems:'center',gap:'8px',margin:'0 0 8px',padding:'7px 9px',borderRadius:'10px',backgroundColor:group.meta.bg,border:'1.5px solid '+group.meta.border}}>
                                <span style={{color:group.meta.color,display:'inline-flex'}}>{group.meta.icon}</span>
                                <b style={{color:group.meta.color,fontSize:'12px'}}>{group.meta.label}</b>
                                <span style={badge(group.meta.color,group.meta.bg,group.meta.border)}>{group.tasks.length}</span>
                              </div>
                              {group.tasks.map(task=>{
                                const payload=parseAiTaskPayload(task);
                                const isEstimateTask=['estimate_quality_review','estimate_norm_review','material_norm_coverage','estimate_diff_review','estimate_change_reconcile'].includes(payload.type);
                                const isMaterialTask=['material_purchase_review','material_outside_estimate_review','material_writeoff_review','material_norm_over_review','material_without_norm_review','material_transfer_sign_review'].includes(payload.type);
                                const isRoomTask=['room_measurement_review','work_room_link_review'].includes(payload.type);
                                const aliasCandidate=payload.aliasCandidate||null;
                                const purchaseRow=payload.type==='material_purchase_review'
                                  ? materialReconciliationRows(payload.projectName||task.projectName||'').find(r=>materialNameKey(r.name)===materialNameKey(payload.materialName)&&(!payload.unit||_normalizeUnit(r.unit||'')===_normalizeUnit(payload.unit||'')))
                                  : null;
                                return (<div key={task.id} style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bg,border:'1.5px solid '+C.border,marginBottom:'8px'}}>
                                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                                    <div style={{flex:1,minWidth:'220px'}}>
                                      <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap',marginBottom:'5px'}}>
                                        <span style={badge(C.info,C.infoLight,C.infoBorder)}>{task.status||'Новое'}</span>
                                        <span style={{fontSize:'11px',color:C.textSec}}>{task.assignedRole?'кому: '+task.assignedRole:'без роли'}</span>
                                      </div>
                                      <b style={{display:'block',color:C.text,fontSize:'13px',lineHeight:1.35}}>{task.title}</b>
                                      {payload.type==='estimate_change_reconcile'
                                        ? renderEstimateChangeReconcileTask(task)
                                        : task.description&&<p style={{color:C.textSec,fontSize:'12px',margin:'6px 0 0',lineHeight:1.45,whiteSpace:'pre-wrap'}}>{task.description}</p>}
                                    </div>
                                    <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                      {aliasCandidate?.aliasName&&aliasCandidate?.canonicalName&&<button onClick={()=>acceptMaterialAliasTask(task)} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}><Check size={11}/>Привязать</button>}
                                      {purchaseRow&&toNum(purchaseRow.toBuy)>0&&renderMaterialSupplyAction(payload.projectName||task.projectName||'', purchaseRow)}
                                      {task.actionLabel&&<button onClick={()=>openAiTaskAction(task)} style={{...btnB,padding:'5px 9px',fontSize:'11px'}}>{payload.type==='estimate_diff_review'?<FileText size={11}/>:isEstimateTask?<Calculator size={11}/>:isMaterialTask?<Package size={11}/>:isRoomTask?<MapPin size={11}/>:<Eye size={11}/>} {task.actionLabel}</button>}
                                      {task.status==='Новое'&&<button onClick={()=>updateAiTask(task.id,{status:'Принято к исполнению'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Принять</button>}
                                      {['Новое','Принято к исполнению'].includes(task.status||'')&&<button onClick={()=>updateAiTask(task.id,{status:'В работе'})} style={{...btnO,padding:'5px 9px',fontSize:'11px'}}>В работу</button>}
                                      <button onClick={()=>updateAiTask(task.id,{status:'Закрыто'})} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}>Закрыть</button>
                                      <button onClick={()=>updateAiTask(task.id,{status:'Отклонено'})} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}>Отклонить</button>
                                    </div>
                                  </div>
                                </div>);
                              })}
                            </div>
                          ))}
                        </div>)}
                        {Object.entries(byCategory).map(([category,list])=>(
                          <div key={category} style={{...card,padding:'14px',marginBottom:'12px'}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',marginBottom:'10px'}}>
                              <b style={{color:C.text,fontSize:'13px'}}>{category}</b>
                              <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{list.length}</span>
                            </div>
                            {list.map(f=>{
                              const meta=aiSeverityMeta(f.severity);
                              const task=projectTasks.find(t=>Number(t.findingId)===Number(f.id));
                              return (<div key={f.id} style={{padding:'12px',borderRadius:'10px',backgroundColor:meta.bg,border:'1.5px solid '+meta.border,marginBottom:'8px'}}>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                                  <div style={{flex:1,minWidth:'220px'}}>
                                    <div style={{display:'flex',alignItems:'center',gap:'6px',flexWrap:'wrap',marginBottom:'5px'}}>
                                      <span style={badge(meta.color,meta.bg,meta.border)}>{f.severity||'Проверить'}</span>
                                      <span style={{fontSize:'11px',color:C.textSec}}>{f.assignedRole?'кому: '+f.assignedRole:'без роли'}{task&&task.status?' · '+task.status:''}</span>
                                    </div>
                                    <b style={{display:'block',color:C.text,fontSize:'13px',lineHeight:1.35}}>{f.title}</b>
                                    {f.description&&<p style={{color:C.textSec,fontSize:'12px',margin:'6px 0 0',lineHeight:1.45}}>{f.description}</p>}
                                    {f.suggestedAction&&<p style={{color:C.text,fontSize:'12px',margin:'6px 0 0'}}><b>Что сделать:</b> {f.suggestedAction}</p>}
                                  </div>
                                  <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                    {task&&task.status==='Новое'&&<button onClick={()=>updateAiTask(task.id,{status:'Принято к исполнению'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Принять</button>}
                                    {task&&['Новое','Принято к исполнению'].includes(task.status||'')&&<button onClick={()=>updateAiTask(task.id,{status:'В работе'})} style={{...btnO,padding:'5px 9px',fontSize:'11px'}}>В работу</button>}
                                    <button onClick={()=>updateAiFinding(f.id,{status:'Исправлено'})} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}>Исправлено</button>
                                    <button onClick={()=>updateAiFinding(f.id,{status:'Закрыто'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Закрыть</button>
                                    <button onClick={()=>updateAiFinding(f.id,{status:'Отклонено'})} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}>Отклонить</button>
                                  </div>
                                </div>
                              </div>);
                            })}
                          </div>
                        ))}
                      </div>);
                    })()}

                    {activeProjectTab==='Проект / Обмеры'&&(()=> {
                      const docs = (projectMeasurements||[]).filter(d=>d.projectName===p.name);
                      const drafts = (measurementRoomDrafts||[]).filter(d=>d.projectName===p.name);
                      const projectRooms = rooms.filter(r=>r.project===p.name);
                      const roomChecks = projectRooms.map(roomCompleteness);
                      const fullRooms = roomChecks.filter(x=>x.status==='Обмер полный').length;
                      const missingRooms = roomChecks.filter(x=>x.status==='Не хватает данных').length;
                      const acceptedDocs = docs.filter(d=>d.status==='Принято').length;
                      const reviewDocs = docs.filter(d=>d.status==='На проверке').length;
                      const pendingDrafts = drafts.filter(d=>d.status==='Черновик ИИ').length;
                      const acceptedDrafts = drafts.filter(d=>d.acceptedRoomId||d.status==='Принято').length;
                      const canEditMeasurements = user&&['директор','зам_директора','прораб','главный_инженер','сметчик'].includes(user.role);
                      const {
                        acceptRoomDraft,
                        deleteMeasurement,
                        generateRoomDrafts,
                        rejectRoomDraft,
                        saveMeasurement,
                        statusMeta,
                        updateMeasurement,
                      } = createProjectMeasurementActions({
                        API,
                        C,
                        newMeasurementDoc,
                        project: p,
                        refreshData,
                        setMeasurementDraftLoadingId,
                        setNewMeasurementDoc,
                        setShowMeasurementForm,
                        user,
                      });
                      return (<div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
                          <div>
                            <b style={{color:C.text,fontSize:'15px'}}>📐 Проект / Обмеры</b>
                            <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>Исходники объёмов: проект, экспликации, ведомости окон/дверей, ручные и фактические обмеры.</p>
                          </div>
                          {canEditMeasurements&&<button onClick={()=>setShowMeasurementForm(!showMeasurementForm)} style={btnO}><Plus size={14}/>Добавить источник</button>}
                        </div>

                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(auto-fit,minmax(130px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Исходников</p><b style={{color:C.text,fontSize:'20px'}}>{docs.length}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:acceptedDocs?C.successLight:C.bgWhite,border:'1.5px solid '+(acceptedDocs?C.successBorder:C.border)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Принято</p><b style={{color:acceptedDocs?C.success:C.text,fontSize:'20px'}}>{acceptedDocs}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:reviewDocs?C.warningLight:C.bgWhite,border:'1.5px solid '+(reviewDocs?C.warningBorder:C.border)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>На проверке</p><b style={{color:reviewDocs?C.warning:C.text,fontSize:'20px'}}>{reviewDocs}</b></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:pendingDrafts?C.infoLight:C.bgWhite,border:'1.5px solid '+(pendingDrafts?C.infoBorder:C.border)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Черновики ИИ</p><b style={{color:pendingDrafts?C.info:C.text,fontSize:'20px'}}>{pendingDrafts}</b><span style={{color:C.textMuted,fontSize:'11px',marginLeft:'6px'}}>принято {acceptedDrafts}</span></div>
                          <div style={{padding:'12px',borderRadius:'10px',backgroundColor:missingRooms?C.warningLight:C.successLight,border:'1.5px solid '+(missingRooms?C.warningBorder:C.successBorder)}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Помещения</p><b style={{color:missingRooms?C.warning:C.success,fontSize:'20px'}}>{fullRooms+'/'+projectRooms.length}</b></div>
                        </div>

                        {showMeasurementForm&&canEditMeasurements&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                          <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr 1fr',gap:'8px'}}>
                            <select value={newMeasurementDoc.sourceType} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,sourceType:e.target.value})} style={{...inp,marginBottom:0}}>{PROJECT_MEASUREMENT_SOURCE_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                            <select value={newMeasurementDoc.docType} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,docType:e.target.value})} style={{...inp,marginBottom:0}}>{PROJECT_MEASUREMENT_DOC_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                            <select value={newMeasurementDoc.status} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,status:e.target.value})} style={{...inp,marginBottom:0}}>{PROJECT_MEASUREMENT_STATUSES.map(t=><option key={t}>{t}</option>)}</select>
                            <input placeholder="Название / лист / файл" value={newMeasurementDoc.title} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,title:e.target.value})} style={{...inp,marginBottom:0}}/>
                            <input placeholder="Создано помещений" type="number" min="0" inputMode="numeric" value={newMeasurementDoc.roomsCreated} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,roomsCreated:e.target.value})} style={{...inp,marginBottom:0}}/>
                            <label style={{...btnG,cursor:'pointer',justifyContent:'center',margin:0}}>
                              <Upload size={14}/>{uploadingMeasurementDoc?'Загрузка...':(newMeasurementDoc.fileUrl?'Файл загружен':'Загрузить файл')}
                              <input type='file' accept='.pdf,.doc,.docx,.xls,.xlsx,image/*' style={{display:'none'}} onChange={async e=>{const f=e.target.files[0];if(!f)return;setUploadingMeasurementDoc(true);const url=await uploadPhoto(f,{projectName:p.name,context:'project-measurements'});setUploadingMeasurementDoc(false);if(url)setNewMeasurementDoc(prev=>({...prev,fileUrl:url,title:prev.title||f.name}));}}/>
                            </label>
                          </div>
                          <div style={{marginTop:'8px'}}>
                            <PhotoAttachmentField
                              C={C}
                              btnG={btnG}
                              value={newMeasurementDoc.photoUrl || ''}
                              onChange={photoUrl => {
                                const firstPhoto = String(photoUrl || '').split(',').map(url => url.trim()).filter(Boolean)[0] || '';
                                setNewMeasurementDoc(prev => ({...prev, photoUrl, fileUrl: prev.fileUrl || firstPhoto, title: prev.title || (firstPhoto ? 'Фото обмера' : '')}));
                              }}
                              appendPhotos={appendPhotos}
                              fileSrc={fileSrc}
                              setShowPhotoModal={setShowPhotoModal}
                              projectName={p.name}
                              context="project-measurements"
                              title="Фото/сканы листов замеров"
                            />
                          </div>
                          <textarea placeholder="Комментарий: откуда взяты объёмы, что нужно проверить, какие помещения создать" value={newMeasurementDoc.notes} onChange={e=>setNewMeasurementDoc({...newMeasurementDoc,notes:e.target.value})} style={{...inp,minHeight:'70px',resize:'vertical',marginTop:'8px'}}/>
                          <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                            <button onClick={saveMeasurement} style={btnO}><Check size={14}/>Сохранить</button>
                            <button onClick={()=>setShowMeasurementForm(false)} style={btnG}><X size={14}/>Отмена</button>
                          </div>
                        </div>)}

                        <div style={{...card,padding:'14px',marginBottom:'14px',backgroundColor:missingRooms?C.warningLight:C.successLight,border:'1.5px solid '+(missingRooms?C.warningBorder:C.successBorder)}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                            <div>
                              <b style={{color:C.text,fontSize:'13px'}}>Помещения и обмеры</b>
                              <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>{projectRooms.length?('Полный обмер: '+fullRooms+' из '+projectRooms.length+(missingRooms?' · дозаполнить: '+missingRooms:'')):'Помещения ещё не заведены'}</p>
                            </div>
                            <button onClick={()=>setActiveProjectTab('Помещения')} style={btnG}>Открыть помещения</button>
                          </div>
                        </div>

                        {renderEstimateMeasurementComparisonPanel(p)}

                        {docs.length===0&&(<div style={{...card,padding:'28px',textAlign:'center',color:C.textMuted}}>
                          <FileText size={42} style={{opacity:.35,marginBottom:'10px'}}/>
                          <p style={{margin:0}}>Исходники проекта и обмеров пока не добавлены</p>
                        </div>)}
                        {docs.map(doc=>{
                          const sm=statusMeta(doc.status);
                          const docDrafts = drafts.filter(d=>Number(d.measurementId)===Number(doc.id));
                          const docPhotos = String(doc.photoUrl || '').split(',').map(url=>url.trim()).filter(Boolean);
                          return (<div key={doc.id} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'4px solid '+sm[0]}}>
                            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                              <div style={{flex:1,minWidth:'220px'}}>
                                <div style={{display:'flex',gap:'6px',flexWrap:'wrap',alignItems:'center',marginBottom:'6px'}}>
                                  <span style={badge(sm[0],sm[1],sm[2])}>{doc.status}</span>
                                  <span style={{fontSize:'11px',color:C.textSec}}>{doc.sourceType+' · '+doc.docType}</span>
                                </div>
                                <b style={{color:C.text,fontSize:'13px',display:'block'}}>{doc.title||doc.docType}</b>
                                <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0'}}>{(doc.uploadedBy?'Загрузил: '+doc.uploadedBy:'')+(doc.createdAt?' · '+String(doc.createdAt).slice(0,10):'')+(doc.roomsCreated?(' · помещений: '+doc.roomsCreated):'')}</p>
                                {doc.notes&&<p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0',lineHeight:1.45}}>{doc.notes}</p>}
                                {docPhotos.length>0&&<div style={{display:'flex',gap:'5px',flexWrap:'wrap',marginTop:'8px'}}>{docPhotos.slice(0,6).map((url,index)=><img key={url+index} src={fileSrc(url)} alt='' onClick={()=>setShowPhotoModal(fileSrc(url))} style={{width:'54px',height:'54px',objectFit:'cover',borderRadius:'7px',cursor:'pointer',border:'1px solid '+C.border}}/>)}{docPhotos.length>6&&<span style={{fontSize:'11px',color:C.textSec,alignSelf:'center'}}>+{docPhotos.length-6}</span>}</div>}
                                {doc.reviewedBy&&<p style={{color:C.success,fontSize:'11px',margin:'4px 0 0'}}>{'Принял: '+doc.reviewedBy}</p>}
                              </div>
                              <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                {doc.fileUrl&&<a href={fileSrc(doc.fileUrl)} target='_blank' rel='noreferrer' style={{...btnB,padding:'5px 9px',fontSize:'11px',textDecoration:'none'}}><Eye size={11}/>Файл</a>}
                                {canEditMeasurements&&<button disabled={measurementDraftLoadingId===doc.id} onClick={()=>generateRoomDrafts(doc)} style={{...btnB,padding:'5px 9px',fontSize:'11px',opacity:measurementDraftLoadingId===doc.id?0.7:1}}><Bot size={11}/>{measurementDraftLoadingId===doc.id?'Разбираю...':'ИИ разобрать'}</button>}
                                {canEditMeasurements&&doc.status!=='На проверке'&&<button onClick={()=>updateMeasurement(doc,{status:'На проверке'})} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>На проверку</button>}
                                {canEditMeasurements&&doc.status!=='Принято'&&<button onClick={()=>updateMeasurement(doc,{status:'Принято'})} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}>Принять</button>}
                                {canEditMeasurements&&doc.status!=='Отклонено'&&<button onClick={()=>updateMeasurement(doc,{status:'Отклонено'})} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}>Отклонить</button>}
                                {canEditMeasurements&&<button onClick={()=>deleteMeasurement(doc)} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}><Trash2 size={11}/></button>}
                              </div>
                            </div>
                            {docDrafts.length>0&&(<div style={{marginTop:'12px',paddingTop:'12px',borderTop:'1px solid '+C.border}}>
                              <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>Черновики помещений из этого источника ({docDrafts.length})</b>
                              <div style={{display:'grid',gap:'8px'}}>
                                {docDrafts.map(draft=>{
                                  const accepted = draft.acceptedRoomId || draft.status==='Принято';
                                  const rejected = draft.status==='Отклонено';
                                  const dColor = accepted ? C.success : rejected ? C.danger : C.info;
                                  const dBg = accepted ? C.successLight : rejected ? C.dangerLight : C.infoLight;
                                  const dBorder = accepted ? C.successBorder : rejected ? C.dangerBorder : C.infoBorder;
                                  return (<div key={draft.id} style={{padding:'10px',borderRadius:'8px',backgroundColor:dBg,border:'1.5px solid '+dBorder}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
                                      <div style={{flex:1,minWidth:'210px'}}>
                                        <span style={badge(dColor,dBg,dBorder)}>{draft.status||'Черновик ИИ'}</span>
                                        <b style={{display:'block',color:C.text,fontSize:'13px',marginTop:'5px'}}>{draft.name}</b>
                                        <p style={{color:C.textSec,fontSize:'12px',margin:'4px 0 0'}}>
                                          {'Этаж '+(draft.floor||1)+(draft.roomType?' · '+draft.roomType:'')+
                                          ' · пол '+fmtMeasure(draft.floorArea||0,'м2')+
                                          (draft.wallArea?(' · стены '+fmtMeasure(draft.wallArea,'м2')):'')+
                                          (draft.ceilingArea?(' · потолок '+fmtMeasure(draft.ceilingArea,'м2')):'')+
                                          (draft.height?(' · высота '+fmtMeasure(draft.height,'м')):'')+
                                          ((draft.windows||draft.doors)?(' · окна '+(draft.windows||0)+' / двери '+(draft.doors||0)):'')}
                                        </p>
                                        {draft.notes&&<p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0',lineHeight:1.4}}>{draft.notes}</p>}
                                      </div>
                                      {canEditMeasurements&&<div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                                        {!accepted&&!rejected&&<button onClick={()=>acceptRoomDraft(draft)} style={{...btnGr,padding:'5px 9px',fontSize:'11px'}}><Check size={11}/>В помещения</button>}
                                        {!accepted&&!rejected&&<button onClick={()=>rejectRoomDraft(draft)} style={{...btnR,padding:'5px 9px',fontSize:'11px'}}><X size={11}/>Отклонить</button>}
                                        {accepted&&<button onClick={()=>setActiveProjectTab('Помещения')} style={{...btnG,padding:'5px 9px',fontSize:'11px'}}>Открыть</button>}
                                      </div>}
                                    </div>
                                  </div>);
                                })}
                              </div>
                            </div>)}
                          </div>);
                        })}
                      </div>);
                    })()}

                    {activeProjectTab==='Этапы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Этапы проекта</b>
                        {isProrab()&&<button onClick={()=>setShowForm(showForm==='stages'?false:'stages')} style={btnO}><Plus size={14}/>Добавить этап</button>}
                      </div>
                      {showForm==='stages'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название этапа *" value={newStage.name} onChange={e=>setNewStage({...newStage,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={newStage.status} onChange={e=>setNewStage({...newStage,status:e.target.value})} style={{...inp,marginBottom:0}}>{STAGE_STATUSES.map(s=><option key={s}>{s}</option>)}</select>
                          <input type="date" placeholder="Начало" value={newStage.startDate} onChange={e=>setNewStage({...newStage,startDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input type="date" placeholder="Конец" value={newStage.endDate} onChange={e=>setNewStage({...newStage,endDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Ответственный" value={newStage.responsible} onChange={e=>setNewStage({...newStage,responsible:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <div style={{display:'flex',alignItems:'center',gap:'8px'}}><label style={{fontSize:'12px',color:C.textSec,whiteSpace:'nowrap'}}>Прогресс: {newStage.progress}%</label><input type="range" min="0" max="100" value={newStage.progress} onChange={e=>setNewStage({...newStage,progress:Number(e.target.value)})} style={{flex:1,accentColor:C.accent}}/></div>
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                          <button onClick={()=>saveProjectStage(p.id,p.name)} style={btnO}><Check size={14}/>Сохранить</button>
                          <button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
                        </div>
                  </div>)}
                      {projectStages.filter(s=>s.projectName===p.name).map(stage=>{
                        const stColors={'Не начат':[C.textSec,C.bgGray,C.border],'В работе':[C.info,C.infoLight,C.infoBorder],'Завершён':[C.success,C.successLight,C.successBorder],'Заморожен':[C.warning,C.warningLight,C.warningBorder],'Просрочен':[C.danger,C.dangerLight,C.dangerBorder]};
                        const sc=stColors[stage.status]||stColors['Не начат'];
                        return(<div key={stage.id} style={{...card,padding:'14px',marginBottom:'10px',borderLeft:'3px solid '+sc[0]}}>
                          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                            <div style={{flex:1}}>
                              <div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}>
                                <b style={{color:C.text,fontSize:'13px'}}>{stage.name}</b>
                                <span style={badge(sc[0],sc[1],sc[2])}>{stage.status}</span>
                              </div>
                              {(stage.startDate||stage.endDate)&&<p style={{color:C.textSec,margin:'0 0 4px',fontSize:'12px'}}>{(stage.startDate||'')+(stage.endDate?' — '+stage.endDate:'')}</p>}
                              {stage.responsible&&<p style={{color:C.textSec,margin:'0 0 6px',fontSize:'12px'}}>{'👤 '+stage.responsible}</p>}
                              <div style={{backgroundColor:C.bgGray,borderRadius:'4px',height:'6px',marginTop:'6px'}}>
                                <div style={{backgroundColor:sc[0],width:(stage.progress||0)+'%',height:'100%',borderRadius:'4px'}}/>
                              </div>
                              <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{(stage.progress||0)+'% выполнено'}</p>
                            </div>
                            {isProrab()&&(<div style={{display:'flex',gap:'4px',marginLeft:'10px'}}>
                              <select value={stage.status} onChange={async e=>{await updateStage({...stage,status:e.target.value});}} style={{fontSize:'11px',padding:'3px 6px',border:'1.5px solid '+C.border,borderRadius:'6px',cursor:'pointer'}}>
                                {STAGE_STATUSES.map(s=><option key={s}>{s}</option>)}
                              </select>
                              <button onClick={()=>deleteStage(stage.id)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                  </div>)}
                          </div>
                        </div>);
                      })}
                      {projectStages.filter(s=>s.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Этапов нет — добавьте первый!</p>}
                  </div>)}

	                    {activeProjectTab==='График'&&(<div>
	                      <ProjectScheduleSummaryPanel
	                        C={C}
	                        card={card}
	                        project={p}
	                        stages={projectStages}
	                        workJournal={workJournal}
	                        planDone={projectPlanDone(p)}
	                        progress={projectRealProgress(p)}
	                        materialSummary={materialControlSummaryForProject(p.name)}
	                        supplierInvoices={supplierInvoices}
	                        isMobile={isMobile}
	                        onOpenStages={()=>setActiveProjectTab('Этапы')}
	                        onOpenJournal={()=>setActiveProjectTab('Производство работ')}
	                        onOpenMaterials={()=>setActiveProjectTab('Материалы')}
	                      />
	                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>График Ганта</b>
	                      {(()=>{
                        const stages=projectStages.filter(s=>s.projectName===p.name&&s.startDate&&s.endDate);
                        if(stages.length===0) return <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Добавьте этапы с датами во вкладке Этапы</p>;
                        const allDates=stages.flatMap(s=>[s.startDate,s.endDate]).filter(Boolean).sort();
                        const minDate=new Date(allDates[0]);
                        const maxDate=new Date(allDates[allDates.length-1]);
                        const totalDays=Math.max(1,Math.round((maxDate-minDate)/86400000))+1;
                        const stColors={'Не начат':C.textSec,'В работе':C.info,'Завершён':C.success,'Заморожен':C.warning,'Просрочен':C.danger};
                        return(<div style={{overflowX:'auto'}}>
                          <div style={{minWidth:'600px'}}>
                            <div style={{display:'flex',borderBottom:'1.5px solid '+C.border,paddingBottom:'6px',marginBottom:'8px'}}>
                              <div style={{width:'200px',flexShrink:0,fontSize:'11px',color:C.textSec,fontWeight:'600'}}>Этап</div>
                              <div style={{flex:1,fontSize:'11px',color:C.textSec,fontWeight:'600'}}>Временная шкала</div>
                            </div>
                            {stages.map(stage=>{
                              const sd=new Date(stage.startDate);
                              const ed=new Date(stage.endDate);
                              const left=Math.round((sd-minDate)/86400000)/totalDays*100;
                              const width=Math.max(1,Math.round((ed-sd)/86400000)+1)/totalDays*100;
                              const color=stColors[stage.status]||C.textSec;
                              return(<div key={stage.id} style={{display:'flex',alignItems:'center',marginBottom:'10px'}}>
                                <div style={{width:'200px',flexShrink:0,fontSize:'12px',color:C.text,paddingRight:'10px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{stage.name}</div>
                                <div style={{flex:1,position:'relative',height:'26px',backgroundColor:C.bg,borderRadius:'4px',border:'1px solid '+C.border}}>
                                  <div style={{position:'absolute',left:left+'%',width:width+'%',minWidth:'2%',height:'100%',backgroundColor:color,borderRadius:'4px',display:'flex',alignItems:'center',paddingLeft:'6px',overflow:'hidden'}}>
                                    <span style={{fontSize:'10px',color:'white',fontWeight:'600',whiteSpace:'nowrap'}}>{stage.progress+'%'}</span>
                                  </div>
                                </div>
                              </div>);
                            })}
                          </div>
                          {projectPayments.filter(pay=>pay.projectName===p.name).length>0&&(<div style={{marginTop:'12px'}}>
                            <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px'}}>История оплат:</b>
                            {projectPayments.filter(pay=>pay.projectName===p.name).map(pay=>(<div key={pay.id} style={{display:'flex',justifyContent:'space-between',padding:'6px 0',borderBottom:'1px solid '+C.border}}>
                              <div><span style={{fontSize:'12px',color:C.text}}>{pay.note||'Оплата'}</span>{(pay.workPackage||pay.work_package)&&<span style={{fontSize:'11px',color:C.info,marginLeft:'8px'}}>📁 {pay.workPackage||pay.work_package}</span>}<span style={{fontSize:'11px',color:C.textMuted,marginLeft:'8px'}}>{pay.date}</span></div>
                              <b style={{fontSize:'12px',color:C.success}}>+{Number(pay.amount).toLocaleString()+' ₽'}</b>
                            </div>))}
                          </div>)}
                        </div>);
                      })()}
                  </div>)}

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

	                    {activeProjectTab==='Помещения'&&(<div>
	                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
	                        <b style={{color:C.text}}>Помещения</b>
                        {isProrab()&&<button onClick={()=>{setShowRoomForm(!showRoomForm);setEditingItem(null);setDraftRoomWindows([]);setDraftRoomDoors([]);setNewRoom({project:p.name,name:'',floor:'',liter:'',roomType:'Комната',floorArea:'',wallArea:'',ceilingArea:'',height:'',ceilingType:'Простой',wallMaterial:'Штукатурка',floorMaterial:'Стяжка',photoUrl:'',notes:''});}} style={btnO}><Plus size={14}/>Добавить</button>}
                      </div>
                      {showRoomForm&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                          <input placeholder="Название помещения * (например: Кабинет 204)" value={newRoom.name} onChange={e=>setNewRoom({...newRoom,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Этаж (1,2,3...)" type="number" step="any" inputMode="decimal" value={newRoom.floor||''} onChange={e=>setNewRoom({...newRoom,floor:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Литер (А,Б,В...)" value={newRoom.liter||''} onChange={e=>setNewRoom({...newRoom,liter:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <select value={['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',...customRoomTypes].includes(newRoom.roomType||'Комната')?(newRoom.roomType||'Комната'):'Другое'} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0}}>
                            {[...'Комната,Кабинет,Коридор,Санузел,Кухня,Балкон,Лестница,Холл,Техническое'.split(','),...customRoomTypes,'Другое'].map(t=><option key={t}>{t}</option>)}
                          </select>
                          {(newRoom.roomType==='Другое'||(!['Комната','Кабинет','Коридор','Санузел','Кухня','Балкон','Лестница','Холл','Техническое','Другое',''].includes(newRoom.roomType||'Комната')))&&<input placeholder='Свой тип помещения, например: Серверная' value={newRoom.roomType==='Другое'?'':newRoom.roomType||''} onChange={e=>setNewRoom({...newRoom,roomType:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>}
                          <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newRoom.height} onChange={e=>setNewRoom({...newRoom,height:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь пола (м2)" type="number" step="any" inputMode="decimal" value={newRoom.floorArea} onChange={e=>setNewRoom({...newRoom,floorArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь стен (м2)" type="number" step="any" inputMode="decimal" value={newRoom.wallArea} onChange={e=>setNewRoom({...newRoom,wallArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                          <input placeholder="Площадь потолка (м2)" type="number" step="any" inputMode="decimal" value={newRoom.ceilingArea} onChange={e=>setNewRoom({...newRoom,ceilingArea:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        {(()=>{
                          const existingWins = editingItem ? roomWindows.filter(w=>Number(w.room_id)===Number(editingItem.id)) : [];
                          const existingDoors = editingItem ? roomDoors.filter(d=>Number(d.room_id)===Number(editingItem.id)) : [];
                          const draftOpeningsArea = draftRoomWindows.reduce((s,w)=>s+calcWindowArea(w),0)+draftRoomDoors.reduce((s,d)=>s+calcDoorArea(d),0);
                          const draftWindowReveals = draftRoomWindows.reduce((s,w)=>s+calcWindowReveals(w),0);
                          const draftDoorReveals = draftRoomDoors.reduce((s,d)=>s+calcDoorReveals(d),0);
                          const draftNetWall = Math.max(0, Number(newRoom.wallArea||0)-draftOpeningsArea);
                          return (
                            <div style={{marginTop:'10px',padding:'12px',borderRadius:'10px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                              <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start',marginBottom:'10px',flexWrap:'wrap'}}>
                                <div>
                                  <b style={{color:C.text,fontSize:'13px'}}>Окна, двери и откосы</b>
                                  <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>Окна и двери вычитаются из стен. Откосы считаются отдельной площадью.</p>
                                </div>
                                {!editingItem&&<div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                                  <span style={badge(C.info,C.infoLight,C.infoBorder)}>{'Чистые стены: '+draftNetWall.toFixed(2)+' м2'}</span>
                                  <span style={badge(C.accent,C.accentLight,C.accentBorder)}>{'Откосы: '+(draftWindowReveals+draftDoorReveals).toFixed(2)+' м2'}</span>
                                </div>}
                              </div>
                              {editingItem?(
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border,flexWrap:'wrap'}}>
                                  <span style={{color:C.textSec,fontSize:'12px'}}>{'Сейчас в помещении: окон '+existingWins.length+', дверей '+existingDoors.length+'. Для правки размеров раскройте карточку помещения ниже.'}</span>
                                  <button onClick={()=>{setExpandedRoom(editingItem.id);setShowRoomForm(false);}} style={{...btnG,padding:'6px 10px',fontSize:'12px'}}>Открыть окна/двери</button>
                                </div>
                              ):(
                                <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'10px'}}>
                                  <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',gap:'8px'}}>
                                      <b style={{color:C.text,fontSize:'12px'}}>Окна</b>
                                      <button onClick={()=>setDraftRoomWindows(prev=>[...prev,{name:'Окно '+(prev.length+1),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'}])} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}><Plus size={11}/>Окно</button>
                                    </div>
                                    {draftRoomWindows.length===0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'0'}}>Окон нет</p>}
                                    {draftRoomWindows.map((w,idx)=>(<div key={'draft-window-'+idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1.1fr .9fr .8fr .8fr .8fr 34px',gap:'6px',alignItems:'center',marginBottom:'6px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,name:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <select value={w.windowType||'ПВХ'} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,windowType:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Шир., м" type="number" step="any" inputMode="decimal" value={w.width} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,width:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Выс., м" type="number" step="any" inputMode="decimal" value={w.height} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,height:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Откос, см" type="number" step="any" inputMode="decimal" value={w.revealDepth} onChange={e=>setDraftRoomWindows(prev=>prev.map((x,i)=>i===idx?{...x,revealDepth:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <button onClick={()=>setDraftRoomWindows(prev=>prev.filter((_,i)=>i!==idx))} style={{...btnR,padding:'7px'}}><Trash2 size={11}/></button>
                                    </div>))}
                                  </div>
                                  <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}>
                                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',gap:'8px'}}>
                                      <b style={{color:C.text,fontSize:'12px'}}>Двери</b>
                                      <button onClick={()=>setDraftRoomDoors(prev=>[...prev,{name:'Дверь '+(prev.length+1),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'}])} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}><Plus size={11}/>Дверь</button>
                                    </div>
                                    {draftRoomDoors.length===0&&<p style={{color:C.textMuted,fontSize:'11px',margin:'0'}}>Дверей нет</p>}
                                    {draftRoomDoors.map((d,idx)=>(<div key={'draft-door-'+idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1.1fr .9fr .8fr .8fr .8fr 34px',gap:'6px',alignItems:'center',marginBottom:'6px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,name:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <select value={d.doorPurpose||'Межкомнатная'} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,doorPurpose:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Шир., м" type="number" step="any" inputMode="decimal" value={d.width} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,width:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Выс., м" type="number" step="any" inputMode="decimal" value={d.height} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,height:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <input placeholder="Откос, см" type="number" step="any" inputMode="decimal" value={d.revealDepth} onChange={e=>setDraftRoomDoors(prev=>prev.map((x,i)=>i===idx?{...x,revealDepth:e.target.value}:x))} style={{...inp,marginBottom:0,fontSize:'11px',padding:'8px'}}/>
                                      <button onClick={()=>setDraftRoomDoors(prev=>prev.filter((_,i)=>i!==idx))} style={{...btnR,padding:'7px'}}><Trash2 size={11}/></button>
                                    </div>))}
                                  </div>
                                </div>
                              )}
                            </div>
                          );
                        })()}
                        <div style={{marginTop:'8px'}}>
                          <PhotoAttachmentField
                            C={C}
                            btnG={btnG}
                            value={newRoom.photoUrl || ''}
                            onChange={photoUrl => setNewRoom({...newRoom, photoUrl})}
                            appendPhotos={appendPhotos}
                            fileSrc={fileSrc}
                            setShowPhotoModal={setShowPhotoModal}
                            projectName={p.name}
                            context="room-measurements"
                            title="Фото помещения / лист замера"
                          />
                        </div>
                        <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={saveRoom} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button><button onClick={()=>{setShowRoomForm(false);setEditingItem(null);setDraftRoomWindows([]);setDraftRoomDoors([]);}} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {(()=>{const projectRooms=rooms.filter(r=>r.project===p.name);if(projectRooms.length===0)return null;const checked=projectRooms.map(roomCompleteness);const full=checked.filter(x=>x.status==='Обмер полный').length;const missing=checked.filter(x=>x.status==='Не хватает данных').length;const openings=checked.filter(x=>x.status==='Проверить проёмы').length;return(<div style={{...card,padding:'12px',marginBottom:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
                        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'repeat(4,1fr)',gap:'8px'}}>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Помещений</p><b style={{color:C.text,fontSize:'16px'}}>{projectRooms.length}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.successLight,border:'1px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'10px',margin:'0 0 3px'}}>Обмер полный</p><b style={{color:C.success,fontSize:'16px'}}>{full}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:missing?C.warningLight:C.bg,border:'1px solid '+(missing?C.warningBorder:C.border)}}><p style={{color:missing?C.warning:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Дозаполнить</p><b style={{color:missing?C.warning:C.text,fontSize:'16px'}}>{missing}</b></div>
                          <div style={{padding:'10px',borderRadius:'8px',backgroundColor:openings?C.infoLight:C.bg,border:'1px solid '+(openings?C.infoBorder:C.border)}}><p style={{color:openings?C.info:C.textSec,fontSize:'10px',margin:'0 0 3px'}}>Проёмы/откосы</p><b style={{color:openings?C.info:C.text,fontSize:'16px'}}>{openings}</b></div>
                        </div>
                      </div>);})()}
                      {rooms.filter(r=>r.project===p.name).map(room=>{
                        const wins=roomWindows.filter(w=>Number(w.room_id)===Number(room.id));
                        const doors=roomDoors.filter(d=>Number(d.room_id)===Number(room.id));
                        const netWall=getRoomNetWall(room);
                        const winRevTotal=wins.reduce((s,w)=>s+calcWindowReveals(w),0);
                        const doorRevTotal=doors.reduce((s,d)=>s+calcDoorReveals(d),0);
                        const isRoomOpen=expandedRoom===room.id;
                        const completeness=roomCompleteness(room);
                        const roomPhotos=String(room.photoUrl||room.photo_url||'').split(',').map(url=>url.trim()).filter(Boolean);
                        return(<div key={room.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={()=>setExpandedRoom(isRoomOpen?null:room.id)}>
                            <div style={{minWidth:0,flex:1}}><b style={{color:C.text,fontSize:'13px'}}>{room.name}</b>{room.floor&&<span style={{fontSize:'11px',color:C.accent,marginLeft:'6px',padding:'1px 6px',backgroundColor:C.accentLight,borderRadius:'4px'}}>{'Эт.'+room.floor+(room.liter?' Лит.'+room.liter:'')}</span>}{room.roomType&&<span style={{fontSize:'11px',color:C.textSec,marginLeft:'4px'}}>{'· '+room.roomType}</span>}<span style={{...badge(completeness.color,completeness.bg,completeness.border),marginLeft:'6px'}}>{completeness.status}</span><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{'Пол: '+room.floorArea+'м² · Стены: '+room.wallArea+'м² (чистые: '+netWall+'м²) · Потолок: '+room.ceilingArea+'м² · Высота: '+(room.height||'—')+'м'}</p><p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>{'Окна: '+wins.length+'шт · Двери: '+doors.length+'шт'+(winRevTotal>0?' · Откосы окон: '+winRevTotal+'м²':'')+(doorRevTotal>0?' · Откосы дверей: '+doorRevTotal+'м²':'')}</p>{roomPhotos.length>0&&<div style={{display:'flex',gap:'4px',flexWrap:'wrap',marginTop:'6px'}}>{roomPhotos.slice(0,4).map((url,index)=><img key={url+index} src={fileSrc(url)} alt='' onClick={e=>{e.stopPropagation();setShowPhotoModal(fileSrc(url));}} style={{width:'44px',height:'44px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',border:'1px solid '+C.border}}/>)}{roomPhotos.length>4&&<span style={{fontSize:'11px',color:C.textSec,alignSelf:'center'}}>+{roomPhotos.length-4}</span>}</div>}{completeness.issues.length>0&&<p style={{color:completeness.color,margin:'3px 0 0',fontSize:'11px',fontWeight:'600'}}>{'Нужно: '+completeness.issues.slice(0,4).join(', ')+(completeness.issues.length>4?' …':'')}</p>}</div>
                            <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                              {isProrab()&&(<><button onClick={e=>{e.stopPropagation();setEditingItem(room);setDraftRoomWindows([]);setDraftRoomDoors([]);setNewRoom({project:room.project,name:room.name,floor:room.floor||'',liter:room.liter||'',roomType:room.roomType||'Комната',floorArea:room.floorArea,wallArea:room.wallArea,ceilingArea:room.ceilingArea,height:room.height||'',ceilingType:room.ceiling_type||room.ceilingType||'Простой',wallMaterial:room.wall_material||room.wallMaterial||'Штукатурка',floorMaterial:room.floor_material||room.floorMaterial||'Стяжка',photoUrl:room.photoUrl||room.photo_url||'',notes:room.notes||''});setShowRoomForm(true);}} style={{...btnG,padding:'4px 8px'}}><Edit2 size={11}/></button><button onClick={e=>{e.stopPropagation();deleteRoom(room.id);}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button></>)}
                              {isRoomOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isRoomOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'14px'}}>
                            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'16px'}}>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🪟 Окна</b>
                                  <button onClick={()=>setNewWindow({roomId:room.id,name:'Окно '+(wins.length+1),width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {wins.map(w=>(<div key={w.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingWindow===w.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={w.name} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,name:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.window_type||w.windowType||'ПВХ'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,window_type:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={w.width} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,width:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={w.height} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,height:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={w.reveal_depth||w.revealDepth||''} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_depth:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={w.reveal_material||w.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomWindows.map(x=>x.id===w.id?{...x,reveal_material:e.target.value}:x);setRoomWindows(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateWindow(w)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingWindow(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{w.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(w.window_type||w.windowType||'ПВХ')+' '+w.width+'×'+w.height+'м = '+calcWindowArea(w).toFixed(2)+'м²'}</p>{calcWindowReveals(w)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcWindowReveals(w).toFixed(2)+'м² ('+((w.reveal_depth||w.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingWindow(w.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteWindow(w.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newWindow.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newWindow.name} onChange={e=>setNewWindow({...newWindow,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.windowType} onChange={e=>setNewWindow({...newWindow,windowType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{WINDOW_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={newWindow.width} onChange={e=>setNewWindow({...newWindow,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newWindow.height} onChange={e=>setNewWindow({...newWindow,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={newWindow.revealDepth} onChange={e=>setNewWindow({...newWindow,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newWindow.revealMaterial} onChange={e=>setNewWindow({...newWindow,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveWindow(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewWindow({roomId:'',name:'Окно 1',width:'',height:'',windowType:'ПВХ',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                              <div>
                                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'10px'}}>
                                  <b style={{color:C.text,fontSize:'13px'}}>🚪 Двери</b>
                                  <button onClick={()=>setNewDoor({roomId:room.id,name:'Дверь '+(doors.length+1),width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnO,padding:'4px 10px',fontSize:'11px'}}><Plus size={11}/>Добавить</button>
                                </div>
                                {doors.map(d=>(<div key={d.id} style={{padding:'8px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                                  {editingDoor===d.id?(<div>
                                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                      <input placeholder="Название" value={d.name} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,name:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.door_type||d.doorType||'Деревянная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_type:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                      <select value={d.door_purpose||d.doorPurpose||'Межкомнатная'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,door_purpose:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                      <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={d.width} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,width:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={d.height} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,height:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={d.reveal_depth||d.revealDepth||''} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_depth:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                      <select value={d.reveal_material||d.revealMaterial||'Штукатурка'} onChange={e=>{const updated=roomDoors.map(x=>x.id===d.id?{...x,reveal_material:e.target.value}:x);setRoomDoors(updated);}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                    </div>
                                    <div style={{display:'flex',gap:'6px'}}><button onClick={()=>updateDoor(d)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Сохранить</button><button onClick={()=>setEditingDoor(null)} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                                  </div>):(<div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                                    <div><b style={{fontSize:'12px',color:C.text}}>{d.name}</b><p style={{color:C.textSec,margin:'1px 0',fontSize:'11px'}}>{(d.door_type||d.doorType||'')+(d.door_purpose||d.doorPurpose?'/'+(d.door_purpose||d.doorPurpose):'')+ ' '+d.width+'×'+d.height+'м = '+calcDoorArea(d).toFixed(2)+'м²'}</p>{calcDoorReveals(d)>0&&<p style={{color:C.info,margin:'0',fontSize:'10px'}}>{'Откосы: '+calcDoorReveals(d).toFixed(2)+'м² ('+((d.reveal_depth||d.revealDepth)||0)+'см)'}</p>}</div>
                                    <div style={{display:'flex',gap:'4px'}}><button onClick={()=>setEditingDoor(d.id)} style={{...btnG,padding:'3px 7px'}}><Edit2 size={10}/></button><button onClick={()=>deleteDoor(d.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
                  </div>)}
                                </div>))}
                                {newDoor.roomId===room.id&&(<div style={{padding:'10px',backgroundColor:C.accentLight,borderRadius:'8px',border:'1.5px solid '+C.accentBorder}}>
                                  <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'6px',marginBottom:'8px'}}>
                                    <input placeholder="Название" value={newDoor.name} onChange={e=>setNewDoor({...newDoor,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.doorType} onChange={e=>setNewDoor({...newDoor,doorType:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_TYPES.map(t=><option key={t}>{t}</option>)}</select>
                                    <select value={newDoor.doorPurpose} onChange={e=>setNewDoor({...newDoor,doorPurpose:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{DOOR_PURPOSES.map(t=><option key={t}>{t}</option>)}</select>
                                    <input placeholder="Ширина (м)" type="number" step="any" inputMode="decimal" value={newDoor.width} onChange={e=>setNewDoor({...newDoor,width:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Высота (м)" type="number" step="any" inputMode="decimal" value={newDoor.height} onChange={e=>setNewDoor({...newDoor,height:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <input placeholder="Откос (см)" type="number" step="any" inputMode="decimal" value={newDoor.revealDepth} onChange={e=>setNewDoor({...newDoor,revealDepth:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                                    <select value={newDoor.revealMaterial} onChange={e=>setNewDoor({...newDoor,revealMaterial:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>{REVEAL_MATERIALS.map(t=><option key={t}>{t}</option>)}</select>
                                  </div>
                                  <div style={{display:'flex',gap:'6px'}}><button onClick={()=>saveDoor(room.id)} style={{...btnO,padding:'5px 12px',fontSize:'11px'}}><Check size={11}/>Добавить</button><button onClick={()=>setNewDoor({roomId:'',name:'Дверь 1',width:'',height:'',doorType:'Деревянная',doorPurpose:'Межкомнатная',revealDepth:'',revealMaterial:'Штукатурка'})} style={{...btnG,padding:'5px 12px',fontSize:'11px'}}><X size={11}/>Отмена</button></div>
                  </div>)}
                              </div>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {rooms.filter(r=>r.project===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Помещений нет</p>}
                  </div>)}

                    {activeProjectTab==='Чек-листы'&&(<div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                        <b style={{color:C.text}}>Чек-листы</b>
                        {isProrab()&&<button onClick={()=>setShowForm(showForm==='checklist'?false:'checklist')} style={btnO}><Plus size={14}/>Создать</button>}
                      </div>
                      {showForm==='checklist'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
                        <input placeholder="Название чек-листа *" value={newChecklist.name} onChange={e=>setNewChecklist({...newChecklist,name:e.target.value})} style={inp}/>
                        <select value={newChecklist.template} onChange={e=>setNewChecklist({...newChecklist,template:e.target.value,name:e.target.value||newChecklist.name})} style={inp}><option value="">Свой чек-лист</option>{Object.keys(CHECKLIST_TEMPLATES).map(t=><option key={t} value={t}>{t}</option>)}</select>
                        <div style={{display:'flex',gap:'8px'}}><button onClick={()=>saveChecklist(p.id,p.name)} style={btnO}><Check size={14}/>Создать</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
                  </div>)}
                      {checklists.filter(cl=>cl.projectName===p.name).map(cl=>{
                        const items=checklistItems[cl.id]||[];
                        const checked=items.filter(i=>i.checked).length;
                        const isOpen=selectedChecklist===cl.id;
                        return(<div key={cl.id} style={{...card,marginBottom:'10px'}}>
                          <div style={{padding:'14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center'}} onClick={async()=>{if(isOpen){setSelectedChecklist(null);}else{setSelectedChecklist(cl.id);await loadChecklistItems(cl.id);}}}>
                            <div><b style={{color:C.text,fontSize:'13px'}}>{cl.name}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{checked+'/'+items.length+' выполнено'}</p></div>
                            <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
                              <div style={{backgroundColor:C.bgGray,borderRadius:'10px',height:'8px',width:'80px'}}><div style={{backgroundColor:items.length>0&&checked===items.length?C.success:C.accent,width:(items.length>0?checked/items.length*100:0)+'%',height:'100%',borderRadius:'10px'}}/></div>
                              {isOpen?<ChevronUp size={16} color={C.textMuted}/>:<ChevronDown size={16} color={C.textMuted}/>}
                            </div>
                          </div>
                          {isOpen&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'12px 14px'}}>
                            {items.map(item=>(<div key={item.id} style={{display:'flex',alignItems:'center',gap:'10px',padding:'8px 0',borderBottom:'1px solid '+C.border}}>
                              <input type="checkbox" checked={item.checked} onChange={()=>toggleChecklistItem(item)} style={{width:'18px',height:'18px',accentColor:C.accent,cursor:'pointer'}}/>
                              <span style={{fontSize:'13px',color:item.checked?C.textMuted:C.text,textDecoration:item.checked?'line-through':'none',flex:1}}>{item.name}</span>
                              {item.checked&&item.checkedBy&&<span style={{fontSize:'11px',color:C.textMuted}}>{item.checkedBy}</span>}
                            </div>))}
                            <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                              <input placeholder="Добавить пункт..." value={newChecklistItem} onChange={e=>setNewChecklistItem(e.target.value)} style={{...inp,marginBottom:0,flex:1,fontSize:'12px'}}/>
                              <button onClick={async()=>{if(!newChecklistItem) return;await fetch(API+'/checklist-items',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({checklistId:cl.id,name:newChecklistItem,checked:false,orderNum:items.length})});await loadChecklistItems(cl.id);setNewChecklistItem('');}} style={{...btnO,padding:'6px 12px'}}><Plus size={13}/></button>
                            </div>
                  </div>)}
                        </div>);
                      })}
                      {checklists.filter(cl=>cl.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Чек-листов нет</p>}
                  </div>)}

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
                            setNewTransfer({
                              materialName: '',
                              quantity: '',
                              unit: 'шт',
                              workPackage: '',
                              toPerson: '',
                              toPersonRole: '',
                              fromLocation: p.name,
                              notes: '',
                              transferDate: new Date().toISOString().split('T')[0],
                            });
                            setShowTransferForm(!showTransferForm);
                          }} style={btnO}><Plus size={14}/>Передать материал</button>)}
                        </div>
                      </div>
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
	                          setNewTransfer({
	                            materialName: row.name || '',
	                            quantity: '',
	                            unit: row.unit || 'шт',
	                            workPackage: row.packageName || row.workPackage || '',
	                            toPerson: '',
	                            toPersonRole: '',
	                            fromLocation: p.name,
	                            notes: 'Выдача мастеру из контроля материалов',
	                            transferDate: new Date().toISOString().split('T')[0],
	                          });
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
                    {activeProjectTab==='Чат'&&(<div>
                      <b style={{color:C.text,display:'block',marginBottom:'15px'}}>Чат проекта</b>
                      <div style={{backgroundColor:C.bg,borderRadius:'12px',padding:'15px',minHeight:'250px',maxHeight:'350px',overflowY:'auto',marginBottom:'15px',display:'flex',flexDirection:'column',gap:'10px',border:'1.5px solid '+C.border}}>
                        {(()=>{const msgs=projectChatMessages[p.name]||[];if(msgs.length===0) return <p style={{color:C.textMuted,textAlign:'center',margin:'auto',fontSize:'13px'}}>Нет сообщений</p>;return msgs.map(msg=>{const isMe=msg.authorName===user.name;const msgPhoto=fileSrc(msg.photoUrl||msg.photo_url);return(<div key={msg.id} style={{display:'flex',justifyContent:isMe?'flex-end':'flex-start'}}><div style={{maxWidth:'80%',backgroundColor:isMe?C.accent:C.bgWhite,color:isMe?'white':C.text,padding:'10px 14px',borderRadius:isMe?'16px 16px 4px 16px':'16px 16px 16px 4px',border:'1.5px solid '+(isMe?C.accent:C.border)}}>{!isMe&&<div style={{fontSize:'11px',fontWeight:'700',color:roleColor(msg.authorRole),marginBottom:'4px'}}>{msg.authorName}</div>}{msg.text&&<p style={{margin:0,fontSize:'13px'}}>{msg.text}</p>}{msgPhoto&&<img src={msgPhoto} alt='' style={{width:'180px',borderRadius:'8px',display:'block',marginTop:'6px',cursor:'pointer'}} onClick={()=>setShowPhotoModal(msgPhoto)}/>}<div style={{fontSize:'10px',color:isMe?'rgba(255,255,255,0.7)':C.textMuted,marginTop:'4px',textAlign:'right'}}>{msg.createdAt?new Date(msg.createdAt).toLocaleTimeString('ru-RU'):''}</div></div></div>);});})()}
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <input placeholder="Написать..." value={projectChatMessage} onChange={e=>setProjectChatMessage(e.target.value)} onKeyDown={e=>e.key==='Enter'&&sendProjectChatMessage(p.name,projectChatMessage,'')} style={{...inp,marginBottom:0,flex:1}}/>
                        <button onClick={()=>{if(!projectChatMessages[p.name]) loadProjectChat(p.name);sendProjectChatMessage(p.name,projectChatMessage,'');}} style={btnO}>➤</button>
                      </div>
                      {!projectChatMessages[p.name]&&<button onClick={()=>loadProjectChat(p.name)} style={{...btnG,marginTop:'8px',fontSize:'12px'}}>Загрузить чат</button>}
                  </div>)}

                    {activeProjectTab==='Финансы'&&(<div>
                      {isFinanceRole()&&(
                        <ProjectFinancePanel
                          projectName={p.name}
                          projectPayments={projectPayments}
                          accountablePayments={accountablePayments}
                          ownExpenses={ownExpenses}
                          manualExpenses={manualExpenses}
                          expenseCategories={EXPENSE_CATEGORIES}
                          expByCategory={expByCategory}
                          projectPaymentInAmount={projectPaymentInAmount}
                          projectPaymentSignedAmount={projectPaymentSignedAmount}
                          formatSignedRub={formatSignedRub}
                          user={user}
                          C={C}
                          card={card}
                          btnO={btnO}
                          btnB={btnB}
                          btnG={btnG}
                          btnR={btnR}
                          showBalanceDetails={showBalanceDetails}
                          setShowBalanceDetails={setShowBalanceDetails}
                          setAddExpenseProject={setAddExpenseProject}
                          setNewManualExpense={setNewManualExpense}
                          setShowAccountableForm={setShowAccountableForm}
                          newAccountable={newAccountable}
                          setNewAccountable={setNewAccountable}
                          setShowPhotoModal={setShowPhotoModal}
                          fileSrc={fileSrc}
                          loadAll={loadAll}
                          showProfit={isLeadership()}
                          canAddExpense={isFinanceRole()||user.role==='прораб'}
                        />
                      )}
                  </div>)}
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
                  {activeProjectTab==='Главный'&&(<div>
                    <div style={{marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📚 Журналы объекта</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'4px 0 0'}}>Клик по карточке откроет соответствующий журнал.</p>
                    </div>
                    {(()=>{
                      const cards=[
                        {tab:'Производство работ',icon:'📖',label:'Производство работ',hint:'Журнал по форме КС-6а',count:workJournal.filter(jw=>jw.project===p.name).length},
                        {tab:'АОСР',icon:'🔒',label:'АОСР',hint:'Печатные формы из сметы и журнала работ',count:hiddenActs.filter(a=>a.projectName===p.name).length},
                        {tab:'Входной контроль',icon:'📦',label:'Входной контроль материалов',hint:'СП 48.13330.2019',count:materialInspections.filter(mi=>mi.projectName===p.name).length},
                        {tab:'Кабельная продукция',icon:'⚡',label:'Кабельная продукция',hint:'СП 76.13330 · ПУЭ',count:cableJournal.filter(c=>c.projectName===p.name).length},
                        {tab:'Журнал ТБ',icon:'🛡️',label:'Техника безопасности',hint:'ГОСТ 12.0.004-2015',count:(tbJournal||[]).filter(e=>e.project===p.name).length},
                        {tab:'Погода',icon:'🌤',label:'Погода',hint:'Метеоусловия по дням',count:(weatherLog||[]).filter(w=>w.projectName===p.name).length},
                        {tab:'Предписания',icon:'⚠️',label:'Предписания',hint:'От технадзора и стройконтроля',count:(prescriptionsList||[]).filter(pr=>pr.projectName===p.name).length},
                        {tab:'Чат',icon:'💬',label:'Чат проекта',hint:'Переписка по объекту',count:0},
                      ];
                      return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'12px'}}>
                        {cards.map(c=>(<div key={c.tab} onClick={()=>setActiveProjectTab(c.tab)} style={{...card,padding:'16px',cursor:'pointer',border:'1.5px solid '+C.border}}><div style={{display:'flex',alignItems:'center',gap:'10px',marginBottom:'6px'}}><span style={{fontSize:'24px'}}>{c.icon}</span><b style={{color:C.text,fontSize:'13px'}}>{c.label}</b></div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 6px'}}>{c.hint}</p><b style={{color:C.accent,fontSize:'13px'}}>{c.count+' '+(c.count===1?'запись':c.count>=2&&c.count<=4?'записи':'записей')}</b></div>))}
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='Погода'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🌤 Журнал погоды</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Метеоусловия по дням строительства</span>
                    </div>
                    {(()=>{
                      const here=(weatherLog||[]).filter(w=>w.projectName===p.name).slice().sort((a,b)=>(b.date||'').localeCompare(a.date||''));
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Записей о погоде нет. Логируйте погоду из глобального раздела «Погода» — она автоматически появится здесь по этому объекту.</div>);
                      return(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(220px,1fr))',gap:'10px'}}>
                        {here.map((w,i)=>(<div key={i} style={{...card,padding:'12px'}}><b style={{color:C.text,fontSize:'13px'}}>{w.date}</b><p style={{color:C.textSec,margin:'4px 0 0',fontSize:'12px'}}>{(w.condition||'—')+' · '+(w.temperature!=null?w.temperature+'°C':'—')+(w.windSpeed?' · ветер '+w.windSpeed+' м/с':'')}</p>{w.notes&&<p style={{color:C.textMuted,fontSize:'11px',margin:'4px 0 0',fontStyle:'italic'}}>{w.notes}</p>}</div>))}
                      </div>);
                    })()}
                  </div>)}
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
                  {activeProjectTab==='КС-2'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📄</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Акт о приёмке выполненных работ (КС-2)</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Унифицированная форма по ОКУД 0322005. Формируется из выполненных позиций активной сметы. Утверждённые изменения к смете выводятся отдельными разделами без задвоения.</p>
                      <button onClick={()=>showKS2(p)} style={btnO}><Eye size={14}/>🖨 Открыть КС-2</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='КС-3'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📋</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Справка о стоимости выполненных работ (КС-3)</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Унифицированная форма по ОКУД 0322001. Подаётся вместе с КС-2 за отчётный период.</p>
                      <button onClick={()=>showPreview(buildKS3Content(p),'КС-3 — '+p.name)} style={btnO}><Eye size={14}/>🖨 Открыть КС-3</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='Паспорт'&&(<div>
                    <div style={{...card,padding:'24px',textAlign:'center'}}>
                      <div style={{fontSize:'40px',marginBottom:'10px'}}>📘</div>
                      <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'6px'}}>Паспорт объекта</b>
                      <p style={{color:C.textMuted,fontSize:'12px',margin:'0 0 16px'}}>Сводная карточка объекта с основными характеристиками и реквизитами.</p>
                      <button onClick={()=>showPreview(buildPassportContent(p),'Паспорт — '+p.name)} style={btnO}><Eye size={14}/>🖨 Открыть Паспорт</button>
                    </div>
                  </div>)}
                  {activeProjectTab==='Акты технадзора'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📝 Акты осмотра / обследования от технадзора</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Создаются технадзором в его кабинете</span>
                    </div>
                    {(()=>{const here=(supervisorActs||[]).filter(a=>a.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Технадзор пока не загружал актов осмотра по этому объекту.</div>);return(<div>{here.map(a=>(<div key={a.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+C.accent}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px'}}>
                        <div style={{flex:1}}>
                          <b style={{color:C.text,fontSize:'13px'}}>{a.actNumber+' · '+a.actType}</b>
                          <p style={{color:C.textSec,margin:'4px 0',fontSize:'12px'}}>{a.description||'—'}</p>
                          {a.findings&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Обнаружено:</b> {a.findings}</p>}
                          {a.recommendations&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Рекомендации:</b> {a.recommendations}</p>}
                          <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{a.date+' · '+(a.issuedBy||'—')}</p>
                        </div>
                        {a.photoUrl&&<img src={fileSrc(a.photoUrl)} alt='' onClick={()=>setShowPhotoModal(fileSrc(a.photoUrl))} style={{width:'56px',height:'56px',borderRadius:'6px',objectFit:'cover',cursor:'pointer',flexShrink:0}}/>}
                      </div>
                    </div>))}</div>);})()}
                  </div>)}
                  {activeProjectTab==='Замечания ГСН'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🏛 Замечания контролирующих органов</b>
                      <button onClick={()=>setShowForm(showForm==='gsn'?false:'gsn')} style={btnO}><Plus size={14}/>Добавить</button>
                    </div>
                    {showForm==='gsn'&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <select value={newInspOrder?.body||'ГСН'} onChange={e=>setNewInspOrder({...(newInspOrder||{}),body:e.target.value})} style={{...inp,marginBottom:0}}>{['ГСН','ГПН','Роспотребнадзор','Ростехнадзор','Прокуратура','Иное'].map(b=><option key={b}>{b}</option>)}</select>
                        <input placeholder='ФИО инспектора' value={newInspOrder?.inspector||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),inspector:e.target.value})} style={{...inp,marginBottom:0}}/>
                      </div>
                      <textarea placeholder='Описание замечания/нарушения *' value={newInspOrder?.description||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),description:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                      <textarea placeholder='Требования / рекомендации' value={newInspOrder?.recommendations||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),recommendations:e.target.value})} style={{...inp,minHeight:'50px',marginBottom:'8px'}}/>
                      <div style={{display:'flex',gap:'8px',marginBottom:'8px'}}>
                        <input type='date' value={newInspOrder?.date||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),date:e.target.value})} title='Дата проверки' style={{...inp,marginBottom:0,flex:1}}/>
                        <input type='date' value={newInspOrder?.deadline||''} onChange={e=>setNewInspOrder({...(newInspOrder||{}),deadline:e.target.value})} title='Срок устранения' style={{...inp,marginBottom:0,flex:1}}/>
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if(!(newInspOrder&&newInspOrder.description)){alert('Опишите замечание');return;}
                          await fetch(API+'/inspection-orders',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,body:newInspOrder.body||'ГСН',inspector:newInspOrder.inspector||'',description:newInspOrder.description,recommendations:newInspOrder.recommendations||'',deadline:newInspOrder.deadline||null,date:newInspOrder.date||new Date().toISOString().split('T')[0],status:'Открыто'})});
                          await refreshData();
                          setNewInspOrder(null); setShowForm(false);
                        }} style={btnO}><Check size={14}/>Сохранить</button>
                        <button onClick={()=>{setShowForm(false);setNewInspOrder(null);}} style={btnG}>Отмена</button>
                      </div>
                    </div>)}
                    {(()=>{const here=(inspectionOrders||[]).filter(o=>o.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Замечаний контролирующих органов нет. Если приходила проверка с замечаниями — зафиксируй её здесь, чтобы пакет ИД был полным.</div>);const open=here.filter(o=>o.status!=='Закрыто').length;const closed=here.filter(o=>o.status==='Закрыто').length;return(<div>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                        <div style={{...card,padding:'10px',backgroundColor:C.dangerLight}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>Открытых</p><b style={{color:C.danger,fontSize:'16px'}}>{open}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Закрытых</p><b style={{color:C.success,fontSize:'16px'}}>{closed}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                      </div>
                      {here.map(o=>(<div key={o.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(o.status==='Закрыто'?C.success:C.danger)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{flex:1,minWidth:'200px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>{o.orderNumber+' · '+(o.body||'ГСН')+(o.inspector?' · '+o.inspector:'')}</b>
                            <p style={{color:C.danger,margin:'4px 0',fontSize:'12px'}}>{o.description||'—'}</p>
                            {o.recommendations&&<p style={{color:C.text,margin:'4px 0',fontSize:'11px'}}><b>Требования:</b> {o.recommendations}</p>}
                            <p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'11px'}}>{(o.date||'')+(o.deadline?' · срок: '+o.deadline:'')}</p>
                            {o.response&&<div style={{marginTop:'8px',padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',fontSize:'11px',color:C.success}}><b>Ответ ({o.responseDate||'—'}):</b> {o.response}</div>}
                          </div>
                          <div style={{display:'flex',gap:'4px',alignItems:'flex-start'}}>
                            <span style={badge(o.status==='Закрыто'?C.success:C.danger,o.status==='Закрыто'?C.successLight:C.dangerLight,o.status==='Закрыто'?C.successBorder:C.dangerBorder)}>{o.status||'Открыто'}</span>
                            {o.status!=='Закрыто'&&<button onClick={async()=>{const resp=prompt('Опишите как устранили / ответ органу:');if(!resp) return;await fetch(API+'/inspection-orders/'+o.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Закрыто',response:resp,responseDate:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Закрыть</button>}
                            <button onClick={async()=>{if(!window.confirm('Удалить замечание?')) return;await fetch(API+'/inspection-orders/'+o.id,{method:'DELETE'});await refreshData();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                          </div>
                        </div>
                      </div>))}
                    </div>);})()}
                  </div>)}
                  {activeProjectTab==='Гарантия'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🛠 Гарантийный период и дефекты</b>
                      <button onClick={()=>setNewWarrantyDefect({description:'',foundAt:new Date().toISOString().split('T')[0],reportedBy:'',reporterPhone:'',severity:'Средний'})} style={btnO}><Plus size={14}/>Зафиксировать дефект</button>
                    </div>
                    <div style={{...card,padding:'14px',marginBottom:'12px',backgroundColor:C.bg,border:'1.5px solid '+C.border}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'8px',flexWrap:'wrap',gap:'6px'}}>
                        <b style={{color:C.text,fontSize:'13px'}}>📋 Условия гарантии</b>
                        {warrantyEditForm?.__projectId!==p.id&&(['директор','зам_директора','бухгалтер','прораб'].includes(user.role))&&(
                          <button onClick={()=>setWarrantyEditForm({__projectId:p.id,warrantyStartDate:p.warrantyStartDate||p.warranty_start_date||'',warrantyEndDate:p.warrantyEndDate||p.warranty_end_date||'',warrantyContact:p.warrantyContact||p.warranty_contact||''})} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}>✏️ Редактировать</button>
                        )}
                      </div>
                      {warrantyEditForm?.__projectId===p.id?(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',marginBottom:'8px'}}>
                          <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Начало гарантии</p><input type='date' value={warrantyEditForm.warrantyStartDate||''} onChange={e=>setWarrantyEditForm({...warrantyEditForm,warrantyStartDate:e.target.value})} style={{...inp,marginBottom:0}}/></div>
                          <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Окончание</p><input type='date' value={warrantyEditForm.warrantyEndDate||''} onChange={e=>setWarrantyEditForm({...warrantyEditForm,warrantyEndDate:e.target.value})} style={{...inp,marginBottom:0}}/></div>
                          <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Контакт</p><input type='text' placeholder='ФИО + телефон' value={warrantyEditForm.warrantyContact||''} onChange={e=>setWarrantyEditForm({...warrantyEditForm,warrantyContact:e.target.value})} style={{...inp,marginBottom:0}}/></div>
                        </div>
                        <div style={{display:'flex',gap:'8px'}}>
                          <button onClick={async()=>{
                            await fetch(API+'/projects/'+p.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({warrantyStartDate:warrantyEditForm.warrantyStartDate||null,warrantyEndDate:warrantyEditForm.warrantyEndDate||null,warrantyContact:warrantyEditForm.warrantyContact||''})});
                            await refreshData(); setWarrantyEditForm(null);
                          }} style={btnO}><Check size={14}/>Сохранить</button>
                          <button onClick={()=>setWarrantyEditForm(null)} style={btnG}>Отмена</button>
                        </div>
                      </div>):(<div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',fontSize:'12px'}}>
                        <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Начало гарантии</p><b style={{color:C.text}}>{p.warrantyStartDate||p.warranty_start_date||'не задано'}</b></div>
                        <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Окончание</p><b style={{color:C.text}}>{p.warrantyEndDate||p.warranty_end_date||'обычно +1 год'}</b></div>
                        <div><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Контакт по гарантии</p><b style={{color:C.text}}>{p.warrantyContact||p.warranty_contact||(p.foreman||'—')}</b></div>
                      </div>)}
                      <p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0',lineHeight:1.4}}>Срок гарантии устанавливается договором подряда (обычно 1-5 лет). В период гарантии устранение дефектов — за счёт подрядчика, если они вызваны его работой.</p>
                    </div>
                    {newWarrantyDefect&&(<div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg,border:'1.5px solid '+C.warningBorder}}>
                      <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>📝 Новый дефект</b>
                      <textarea placeholder='Описание дефекта *' value={newWarrantyDefect.description} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,description:e.target.value})} style={{...inp,minHeight:'60px',marginBottom:'8px'}}/>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <input type='date' value={newWarrantyDefect.foundAt} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,foundAt:e.target.value})} title='Когда обнаружено' style={{...inp,marginBottom:0}}/>
                        <select value={newWarrantyDefect.severity} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,severity:e.target.value})} style={{...inp,marginBottom:0}}>{['Низкий','Средний','Высокий','Критический'].map(s=><option key={s}>{s}</option>)}</select>
                        <input placeholder='ФИО кто обнаружил' value={newWarrantyDefect.reportedBy} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,reportedBy:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Телефон для связи' value={newWarrantyDefect.reporterPhone} onChange={e=>setNewWarrantyDefect({...newWarrantyDefect,reporterPhone:e.target.value})} style={{...inp,marginBottom:0}}/>
                      </div>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if(!newWarrantyDefect.description){alert('Опишите дефект');return;}
                          await fetch(API+'/warranty-defects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newWarrantyDefect,projectName:p.name,status:'Открыт'})});
                          await refreshData(); setNewWarrantyDefect(null);
                        }} style={btnO}><Check size={14}/>Сохранить</button>
                        <button onClick={()=>setNewWarrantyDefect(null)} style={btnG}>Отмена</button>
                      </div>
                    </div>)}
                    {(()=>{const here=warrantyDefects.filter(d=>d.projectName===p.name);if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Дефектов нет — гарантийных обращений по объекту не было.</div>);const open=here.filter(d=>d.status!=='Закрыт').length;const fixed=here.filter(d=>d.status==='Закрыт').length;return(<div>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'10px',marginBottom:'12px'}}>
                        <div style={{...card,padding:'10px',backgroundColor:C.dangerLight}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>Открытых</p><b style={{color:C.danger,fontSize:'16px'}}>{open}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Устранено</p><b style={{color:C.success,fontSize:'16px'}}>{fixed}</b></div>
                        <div style={{...card,padding:'10px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Всего</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                      </div>
                      {here.map(d=>(<div key={d.id} style={{...card,padding:'14px',marginBottom:'8px',borderLeft:'3px solid '+(d.status==='Закрыт'?C.success:d.severity==='Критический'?C.danger:d.severity==='Высокий'?C.warning:C.textSec)}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                          <div style={{flex:1,minWidth:'200px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>{d.description}</b>
                            <p style={{color:C.textSec,margin:'4px 0',fontSize:'11px'}}>Обнаружено: {d.foundAt}{d.reportedBy?' · '+d.reportedBy:''}{d.reporterPhone?' · '+d.reporterPhone:''}</p>
                            <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Уровень: <b>{d.severity||'—'}</b></p>
                            {d.fixNotes&&<div style={{marginTop:'6px',padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',fontSize:'11px',color:C.success}}><b>Устранено ({d.fixedAt||'—'}):</b> {d.fixNotes}</div>}
                          </div>
                          <div style={{display:'flex',gap:'4px',alignItems:'flex-start'}}>
                            <span style={badge(d.status==='Закрыт'?C.success:d.severity==='Критический'?C.danger:C.warning,d.status==='Закрыт'?C.successLight:d.severity==='Критический'?C.dangerLight:C.warningLight,d.status==='Закрыт'?C.successBorder:d.severity==='Критический'?C.dangerBorder:C.warningBorder)}>{d.status||'Открыт'}</span>
                            {d.status!=='Закрыт'&&<button onClick={async()=>{const notes=prompt('Опишите как устранили:');if(!notes) return;await fetch(API+'/warranty-defects/'+d.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Закрыт',fixNotes:notes,fixedAt:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>Устранено</button>}
                            <button onClick={async()=>{if(!window.confirm('Удалить дефект?')) return;await fetch(API+'/warranty-defects/'+d.id,{method:'DELETE'});await refreshData();}} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>
                          </div>
                        </div>
                      </div>))}
                    </div>);})()}
                  </div>)}
                  {activeProjectTab==='Входной контроль'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📦 Журнал входного контроля материалов</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>СП 48.13330.2019 · автозаполняется из накладных</span>
                    </div>
                    {(()=>{
                      const here=materialInspections.filter(mi=>mi.projectName===p.name);
	                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>📦</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Записей пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Записи создаются автоматически при приёмке поставки или оформлении приходной накладной на склад.<br/>Затем здесь прораб/кладовщик дополняет паспорт, сертификат и отметку об осмотре.</p></div>);
                      const cntInsp=here.filter(r=>r.inspected).length;
                      const cntPending=here.length-cntInsp;
                      const cntOk=here.filter(r=>r.visualInspectionResult==='Соответствует').length;
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Ждут проверки</p><b style={{color:C.warning,fontSize:'16px'}}>{cntPending}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Проверено</p><b style={{color:C.success,fontSize:'16px'}}>{cntInsp}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Соответствует</p><b style={{color:C.accent,fontSize:'16px'}}>{cntOk}</b></div>
                        </div>
                        <div style={{display:'flex',justifyContent:'flex-end',marginBottom:'10px'}}>
                          <button onClick={()=>showPreview(buildMaterialInspectionContent(here,p.name,'',''),'Журнал входного контроля — '+p.name)} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}><Eye size={13}/>🖨 Печать журнала</button>
                        </div>
                        <div style={{...card,padding:0,overflow:'auto'}}>
                          <table style={tbl}><thead><tr>
                            <th style={tblH}>Дата приёмки</th>
                            <th style={tblH}>Материал</th>
                            <th style={tblH}>Кол-во</th>
                            <th style={tblH}>Поставщик</th>
                            <th style={tblH}>Партия</th>
                            <th style={tblH}>Сертификат</th>
                            <th style={tblH}>Результат осмотра</th>
                            <th style={tblH}>Статус</th>
                          </tr></thead><tbody>
                            {here.map(mi=>(<tr key={mi.id} style={{cursor:'pointer'}} onClick={()=>setEditingInspection(mi)}>
                              <td style={tblC}>{mi.receivedAt||'—'}</td>
                              <td style={{...tblC,maxWidth:'260px',whiteSpace:'normal'}}>{mi.materialName}{mi.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                              <td style={tblC}>{(mi.quantity||0)+' '+(mi.unit||'')}</td>
                              <td style={tblC}>{mi.supplier||'—'}</td>
                              <td style={tblC}>{mi.batchNumber||'—'}</td>
                              <td style={tblC}>{mi.certificateNumber||(mi.passportNumber?'паспорт '+mi.passportNumber:'—')}</td>
                              <td style={tblC}>{mi.visualInspectionResult||'—'}</td>
                              <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:mi.inspected?(mi.visualInspectionResult==='Не соответствует'?C.dangerLight:C.successLight):C.warningLight,color:mi.inspected?(mi.visualInspectionResult==='Не соответствует'?C.danger:C.success):C.warning}}>{mi.inspected?'Проверено':'Ждёт проверки'}</span></td>
                            </tr>))}
                          </tbody></table>
                        </div>
                      </div>);
                    })()}
                  </div>)}
                  {activeProjectTab==='Кабельная продукция'&&(<div>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'10px'}}>
                      <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>⚡ Журнал кабельной продукции</b>
                      <span style={{fontSize:'11px',color:C.textMuted}}>Электрика · СКС · пожарка · слаботочка</span>
                    </div>
                    {(()=>{
                      const here=cableJournal.filter(cb=>cb.projectName===p.name);
                      if(here.length===0) return(<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}><div style={{fontSize:'40px',marginBottom:'10px'}}>⚡</div><p style={{margin:'0 0 8px',fontWeight:'600'}}>Записей пока нет</p><p style={{fontSize:'12px',margin:0,lineHeight:1.6}}>Записи создаются автоматически при приходе кабеля (по поставке или накладной).<br/>Система распознаёт силовые ВВГ/NYM/СИП, СКС UTP/FTP/SFTP, слаботочку КСВВ/КСПВ и пожарные КПС/КПСЭ/FRLS.</p></div>);
                      const cntInstalled=here.filter(cb=>cb.installedAt).length;
                      const cntPending=here.length-cntInstalled;
                      const totalLength=here.reduce((s,cb)=>s+Number(cb.lengthReceived||0),0);
                      const typeCounts=here.reduce((acc,cb)=>{const t=cableTypeOf(cb);acc[t]=(acc[t]||0)+1;return acc;},{});
                      return(<div>
                        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(120px,1fr))',gap:'10px',marginBottom:'14px'}}>
                          <div style={{...card,padding:'12px',backgroundColor:C.bg}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 4px'}}>Записей</p><b style={{color:C.text,fontSize:'16px'}}>{here.length}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>Ждут монтажа</p><b style={{color:C.warning,fontSize:'16px'}}>{cntPending}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Проложено</p><b style={{color:C.success,fontSize:'16px'}}>{cntInstalled}</b></div>
                          <div style={{...card,padding:'12px',backgroundColor:C.accentLight,border:'1.5px solid '+C.accentBorder}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>Общая длина</p><b style={{color:C.accent,fontSize:'16px'}}>{totalLength.toLocaleString('ru-RU')+' м'}</b></div>
                        </div>
                        <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginBottom:'10px'}}>
                          {Object.entries(typeCounts).map(([t,n])=><span key={t} style={badge(C.accent,C.accentLight,C.accentBorder)}>{t+': '+n}</span>)}
                        </div>
                        <div style={{display:'flex',justifyContent:'flex-end',marginBottom:'10px'}}>
                          <button onClick={()=>showPreview(buildCableJournalContent(here,p.name,'',''),'Журнал кабельной продукции — '+p.name)} style={{...btnB,fontSize:'12px',padding:'7px 12px'}}><Eye size={13}/>🖨 Печать журнала</button>
                        </div>
                        <div style={{...card,padding:0,overflow:'auto'}}>
                          <table style={tbl}><thead><tr>
                            <th style={tblH}>Дата</th>
                            <th style={tblH}>Тип системы</th>
                            <th style={tblH}>Марка</th>
                            <th style={tblH}>Сечение</th>
                            <th style={tblH}>Жил</th>
                            <th style={tblH}>Длина</th>
                            <th style={tblH}>Барабан №</th>
                            <th style={tblH}>R изол. ДО</th>
                            <th style={tblH}>R изол. ПОСЛЕ</th>
                            <th style={tblH}>Место прокладки</th>
                            <th style={tblH}>Статус</th>
                          </tr></thead><tbody>
                            {here.map(cb=>(<tr key={cb.id} style={{cursor:'pointer'}} onClick={()=>setEditingCable(cb)}>
                              <td style={tblC}>{cb.receivedAt||'—'}</td>
                              <td style={tblC}>{cableTypeOf(cb)}</td>
                              <td style={{...tblC,maxWidth:'220px',whiteSpace:'normal'}}>{cb.cableBrand}{cb.aiFilled?<span title="Заполнено AI" style={{marginLeft:'4px'}}>🤖</span>:null}</td>
                              <td style={tblC}>{cb.crossSection?cb.crossSection+' мм²':'—'}</td>
                              <td style={tblC}>{cb.coresCount||'—'}</td>
                              <td style={tblC}>{(cb.lengthReceived||0)+' м'}</td>
                              <td style={tblC}>{cb.drumNumber||'—'}</td>
                              <td style={tblC}>{cb.insulationBefore?cb.insulationBefore+' МΩ':'—'}</td>
                              <td style={tblC}>{cb.insulationAfter?cb.insulationAfter+' МΩ':'—'}</td>
                              <td style={{...tblC,maxWidth:'220px',whiteSpace:'normal'}}>{cb.installationLocation||'—'}</td>
                              <td style={tblC}><span style={{padding:'2px 8px',borderRadius:'10px',fontSize:'11px',fontWeight:'600',backgroundColor:cb.installedAt?C.successLight:C.warningLight,color:cb.installedAt?C.success:C.warning}}>{cb.installedAt?'Проложен':'На складе'}</span></td>
                            </tr>))}
                          </tbody></table>
                        </div>
                      </div>);
                    })()}
                  </div>)}
                  </div>
                </div>)}
              </div>);
            })}
            {projects.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}><FolderKanban size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Проектов нет — создайте первый!</p></div>}
          </div>
  );
}
