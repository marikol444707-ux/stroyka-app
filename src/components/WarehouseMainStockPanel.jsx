import React from 'react';
import { Download, Plus, Search, Trash2 } from 'lucide-react';

export default function WarehouseMainStockPanel({
  user,
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
  isMobile,
}) {
  const [visibleRows, setVisibleRows] = React.useState(60);
  const canDeleteMainMaterial = user?.role === 'директор';
  const touchCompact = typeof window !== 'undefined'
    && (window.visualViewport?.width || window.innerWidth || 0) < 1100
    && (
      (typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches)
      || (typeof navigator !== 'undefined' && /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || ''))
    );
  const compactRows = isMobile || touchCompact;
  const rowsStep = compactRows ? 60 : 180;
  const deferredListSearch = React.useDeferredValue(listSearch);
  const rows = React.useMemo(
    () => (warehouseMain || []).filter(material => matchSearch(deferredListSearch, material.name, material.category)),
    [warehouseMain, deferredListSearch, matchSearch],
  );
  const displayedRows = rows.slice(0, visibleRows);
  const hiddenRows = Math.max(0, rows.length - displayedRows.length);

  React.useEffect(() => {
    setVisibleRows(compactRows ? 60 : 180);
  }, [compactRows, listSearch, warehouseMain?.length]);

  return (
    <div style={{width:'100%',maxWidth:'100%',minWidth:0,overflowX:'hidden'}}>
      <div style={{
        display:'flex',
        gap:'8px',
        margin:'0 auto 15px',
        flexWrap:'wrap',
        justifyContent:compactRows?'center':'flex-start',
        maxWidth:compactRows?'min(720px,100%)':'100%',
      }}>
        <button onClick={() => openReceiveInvoice('Основной склад')} style={{...btnO,justifyContent:'center',width:compactRows?'100%':undefined,maxWidth:compactRows?'320px':undefined}}><Plus size={14}/>Принять материал</button>
        <button onClick={() => exportToExcel((warehouseMain || []).map(material => ({
          Наименование: material.name,
          Единица: material.unit,
          Количество: material.quantity,
          Цена: material.price,
          Сумма: material.quantity * material.price,
        })), 'Основной_склад')} style={{...btnG,justifyContent:'center',width:compactRows?'100%':undefined,maxWidth:compactRows?'160px':undefined}}><Download size={14}/>Excel</button>
        <div style={{position:'relative',flex:compactRows?'0 0 100%':1,minWidth:0,width:compactRows?'100%':undefined}}>
          <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
          <input placeholder="🔍 Поиск материала" value={listSearch} onChange={event => setListSearch(event.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px',fontSize:'12px',padding:'6px 8px 6px 32px'}}/>
        </div>
      </div>

      {compactRows ? (
        <div style={{display:'grid',gap:'10px',width:'100%',maxWidth:'min(720px,100%)',margin:'0 auto'}}>
          {displayedRows.map(material => {
            const low = material.minQuantity && material.quantity < material.minQuantity;
            return (
              <div key={material.id} style={{
                border:'1.5px solid '+(low ? C.dangerBorder : C.border),
                backgroundColor:low ? C.dangerLight : C.bgWhite,
                borderRadius:'12px',
                padding:'12px',
                display:'grid',
                gap:'10px',
                minWidth:0,
              }}>
                <div style={{display:'flex',justifyContent:'space-between',gap:'10px',alignItems:'flex-start'}}>
                  <div style={{minWidth:0}}>
                    <b style={{display:'block',color:C.text,fontSize:'14px',lineHeight:1.25,overflowWrap:'anywhere'}}>{material.name}</b>
                    <span style={{color:C.textSec,fontSize:'12px'}}>{material.category || 'Без категории'}</span>
                  </div>
                  {canDeleteMainMaterial && (
                    <button onClick={() => deleteMainMaterial(material.id)} style={{...btnR,padding:'7px 9px',flex:'0 0 auto'}}><Trash2 size={13}/></button>
                  )}
                </div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(130px,1fr))',gap:'8px'}}>
                  <div>
                    <span style={{display:'block',color:C.textMuted,fontSize:'10px',textTransform:'uppercase',fontWeight:700}}>Кол-во</span>
                    <b style={{display:'block',color:C.text,fontSize:'13px',overflowWrap:'anywhere'}}>{material.quantity+' '+material.unit}</b>
                  </div>
                  <div>
                    <span style={{display:'block',color:C.textMuted,fontSize:'10px',textTransform:'uppercase',fontWeight:700}}>Цена</span>
                    <b style={{display:'block',color:C.text,fontSize:'13px',overflowWrap:'anywhere'}}>{material.price.toLocaleString()+' ₽'}</b>
                  </div>
                  <div>
                    <span style={{display:'block',color:C.textMuted,fontSize:'10px',textTransform:'uppercase',fontWeight:700}}>Сумма</span>
                    <b style={{display:'block',color:C.success,fontSize:'13px',overflowWrap:'anywhere'}}>{(material.price*material.quantity).toLocaleString()+' ₽'}</b>
                  </div>
                </div>
                {low && <span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),justifySelf:'start',fontSize:'10px'}}>Мало!</span>}
              </div>
            );
          })}
        </div>
      ) : (
      <div style={{width:'100%',overflowX:'auto'}}>
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
          {displayedRows.map(material => (
            <tr key={material.id} style={{backgroundColor:material.minQuantity&&material.quantity<material.minQuantity?C.dangerLight:'transparent'}}>
              <td style={tblC}>
                <b style={{fontSize:'13px'}}>{material.name}</b>
                {material.minQuantity&&material.quantity<material.minQuantity&&<span style={{...badge(C.danger,C.dangerLight,C.dangerBorder),marginLeft:'6px',fontSize:'10px'}}>Мало!</span>}
              </td>
              <td style={{...tblC,fontSize:'11px',color:C.textSec}}>{material.category||'—'}</td>
              <td style={tblC}>{material.quantity+' '+material.unit}</td>
              <td style={tblC}>{material.price.toLocaleString()+' ₽'}</td>
              <td style={{...tblC,fontWeight:'600'}}>{(material.price*material.quantity).toLocaleString()+' ₽'}</td>
              <td style={tblC}>
                {canDeleteMainMaterial && (
                  <button onClick={() => deleteMainMaterial(material.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      )}

      {hiddenRows > 0 && (
        <button
          type="button"
          onClick={() => setVisibleRows(limit => Math.min(rows.length, limit + rowsStep))}
          style={{...btnG, width:'100%', justifyContent:'center', marginTop:'10px'}}
        >
          Показать ещё {Math.min(hiddenRows, rowsStep)} материалов
        </button>
      )}

      {(warehouseMain || []).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Склад пуст</p>}
      {(warehouseMain || []).length>0&&!rows.length&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Поиск ничего не нашёл</p>}
    </div>
  );
}
