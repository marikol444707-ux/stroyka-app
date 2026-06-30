import React from 'react';
import { Menu, MessageSquare, Search, Settings, Zap } from 'lucide-react';
import NotificationsDropdown from './NotificationsDropdown';

export default function AppHeaderBar({
  C,
  activePage,
  isCompactHeader,
  isMobile,
  setSidebarVisible,
  allMenuItems,
  globalSearch,
  setGlobalSearch,
  setShowSearch,
  showSearch,
  searchResults,
  navigateTo,
  inp,
  darkMode,
  setDarkMode,
  setShowQuickActions,
  user,
  openSystemStatus,
  setShowChatPanel,
  unreadMessagesCount,
  showNotifications,
  toggleNotifications,
  unreadNotifications,
  btnG,
  btnO,
  myNotifications,
  notifications,
  markMyNotificationsRead,
  closeNotifications,
  getNotifPage,
  setShowNotifications,
  setNotifications,
  setUser,
  API,
}) {
  const touchCompact = typeof window !== 'undefined'
    && (window.visualViewport?.width || window.innerWidth || 0) < 1100
    && (
      (typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches)
      || (typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || ''))
    );
  const compact = Boolean(isCompactHeader || isMobile || touchCompact);
  const phoneLike = Boolean(isMobile || touchCompact);
  const headerButtonStyle = {
    padding: phoneLike ? '8px 10px' : '8px 12px',
    backgroundColor: C.bgGray,
    border: '1.5px solid ' + C.border,
    borderRadius: '10px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: '0 0 auto',
    minWidth: phoneLike ? '40px' : undefined,
    minHeight: phoneLike ? '40px' : undefined,
    color: C.textSec,
  };

  return (
    <div style={{backgroundColor:C.bgWhite,paddingTop:phoneLike?'calc(env(safe-area-inset-top, 0px) + 10px)':compact?'10px':'12px',paddingRight:compact?'12px':'24px',paddingBottom:compact?'10px':'12px',paddingLeft:compact?'12px':'24px',borderBottom:'1.5px solid '+C.border,display:activePage==='dashboard'?'none':'flex',alignItems:compact?'flex-start':'center',gap:compact?'8px':'15px',flexWrap:'wrap',flexShrink:0,boxShadow:'0 1px 3px rgba(0,0,0,0.04)',width:'100%',maxWidth:'100vw',minWidth:0,boxSizing:'border-box',overflowX:'hidden',justifyContent:compact?'flex-start':'space-between'}}>
      <button onClick={()=>setSidebarVisible(true)} title="Открыть меню" style={headerButtonStyle}><Menu size={18}/></button>
      <div style={{width:'8px',height:'32px',borderRadius:'4px',background:'linear-gradient(135deg,#f97316,#ea580c)',flexShrink:0,display:phoneLike?'none':'block'}}/>
      <h2 style={{margin:0,color:C.text,fontSize:phoneLike?'17px':'18px',lineHeight:1.2,fontWeight:'700',flex:compact?'1 1 calc(100% - 56px)':'1 1 auto',minWidth:0,alignSelf:'center',whiteSpace:phoneLike?'normal':'nowrap',overflow:'hidden',textOverflow:'ellipsis',overflowWrap:'anywhere',maxWidth:phoneLike?'calc(100vw - 92px)':'none'}}>{allMenuItems.find(m=>m.id===activePage)?.label||'СтройКа'}</h2>
      <div style={{flex:compact?'1 1 100%':'0 1 320px',maxWidth:compact?'none':'320px',position:'relative',order:compact?3:0,display:phoneLike?'none':'block',minWidth:0}}>
        <Search size={15} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
        <input placeholder="Поиск..." value={globalSearch} onChange={e=>{setGlobalSearch(e.target.value);setShowSearch(e.target.value.length>=2);}} onBlur={()=>setTimeout(()=>setShowSearch(false),200)} style={{...inp,marginBottom:0,paddingLeft:'32px',fontSize:'13px'}}/>
        {showSearch&&searchResults.length>0&&(<div style={{position:'absolute',top:'100%',left:0,right:0,backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'10px',boxShadow:'0 8px 25px rgba(0,0,0,0.1)',zIndex:1000,maxHeight:'280px',overflowY:'auto',marginTop:'4px'}}>{searchResults.map((r,i)=>(<div key={i} onClick={()=>{navigateTo(r.page);setGlobalSearch('');setShowSearch(false);}} style={{padding:'10px 15px',cursor:'pointer',borderBottom:'1px solid '+C.border,display:'flex',gap:'10px',alignItems:'center'}}><span style={{fontSize:'16px'}}>{r.icon}</span><div><b style={{fontSize:'13px',color:C.text}}>{r.title}</b><p style={{color:C.textSec,margin:0,fontSize:'11px'}}>{r.subtitle}</p></div></div>))}</div>)}
      </div>
      <div style={{position:'relative',display:'flex',gap:'8px',alignItems:'center',justifyContent:phoneLike?'flex-start':'flex-end',flexWrap:'wrap',marginLeft:phoneLike?0:'auto',width:phoneLike?'100%':'auto',maxWidth:'100%',minWidth:0,overflowX:'hidden'}}>
        <button onClick={()=>setDarkMode(d=>!d)} title={darkMode?'Светлая тема':'Тёмная тема'} style={{...headerButtonStyle,fontSize:'16px'}}>{darkMode?'☀️':'🌙'}</button>
        <button onClick={()=>setShowQuickActions(true)} title='Быстрые действия' style={{...headerButtonStyle,background:'linear-gradient(135deg,#f97316,#ea580c)',border:'none',color:'white',fontWeight:'700',fontSize:'13px',gap:'4px'}}><Zap size={17}/><span style={{fontSize:'13px',display:phoneLike?'none':'inline'}}>Быстро</span></button>
        {['директор','зам_директора','system_owner'].includes(user.role)&&<button onClick={openSystemStatus} title='Статус системы' style={{...headerButtonStyle,gap:'5px',fontSize:phoneLike?'0':'12px',fontWeight:'700'}}><Settings size={17}/><span style={{display:phoneLike?'none':'inline'}}>Статус</span></button>}
        <button onClick={()=>setShowChatPanel(s=>!s)} title='Чат' style={{...headerButtonStyle,position:'relative'}}><MessageSquare size={18} color={C.textSec}/>{unreadMessagesCount>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:'#ef4444',color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700',minWidth:'16px',textAlign:'center'}}>{unreadMessagesCount>99?'99+':unreadMessagesCount}</span>}</button>
        <NotificationsDropdown showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} C={C} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} navigateTo={navigateTo} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} user={user} setUser={setUser} API={API} isMobile={phoneLike} showVkConnect/>
      </div>
    </div>
  );
}
