import React from 'react';
import { Check, Plus, X } from 'lucide-react';
import { API } from '../api';
import { createWarehouseInvoiceItemForm } from '../features/warehouse/warehouseInitialForms';

export default function ScannedInvoiceFormModal({
  user,
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
  const [rememberingTemplate, setRememberingTemplate] = React.useState(false);
  if (!showScannedInvoiceForm) return null;
  const isMobile = typeof window !== 'undefined' && window.innerWidth <= 640;
  const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : '';
  const packageOptions = invoiceProject && typeof getProjectWorkPackageOptions === 'function'
    ? getProjectWorkPackageOptions(invoiceProject)
    : [];
  const defaultWorkPackage = packageOptions.length === 1 ? packageOptions[0] : '';
  const isScannedInvoice = String(newInvoice.sourceType || '').startsWith('scan_') || Boolean(newInvoice.scanDocumentType || newInvoice.scanWarnings || newInvoice.scanRecognition);
  const scanRecognition = newInvoice.scanRecognition || {};
  const isMainWarehouse = newInvoice.location === 'Основной склад';
  const canReceiveWithoutSupplier = ['директор', 'зам_директора'].includes(String(user?.role || ''));
  const inventoryOnly = isMainWarehouse && newInvoice.inventoryOnly === true;

  const updateItem = (idx, patch) => {
    const items=[...newInvoice.items];
    items[idx]={...items[idx],...patch};
    setNewInvoice({...newInvoice,items,...(isScannedInvoice?{scanHasManualCorrections:true}:{})});
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
      warehouseTarget: project ? 'object' : 'main',
      inventoryOnly: project ? false : newInvoice.inventoryOnly,
      accountingRequired: project ? true : newInvoice.accountingRequired,
      syncSupplierInvoice: project ? true : newInvoice.syncSupplierInvoice,
      selectedAction: project
        ? 'receive_to_warehouse'
        : (newInvoice.inventoryOnly ? 'receive_stock_without_supplier' : 'receive_to_warehouse'),
      sourceType: project
        ? (isScannedInvoice ? newInvoice.sourceType : 'manual_project_invoice')
        : (newInvoice.inventoryOnly ? 'manual_main_receipt' : (isScannedInvoice ? newInvoice.sourceType : 'manual_main_invoice')),
      workPackage: defaultPackage,
      items: (newInvoice.items || []).map(item => ({...item, workPackage: item.workPackage || defaultPackage})),
      ...(isScannedInvoice ? {scanHasManualCorrections:true} : {}),
    });
  };

  const save = async () => {
    if(!newInvoice.number && !inventoryOnly) return alert('Укажите номер накладной');
    if(!newInvoice.location) return alert('Выберите склад');
    const validItems=(newInvoice.items||[]).filter(i=>i.name&&Number(i.quantity)>0);
    if(!validItems.length) return alert('Добавьте хотя бы одну позицию');
    try{
      const saved = await saveInvoiceNew();
      if (saved) setShowScannedInvoiceForm(false);
    }catch(e){alert('Ошибка: '+(e.message||e));}
  };

  const patchInvoice = (patch, markEdited = true) => {
    setNewInvoice({
      ...newInvoice,
      ...patch,
      ...(markEdited && isScannedInvoice ? {scanHasManualCorrections:true} : {}),
    });
  };

  const setInventoryOnly = (enabled) => {
    patchInvoice({
      inventoryOnly: enabled,
      accountingRequired: !enabled,
      syncSupplierInvoice: !enabled,
      selectedAction: enabled ? 'receive_stock_without_supplier' : 'receive_to_warehouse',
      sourceType: enabled ? 'manual_main_receipt' : 'manual_main_invoice',
      supplierId: enabled ? '' : newInvoice.supplierId,
      supplier: enabled ? '' : newInvoice.supplier,
      supplierName: enabled ? '' : newInvoice.supplierName,
      isNewSupplier: enabled ? false : newInvoice.isNewSupplier,
      newSupplierName: enabled ? '' : newInvoice.newSupplierName,
      vat: enabled ? 'Без НДС' : newInvoice.vat,
    });
  };

  const rememberInvoiceTemplate = async () => {
    const supplierName = String(newInvoice.supplier || newInvoice.newSupplierName || scanRecognition.supplierName || '').trim();
    if (!supplierName) return alert('Сначала укажите поставщика.');
    const items = (newInvoice.items || []).filter(item => item.name && Number(item.quantity) > 0);
    if (!items.length) return alert('Добавьте хотя бы одну распознанную позицию.');
    setRememberingTemplate(true);
    try {
      const response = await fetch(API + '/supplier-invoice-templates/learn', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          supplierId:newInvoice.supplierId || scanRecognition.supplierId || 0,
          supplierName,
          number:newInvoice.number || '',
          date:newInvoice.date || '',
          documentType:newInvoice.scanDocumentType || 'supplier_invoice',
          vat:newInvoice.vat || '',
          totalBase:newInvoice.totalBase || 0,
          totalVat:newInvoice.totalVat || 0,
          totalWithVat:newInvoice.totalWithVat || 0,
          items,
          recognition:scanRecognition,
          project:newInvoice.project || '',
        })
      });
      const data = await response.json().catch(()=>({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || data.error || 'Не удалось сохранить правило поставщика');
      setNewInvoice({
        ...newInvoice,
        scanRecognition:data.recognition || scanRecognition,
        scanHasManualCorrections:false,
        supplierId:data.template?.supplierId || newInvoice.supplierId,
        supplier:data.template?.supplierName || newInvoice.supplier || supplierName,
        newSupplierName:data.template?.supplierName || newInvoice.newSupplierName || supplierName,
      });
      alert('Правило распознавания поставщика сохранено.');
    } catch (error) {
      alert(error.message || 'Не удалось сохранить правило поставщика');
    } finally {
      setRememberingTemplate(false);
    }
  };

  const inputStyle = {
    ...inp,
    width:'100%',
    minWidth:0,
    boxSizing:'border-box',
  };
  const itemInputStyle = {
    ...inputStyle,
    marginBottom:0,
    fontSize:isMobile ? '15px' : '12px',
    padding:isMobile ? '10px 12px' : undefined,
  };
  const itemSelectStyle = {
    ...itemInputStyle,
    fontSize:isMobile ? '15px' : '11px',
    padding:isMobile ? '10px 12px' : '6px 4px',
  };
  const itemsTotal = (newInvoice.items||[]).reduce((s,i)=>s+(Number(i.lineTotal||0)||Number(i.quantity||0)*Number(i.price||0)),0);
  const displayTotal = Number(newInvoice.totalWithVat||0) || itemsTotal;
  const displayVat = Number(newInvoice.totalVat||0);
  const scanWarnings = Array.isArray(newInvoice.scanWarnings) ? newInvoice.scanWarnings.filter(Boolean) : [];
  const isDraftNumber = /^SCAN-\d{8}-\d{4}$/i.test(String(newInvoice.number || ''));
  const canRememberTemplate = !inventoryOnly && isScannedInvoice && String(newInvoice.supplier || newInvoice.newSupplierName || scanRecognition.supplierName || '').trim();

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:isMobile?'center':'center',justifyContent:'center',padding:isMobile?'12px':0,boxSizing:'border-box'}}>
      <div className='mobile-modal' style={{...card,padding:isMobile?'14px':'20px',width:isMobile?'calc(100vw - 24px)':'520px',margin:isMobile?'0 auto':'20px',maxHeight:isMobile?'calc(100dvh - 24px)':'90vh',borderRadius:isMobile?'16px':card.borderRadius,overflowY:'auto',overflowX:'hidden',paddingBottom:isMobile?'24px':'20px',boxSizing:'border-box'}}>
        <b style={{color:C.text,fontSize:isMobile?'21px':'15px',display:'block',marginBottom:'4px'}}>📋 Накладная</b>
        <p style={{color:C.textSec,fontSize:isMobile?'16px':'12px',margin:'0 0 12px'}}>Проверьте данные и сохраните</p>
        {(newInvoice.photos || []).length > 0 && (
          <div style={{border:'1.5px solid '+C.success,borderRadius:'12px',padding:isMobile?'10px 12px':'8px 10px',marginBottom:'10px',backgroundColor:'rgba(16,185,129,0.12)',color:C.success,fontSize:isMobile?'14px':'12px',fontWeight:700}}>
            📎 Фото накладной прикреплено: {(newInvoice.photos || []).length}
            {Number(newInvoice.pagesCount || 0) > 1 ? ` · страниц: ${newInvoice.pagesCount}` : ''}
          </div>
        )}
        {isScannedInvoice && (
          <div style={{border:'1.5px solid '+(scanRecognition.method === 'template' ? C.success : C.info),borderRadius:'12px',padding:isMobile?'10px 12px':'8px 10px',marginBottom:'10px',backgroundColor:scanRecognition.method === 'template' ? 'rgba(16,185,129,0.10)' : 'rgba(59,130,246,0.10)',color:C.text,fontSize:isMobile?'14px':'12px',lineHeight:1.45}}>
            <b style={{display:'block',marginBottom:'3px',color:scanRecognition.method === 'template' ? C.success : C.info}}>
              {scanRecognition.label || (scanRecognition.method === 'template' ? 'Распознано по шаблону поставщика' : 'Распознано через AI/OCR')}
            </b>
            <div>{scanRecognition.templateName ? 'Шаблон: ' + scanRecognition.templateName : 'Если поправите строки, поставщика или суммы, можно сохранить это как правило поставщика.'}</div>
            {scanRecognition.supplierName && <div style={{color:C.textSec}}>Поставщик: {scanRecognition.supplierName}</div>}
          </div>
        )}
        {(scanWarnings.length > 0 || isDraftNumber) && (
          <div style={{border:'1.5px solid '+C.warningBorder,borderRadius:'12px',padding:isMobile?'10px 12px':'8px 10px',marginBottom:'10px',backgroundColor:C.warningLight,color:C.warning,fontSize:isMobile?'14px':'12px',lineHeight:1.45}}>
            <b style={{display:'block',marginBottom:'4px'}}>Проверьте распознавание</b>
            {isDraftNumber && <div>Номер не найден на фото: стоит черновой номер, его можно заменить вручную.</div>}
            {scanWarnings.map((warning, index) => <div key={index}>{warning}</div>)}
          </div>
        )}
        <input placeholder={inventoryOnly ? 'Номер документа (необязательно)' : 'Номер документа *'} value={newInvoice.number||''} onChange={e=>patchInvoice({number:e.target.value})} style={inputStyle}/>
        {!inventoryOnly && <input placeholder='Поставщик' value={newInvoice.supplier||newInvoice.newSupplierName||''} onChange={e=>patchInvoice({supplier:e.target.value,newSupplierName:e.target.value,isNewSupplier:true})} style={inputStyle}/>}
        <select value={newInvoice.location||''} onChange={e=>updateLocation(e.target.value)} style={inputStyle}>
          <option value=''>Выберите склад *</option>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        {isMainWarehouse && canReceiveWithoutSupplier && (
          <label style={{display:'flex',gap:'10px',alignItems:'flex-start',padding:'12px',border:'1.5px solid '+(inventoryOnly?C.successBorder:C.border),backgroundColor:inventoryOnly?C.successLight:C.bg,borderRadius:'8px',cursor:'pointer',marginBottom:'10px'}}>
            <input type='checkbox' checked={inventoryOnly} onChange={event=>setInventoryOnly(event.target.checked)} style={{accentColor:C.success,marginTop:'2px'}}/>
            <span>
              <b style={{display:'block',color:C.text,fontSize:isMobile?'15px':'13px'}}>Без поставщика и оплаты</b>
              <span style={{display:'block',color:C.textSec,fontSize:isMobile?'13px':'12px',lineHeight:1.45,marginTop:'3px'}}>
                Только приход на основной склад. В бухгалтерию и задолженность поставщику документ не попадёт.
              </span>
            </span>
          </label>
        )}
        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:'8px'}}>
          <input type='date' value={newInvoice.date||new Date().toISOString().split('T')[0]} onChange={e=>patchInvoice({date:e.target.value})} style={inputStyle}/>
          <select value={newInvoice.vat||'Без НДС'} disabled={inventoryOnly} onChange={e=>patchInvoice({vat:e.target.value})} style={{...inputStyle,opacity:inventoryOnly?0.65:1}}>
            <option value='Без НДС'>Без НДС</option>
            <option value='С НДС 20%'>С НДС 20%</option>
            <option value='С НДС 22%'>С НДС 22%</option>
          </select>
        </div>
        <b style={{color:C.text,fontSize:isMobile?'17px':'13px',display:'block',marginBottom:'8px'}}>Позиции:</b>
        {(newInvoice.items||[]).map((item,idx)=>(
          <div key={idx} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'2fr 1.2fr 0.7fr 0.7fr 1fr 36px',gap:isMobile?'8px':'4px',marginBottom:isMobile?'12px':'6px',padding:isMobile?'10px':0,border:isMobile?'1px solid '+C.border:'none',borderRadius:isMobile?'12px':0}}>
            <input placeholder='Название' value={item.name} onChange={e=>updateItem(idx,{name:e.target.value})} style={itemInputStyle}/>
            <select value={item.workPackage || ''} onChange={e=>updateItem(idx,{workPackage:e.target.value, estimateWorkValue:'', estimateId:'', estimateItemKey:'', parentWorkKey:'', parentWorkName:'', parentWorkSourceCode:'', sectionName:''})} disabled={!invoiceProject} style={{...itemSelectStyle,opacity:invoiceProject?1:0.65}}>
              <option value=''>{invoiceProject ? 'Раздел' : 'Склад'}</option>
              {packageOptions.map(pkg=><option key={pkg} value={pkg}>{pkg}</option>)}
            </select>
            <div className='mobile-two-cols' style={{display:'grid',gridTemplateColumns:isMobile?'1fr 0.8fr':'1fr',gap:isMobile?'8px':'4px'}}>
              <input placeholder='Кол.' type='number' step='any' inputMode='decimal' value={item.quantity} onChange={e=>updateItem(idx,{quantity:e.target.value})} style={itemInputStyle}/>
              <select value={item.unit||'шт'} onChange={e=>updateItem(idx,{unit:e.target.value})} style={itemSelectStyle}>{units.map(u=><option key={u}>{u}</option>)}</select>
            </div>
            <div className='mobile-two-cols' style={{display:'grid',gridTemplateColumns:isMobile?'1fr 1fr':'1fr',gap:isMobile?'8px':'4px'}}>
              <input placeholder='Цена с НДС' type='number' step='any' inputMode='decimal' value={item.price} onChange={e=>updateItem(idx,{price:e.target.value})} style={itemInputStyle}/>
              <input placeholder='Сумма строки' type='number' step='any' inputMode='decimal' value={item.lineTotal||''} onChange={e=>updateItem(idx,{lineTotal:e.target.value})} style={itemInputStyle}/>
            </div>
            <button onClick={()=>{const items=newInvoice.items.filter((_,i)=>i!==idx);if(!items.length)items.push(createWarehouseInvoiceItemForm({workPackage:defaultWorkPackage}));setNewInvoice({...newInvoice,items,...(isScannedInvoice?{scanHasManualCorrections:true}:{})});}} style={{...btnR,padding:isMobile?'8px':'4px 6px',fontSize:'11px',alignSelf:'stretch',justifyContent:'center'}}><X size={isMobile?16:12}/></button>
            {invoiceProject && (
              <select value={item.estimateWorkValue || ''} onChange={e=>updateItemWork(idx, e.target.value)} style={{...itemSelectStyle,gridColumn:isMobile?undefined:'1 / span 6'}}>
                <option value=''>Работа сметы, если материал не выделен отдельной строкой</option>
                {workOptionsForItem(item).map(work=><option key={work.value} value={work.value}>{work.label}</option>)}
              </select>
            )}
          </div>
        ))}
        <button onClick={()=>setNewInvoice({...newInvoice,items:[...(newInvoice.items||[]),createWarehouseInvoiceItemForm({workPackage:defaultWorkPackage})],...(isScannedInvoice?{scanHasManualCorrections:true}:{})})} style={{...btnG,fontSize:isMobile?'15px':'12px',padding:isMobile?'10px 14px':'6px 12px',marginBottom:'10px'}}><Plus size={12}/>Ещё позиция</button>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',margin:'8px 0'}}>
          <b style={{color:C.text,fontSize:isMobile?'18px':'13px'}}>Итого: {displayTotal.toLocaleString()} ₽</b>
        </div>
        {(displayVat > 0 || Number(newInvoice.totalBase||0) > 0) && (
          <div style={{color:C.textSec,fontSize:isMobile?'13px':'11px',lineHeight:1.45,margin:'-4px 0 8px'}}>
            {Number(newInvoice.totalBase||0) > 0 && <div>Без НДС: {Number(newInvoice.totalBase||0).toLocaleString()} ₽</div>}
            {displayVat > 0 && <div>НДС: {displayVat.toLocaleString()} ₽</div>}
          </div>
        )}
        <div className='mobile-actions' style={{display:'flex',gap:'8px',marginTop:'12px',flexWrap:isMobile?'wrap':'nowrap'}}>
          {canRememberTemplate && (
            <button onClick={rememberInvoiceTemplate} disabled={rememberingTemplate} style={{...btnG,flex:isMobile?'1 1 100%':undefined,justifyContent:'center',borderColor:C.accent,color:C.accent,opacity:rememberingTemplate?0.7:1}}>
              {rememberingTemplate ? 'Сохраняю...' : '🧠 Запомнить исправления'}
            </button>
          )}
          <button onClick={save} style={{...btnO,flex:isMobile?'1 1 100%':undefined,justifyContent:'center'}}><Check size={14}/>Сохранить</button>
          <button onClick={()=>setShowScannedInvoiceForm(false)} style={{...btnG,flex:isMobile?'1 1 100%':undefined,justifyContent:'center'}}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
