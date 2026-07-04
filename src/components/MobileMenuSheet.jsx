import React from 'react';
import { C as DEFAULT_C } from '../constants/uiTheme';

export default function MobileMenuSheet({showMobileMenu, setShowMobileMenu, menuItems, activePage, navigateTo, setActivePage, C}) {
  if (!showMobileMenu) return null;
  const theme = C || DEFAULT_C;
  const items = Array.isArray(menuItems) ? menuItems : [];
  const closeMenu = typeof setShowMobileMenu === 'function' ? setShowMobileMenu : () => {};
  const openPage = typeof navigateTo === 'function' ? navigateTo : (typeof setActivePage === 'function' ? setActivePage : () => {});
  return (
    <>
      <div onMouseDown={e=>{e.preventDefault();closeMenu(false);}} style={{position:'fixed',top:0,left:0,right:0,bottom:'60px',backgroundColor:'rgba(0,0,0,0.5)',zIndex:299}}/>
      <div style={{position:'fixed',bottom:'60px',left:0,right:0,backgroundColor:theme.bgWhite,borderRadius:'16px 16px 0 0',padding:'16px',zIndex:300,maxHeight:'60vh',overflowY:'auto',boxShadow:'0 -8px 30px rgba(0,0,0,0.15)',borderTop:'1.5px solid '+theme.border}}>
        <div style={{textAlign:'center',marginBottom:'12px'}}><div style={{width:'36px',height:'4px',backgroundColor:theme.borderDark,borderRadius:'2px',margin:'0 auto'}}/></div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'8px'}}>
          {items.map(m=>(
            <div key={m.id} onClick={()=>{
              openPage(m.id);
              closeMenu(false);
            }} style={{display:'flex',flexDirection:'column',alignItems:'center',padding:'12px 8px',borderRadius:'12px',cursor:'pointer',backgroundColor:activePage===m.id?'rgba(249,115,22,0.15)':'rgba(30,41,59,0.6)',border:'1px solid rgba(148,163,184,0.12)'}}>
              <span style={{fontSize:'24px',marginBottom:'4px'}}>{m.icon}</span>
              <span style={{fontSize:'11px',color:activePage===m.id?'#f97316':'#94a3b8',fontWeight:activePage===m.id?'700':'400',textAlign:'center',lineHeight:'1.3'}}>{m.label}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
