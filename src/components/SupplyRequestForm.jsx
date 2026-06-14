import React from 'react';
import { Check, Plus, X } from 'lucide-react';

function SupplyRequestForm({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  role,
  isLeadership,
  supplyTemplates,
  applySupplyTemplate,
  deleteSupplyTemplate,
  newSupplyReq,
  setNewSupplyReq,
  priceHints,
  fetchPriceHint,
  UNITS,
  projects,
  getProjectWorkPackageOptions,
  renderSupplyPlanningHint,
  createSupplyReq,
  saveSupplyTemplate,
  setShowSupplyForm,
}) {
  const items = newSupplyReq.items || [];
  const packageOptions = typeof getProjectWorkPackageOptions === 'function'
    ? getProjectWorkPackageOptions(newSupplyReq.project)
    : [];
  const defaultWorkPackage = packageOptions.length === 1 ? packageOptions[0] : '';

  const updateItem = (idx, patch) => {
    const nextItems = [...items];
    nextItems[idx] = {...nextItems[idx], ...patch};
    setNewSupplyReq({...newSupplyReq, items: nextItems});
  };

  const removeItem = (idx) => {
    setNewSupplyReq({...newSupplyReq, items: items.filter((_, i) => i !== idx)});
  };

  const addItem = () => {
    setNewSupplyReq({...newSupplyReq, items: [...items, {materialName:'',quantity:'',unit:'шт',workPackage:defaultWorkPackage}]});
  };

  const updateProject = (projectName) => {
    const nextPackages = typeof getProjectWorkPackageOptions === 'function'
      ? getProjectWorkPackageOptions(projectName)
      : [];
    const nextDefault = nextPackages.length === 1 ? nextPackages[0] : '';
    setNewSupplyReq({
      ...newSupplyReq,
      project: projectName,
      workPackage: nextDefault,
      items: items.map(item => ({...item, workPackage: item.workPackage || nextDefault})),
    });
  };

  return (
    <div style={{...card,padding:'20px',marginBottom:'16px'}}>
      <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>📝 Новая заявка на материал</b>

      {(supplyTemplates||[]).length>0 && (
        <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'12px',flexWrap:'wrap'}}>
          <span style={{fontSize:'12px',color:C.textSec}}>📋 Шаблон:</span>
          <select defaultValue="" onChange={e=>{if(e.target.value){applySupplyTemplate(e.target.value);e.target.value='';}}} style={{...inp,marginBottom:0,fontSize:'13px',width:'auto',minWidth:'220px'}}>
            <option value="">— выбрать готовый набор —</option>
            {supplyTemplates.map(t=><option key={t.id} value={t.id}>{t.name+' ('+(t.items||[]).length+' поз.)'}</option>)}
          </select>
          {isLeadership && supplyTemplates.length>0 && (
            <select defaultValue="" onChange={e=>{if(e.target.value){deleteSupplyTemplate(e.target.value);e.target.value='';}}} style={{...inp,marginBottom:0,fontSize:'12px',width:'auto',color:C.danger}}>
              <option value="">🗑 удалить шаблон…</option>
              {supplyTemplates.map(t=><option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          )}
        </div>
      )}

      {items.map((it,idx)=>{
        const hint = priceHints[(it.materialName||'').trim()];
        return (
          <React.Fragment key={idx}>
            <div style={{display:'grid',gridTemplateColumns:'minmax(180px,3fr) minmax(120px,1.5fr) 1fr 1fr auto',gap:'6px',marginBottom:'4px',alignItems:'center'}}>
              <input placeholder="Материал *" value={it.materialName} onBlur={e=>fetchPriceHint(e.target.value)} onChange={e=>updateItem(idx,{materialName:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}/>
              <select value={it.workPackage || ''} onChange={e=>updateItem(idx,{workPackage:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}>
                <option value="">Раздел сметы</option>
                {packageOptions.map(pkg=><option key={pkg} value={pkg}>{pkg}</option>)}
              </select>
              <input placeholder="Кол-во *" type="number" step="any" inputMode="decimal" value={it.quantity} onChange={e=>updateItem(idx,{quantity:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}/>
              <select value={it.unit} onChange={e=>updateItem(idx,{unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}>
                {UNITS.map(u=><option key={u}>{u}</option>)}
              </select>
              {items.length>1
                ? <button onClick={()=>removeItem(idx)} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
                : <span style={{width:'30px'}}/>}
            </div>
            {hint && hint.stats && (
              <div style={{fontSize:'11px',color:C.textSec,margin:'0 0 8px 2px'}}>
                💰 Раньше брали: от <b style={{color:C.success}}>{hint.stats.min.toLocaleString('ru-RU')} ₽</b> до {hint.stats.max.toLocaleString('ru-RU')} ₽, в среднем {hint.stats.avg.toLocaleString('ru-RU')} ₽
                {hint.catalog && hint.catalog[0] && <span> · мин. в каталоге: {hint.catalog[0].price.toLocaleString('ru-RU')} ₽ ({hint.catalog[0].supplierName})</span>}
              </div>
            )}
            {hint && hint.stats===null && <div style={{fontSize:'11px',color:C.textMuted,margin:'0 0 8px 2px'}}>💡 По этому материалу истории цен пока нет</div>}
            {renderSupplyPlanningHint(it,idx)}
          </React.Fragment>
        );
      })}

      <button onClick={addItem} style={{...btnG,fontSize:'12px',marginBottom:'12px'}}><Plus size={12}/>Добавить строку</button>
      <div style={{display:'grid',gridTemplateColumns:'2fr 1fr',gap:'8px',marginBottom:'8px'}}>
        <select value={newSupplyReq.project} onChange={e=>updateProject(e.target.value)} style={{...inp,marginBottom:0}}>
          <option value="">Объект *</option>
          {projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}
        </select>
        <select value={newSupplyReq.urgency} onChange={e=>setNewSupplyReq({...newSupplyReq,urgency:e.target.value})} style={{...inp,marginBottom:0}}>
          <option value="низкая">🟢 Низкая</option>
          <option value="обычная">🟡 Обычная</option>
          <option value="срочная">🔴 Срочная</option>
        </select>
      </div>
      <textarea placeholder="Комментарий (для чего, особенности)" value={newSupplyReq.notes} onChange={e=>setNewSupplyReq({...newSupplyReq,notes:e.target.value})} style={{...inp,height:'60px',resize:'vertical'}}/>

      <div style={{padding:'10px 12px',backgroundColor:C.infoLight||C.warningLight,border:'1.5px solid '+(C.infoBorder||C.warningBorder),borderRadius:'8px',marginBottom:'12px',fontSize:'12px',color:C.text}}>
        {role==='мастер'||role==='субподрядчик'?'ℹ️ После создания заявка попадёт прорабу на подтверждение':
          role==='прораб'?'ℹ️ Заявка сразу пойдёт директору на утверждение':
          '✅ Заявка будет утверждена автоматически'}
      </div>
      <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
        <button onClick={createSupplyReq} style={btnO}><Check size={14}/>Создать заявку</button>
        <button onClick={saveSupplyTemplate} style={btnG}><Plus size={14}/>Сохранить как шаблон</button>
        <button onClick={()=>setShowSupplyForm(false)} style={btnG}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}

export default SupplyRequestForm;
