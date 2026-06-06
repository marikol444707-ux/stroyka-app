import React from 'react';
import { Download, Printer, ShoppingCart } from 'lucide-react';

export default function MaterialNormCoverageHeader({
  C,
  inp,
  btnB,
  btnG,
  btnO,
  btnState,
  isMobile,
  projectOptions,
  selectedProject,
  setMaterialNormCoverageProject,
  rows,
  showCreateBatchSupply,
  canCreateBatchSupply,
  onPrint,
  onExport,
  onCreateBatchSupply,
}) {
  return (
    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'12px'}}>
      <div>
        <b style={{color:C.text,fontSize:'13px',display:'block'}}>📐 Вся смета по нормам</b>
        <p style={{color:C.textSec,margin:'3px 0 0',fontSize:'12px'}}>Показывает не только проблемы, а полный проход по работам и материалам активной сметы.</p>
      </div>
      <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap',justifyContent:isMobile?'stretch':'flex-end',width:isMobile?'100%':'auto'}}>
        <select value={selectedProject} onChange={e=>setMaterialNormCoverageProject(e.target.value)} style={{...inp,marginBottom:0,width:isMobile?'100%':'260px'}}>
          {projectOptions.length===0&&<option value="">Нет объектов</option>}
          {projectOptions.map(p=><option key={p.id||p.name} value={p.name}>{p.name}</option>)}
        </select>
        <button disabled={!rows.length} onClick={onPrint} style={btnState(btnB,!rows.length,{padding:'7px 10px',fontSize:'12px'})}>
          <Printer size={13}/>Печать
        </button>
        <button disabled={!rows.length} onClick={onExport} style={btnState(btnG,!rows.length,{padding:'7px 10px',fontSize:'12px'})}>
          <Download size={13}/>Excel
        </button>
        {showCreateBatchSupply&&(
          <button disabled={!canCreateBatchSupply} onClick={onCreateBatchSupply} style={btnState(btnO,!canCreateBatchSupply,{padding:'7px 10px',fontSize:'12px'})}>
            <ShoppingCart size={13}/>Заявка по всем
          </button>
        )}
      </div>
    </div>
  );
}
