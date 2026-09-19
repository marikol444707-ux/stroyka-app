import React from 'react';
import { Check, Plus, X } from 'lucide-react';
import useAsyncSubmit from '../hooks/useAsyncSubmit';
import SupplyTemplates from '../features/supply/SupplyTemplates';
import { templateItemsForProject } from '../features/supply/templateItems';
function SupplyRequestForm({
  API, companyContext, user,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  role,
  isLeadership,
  newSupplyReq,
  setNewSupplyReq,
  priceHints,
  fetchPriceHint,
  UNITS,
  projects,
  getProjectWorkPackageOptions,
  renderSupplyPlanningHint,
  createSupplyReq,
  setShowSupplyForm,
}) {
  const {submit, pending, error} = useAsyncSubmit(
    createSupplyReq,
    'Не удалось создать заявку. Проверьте список заявок перед повторной отправкой.',
  );
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
      items: templateItemsForProject(items, nextPackages),
    });
  };

  return (
    <div style={{...card,padding:'20px',marginBottom:'16px'}}>
      <fieldset disabled={pending} style={{border:0,padding:0,margin:0,minWidth:0}}>
      <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'10px'}}>📝 Новая заявка на материал</b>
      <SupplyTemplates API={API} companyContext={companyContext} user={user} C={C}
        draft={newSupplyReq} setDraft={setNewSupplyReq} disabled={pending}
        getProjectWorkPackageOptions={getProjectWorkPackageOptions} />
      {items.map((it,idx)=>{
        const hint = priceHints[(it.materialName||'').trim()];
        return (
          <React.Fragment key={idx}>
            <div className="supply-request-item">
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
      <div className="supply-request-object">
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
        {['мастер','субподрядчик','бригадир'].includes(role)?'ℹ️ После создания заявка попадёт прорабу на подтверждение':
          role==='прораб'?'ℹ️ Заявка сразу пойдёт директору на утверждение':
          isLeadership?'ℹ️ После создания заявка ожидает подтверждения прораба и утверждения директора. Затем можно запросить КП у поставщиков.':
          'ℹ️ Заявка будет создана внутри снабжения. После утверждения директора выберите поставщиков через «Запросить КП».'}
      </div>
      {error && <p role="alert" style={{color:C.danger,fontSize:'12px'}}>{error}</p>}
      <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
        <button onClick={submit} disabled={pending} aria-busy={pending} style={btnO}><Check size={14}/>{pending?'Создание…':'Создать заявку'}</button>
        <button onClick={()=>setShowSupplyForm(false)} disabled={pending} style={btnG}><X size={14}/>Отмена</button>
      </div>
      </fieldset>
    </div>
  );
}

export default SupplyRequestForm;
