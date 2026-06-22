import React from 'react';
import { Bot, CloudSun, CreditCard, FolderKanban, MessageSquare, Package, Plus, Truck, X } from 'lucide-react';

export default function QuickActionsModal({
  showQuickActions,
  setShowQuickActions,
  C,
  btnG,
  user,
  projects,
  visibleActiveProjects,
  openReceiveInvoice,
  setActivePage,
  setWarehouseTab,
  navigateTo,
  API,
  setMaterialTransfers,
  setShowTransferForm,
  setSelectedWarehouseProject,
  setShowOwnExpenseForm,
  setShowChatPanel,
  setShowAiAssistant,
}) {
  if (!showQuickActions) return null;
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 640;
  const isSmallScreen = typeof window !== 'undefined' && window.innerWidth <= 860;

  const iconBg = (color) => `rgba(${color==='#f97316'?'249,115,22':color==='#22c55e'?'34,197,94':color==='#3b82f6'?'59,130,246':color==='#f59e0b'?'245,158,11':color==='#8b5cf6'?'139,92,246':color==='#10b981'?'16,185,129':color==='#06b6d4'?'6,182,212':'249,115,22'},.15)`;
  const actions = [
    {icon:<Plus size={24}/>,label:'Принять на склад',color:'#3b82f6',action:()=>{openReceiveInvoice('',{scanFirst:true});setShowQuickActions(false);},roles:['директор','зам_директора','прораб','кладовщик','снабженец']},
    {icon:<Truck size={24}/>,label:'Передать материал',color:'#10b981',action:async()=>{const visible=visibleActiveProjects(projects);if(visible.length===1){const pn=visible[0].name;try{const res=await fetch(API+'/material-transfers?project_name='+encodeURIComponent(pn));const data=await res.json();setMaterialTransfers(Array.isArray(data)?data:[]);}catch(_e){setMaterialTransfers([]);}if(setSelectedWarehouseProject) setSelectedWarehouseProject(pn);if(setWarehouseTab) setWarehouseTab('objects');(navigateTo || setActivePage)('warehouse');setShowTransferForm(true);setShowQuickActions(false);return;}setShowQuickActions(false);if(setWarehouseTab) setWarehouseTab('objects');(navigateTo || setActivePage)('warehouse');},roles:['директор','зам_директора','прораб','кладовщик']},
    {icon:<CreditCard size={24}/>,label:'Мои траты',color:'#22c55e',action:()=>{setShowQuickActions(false);setShowOwnExpenseForm(true);}},
    {icon:<MessageSquare size={24}/>,label:'Чат',color:'#3b82f6',action:()=>{setShowQuickActions(false);setShowChatPanel(true);}},
    {icon:<CloudSun size={24}/>,label:'Погода',color:'#06b6d4',action:()=>{setShowQuickActions(false);(navigateTo || setActivePage)('weather');},roles:['прораб','главный_инженер']},
    {icon:<FolderKanban size={24}/>,label:'Объекты',color:'#f59e0b',action:()=>{setShowQuickActions(false);(navigateTo || setActivePage)('projects');},roles:['директор','зам_директора','главный_инженер','прораб','стройконтроль','технадзор','сметчик']},
    {icon:<Package size={24}/>,label:'Склад',color:'#10b981',action:()=>{setShowQuickActions(false);(navigateTo || setActivePage)('warehouse');},roles:['директор','зам_директора','кладовщик','снабженец']},
    {icon:<Bot size={24}/>,label:'ИИ',color:'#f97316',action:()=>{setShowQuickActions(false);setShowAiAssistant(true);}},
  ].filter(btn=>!btn.roles||(user&&btn.roles.includes(user.role)));

  return (<>
    <div onMouseDown={e=>{e.preventDefault();setShowQuickActions(false);}} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1700}}/>
    <div style={{position:'fixed',top:isSmallScreen?'calc(env(safe-area-inset-top, 0px) + 16px)':'50%',left:'50%',transform:isSmallScreen?'translateX(-50%)':'translate(-50%,-50%)',backgroundColor:C.bgWhite,borderRadius:'18px',padding:isMobile?'16px':'20px',zIndex:1701,boxShadow:'0 12px 50px rgba(0,0,0,0.4)',width:isSmallScreen?'min(520px, calc(100vw - 24px))':'min(520px, 92vw)',maxWidth:'calc(100vw - 24px)',maxHeight:isSmallScreen?'calc(100dvh - env(safe-area-inset-top, 0px) - env(safe-area-inset-bottom, 0px) - 32px)':'calc(100dvh - 24px)',overflowY:'auto',overflowX:'hidden',border:'1.5px solid '+C.border,boxSizing:'border-box'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',marginBottom:'14px'}}>
        <b style={{color:C.text,fontSize:'16px',lineHeight:1.2,overflowWrap:'anywhere'}}>⚡ Быстрые действия</b>
        <button onClick={()=>setShowQuickActions(false)} style={{...btnG,padding:'4px 10px'}}><X size={14}/></button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:isMobile?'repeat(2,minmax(0,1fr))':'repeat(auto-fit,minmax(110px,1fr))',gap:'10px',minWidth:0}}>
        {actions.map((btn,i)=>(
          <div key={i} onClick={btn.action} style={{display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',minHeight:isMobile?'104px':'auto',padding:isMobile?'12px 6px':'14px 8px',borderRadius:'14px',cursor:'pointer',backgroundColor:C.bg,border:'1.5px solid '+C.border,transition:'all 0.15s',minWidth:0,boxSizing:'border-box'}}>
            <div style={{width:isMobile?'46px':'48px',height:isMobile?'46px':'48px',borderRadius:'14px',background:iconBg(btn.color),display:'flex',alignItems:'center',justifyContent:'center',marginBottom:'8px',color:btn.color,flex:'0 0 auto'}}>{btn.icon}</div>
            <span style={{fontSize:isMobile?'11px':'11px',color:C.text,fontWeight:'600',textAlign:'center',lineHeight:'1.25',overflowWrap:'anywhere',maxWidth:'100%'}}>{btn.label}</span>
          </div>
        ))}
      </div>
    </div>
  </>);
}
