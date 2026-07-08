import React from 'react';
import { Menu, MessageSquare, Search, Settings, Zap } from 'lucide-react';
import { C as DEFAULT_C } from '../constants/uiTheme';
import { CompanyContextSwitcher } from '../features/company-context';
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
  companyContext,
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
  const theme = C || DEFAULT_C;
  const currentUser = user || {};
  const currentRole = currentUser.role || '';
  const menuList = Array.isArray(allMenuItems) ? allMenuItems : [];
  const resultList = Array.isArray(searchResults) ? searchResults : [];
  const openPage = typeof navigateTo === 'function' ? navigateTo : () => {};
  const openSidebar = typeof setSidebarVisible === 'function' ? setSidebarVisible : () => {};
  const changeGlobalSearch = typeof setGlobalSearch === 'function' ? setGlobalSearch : () => {};
  const toggleSearch = typeof setShowSearch === 'function' ? setShowSearch : () => {};
  const toggleTheme = typeof setDarkMode === 'function' ? setDarkMode : () => {};
  const openQuickActions = typeof setShowQuickActions === 'function' ? setShowQuickActions : () => {};
  const openStatus = typeof openSystemStatus === 'function' ? openSystemStatus : () => {};
  const toggleChat = typeof setShowChatPanel === 'function' ? setShowChatPanel : () => {};
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
    backgroundColor: theme.bgGray,
    border: '1.5px solid ' + theme.border,
    borderRadius: '10px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flex: '0 0 auto',
    minWidth: phoneLike ? '40px' : undefined,
    minHeight: phoneLike ? '40px' : undefined,
    color: theme.textSec,
  };

  return (
    <div style={{backgroundColor:theme.bgWhite,paddingTop:phoneLike?'calc(env(safe-area-inset-top, 0px) + 10px)':compact?'10px':'12px',paddingRight:compact?'12px':'24px',paddingBottom:compact?'10px':'12px',paddingLeft:compact?'12px':'24px',borderBottom:'1.5px solid '+theme.border,display:activePage==='dashboard'?'none':'flex',alignItems:compact?'flex-start':'center',gap:compact?'8px':'15px',flexWrap:'wrap',flexShrink:0,boxShadow:'0 1px 3px rgba(0,0,0,0.04)',width:'100%',maxWidth:'100vw',minWidth:0,boxSizing:'border-box',overflowX:'hidden',justifyContent:compact?'flex-start':'space-between'}}>
      <button onClick={()=>openSidebar(true)} title="Открыть меню" style={headerButtonStyle}><Menu size={18}/></button>
      <div style={{width:'8px',height:'32px',borderRadius:'4px',background:'linear-gradient(135deg,#f97316,#ea580c)',flexShrink:0,display:phoneLike?'none':'block'}}/>
      <h2 style={{margin:0,color:theme.text,fontSize:phoneLike?'17px':'18px',lineHeight:1.2,fontWeight:'700',flex:compact?'1 1 calc(100% - 56px)':'1 1 auto',minWidth:0,alignSelf:'center',whiteSpace:phoneLike?'normal':'nowrap',overflow:'hidden',textOverflow:'ellipsis',overflowWrap:'anywhere',maxWidth:phoneLike?'calc(100vw - 92px)':'none'}}>{menuList.find(m=>m.id===activePage)?.label||'СтройКа'}</h2>
      <div style={{flex:compact?'1 1 100%':'0 1 320px',maxWidth:compact?'none':'320px',position:'relative',order:compact?3:0,display:phoneLike?'none':'block',minWidth:0}}>
        <Search size={15} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:theme.textMuted}}/>
        <input placeholder="Поиск..." value={globalSearch} onChange={e=>{changeGlobalSearch(e.target.value);toggleSearch(e.target.value.length>=2);}} onBlur={()=>setTimeout(()=>toggleSearch(false),200)} style={{...inp,marginBottom:0,paddingLeft:'32px',fontSize:'13px'}}/>
        {showSearch&&resultList.length>0&&(<div style={{position:'absolute',top:'100%',left:0,right:0,backgroundColor:theme.bgWhite,border:'1.5px solid '+theme.border,borderRadius:'10px',boxShadow:'0 8px 25px rgba(0,0,0,0.1)',zIndex:1000,maxHeight:'280px',overflowY:'auto',marginTop:'4px'}}>{resultList.map((r,i)=>(<div key={i} onClick={()=>{openPage(r.page);changeGlobalSearch('');toggleSearch(false);}} style={{padding:'10px 15px',cursor:'pointer',borderBottom:'1px solid '+theme.border,display:'flex',gap:'10px',alignItems:'center'}}><span style={{fontSize:'16px'}}>{r.icon}</span><div><b style={{fontSize:'13px',color:theme.text}}>{r.title}</b><p style={{color:theme.textSec,margin:0,fontSize:'11px'}}>{r.subtitle}</p></div></div>))}</div>)}
      </div>
      <div style={{position:'relative',display:'flex',gap:'8px',alignItems:'center',justifyContent:phoneLike?'flex-start':'flex-end',flexWrap:'wrap',marginLeft:phoneLike?0:'auto',width:phoneLike?'100%':'auto',maxWidth:'100%',minWidth:0,overflowX:'hidden'}}>
        <CompanyContextSwitcher C={theme} companyContext={companyContext} isMobile={phoneLike}/>
        <button onClick={()=>toggleTheme(d=>!d)} title={darkMode?'Светлая тема':'Тёмная тема'} style={{...headerButtonStyle,fontSize:'16px'}}>{darkMode?'☀️':'🌙'}</button>
        <button onClick={()=>openQuickActions(true)} title='Быстрые действия' style={{...headerButtonStyle,background:'linear-gradient(135deg,#f97316,#ea580c)',border:'none',color:'white',fontWeight:'700',fontSize:'13px',gap:'4px'}}><Zap size={17}/><span style={{fontSize:'13px',display:phoneLike?'none':'inline'}}>Быстро</span></button>
        {['директор','зам_директора','system_owner'].includes(currentRole)&&<button onClick={openStatus} title='Статус системы' style={{...headerButtonStyle,gap:'5px',fontSize:phoneLike?'0':'12px',fontWeight:'700'}}><Settings size={17}/><span style={{display:phoneLike?'none':'inline'}}>Статус</span></button>}
        <button onClick={()=>toggleChat(s=>!s)} title='Чат' style={{...headerButtonStyle,position:'relative'}}><MessageSquare size={18} color={theme.textSec}/>{unreadMessagesCount>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:'#ef4444',color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700',minWidth:'16px',textAlign:'center'}}>{unreadMessagesCount>99?'99+':unreadMessagesCount}</span>}</button>
        <NotificationsDropdown showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} C={theme} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} navigateTo={openPage} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} user={currentUser} setUser={setUser} API={API} isMobile={phoneLike} showVkConnect/>
      </div>
    </div>
  );
}
