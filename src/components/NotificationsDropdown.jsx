import React from 'react';
import { Bell, X } from 'lucide-react';

export default function NotificationsDropdown({
  showNotifications,
  toggleNotifications,
  unreadNotifications,
  C,
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
  isMobile = false,
  buttonStyle = {},
  bellSize = 18,
  dropdownWidth,
  dropdownRight,
  title = 'Уведомления',
  markAllText = 'Прочитать все',
  showVkConnect = false,
  emptyStyle = {},
}) {
  const fullList = myNotifications(notifications);
  const list = fullList.slice(0, isMobile ? 20 : 50);
  const width = dropdownWidth || (isMobile ? 'calc(100vw - 24px)' : '360px');
  const right = dropdownRight !== undefined ? dropdownRight : (isMobile ? '-8px' : 0);

  const markReadAndOpen = (n) => {
    navigateTo(getNotifPage(n.type));
    setShowNotifications(false);
    const updated = notifications.map(x => x.id === n.id ? {...x, read: true} : x);
    setNotifications(updated);
    localStorage.setItem('notifications', JSON.stringify(updated));
  };

  const connectVk = () => {
    const vkId = prompt('Введите ваш ID ВКонтакте (число из vk.com/id12345):');
    if (vkId && Number(vkId)) {
      fetch(API + '/vk-connect', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({vkId: Number(vkId), email: user.email})
      }).then(() => {
        const updated = {...user, vkId: Number(vkId)};
        setUser(updated);
        localStorage.setItem('user', JSON.stringify(updated));
        alert('ВК подключён!');
      });
    }
  };

  return (
    <div data-notification-root="1" style={{position:'relative',display:'flex',alignItems:'center'}}>
      <button onClick={toggleNotifications} style={{position:'relative',padding:'8px',backgroundColor:C.bgGray,border:'1.5px solid '+C.border,borderRadius:'10px',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',...buttonStyle}}>
        <Bell size={bellSize} color={buttonStyle.color || C.textSec}/>
        {unreadNotifications>0&&<span style={{position:'absolute',top:'-4px',right:'-4px',backgroundColor:C.danger||'#ef4444',color:'white',borderRadius:'50%',padding:'1px 5px',fontSize:'10px',fontWeight:'700'}}>{unreadNotifications>99?'99+':unreadNotifications}</span>}
      </button>
      {showNotifications&&(
        <div style={{position:'absolute',top:'calc(100% + 8px)',right,width,backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,borderRadius:'14px',boxShadow:'0 8px 40px rgba(0,0,0,0.18)',zIndex:1000,maxHeight:'420px',overflowY:'auto'}}>
          <div style={{padding:'14px 18px',borderBottom:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px'}}>
            <b style={{color:C.text,fontSize:'14px'}}>{title}</b>
            <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
              <button onClick={markMyNotificationsRead} style={{...btnG,fontSize:'11px',padding:'3px 10px'}}>{markAllText}</button>
              <button onClick={closeNotifications} title="Свернуть" style={{...btnG,fontSize:'11px',padding:'3px 8px'}}><X size={13}/></button>
            </div>
          </div>
          {fullList.length===0&&<p style={{padding:'20px',textAlign:'center',color:C.textMuted,...emptyStyle}}>Нет уведомлений</p>}
          {showVkConnect&&(
            <div style={{padding:'12px 18px',borderTop:'1.5px solid '+C.border,backgroundColor:C.bg}}>
              <p style={{fontSize:'11px',color:C.textSec,margin:'0 0 8px'}}>📱 Уведомления в ВКонтакте:</p>
              {user.vkId ? <span style={{fontSize:'12px',color:C.success}}>✅ ВК подключён (ID: {user.vkId})</span> :
              <button onClick={connectVk} style={{...btnO,fontSize:'11px',padding:'5px 12px',width:'100%',justifyContent:'center'}}>Подключить ВК</button>}
            </div>
          )}
          {list.map(n=>(
            <div key={n.id} onClick={()=>markReadAndOpen(n)} style={{padding:'12px 18px',borderBottom:'1px solid '+C.border,backgroundColor:n.read?'transparent':C.accentLight,cursor:'pointer'}}>
              <p style={{margin:0,fontSize:'13px',color:C.text}}>{n.text}</p>
              <p style={{margin:'3px 0 0',fontSize:'11px',color:C.textMuted}}>{n.time}</p>
            </div>
          ))}
          {fullList.length>list.length&&(
            <div style={{padding:'10px 18px',fontSize:'11px',color:C.textMuted,textAlign:'center'}}>
              Показаны последние {list.length} из {fullList.length}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
