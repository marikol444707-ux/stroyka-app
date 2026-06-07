import React from 'react';

export default function SverkaModal({sverkaModal, setSverkaModal, btnO}) {
  if (!sverkaModal) return null;

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:2000,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div style={{backgroundColor:'white',borderRadius:'16px',padding:'24px',width:'90%',maxWidth:'600px',maxHeight:'80vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'16px'}}>
          <b style={{fontSize:'15px'}}>📊 {sverkaModal.title}</b>
          <button onClick={()=>setSverkaModal(null)} style={{background:'none',border:'none',fontSize:'20px',cursor:'pointer'}}>×</button>
        </div>
        <pre style={{fontSize:'13px',lineHeight:'1.8',whiteSpace:'pre-wrap',fontFamily:'inherit'}}>{sverkaModal.text}</pre>
        <button onClick={()=>setSverkaModal(null)} style={{...btnO,marginTop:'16px',width:'100%',justifyContent:'center'}}>Закрыть</button>
      </div>
    </div>
  );
}
