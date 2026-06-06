import React from 'react';
import { Download, Plus, Search, Trash2 } from 'lucide-react';

export default function WarehouseMainStockPanel({
  warehouseMain,
  listSearch,
  setListSearch,
  matchSearch,
  openReceiveInvoice,
  exportToExcel,
  deleteMainMaterial,
  C,
  inp,
  btnO,
  btnG,
  btnR,
  tbl,
  tblH,
  tblC,
  badge,
}) {
  const rows = (warehouseMain || []).filter(material => matchSearch(listSearch, material.name, material.category));

  return (
    <div>
      <div style={{display:'flex',gap:'8px',marginBottom:'15px',flexWrap:'wrap'}}>
        <button onClick={() => openReceiveInvoice('Основной склад')} style={btnO}><Plus size={14}/>Принять материал</button>
        <button onClick={() => exportToExcel((warehouseMain || []).map(material => ({
          Наименование: material.name,
          Единица: material.unit,
          Количество: material.quantity,
          Цена: material.price,
          Сумма: material.quantity * material.price,
        })), 'Основной_склад')} style={btnG}><Download size={14}/>Excel</button>
        <div style={{position:'relative',flex:1,minWidth:'200px'}}>
          <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
          <input placeholder="🔍 Поиск материала" value={listSearch} onChange={event => setListSearch(event.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px',fontSize:'12px',padding:'6px 8px 6px 32px'}}/>
        </div>
      </div>

      <table style={tbl}>
        <thead>
          <tr>
            <th style={tblH}>Наименование</th>
            <th style={tblH}>Категория</th>
            <th style={tblH}>Кол-во</th>
            <th style={tblH}>Цена</th>
            <th style={tblH}>Сумма</th>
            <th style={tblH}></th>
          </tr>
        </thead>
        <tbody>
          {rows.map(material => (
            <tr key={material.id} style={{backgroundColor:material.minQuantity&&material.quantity<material.minQuantity?C.dangerLight:'transparent'}}>
              <td style={tblC}>
                <b style={{fontSize:'13px'}}>{material.name}</b>
                {material.minQuantity&&material.quantity<material.minQuantity&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),marginLeft:'6px',fontSize:'10px'}}>Мало!</span>}
              </td>
              <td style={{...tblC,fontSize:'11px',color:C.textSec}}>{material.category||'—'}</td>
              <td style={tblC}>{material.quantity+' '+material.unit}</td>
              <td style={tblC}>{material.price.toLocaleString()+' ₽'}</td>
              <td style={{...tblC,fontWeight:'600'}}>{(material.price*material.quantity).toLocaleString()+' ₽'}</td>
              <td style={tblC}><button onClick={() => deleteMainMaterial(material.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
            </tr>
          ))}
        </tbody>
      </table>

      {(warehouseMain || []).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Склад пуст</p>}
    </div>
  );
}
