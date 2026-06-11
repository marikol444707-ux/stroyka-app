import React from 'react';
import { ChevronUp, FolderKanban, LayoutDashboard, MessageSquare, Package } from 'lucide-react';

const MOBILE_NAV_ITEMS = [
  {id:'dashboard',icon:<LayoutDashboard size={20}/>,label:'Главная'},
  {id:'projects',icon:<FolderKanban size={20}/>,label:'Объекты'},
  {id:'warehouse',icon:<Package size={20}/>,label:'Склад'},
  {id:'companychat',icon:<MessageSquare size={20}/>,label:'Чат',isPanel:true},
  {id:'more',icon:<ChevronUp size={20}/>,label:'Ещё'},
];

export default function MobileBottomNav({activePage, isMobile, unreadMessagesCount, menuItems = [], navigateTo, setActivePage, setShowMobileMenu, setShowQuickActions, setShowChatPanel}) {
  const allowedMenuIds = new Set((menuItems || []).map(item => item.id));
  const visibleItems = MOBILE_NAV_ITEMS.filter(item => item.id === 'more' || item.id === 'companychat' || allowedMenuIds.has(item.id));
  const goToPage = (pageId) => {
    if (typeof navigateTo === 'function') {
      navigateTo(pageId);
    } else {
      setActivePage(pageId);
    }
  };
  return (
    <div style={{position:'fixed',bottom:0,left:0,right:0,backgroundColor:activePage==='dashboard'?'rgba(15,23,42,0.95)':'white',borderTop:activePage==='dashboard'?'1px solid rgba(148,163,184,0.18)':'1.5px solid #e5e7eb',display:isMobile?'flex':'none',justifyContent:'space-around',padding:'8px 0 12px',zIndex:200,boxShadow:'0 -4px 20px rgba(0,0,0,0.06)'}}>
      {visibleItems.map(item=>(
        <div key={item.id} onClick={()=>{
          if(item.id==='more'){
            setShowMobileMenu(s=>!s);
            setShowQuickActions(false);
          } else if(item.id==='companychat'){
            setShowChatPanel(s=>!s);
            setShowMobileMenu(false);
            setShowQuickActions(false);
          } else {
            goToPage(item.id);
            setShowMobileMenu(false);
            setShowQuickActions(false);
          }
        }} style={{position:'relative',display:'flex',flexDirection:'column',alignItems:'center',cursor:'pointer',padding:'4px 8px',borderRadius:'8px',backgroundColor:activePage===item.id?(activePage==='dashboard'?'rgba(249,115,22,0.15)':'#fff7ed'):'transparent'}}>
          <span style={{color:activePage===item.id?'#f97316':activePage==='dashboard'?'#94a3b8':'#6b7280',position:'relative'}}>
            {item.icon}
            {item.id==='companychat'&&unreadMessagesCount>0&&<span style={{position:'absolute',top:'-6px',right:'-8px',backgroundColor:'#ef4444',color:'white',borderRadius:'10px',padding:'1px 5px',fontSize:'9px',fontWeight:'700',minWidth:'14px',textAlign:'center',lineHeight:'1.2'}}>{unreadMessagesCount>99?'99+':unreadMessagesCount}</span>}
          </span>
          <span style={{fontSize:'10px',color:activePage===item.id?'#f97316':activePage==='dashboard'?'#94a3b8':'#9ca3af',fontWeight:activePage===item.id?'700':'400',marginTop:'2px'}}>{item.label}</span>
        </div>
      ))}
    </div>
  );
}
