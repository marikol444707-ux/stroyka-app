import React from 'react';
import { Printer, X } from 'lucide-react';

export default function PreviewModal({content, title, onClose, onPrint}) {
  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.6)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:3000}}>
      <div style={{backgroundColor:'white',borderRadius:'16px',width:'820px',maxWidth:'95%',maxHeight:'90vh',display:'flex',flexDirection:'column',boxShadow:'0 20px 60px rgba(0,0,0,0.2)'}}>
        <div style={{padding:'16px 24px',borderBottom:'1px solid #e5e7eb',display:'flex',justifyContent:'space-between',alignItems:'center',backgroundColor:'#f9fafb',borderRadius:'16px 16px 0 0'}}>
          <b style={{color:'#111827',fontSize:'15px'}}>{'📄 '+title}</b>
          <div style={{display:'flex',gap:'10px'}}>
            <button onClick={() => onPrint?.(content)} style={{padding:'8px 20px',background:'linear-gradient(135deg,#f97316,#ea580c)',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',fontSize:'14px',fontWeight:'600',display:'flex',alignItems:'center',gap:'6px'}}>
              <Printer size={14}/>Распечатать
            </button>
            <button onClick={onClose} style={{padding:'8px 16px',backgroundColor:'#6b7280',color:'white',border:'none',borderRadius:'8px',cursor:'pointer',display:'flex',alignItems:'center',gap:'6px'}}>
              <X size={14}/>Закрыть
            </button>
          </div>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'24px',backgroundColor:'white',borderRadius:'0 0 16px 16px',colorScheme:'light'}}>
          <div style={{fontFamily:'Arial',fontSize:'12px',lineHeight:'1.6',color:'#111827'}} dangerouslySetInnerHTML={{__html:content}}/>
        </div>
      </div>
    </div>
  );
}
