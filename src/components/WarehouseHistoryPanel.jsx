import React from 'react';
import { Download } from 'lucide-react';

export default function WarehouseHistoryPanel({
  history,
  listSearch,
  matchSearch,
  exportToExcel,
  C,
  btnG,
  tbl,
  tblH,
  tblC,
  badge,
  isMobile = false,
}) {
  const rows = (history || []).filter(item => matchSearch(listSearch, item.material, item.project, item.type)).slice(0, 50);

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'15px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>История движения</b>
        <button onClick={() => exportToExcel((history || []).map(item => ({
          Материал:item.material,
          Тип:item.type,
          Количество:item.quantity,
          Дата:item.date,
          Проект:item.project,
          Кому:item.issuedTo||'',
        })), 'История_склада')} style={{...btnG,...(isMobile ? {width:'100%',justifyContent:'center'} : {})}}><Download size={14}/>Excel</button>
      </div>
      {isMobile ? (
        <div style={{display:'grid',gap:'10px'}}>
          {rows.map((item, index) => (
            <div key={index} style={{padding:'12px',borderRadius:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,display:'grid',gap:'8px'}}>
              <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'flex-start'}}>
                <b style={{color:C.text,fontSize:'13px',lineHeight:'1.35',minWidth:0,overflowWrap:'anywhere'}}>{item.material || 'Материал'}</b>
                <span style={badge(item.type==='приход'?C.success:C.danger,item.type==='приход'?C.successLight:C.dangerLight,item.type==='приход'?C.successBorder:C.dangerBorder)}>{item.type || 'движение'}</span>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',fontSize:'12px',color:C.textSec}}>
                <span><b style={{color:C.text}}>Кол-во:</b> {item.quantity || '—'}</span>
                <span><b style={{color:C.text}}>Дата:</b> {item.date || '—'}</span>
                <span style={{gridColumn:'1 / -1',overflowWrap:'anywhere'}}><b style={{color:C.text}}>Объект:</b> {item.project || '—'}</span>
                {item.issuedTo && <span style={{gridColumn:'1 / -1',overflowWrap:'anywhere'}}><b style={{color:C.text}}>Кому:</b> {item.issuedTo}</span>}
              </div>
            </div>
          ))}
          {!rows.length && (
            <div style={{padding:'18px',borderRadius:'12px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border,color:C.textMuted,textAlign:'center'}}>
              История пуста
            </div>
          )}
        </div>
      ) : (
      <table style={tbl}>
        <thead>
          <tr><th style={tblH}>Материал</th><th style={tblH}>Тип</th><th style={tblH}>Кол-во</th><th style={tblH}>Проект</th><th style={tblH}>Дата</th></tr>
        </thead>
        <tbody>
          {rows.map((item, index) => (
            <tr key={index}>
              <td style={tblC}>{item.material}</td>
              <td style={tblC}><span style={badge(item.type==='приход'?C.success:C.danger,item.type==='приход'?C.successLight:C.dangerLight,item.type==='приход'?C.successBorder:C.dangerBorder)}>{item.type}</span></td>
              <td style={tblC}>{item.quantity}</td>
              <td style={tblC}>{item.project}</td>
              <td style={tblC}>{item.date}</td>
            </tr>
          ))}
        </tbody>
      </table>
      )}
    </div>
  );
}
