import React from 'react';
import { Check, X } from 'lucide-react';
import { groupSuppliers } from '../utils/supplierUtils';

export default function RequestKpModal({
  showRequestKpModal,
  setShowRequestKpModal,
  C,
  card,
  btnG,
  btnO,
  badge,
  supplyRequests,
  parseSupplyItems,
  renderSupplyRequestOrigin,
  requestKpLoading,
  suggestedSuppliers,
  selectedSupplierIds,
  setSelectedSupplierIds,
  sendKpRequest,
}) {
  const suggestedSupplierGroups = React.useMemo(
    () => groupSuppliers(suggestedSuppliers?.suppliers || []),
    [suggestedSuppliers]
  );
  React.useEffect(() => {
    if (!showRequestKpModal || suggestedSupplierGroups.length === 0) return;
    setSelectedSupplierIds(prev => {
      const prevIds = new Set((prev || []).map(String));
      const next = suggestedSupplierGroups
        .filter(supplier => (supplier._supplierIds || [supplier.id]).some(id => prevIds.has(String(id))))
        .map(supplier => supplier.id);
      const same = next.length === (prev || []).length && next.every((id, index) => String(id) === String(prev[index]));
      return same ? prev : next;
    });
  }, [showRequestKpModal, suggestedSupplierGroups, setSelectedSupplierIds]);

  if (!showRequestKpModal) return null;

  const req = supplyRequests.find(r=>r.id===showRequestKpModal);
  const items = req ? parseSupplyItems(req) : [];

  const renderTitleMeta = () => {
    if (!req) return null;
    if (items.length<=1) {
      const it = items[0]||{materialName:req.materialName,quantity:req.quantity,unit:req.unit};
      return (<><p style={{color:C.textSec,margin:'2px 0 0',fontSize:'12px'}}>{it.materialName+' · '+it.quantity+' '+it.unit+' · 🏗 '+(req.project||'')}</p>{renderSupplyRequestOrigin(req,{compact:true})}</>);
    }
    return (
      <div style={{margin:'4px 0 0'}}>
        <p style={{color:C.textSec,margin:'0 0 4px',fontSize:'12px'}}>📋 Пакет из {items.length} позиций · 🏗 {req.project||''} — отправим одним запросом</p>
        <ol style={{margin:0,paddingLeft:'18px',color:C.textSec,fontSize:'11px'}}>
          {items.slice(0,5).map((it,i)=><li key={i}>{it.materialName} <span>— {it.quantity} {it.unit}</span></li>)}
          {items.length>5 && <li style={{listStyle:'none',fontStyle:'italic'}}>...и ещё {items.length-5}</li>}
        </ol>
        {renderSupplyRequestOrigin(req,{compact:true})}
      </div>
    );
  };

  return (
    <div onClick={()=>setShowRequestKpModal(null)} style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.55)',zIndex:1700,display:'flex',alignItems:'center',justifyContent:'center',padding:'20px'}}>
      <div onClick={e=>e.stopPropagation()} style={{...card,padding:'20px',width:'min(640px,100%)',maxHeight:'85vh',overflowY:'auto'}}>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'14px'}}>
          <div>
            <b style={{color:C.text,fontSize:'16px',display:'block'}}>📨 Запросить КП у поставщиков</b>
            {renderTitleMeta()}
          </div>
          <button onClick={()=>setShowRequestKpModal(null)} style={{...btnG,padding:'4px 8px'}}><X size={14}/></button>
        </div>
        {requestKpLoading && <p style={{color:C.textMuted,padding:'20px',textAlign:'center',fontSize:'13px'}}>⏳ AI подбирает поставщиков...</p>}
        {!requestKpLoading && suggestedSuppliers && suggestedSuppliers.error && (
          <p style={{color:C.danger,padding:'20px',textAlign:'center',fontSize:'13px'}}>❌ {suggestedSuppliers.error}</p>
        )}
        {!requestKpLoading && suggestedSuppliers && !suggestedSuppliers.error && (<>
          <div style={{padding:'10px 12px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,borderRadius:'8px',marginBottom:'12px',fontSize:'12px',color:C.text}}>
            🤖 AI нашёл {suggestedSupplierGroups.length} поставщиков по категории «{suggestedSuppliers.category||'не указана'}». Из них рекомендует {suggestedSuppliers.aiRecommendedCount} — отметил их ⭐ галочкой автоматически. Можно добавить или убрать.
          </div>
          {suggestedSupplierGroups.length===0 && (
            <div style={{padding:'30px',textAlign:'center',color:C.textMuted,fontSize:'13px'}}>
              Поставщиков по этой категории нет.<br/>Добавьте поставщиков в разделе «Снабжение → Поставщики».
            </div>
          )}
          {suggestedSupplierGroups.map(s=>{
            const checked = selectedSupplierIds.includes(s.id);
            return (
              <div key={s.id} onClick={()=>{
                if (s.alreadyRequested) return;
                setSelectedSupplierIds(prev=>checked?prev.filter(x=>x!==s.id):[...prev,s.id]);
              }} style={{padding:'10px 12px',marginBottom:'6px',borderRadius:'8px',backgroundColor:checked?C.successLight:C.bg,border:'1.5px solid '+(checked?C.successBorder:C.border),cursor:s.alreadyRequested?'not-allowed':'pointer',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',opacity:s.alreadyRequested?0.5:1}}>
                <div style={{display:'flex',alignItems:'center',gap:'10px',flex:1}}>
                  <input type='checkbox' checked={checked} readOnly disabled={s.alreadyRequested} style={{accentColor:C.accent,cursor:s.alreadyRequested?'not-allowed':'pointer'}}/>
                  <div>
                    <div style={{display:'flex',alignItems:'center',gap:'6px'}}>
                      <b style={{color:C.text,fontSize:'13px'}}>{s.name}</b>
                      {s.aiRecommend && <span style={badge(C.accent,C.accentLight,C.accentBorder||C.border)}>🤖 AI рек.</span>}
                      {s.alreadyRequested && <span style={badge(C.textMuted,C.bg,C.border)}>уже запросили</span>}
                    </div>
                    <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(s.category||'')+(s.specialization?' · '+s.specialization:'')+(s.phone?' · '+s.phone:'')}</p>
                    <p style={{color:C.textMuted,margin:0,fontSize:'10px'}}>⭐ {s.rating||'нет'} · 📦 успешных поставок: {s.deliveriesCount}</p>
                  </div>
                </div>
              </div>
            );
          })}
          <div style={{display:'flex',gap:'8px',marginTop:'14px',justifyContent:'flex-end'}}>
            <button onClick={()=>setShowRequestKpModal(null)} style={btnG}><X size={14}/>Отмена</button>
            <button onClick={sendKpRequest} disabled={selectedSupplierIds.length===0} style={{...btnO,opacity:selectedSupplierIds.length===0?0.5:1}}>
              <Check size={14}/>Отправить ({selectedSupplierIds.length})
            </button>
          </div>
        </>)}
      </div>
    </div>
  );
}
