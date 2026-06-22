import React from 'react';
import { Bot, Menu, MessageSquare } from 'lucide-react';
import NotificationsDropdown from './NotificationsDropdown';

export default function DashboardTopBar({
  C,
  setSidebarVisible,
  darkMode,
  setDarkMode,
  setShowChatPanel,
  unreadMessagesCount,
  setShowAiAssistant,
  showAiAssistant,
  showNotifications,
  toggleNotifications,
  unreadNotifications,
  btnG,
  btnO,
  myNotifications,
  notifications,
  markMyNotificationsRead,
  closeNotifications,
  navigateTo,
  getNotifPage,
  setShowNotifications,
  setNotifications,
  user,
  setUser,
  API,
  setShowQuickActions,
  isMobile = false,
}) {
  const iconButtonStyle = {
    padding: isMobile ? '9px 11px' : '8px 10px',
    background: 'rgba(30,41,59,.78)',
    border: '1px solid rgba(148,163,184,.18)',
    borderRadius: '12px',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    color: '#94a3b8',
    flex: '0 0 auto',
  };

  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:isMobile?'flex-start':'center',marginBottom:isMobile?'18px':'28px',flexWrap:'wrap',gap:isMobile?'10px':'12px',width:'100%',minWidth:0,boxSizing:'border-box',overflowX:'hidden'}}>
      <div style={{width:isMobile?'100%':'auto',minWidth:0}}>
        <h1 style={{fontSize:isMobile?'23px':'28px',lineHeight:1.08,fontWeight:'800',letterSpacing:0,margin:0,color:'#f8fafc',overflowWrap:'anywhere'}}>Центр управления стройкой</h1>
        <p style={{color:'#94a3b8',margin:'6px 0 0',fontSize:isMobile?'13px':'14px',lineHeight:1.35,overflowWrap:'anywhere'}}>Контроль объектов, финансов, склада и рисков</p>
      </div>
      <div style={{display:'flex',gap:isMobile?'8px':'10px',alignItems:'center',justifyContent:isMobile?'flex-start':'flex-end',flexWrap:'wrap',width:isMobile?'100%':'auto',minWidth:0}}>
        <button onClick={()=>setSidebarVisible(true)} title="Открыть меню" style={iconButtonStyle}><Menu size={18}/></button>
        <button onClick={()=>setDarkMode(d=>!d)} title={darkMode?'Светлая тема':'Тёмная тема'} style={{...iconButtonStyle,fontSize:'16px'}}>{darkMode?'☀️':'🌙'}</button>
        <button onClick={()=>setShowChatPanel(s=>!s)} style={{...iconButtonStyle,position:'relative'}}><MessageSquare size={18} color='#94a3b8'/>{unreadMessagesCount>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:'#ef4444',color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700',minWidth:'16px',textAlign:'center'}}>{unreadMessagesCount>99?'99+':unreadMessagesCount}</span>}</button>
        <button onClick={()=>setShowAiAssistant(!showAiAssistant)} style={iconButtonStyle}><Bot size={18} color='#94a3b8'/></button>
        <NotificationsDropdown showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} C={C} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} navigateTo={navigateTo} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} user={user} setUser={setUser} API={API} isMobile={isMobile} buttonStyle={{...iconButtonStyle,padding:isMobile?'9px 11px':'8px 10px'}}/>
        <button onClick={()=>setShowQuickActions(true)} style={{background:'linear-gradient(135deg,#f97316,#ea580c)',border:'none',borderRadius:'14px',padding:isMobile?'9px 14px':'10px 18px',color:'white',fontWeight:'700',cursor:'pointer',fontSize:isMobile?'12px':'13px',boxShadow:'0 8px 24px rgba(234,88,12,.35)',flex:'0 0 auto'}}>⚡ Быстро</button>
      </div>
    </div>
  );
}
