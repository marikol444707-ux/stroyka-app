import React from 'react';

export const theme = {
  accent: '#f97316',
  accentLight: '#fff7ed',
  success: '#10b981',
  danger: '#ef4444',
  warning: '#f59e0b',
  text: '#111827',
  textSec: '#6b7280',
  textMuted: '#9ca3af',
  border: '#e5e7eb',
  bg: '#f9fafb',
  bgWhite: '#ffffff',
};

export const Card = ({children, style, onClick}) => (
  <div onClick={onClick} style={{backgroundColor:'white',borderRadius:'12px',border:'1.5px solid #e5e7eb',boxShadow:'0 1px 3px rgba(0,0,0,0.06)',...style}}>{children}</div>
);

export const BtnPrimary = ({children, onClick, disabled, style}) => (
  <button onClick={onClick} disabled={disabled} style={{backgroundColor:'#f97316',color:'white',border:'none',borderRadius:'8px',padding:'8px 16px',cursor:'pointer',display:'flex',alignItems:'center',gap:'6px',fontSize:'13px',fontWeight:'600',opacity:disabled?0.6:1,...style}}>{children}</button>
);

export const BtnSecondary = ({children, onClick, style}) => (
  <button onClick={onClick} style={{backgroundColor:'white',color:'#111827',border:'1.5px solid #e5e7eb',borderRadius:'8px',padding:'8px 16px',cursor:'pointer',display:'flex',alignItems:'center',gap:'6px',fontSize:'13px',...style}}>{children}</button>
);

export const Modal = ({children, title, onClose}) => (
  <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
    <div style={{backgroundColor:'white',borderRadius:'16px',padding:'20px',width:'360px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
      {title&&<b style={{color:'#111827',fontSize:'15px',display:'block',marginBottom:'12px'}}>{title}</b>}
      {children}
    </div>
  </div>
);
