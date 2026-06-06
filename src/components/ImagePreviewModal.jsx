import React from 'react';

export default function ImagePreviewModal({src, onClose}) {
  if (!src) return null;

  return (
    <div onClick={onClose} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.9)',display:'flex',justifyContent:'center',alignItems:'center',zIndex:2000,cursor:'pointer'}}>
      <img src={src} alt="" style={{maxWidth:'90%',maxHeight:'90%',borderRadius:'12px'}}/>
    </div>
  );
}
