import React from 'react';

export default function QrModal({showQRModal, setShowQRModal, generateQR, C, btnG}) {
  if (!showQRModal) return null;
  return (
    <div onClick={()=>setShowQRModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.7)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}>
      <div style={{backgroundColor:'white',padding:'30px',borderRadius:'16px',textAlign:'center'}} onClick={e=>e.stopPropagation()}>
        <h3 style={{color:C.text,marginBottom:'16px'}}>{showQRModal.title}</h3>
        <img src={generateQR(showQRModal.data)} alt="QR" style={{width:'200px',height:'200px'}}/>
        <p style={{color:C.textSec,fontSize:'12px',marginTop:'12px'}}>Сканируйте для быстрого доступа</p>
        <button onClick={()=>setShowQRModal(null)} style={{...btnG,marginTop:'12px'}}>Закрыть</button>
      </div>
    </div>
  );
}
