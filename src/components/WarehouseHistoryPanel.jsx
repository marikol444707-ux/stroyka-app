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
}) {
  const rows = (history || []).filter(item => matchSearch(listSearch, item.material, item.project, item.type)).slice(0, 50);

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>История движения</b>
        <button onClick={() => exportToExcel((history || []).map(item => ({
          Материал:item.material,
          Тип:item.type,
          Количество:item.quantity,
          Дата:item.date,
          Проект:item.project,
          Кому:item.issuedTo||'',
        })), 'История_склада')} style={btnG}><Download size={14}/>Excel</button>
      </div>
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
    </div>
  );
}
