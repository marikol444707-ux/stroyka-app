import React from 'react';
import { Bot, Calculator, FileText, Package } from 'lucide-react';
import DashboardTopBar from '../../components/DashboardTopBar';
import DashboardStatsGrid from '../../components/DashboardStatsGrid';
import DashboardRisksPanel from '../../components/DashboardRisksPanel';
import {
  DashboardActivityPanel,
  DashboardDirectorAiPanel,
  DashboardProductionSummaryPanel,
  DashboardSupplyPanel,
} from '../../app/lazyComponents';
import { isOpenAiStatus } from '../../utils/statusMetaUtils';

export default function DashboardPage({
  actions = {},
  data = {},
  ui = {},
} = {}) {
  const {
  API,
  C,
    btnG,
    btnO,
    darkMode,
    isMobile,
    showAiAssistant,
    showNotifications,
    unreadMessagesCount,
    unreadNotifications,
  } = ui;
  const {
  accountablePayments,
  activityLog,
  aiFindings,
  canUseDirectorAgent,
  dailyReportDate,
  directorAgentAnswer,
  directorAgentError,
  directorAgentLoading,
  directorAgentQuestion,
  directorAgentSteps,
  estimateControlIssues,
  hiddenActs,
  initialDataLoaded,
  inspectionOrders,
  lowMainStock,
  lowStock,
  manualExpenses,
  mobileExpandedRenderLists,
  myNotifications,
  notifications,
  ownExpenses,
  projectPayments,
  projects,
    supplierInvoices,
    supplierOffers,
    supplyRequests,
    unexpectedWorksList,
    user,
    workJournal,
  } = data;
  const {
    askDirectorAgent,
    buildDailyObjectReportContent,
    buildDirectorBriefReportContent,
    buildSupplyControlReportContent,
    closeNotifications,
    getNotifPage,
    isApprovedEstimateChangeStatus,
    isLeadership,
    markMyNotificationsRead,
    navigateTo,
    normalizeDocDate,
    openEstimateControlReport,
    projectBudgetSpent,
    projectPaymentSignedAmount,
    projectRealProgress,
  setAccountingTab,
  setActivePage,
    setDailyReportDate,
    setDirectorAgentQuestion,
    setDarkMode,
  setExpandedProject,
  setMobileExpandedRenderLists,
  setNotifications,
  setShowAiAssistant,
  setShowChatPanel,
  setShowForm,
  setShowNotifications,
  setShowQuickActions,
  setShowReimburseModal,
  setShowSupplyForm,
  setSidebarVisible,
  setSupplyTab,
  setUser,
  setWarehouseTab,
  showPreview,
  toggleNotifications,
  visibleActiveProjects,
  workDocDate,
  } = actions;
  const noop = () => {};
  const safeSetActivePage = typeof setActivePage === 'function' ? setActivePage : noop;
  const safeNavigateTo = typeof navigateTo === 'function' ? navigateTo : safeSetActivePage;
  const safeSetAccountingTab = typeof setAccountingTab === 'function' ? setAccountingTab : noop;
  const safeSetDarkMode = typeof setDarkMode === 'function' ? setDarkMode : noop;
  const safeSetDailyReportDate = typeof setDailyReportDate === 'function' ? setDailyReportDate : noop;
  const safeSetDirectorAgentQuestion = typeof setDirectorAgentQuestion === 'function' ? setDirectorAgentQuestion : noop;
  const safeSetExpandedProject = typeof setExpandedProject === 'function' ? setExpandedProject : noop;
  const safeSetMobileExpandedRenderLists = typeof setMobileExpandedRenderLists === 'function' ? setMobileExpandedRenderLists : noop;
  const safeSetNotifications = typeof setNotifications === 'function' ? setNotifications : noop;
  const safeSetShowAiAssistant = typeof setShowAiAssistant === 'function' ? setShowAiAssistant : noop;
  const safeSetShowChatPanel = typeof setShowChatPanel === 'function' ? setShowChatPanel : noop;
  const safeSetShowForm = typeof setShowForm === 'function' ? setShowForm : noop;
  const safeSetShowNotifications = typeof setShowNotifications === 'function' ? setShowNotifications : noop;
  const safeSetShowQuickActions = typeof setShowQuickActions === 'function' ? setShowQuickActions : noop;
  const safeSetShowReimburseModal = typeof setShowReimburseModal === 'function' ? setShowReimburseModal : noop;
  const safeSetShowSupplyForm = typeof setShowSupplyForm === 'function' ? setShowSupplyForm : noop;
  const safeSetSidebarVisible = typeof setSidebarVisible === 'function' ? setSidebarVisible : noop;
  const safeSetSupplyTab = typeof setSupplyTab === 'function' ? setSupplyTab : noop;
  const safeSetUser = typeof setUser === 'function' ? setUser : noop;
  const safeSetWarehouseTab = typeof setWarehouseTab === 'function' ? setWarehouseTab : noop;
  const safeAskDirectorAgent = typeof askDirectorAgent === 'function' ? askDirectorAgent : noop;
  const safeCloseNotifications = typeof closeNotifications === 'function' ? closeNotifications : noop;
  const safeGetNotifPage = typeof getNotifPage === 'function' ? getNotifPage : () => null;
  const safeMarkMyNotificationsRead = typeof markMyNotificationsRead === 'function' ? markMyNotificationsRead : noop;
  const safeToggleNotifications = typeof toggleNotifications === 'function' ? toggleNotifications : noop;
  const lowStockList = Array.isArray(lowStock) ? lowStock : [];
  const lowMainStockList = Array.isArray(lowMainStock) ? lowMainStock : [];
  const activityLogList = Array.isArray(activityLog) ? activityLog : [];
  const hiddenActsList = Array.isArray(hiddenActs) ? hiddenActs : [];
  const inspectionOrdersList = Array.isArray(inspectionOrders) ? inspectionOrders : [];
  const unexpectedWorks = Array.isArray(unexpectedWorksList) ? unexpectedWorksList : [];
  const ownExpensesList = Array.isArray(ownExpenses) ? ownExpenses : [];
  const aiFindingsList = Array.isArray(aiFindings) ? aiFindings : [];
  const projectPaymentsList = Array.isArray(projectPayments) ? projectPayments : [];
  const manualExpensesList = Array.isArray(manualExpenses) ? manualExpenses : [];
  const accountablePaymentsList = Array.isArray(accountablePayments) ? accountablePayments : [];
  const projectsList = Array.isArray(projects) ? projects : [];
  const supplyRequestsList = Array.isArray(supplyRequests) ? supplyRequests : [];
  const supplierOffersList = Array.isArray(supplierOffers) ? supplierOffers : [];
  const supplierInvoicesList = Array.isArray(supplierInvoices) ? supplierInvoices : [];
  const workJournalList = Array.isArray(workJournal) ? workJournal : [];
  const mobileExpandedRenderListsState = mobileExpandedRenderLists && typeof mobileExpandedRenderLists === 'object' ? mobileExpandedRenderLists : {};
  const topBarProps = {
    API,
    C,
    btnG,
    btnO,
    closeNotifications: safeCloseNotifications,
    darkMode,
    getNotifPage: safeGetNotifPage,
    isMobile,
    markMyNotificationsRead: safeMarkMyNotificationsRead,
    myNotifications: Array.isArray(myNotifications) ? myNotifications : [],
    navigateTo: safeNavigateTo,
    notifications: Array.isArray(notifications) ? notifications : [],
    setDarkMode: safeSetDarkMode,
    setNotifications: safeSetNotifications,
    setShowAiAssistant: safeSetShowAiAssistant,
    setShowChatPanel: safeSetShowChatPanel,
    setShowNotifications: safeSetShowNotifications,
    setShowQuickActions: safeSetShowQuickActions,
    setSidebarVisible: safeSetSidebarVisible,
    setUser: safeSetUser,
    showAiAssistant,
    showNotifications,
    toggleNotifications: safeToggleNotifications,
    unreadMessagesCount,
    unreadNotifications,
    user,
  };

  if (!initialDataLoaded) {
    return (
      <div style={{minHeight:'100%',padding:'28px',background:'radial-gradient(circle at 15% 0%,rgba(249,115,22,.15),transparent 32%),linear-gradient(135deg,#0b1120 0%,#111827 100%)',color:'#f8fafc'}}>
        <DashboardTopBar {...topBarProps}/>
        <div style={{marginTop:'24px',background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'24px',boxShadow:'0 18px 60px rgba(0,0,0,.25)'}}>
          <div style={{fontSize:'18px',fontWeight:800,marginBottom:'8px'}}>Загружаю данные объекта</div>
          <div style={{color:'#94a3b8',fontSize:'14px'}}>Сейчас подтягиваются сметы, задачи, склад и журналы. Нули на дашборде не показываются до окончания загрузки.</div>
        </div>
      </div>
    );
  }

  const currentUserRole = user?.role || '';
  const isApprovedEstimateChange = typeof isApprovedEstimateChangeStatus === 'function'
    ? isApprovedEstimateChangeStatus
    : () => false;
  const getProjectBudgetSpent = typeof projectBudgetSpent === 'function'
    ? projectBudgetSpent
    : () => ({ works: 0, materials: 0, unexpected: 0, total: 0 });
  const getProjectPaymentSignedAmount = typeof projectPaymentSignedAmount === 'function'
    ? projectPaymentSignedAmount
    : () => 0;
  const getProjectRealProgress = typeof projectRealProgress === 'function'
    ? projectRealProgress
    : (project) => Math.max(0, Math.min(100, Number(project?.progress || 0)));
  const isLeadershipUser = typeof isLeadership === 'function'
    ? isLeadership
    : () => ['директор', 'зам_директора'].includes(currentUserRole);
  const formatDocDate = typeof normalizeDocDate === 'function'
    ? normalizeDocDate
    : (value) => String(value || '').split('T')[0] || '';
  const getWorkDocDate = typeof workDocDate === 'function'
    ? workDocDate
    : (work) => formatDocDate(work?.date || work?.createdAt);
  const getEstimateControlIssues = typeof estimateControlIssues === 'function'
    ? estimateControlIssues
    : () => [];
  const previewDocument = typeof showPreview === 'function' ? showPreview : () => {};
  const buildDirectorBriefReport = typeof buildDirectorBriefReportContent === 'function' ? buildDirectorBriefReportContent : () => '';
  const buildDailyObjectReport = typeof buildDailyObjectReportContent === 'function' ? buildDailyObjectReportContent : () => '';
  const buildSupplyControlReport = typeof buildSupplyControlReportContent === 'function' ? buildSupplyControlReportContent : () => '';
  const openEstimateControl = typeof openEstimateControlReport === 'function' ? openEstimateControlReport : () => {};

  const _today = new Date().toISOString().split('T')[0];
  const getVisibleActiveProjects = typeof visibleActiveProjects === 'function'
    ? visibleActiveProjects
    : (list = []) => (list || []).filter(project => !project?.archived);
  const dashboardProjects = getVisibleActiveProjects(projectsList);
  const risks = [];
  lowStockList.slice(0,2).forEach(m=>risks.push({icon:'📦',text:'Мало на объекте: '+m.name,severity:'warn',page:'warehouse'}));
  lowMainStockList.slice(0,2).forEach(m=>risks.push({icon:'🏭',text:'Мало на складе: '+m.name,severity:'warn',page:'warehouse',tab:'main'}));
  dashboardProjects.filter(p=>p.deadline&&p.deadline<_today).slice(0,2).forEach(p=>risks.push({icon:'⏰',text:'Срок истёк: '+p.name+' (до '+p.deadline+')',severity:'danger',page:'projects'}));
  const _weekAgo = new Date(Date.now()-7*24*3600*1000).toISOString().split('T')[0];
  hiddenActsList.filter(a=>a.status!=='Подписан'&&a.createdAt&&String(a.createdAt).split('T')[0]<_weekAgo).slice(0,2).forEach(a=>risks.push({icon:'🔒',text:'АОСР долго без подписи: '+a.actNumber,severity:'warn',page:'projects'}));
  const openInsp = inspectionOrdersList.filter(o=>o.status!=='Закрыто').length;
  if (openInsp > 0) risks.push({icon:'🏛',text:'Открытых замечаний ГСН: '+openInsp,severity:'danger',page:'projects'});
  dashboardProjects.forEach(p=>{
    const budget = Number(p.budget||0);
    if (budget <= 0) return;
    const sumUnx = unexpectedWorks
      .filter(u=>u.projectName===p.name&&isApprovedEstimateChange(u.status)&&u.changeType!=='Исключение объёма'&&!u.includedInEstimateId)
      .reduce((s,u)=>s+Number(u.total||0),0);
    const pct = sumUnx/budget*100;
    if (pct > 10) risks.push({icon:'💸',text:p.name+': изменения к смете '+pct.toFixed(1)+'% от бюджета',severity:'danger',page:'projects'});
  });
  const pendingExp = ownExpensesList.filter(e=>e.status==='Ожидает');
  if (pendingExp.length > 0) {
    const sum = pendingExp.reduce((s,e)=>s+Number(e.amount||0),0);
    risks.push({icon:'💸',text:'К возмещению сотрудникам: '+Math.round(sum).toLocaleString('ru-RU')+' ₽ ('+pendingExp.length+' трат)',severity:'warn',action:'reimburse'});
  }
  const openAiControl = aiFindingsList.filter(f=>isOpenAiStatus(f.status));
  const criticalAiControl = openAiControl.filter(f=>f.severity==='Критично'||f.severity==='Не хватает данных');
  if (openAiControl.length > 0) risks.push({icon:'🤖',text:'ИИ-контроль: '+openAiControl.length+' замечаний, из них важных '+criticalAiControl.length,severity:criticalAiControl.length?'danger':'warn',page:'projects'});
  const _projProgress = getProjectRealProgress;
  const avgProg = dashboardProjects.length ? Math.round(dashboardProjects.reduce((s,p)=>s+_projProgress(p),0)/dashboardProjects.length) : 0;
  const dashboardBudgetSpent = dashboardProjects.map(p=>({projectId:p.id,projectName:p.name,spent:getProjectBudgetSpent(p)}));
  const dashboardBudgetSpentById = new Map(dashboardBudgetSpent.map(x=>[String(x.projectId),x.spent]));
  const dashboardBudgetSpentByName = new Map(dashboardBudgetSpent.map(x=>[x.projectName,x.spent]));
  const totalDone = dashboardBudgetSpent.reduce((s,x)=>s+Number(x.spent?.total||0),0);
  const dashboardJournalExpenses = projectPaymentsList.reduce((sum,pay)=>{
    const signed = getProjectPaymentSignedAmount(pay);
    return signed < 0 ? sum + Math.abs(signed) : sum;
  },0);
  const dashboardDirectExpenses = manualExpensesList
    .filter(expense=>!expense.ownExpenseId&&expense.source!=='own_expense')
    .reduce((sum,expense)=>sum+Number(expense.amount||0),0);
  const dashboardAccountableExpenses = accountablePaymentsList.reduce((sum,payment)=>sum+Number(payment.amount||0),0);
  const dashboardAccountingExpenses = dashboardJournalExpenses + dashboardDirectExpenses + dashboardAccountableExpenses;
  const dashboardProjectPreviewLimit = isMobile ? 3 : 5;
  const openSupplyDashboard = (tab) => {
    safeSetActivePage('supply');
    safeSetSupplyTab(tab);
    safeSetShowSupplyForm(false);
    safeSetShowForm(false);
  };
  const dashboardExtraKey = 'dashboard-extra-panels';
  const showDashboardExtra = !isMobile || !!mobileExpandedRenderListsState[dashboardExtraKey];
  const showSupplyDashboard = showDashboardExtra && ['директор','зам_директора','бухгалтер','прораб','кладовщик','снабженец'].includes(currentUserRole);
  const supplyPendingRequests = showDashboardExtra ? supplyRequestsList.filter(r=>{
    if (currentUserRole==='прораб') return r.status==='Новая';
    if (isLeadershipUser()) return r.status==='Новая'||r.status==='Подтверждена прорабом';
    return r.status==='Утверждена'||r.status==='КП запрошены';
  }) : [];
  const supplyOffersToReview = showDashboardExtra ? supplierOffersList.filter(o=>o.status==='Получено') : [];
  const supplyInvoicesToPay = showDashboardExtra ? supplierInvoicesList.filter(i=>i.status==='На утверждении'||i.status==='Утверждён'||i.status==='Частично оплачен'||!i.status) : [];
  const supplyInvoiceDebt = showDashboardExtra ? supplyInvoicesToPay.reduce((s,i)=>s+Math.max(0,Number(i.amount||i.totalAmount||0)-Number(i.paidAmount||0)),0) : 0;
  const directorSkillDate = showDashboardExtra ? (formatDocDate(dailyReportDate)||_today) : _today;
  const directorSkillDailyWorks = showDashboardExtra ? workJournalList.filter(w=>getWorkDocDate(w)===directorSkillDate) : [];
  const directorSkillEstimateIssues = showDashboardExtra && isLeadershipUser() ? getEstimateControlIssues().length : 0;
  const directorSkillSupplyIssues = showDashboardExtra ? lowStockList.length+lowMainStockList.length
    +supplyRequestsList.filter(r=>r.status==='Новая'||r.status==='Подтверждена прорабом').length
    +supplierInvoicesList.filter(i=>i.status==='На утверждении'||!i.status).length : 0;
  const directorSkillCards = showDashboardExtra ? [
    {label:'Сводка директору',sub:'риски, деньги, задачи',icon:<Bot size={18}/>,color:'#fdba74',bg:'rgba(234,88,12,.14)',border:'rgba(234,88,12,.32)',metric:risks.length+' рисков',onClick:()=>previewDocument(buildDirectorBriefReport(directorSkillDate),'Сводка директора — '+new Date(directorSkillDate+'T00:00:00').toLocaleDateString('ru-RU'))},
    {label:'ИИ-контроль',sub:'обмеры и поручения',icon:<Bot size={18}/>,color:'#fca5a5',bg:'rgba(239,68,68,.12)',border:'rgba(239,68,68,.28)',metric:openAiControl.length+' замеч.',onClick:()=>safeNavigateTo('projects')},
    {label:'Ежедневный отчёт',sub:'работы по объектам',icon:<FileText size={18}/>,color:'#86efac',bg:'rgba(34,197,94,.12)',border:'rgba(34,197,94,.28)',metric:directorSkillDailyWorks.length+' работ',onClick:()=>previewDocument(buildDailyObjectReport(directorSkillDate),'Ежедневный отчет — '+new Date(directorSkillDate+'T00:00:00').toLocaleDateString('ru-RU'))},
    {label:'Проверка смет',sub:'нули, дубли, бюджет',icon:<Calculator size={18}/>,color:'#93c5fd',bg:'rgba(59,130,246,.12)',border:'rgba(59,130,246,.28)',metric:directorSkillEstimateIssues+' замеч.',onClick:openEstimateControl},
    {label:'Склад и снабжение',sub:'остатки, заявки, счета',icon:<Package size={18}/>,color:'#c4b5fd',bg:'rgba(139,92,246,.12)',border:'rgba(139,92,246,.28)',metric:directorSkillSupplyIssues+' задач',onClick:()=>previewDocument(buildSupplyControlReport(),'Контроль снабжения и склада')},
  ] : [];

  return (
    <div style={{minHeight:'100%',padding:'28px',background:'radial-gradient(circle at 15% 0%,rgba(249,115,22,.15),transparent 32%),linear-gradient(135deg,#0b1120 0%,#111827 100%)',color:'#f8fafc'}}>
      <DashboardTopBar {...topBarProps}/>
      <DashboardStatsGrid dashboardProjects={dashboardProjects} avgProg={avgProg} totalDone={totalDone} totalExpenses={dashboardAccountingExpenses} setActivePage={safeSetActivePage} navigateTo={safeNavigateTo} setAccountingTab={safeSetAccountingTab}/>
      {showDashboardExtra&&<DashboardDirectorAiPanel isLeadership={isLeadershipUser} directorSkillCards={directorSkillCards} dailyReportDate={dailyReportDate} setDailyReportDate={safeSetDailyReportDate} canUseDirectorAgent={canUseDirectorAgent} directorAgentLoading={directorAgentLoading} askDirectorAgent={safeAskDirectorAgent} directorAgentQuestion={directorAgentQuestion} setDirectorAgentQuestion={safeSetDirectorAgentQuestion} isMobile={isMobile} directorAgentAnswer={directorAgentAnswer} directorAgentError={directorAgentError} directorAgentSteps={directorAgentSteps}/>}
      {showDashboardExtra&&<DashboardSupplyPanel showSupplyDashboard={showSupplyDashboard} user={user} openSupplyDashboard={openSupplyDashboard} supplyPendingRequests={supplyPendingRequests} supplyOffersToReview={supplyOffersToReview} supplyInvoicesToPay={supplyInvoicesToPay} supplyInvoiceDebt={supplyInvoiceDebt}/>}
      <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1.3fr 0.7fr',gap:'16px'}}>
        <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'20px',backdropFilter:'blur(24px)'}}>
          <h2 style={{margin:'0 0 16px',fontSize:'18px',color:'#f8fafc'}}>Ключевые объекты</h2>
          {dashboardProjects.slice(0,dashboardProjectPreviewLimit).map(p=>{
            const bs = dashboardBudgetSpentById.get(String(p.id)) || dashboardBudgetSpentByName.get(p.name) || {works:0,materials:0,unexpected:0,total:0};
            const factTotal = bs.total;
            const realProg = _projProgress(p);
            return (
              <div key={p.id} onClick={()=>{safeSetExpandedProject(p.id);safeNavigateTo('projects');}} style={{padding:'16px',borderRadius:'18px',background:'rgba(30,41,59,.62)',border:'1px solid rgba(148,163,184,.18)',marginBottom:'10px',cursor:'pointer'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'12px'}}>
                  <div><div style={{fontWeight:'800',fontSize:'15px',color:'#f8fafc'}}>{p.name}</div><div style={{color:'#94a3b8',fontSize:'12px',marginTop:'3px'}}>{p.client||'Без заказчика'} · {p.status}</div></div>
                  <span style={{display:'inline-flex',borderRadius:'999px',padding:'4px 10px',fontSize:'11px',fontWeight:'700',background:'rgba(234,88,12,.14)',color:'#fdba74',border:'1px solid rgba(234,88,12,.32)',whiteSpace:'nowrap'}}>{realProg}%</span>
                </div>
                <div style={{height:'6px',background:'rgba(148,163,184,.16)',borderRadius:'999px',overflow:'hidden',margin:'10px 0'}}>
                  <div style={{height:'100%',borderRadius:'999px',background:'linear-gradient(90deg,#f97316,#22c55e)',width:`${realProg}%`}}/>
                </div>
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
                  <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Бюджет</div><div style={{fontWeight:'700',color:'#f8fafc',fontSize:'13px',marginTop:'3px'}}>{(Number(p.budget||0)/1000).toFixed(0)+' тыс'}</div></div>
                  <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}} title={'Работы: '+Math.round(bs.works).toLocaleString('ru-RU')+' ₽\nМатериалы: '+Math.round(bs.materials).toLocaleString('ru-RU')+' ₽'+(bs.unexpected>0?'\nДоп.соглашения: '+Math.round(bs.unexpected).toLocaleString('ru-RU')+' ₽':'')}><div style={{color:'#94a3b8',fontSize:'11px'}}>Выполнено</div><div style={{fontWeight:'700',color:'#86efac',fontSize:'13px',marginTop:'3px'}}>{factTotal>0?(factTotal/1000).toFixed(0)+' тыс':'0'}</div></div>
                  <div style={{background:'rgba(30,41,59,.6)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'10px'}}><div style={{color:'#94a3b8',fontSize:'11px'}}>Срок</div><div style={{fontWeight:'700',color:'#f8fafc',fontSize:'13px',marginTop:'3px'}}>{p.deadline||'—'}</div></div>
                </div>
                <div style={{marginTop:'10px',padding:'8px 12px',borderRadius:'12px',background:'rgba(234,88,12,.12)',border:'1px solid rgba(234,88,12,.24)',color:'#fed7aa',fontSize:'12px',fontWeight:'700'}}>{realProg<40?'⚠️ AI: низкий темп':realProg>80?'✅ AI: близко к сдаче':'🔵 AI: темп в норме'}</div>
              </div>
            );
          })}
          {isMobile&&dashboardProjects.length>dashboardProjectPreviewLimit&&(
            <button type="button" onClick={()=>safeNavigateTo('projects')} style={{...btnG,width:'100%',justifyContent:'center',marginTop:'8px',borderColor:'rgba(148,163,184,.28)',background:'rgba(30,41,59,.72)',color:'#e2e8f0'}}>
              Показать все объекты ({dashboardProjects.length})
            </button>
          )}
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:'16px'}}>
          <DashboardRisksPanel risks={risks} setShowReimburseModal={safeSetShowReimburseModal} setActivePage={safeSetActivePage} setWarehouseTab={safeSetWarehouseTab}/>
          {!showDashboardExtra&&isMobile&&(
            <button type="button" onClick={()=>safeSetMobileExpandedRenderLists(prev=>({...prev,[dashboardExtraKey]:true}))} style={{...btnO,width:'100%',justifyContent:'center',padding:'12px 14px'}}>
              Загрузить рабочие панели
            </button>
          )}
          {showDashboardExtra&&<DashboardProductionSummaryPanel workJournal={workJournalList} workDocDate={getWorkDocDate} normalizeDocDate={formatDocDate} dailyReportDate={dailyReportDate} setDailyReportDate={safeSetDailyReportDate} user={user} showPreview={previewDocument} buildDailyObjectReportContent={buildDailyObjectReport} setActivePage={safeSetActivePage} setAccountingTab={safeSetAccountingTab}/>}
          {showDashboardExtra&&<DashboardActivityPanel activityLog={activityLogList}/>}
        </div>
      </div>
      <div style={{height:'100px'}}/>
    </div>
  );
}
