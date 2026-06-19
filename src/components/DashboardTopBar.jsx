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
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'28px',flexWrap:'wrap',gap:'12px'}}>
      <div>
        <h1 style={{fontSize:'28px',fontWeight:'800',letterSpacing:'-.04em',margin:0,color:'#f8fafc'}}>Центр управления стройкой</h1>
        <p style={{color:'#94a3b8',margin:'6px 0 0',fontSize:'14px'}}>Контроль объектов, финансов, склада и рисков</p>
      </div>
      <div style={{display:'flex',gap:'10px',alignItems:'center'}}>
        <button onClick={()=>setSidebarVisible(true)} title="Открыть меню" style={{padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',color:'#94a3b8'}}><Menu size={18}/></button>
        <button onClick={()=>setDarkMode(d=>!d)} title={darkMode?'Светлая тема':'Тёмная тема'} style={{padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',fontSize:'16px'}}>{darkMode?'☀️':'🌙'}</button>
        <button onClick={()=>setShowChatPanel(s=>!s)} style={{position:'relative',padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}><MessageSquare size={18} color='#94a3b8'/>{unreadMessagesCount>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:'#ef4444',color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700',minWidth:'16px',textAlign:'center'}}>{unreadMessagesCount>99?'99+':unreadMessagesCount}</span>}</button>
        <button onClick={()=>setShowAiAssistant(!showAiAssistant)} style={{padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}><Bot size={18} color='#94a3b8'/></button>
        <NotificationsDropdown showNotifications={showNotifications} toggleNotifications={toggleNotifications} unreadNotifications={unreadNotifications} C={C} btnG={btnG} btnO={btnO} myNotifications={myNotifications} notifications={notifications} markMyNotificationsRead={markMyNotificationsRead} closeNotifications={closeNotifications} navigateTo={navigateTo} getNotifPage={getNotifPage} setShowNotifications={setShowNotifications} setNotifications={setNotifications} user={user} setUser={setUser} API={API} isMobile={isMobile} buttonStyle={{padding:'8px 10px',background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',color:'#94a3b8'}}/>
        <button onClick={()=>setShowQuickActions(true)} style={{background:'linear-gradient(135deg,#f97316,#ea580c)',border:'none',borderRadius:'14px',padding:'10px 18px',color:'white',fontWeight:'700',cursor:'pointer',fontSize:'13px',boxShadow:'0 8px 24px rgba(234,88,12,.35)'}}>⚡ Быстро</button>
      </div>
    </div>
  );
}
