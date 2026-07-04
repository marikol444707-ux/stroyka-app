import React from 'react';
import { ChevronRight, LogOut } from 'lucide-react';
import { C as DEFAULT_C } from '../constants/uiTheme';

export default function AppSidebar({
  isMobile,
  sidebarRef,
  sidebarVisible,
  setSidebarVisible,
  C,
  user,
  roleLabels,
  roleColor,
  menuItems,
  supplyRequests,
  isLeadership,
  isMasterRole,
  activePage,
  navigateTo,
  handleLogout,
}) {
  const theme = C || DEFAULT_C;
  const currentUser = user || {};
  const currentRole = currentUser.role || '';
  const currentName = currentUser.name || 'Пользователь';
  const currentUserId = currentUser.id;
  const requests = Array.isArray(supplyRequests) ? supplyRequests : [];
  const items = Array.isArray(menuItems) ? menuItems : [];
  const setSidebarOpen = typeof setSidebarVisible === 'function' ? setSidebarVisible : () => {};
  const openPage = typeof navigateTo === 'function' ? navigateTo : () => {};
  const logout = typeof handleLogout === 'function' ? handleLogout : () => {};
  const leadershipCheck = typeof isLeadership === 'function'
    ? isLeadership
    : () => ['директор', 'зам_директора', 'system_owner'].includes(currentRole);
  const masterRoleCheck = typeof isMasterRole === 'function'
    ? isMasterRole
    : () => ['мастер', 'субподрядчик', 'бригадир'].includes(currentRole);
  const labels = roleLabels || {};
  const colorForRole = typeof roleColor === 'function' ? roleColor : () => theme.accent || '#f97316';
  const isOpen = isMobile ? sidebarVisible : true;
  const closeAfterNavigate = () => {
    if (isMobile) setSidebarOpen(false);
  };
  const supplyBadgeCount = item => {
    if (item.id !== 'supply' || !requests.length) return 0;
    if (currentRole === 'прораб') return requests.filter(r => r.status === 'Новая').length;
    if (leadershipCheck()) return requests.filter(r => r.status === 'Подтверждена прорабом').length;
    if (masterRoleCheck()) {
      return requests.filter(r => (r.createdBy === currentName || r.requestedById === currentUserId) && (r.status === 'Утверждена' || r.status === 'Отклонена')).length;
    }
    return 0;
  };

  return (
    <>
      {isMobile && <div style={{position:'fixed',top:0,left:0,width:'16px',height:'100vh',zIndex:200}} onMouseEnter={()=>setSidebarOpen(true)}/>}
      <div ref={sidebarRef} onMouseLeave={isMobile ? ()=>setSidebarOpen(false) : undefined} style={{position:'fixed',top:0,left:0,height:'100vh',width:isMobile?'min(86vw,300px)':'240px',backgroundColor:theme.sidebar,color:'white',zIndex:300,transform:isOpen?'translateX(0)':'translateX(-100%)',transition:'transform 0.25s cubic-bezier(0.4,0,0.2,1)',display:'flex',flexDirection:'column',boxShadow:isOpen?'4px 0 30px rgba(0,0,0,0.15)':'none'}}>
        <div style={{padding:'22px 20px',borderBottom:'1px solid rgba(255,255,255,0.08)'}}><div style={{display:'flex',alignItems:'center',gap:'12px'}}><div style={{width:'40px',height:'40px',borderRadius:'12px',background:'linear-gradient(135deg,#f97316,#ea580c)',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'20px',flexShrink:0}}>🏗️</div><div><h3 style={{margin:0,color:'white',fontSize:'18px',fontWeight:'800'}}>СтройКа</h3><p style={{margin:0,color:'rgba(255,255,255,0.4)',fontSize:'11px'}}>ERP система</p></div></div></div>
        <div style={{padding:'14px',borderBottom:'1px solid rgba(255,255,255,0.08)'}}><div style={{backgroundColor:'rgba(255,255,255,0.06)',borderRadius:'10px',padding:'12px',display:'flex',alignItems:'center',gap:'10px'}}><div style={{width:'36px',height:'36px',borderRadius:'10px',backgroundColor:colorForRole(currentRole),display:'flex',alignItems:'center',justifyContent:'center',fontSize:'14px',color:'white',fontWeight:'800',flexShrink:0}}>{currentName.charAt(0)}</div><div style={{overflow:'hidden'}}><div style={{fontSize:'13px',fontWeight:'600',color:'white',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{currentName}</div><div style={{fontSize:'11px',color:'rgba(255,255,255,0.4)',marginTop:'1px'}}>{labels[currentRole]||currentRole}</div></div></div></div>
        <div style={{padding:'10px',flex:1,overflowY:'auto'}}>
          {items.map(item => {
            const badgeCount = supplyBadgeCount(item);
            return (<div key={item.id} onClick={()=>{ openPage(item.id); closeAfterNavigate(); }} style={{display:'flex',alignItems:'center',gap:'10px',padding:'10px 12px',borderRadius:'8px',cursor:'pointer',marginBottom:'2px',backgroundColor:activePage===item.id?'rgba(249,115,22,0.15)':'transparent',border:activePage===item.id?'1px solid rgba(249,115,22,0.3)':'1px solid transparent',transition:'all 0.15s'}}><span style={{color:activePage===item.id?theme.accent:'rgba(255,255,255,0.5)',flexShrink:0,position:'relative'}}>{item.icon}{badgeCount>0&&<span style={{position:'absolute',top:'-6px',right:'-8px',backgroundColor:theme.danger,color:'white',borderRadius:'10px',padding:'1px 5px',fontSize:'9px',fontWeight:'700',minWidth:'14px',textAlign:'center',lineHeight:'1.2'}}>{badgeCount>99?'99+':badgeCount}</span>}</span><span style={{fontSize:'13px',fontWeight:activePage===item.id?'600':'400',color:activePage===item.id?'white':'rgba(255,255,255,0.6)',flex:1}}>{item.label}</span>{activePage===item.id&&<ChevronRight size={14} color={theme.accent}/>}</div>);
          })}
        </div>
        <div style={{padding:'10px',borderTop:'1px solid rgba(255,255,255,0.08)'}}>
          <div onClick={()=>logout()} style={{display:'flex',alignItems:'center',gap:'10px',padding:'10px 12px',borderRadius:'8px',cursor:'pointer',backgroundColor:'rgba(239,68,68,0.1)',border:'1px solid rgba(239,68,68,0.2)'}}><LogOut size={18} color='#ef4444'/><span style={{fontSize:'13px',color:'#ef4444',fontWeight:'500'}}>Выйти</span></div>
        </div>
      </div>
    </>
  );
}
