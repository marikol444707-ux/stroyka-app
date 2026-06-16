import React from 'react';
import { Check, Plus, X } from 'lucide-react';

export default function ScannedInvoiceFormModal({
  showScannedInvoiceForm,
  setShowScannedInvoiceForm,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  newInvoice,
  setNewInvoice,
  projects,
  getProjectWorkPackageOptions,
  getProjectEstimateWorkOptions,
  units,
  saveInvoiceNew,
}) {
  if (!showScannedInvoiceForm) return null;
  const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : '';
  const packageOptions = invoiceProject && typeof getProjectWorkPackageOptions === 'function'
    ? getProjectWorkPackageOptions(invoiceProject)
    : [];
  const defaultWorkPackage = packageOptions.length === 1 ? packageOptions[0] : '';

  const updateItem = (idx, patch) => {
    const items=[...newInvoice.items];
    items[idx]={...items[idx],...patch};
    setNewInvoice({...newInvoice,items});
  };
  const workOptionsForItem = (item = {}) => invoiceProject && typeof getProjectEstimateWorkOptions === 'function'
    ? getProjectEstimateWorkOptions(invoiceProject, item.workPackage || newInvoice.workPackage || '')
    : [];
  const updateItemWork = (idx, value) => {
    const item = (newInvoice.items || [])[idx] || {};
    const option = workOptionsForItem(item).find(row => row.value === value);
    if (!option) {
      updateItem(idx, {estimateWorkValue:'', estimateId:'', estimateItemKey:'', parentWorkKey:'', parentWorkName:'', parentWorkSourceCode:'', sectionName:''});
      return;
    }
    updateItem(idx, {
      estimateWorkValue:option.value,
      estimateId:option.estimateId,
      estimateItemKey:option.estimateItemKey,
      parentWorkKey:option.parentWorkKey,
      parentWorkName:option.parentWorkName,
      parentWorkSourceCode:option.parentWorkSourceCode,
      sectionName:option.sectionName,
      workPackage:option.workPackage || item.workPackage || '',
    });
  };
  const updateLocation = (location) => {
    const project = location !== 'Основной склад' ? location : '';
    const packages = project && typeof getProjectWorkPackageOptions === 'function'
      ? getProjectWorkPackageOptions(project)
      : [];
    const defaultPackage = packages.length === 1 ? packages[0] : '';
    setNewInvoice({
      ...newInvoice,
      location,
      project,
      workPackage: defaultPackage,
      items: (newInvoice.items || []).map(item => ({...item, workPackage: item.workPackage || defaultPackage})),
    });
  };

  const save = async () => {
    if(!newInvoice.number) return alert('Укажите номер накладной');
    if(!newInvoice.location) return alert('Выберите склад');
    const validItems=(newInvoice.items||[]).filter(i=>i.name&&Number(i.quantity)>0);
    if(!validItems.length) return alert('Добавьте хотя бы одну позицию');
    try{
      const saved = await saveInvoiceNew();
      if (saved) setShowScannedInvoiceForm(false);
    }catch(e){alert('Ошибка: '+(e.message||e));}
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'380px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'4px'}}>📋 Накладная</b>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>Проверьте данные и сохраните</p>
        <input placeholder='Номер накладной *' value={newInvoice.number||''} onChange={e=>setNewInvoice({...newInvoice,number:e.target.value})} style={inp}/>
        <input placeholder='Поставщик' value={newInvoice.supplier||newInvoice.newSupplierName||''} onChange={e=>setNewInvoice({...newInvoice,supplier:e.target.value,newSupplierName:e.target.value,isNewSupplier:true})} style={inp}/>
        <select value={newInvoice.location||''} onChange={e=>updateLocation(e.target.value)} style={inp}>
          <option value=''>Выберите склад *</option>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        <input type='date' value={newInvoice.date||new Date().toISOString().split('T')[0]} onChange={e=>setNewInvoice({...newInvoice,date:e.target.value})} style={inp}/>
        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Позиции:</b>
        {(newInvoice.items||[]).map((item,idx)=>(
          <div key={idx} style={{display:'grid',gridTemplateColumns:'2fr 1.2fr 0.7fr 0.7fr 1fr 24px',gap:'4px',marginBottom:'6px'}}>
            <input placeholder='Название' value={item.name} onChange={e=>updateItem(idx,{name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
            <select value={item.workPackage || ''} onChange={e=>updateItem(idx,{workPackage:e.target.value, estimateWorkValue:'', estimateId:'', estimateItemKey:'', parentWorkKey:'', parentWorkName:'', parentWorkSourceCode:'', sectionName:''})} disabled={!invoiceProject} style={{...inp,marginBottom:0,fontSize:'11px',padding:'6px 4px',opacity:invoiceProject?1:0.65}}>
              <option value=''>{invoiceProject ? 'Раздел' : 'Склад'}</option>
              {packageOptions.map(pkg=><option key={pkg} value={pkg}>{pkg}</option>)}
            </select>
            <input placeholder='Кол.' type='number' step='any' inputMode='decimal' value={item.quantity} onChange={e=>updateItem(idx,{quantity:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
            <select value={item.unit||'шт'} onChange={e=>updateItem(idx,{unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'11px',padding:'6px 4px'}}>{units.map(u=><option key={u}>{u}</option>)}</select>
            <input placeholder='Цена' type='number' step='any' inputMode='decimal' value={item.price} onChange={e=>updateItem(idx,{price:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
            <button onClick={()=>{const items=newInvoice.items.filter((_,i)=>i!==idx);if(!items.length)items.push({name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:defaultWorkPackage});setNewInvoice({...newInvoice,items});}} style={{...btnR,padding:'4px 6px',fontSize:'11px'}}><X size={12}/></button>
            {invoiceProject && (
              <select value={item.estimateWorkValue || ''} onChange={e=>updateItemWork(idx, e.target.value)} style={{...inp,gridColumn:'1 / span 6',marginBottom:0,fontSize:'11px',padding:'6px 4px'}}>
                <option value=''>Работа сметы, если материал не выделен отдельной строкой</option>
                {workOptionsForItem(item).map(work=><option key={work.value} value={work.value}>{work.label}</option>)}
              </select>
            )}
          </div>
        ))}
        <button onClick={()=>setNewInvoice({...newInvoice,items:[...(newInvoice.items||[]),{name:'',quantity:'',unit:'шт',price:'',category:'',workPackage:defaultWorkPackage}]})} style={{...btnG,fontSize:'12px',padding:'6px 12px',marginBottom:'10px'}}><Plus size={12}/>Ещё позиция</button>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',margin:'8px 0'}}>
          <b style={{color:C.text,fontSize:'13px'}}>Итого: {(newInvoice.items||[]).reduce((s,i)=>s+Number(i.quantity||0)*Number(i.price||0),0).toLocaleString()} ₽</b>
        </div>
        <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
          <button onClick={save} style={btnO}><Check size={14}/>Сохранить</button>
          <button onClick={()=>setShowScannedInvoiceForm(false)} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
