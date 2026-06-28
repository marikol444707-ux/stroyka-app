import React from 'react';
import { Check, Eye, Plus, QrCode, Truck, Upload, X } from 'lucide-react';
import { invoiceImageAccept, normalizeInvoiceImageFiles } from '../../utils/invoiceImages';

export function WarehouseInvoiceForm({
  newInvoice,
  setNewInvoice,
  suppliers,
  projects,
  materialEstimates,
  getProjectWorkPackageOptions,
  getProjectEstimateWorkOptions,
  invoiceItems,
  invoiceTotal,
  draftEstimateControl,
  draftControlIssues,
  saveInvoiceNew,
  uploadPhoto,
  fileSrc,
  setShowForm,
  setShowPhotoModal,
  setSverkaModal,
  buildEstimateReconciliationReport,
  renderControlBadge,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
  VAT_OPTIONS,
  UNITS,
  MATERIAL_CATEGORIES,
  isMobile = false,
}) {
  const invoiceGalleryInputRef = React.useRef(null);
  const invoiceCameraInputRef = React.useRef(null);
  const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : '';
  const packageOptions = invoiceProject && typeof getProjectWorkPackageOptions === 'function'
    ? getProjectWorkPackageOptions(invoiceProject)
    : [];
  const defaultWorkPackage = packageOptions.length === 1 ? packageOptions[0] : '';
  const vatRateMatch = String(newInvoice.vat || '').match(/НДС\s*(\d+(?:[,.]\d+)?)%/i);
  const vatRateValue = vatRateMatch ? Number(vatRateMatch[1].replace(',', '.')) : 0;
  const invoiceBaseAmount = vatRateValue > 0
    ? Math.round((invoiceTotal / (1 + vatRateValue / 100)) * 100) / 100
    : invoiceTotal;
  const invoiceVatAmount = vatRateValue > 0
    ? Math.round((invoiceTotal - invoiceBaseAmount) * 100) / 100
    : 0;
  const compactInput = {...inp,marginBottom:0,fontSize:isMobile?'16px':'12px',width:'100%',minWidth:0,boxSizing:'border-box'};
  const formGridStyle = {display:'grid',gridTemplateColumns:isMobile?'1fr':'1fr 1fr',gap:isMobile?'8px':'10px'};
  const spanAll = isMobile ? undefined : 'span 2';
  const isPdfUrl = (url) => /\.pdf(?:$|[?#])/i.test(String(url || ''));
  const itemGridStyle = isMobile
    ? {display:'grid',gridTemplateColumns:'1fr',gap:'8px',marginBottom:'10px',padding:'10px',borderRadius:'12px',border:'1.5px solid '+C.border,backgroundColor:C.bg,minWidth:0}
    : {display:'grid',gridTemplateColumns:'minmax(180px,2.5fr) 0.8fr 0.8fr 0.9fr minmax(120px,1.2fr) minmax(130px,1.4fr) minmax(180px,1.8fr) auto',gap:'6px',marginBottom:'8px',alignItems:'center'};

  const setItem = (idx, patch) => {
    const items = [...invoiceItems];
    items[idx] = {...items[idx], ...patch};
    setNewInvoice({...newInvoice, items});
  };
  const workOptionsForItem = (item = {}) => invoiceProject && typeof getProjectEstimateWorkOptions === 'function'
    ? getProjectEstimateWorkOptions(invoiceProject, item.workPackage || newInvoice.workPackage || '')
    : [];
  const setItemWork = (idx, value) => {
    const item = invoiceItems[idx] || {};
    const option = workOptionsForItem(item).find(row => row.value === value);
    if (!option) {
      setItem(idx, {
        estimateWorkValue:'',
        estimateId:'',
        estimateItemKey:'',
        parentWorkKey:'',
        parentWorkName:'',
        parentWorkSourceCode:'',
        sectionName:'',
      });
      return;
    }
    setItem(idx, {
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

  const removeItem = (idx) => {
    const items = invoiceItems.filter((_, itemIdx) => itemIdx !== idx);
    setNewInvoice({
      ...newInvoice,
      items: items.length ? items : [{name:'', quantity:'', unit:'шт', price:'', category:'', workPackage:defaultWorkPackage}],
    });
  };

  const addItem = () => {
    setNewInvoice({
      ...newInvoice,
      items: [...invoiceItems, {name:'', quantity:'', unit:'шт', price:'', category:'', workPackage:defaultWorkPackage}],
    });
  };

  const updateLocation = (location) => {
    const nextProject = location === 'Основной склад' ? '' : location;
    const nextPackages = nextProject && typeof getProjectWorkPackageOptions === 'function'
      ? getProjectWorkPackageOptions(nextProject)
      : [];
    const nextDefault = nextPackages.length === 1 ? nextPackages[0] : '';
    setNewInvoice({
      ...newInvoice,
      location,
      project: nextProject,
      workPackage: nextDefault,
      items: invoiceItems.map(item => ({...item, workPackage: item.workPackage || nextDefault})),
    });
  };

  const addPhotos = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : 'Основной склад';
    try {
      const normalizedPages = await normalizeInvoiceImageFiles(files);
      const urls = await Promise.all(normalizedPages.map(page => uploadPhoto(page.uploadFile, {projectName: invoiceProject, context: 'warehouse-invoices'})));
      setNewInvoice(prev => ({...prev, photos: [...(prev.photos || []), ...urls.filter(Boolean)]}));
    } catch (error) {
      alert(error?.message || 'Не удалось подготовить фото накладной');
    }
    event.target.value = '';
  };

  return (
    <div style={{...card,padding:isMobile?'14px':'20px',marginBottom:'20px',overflow:'hidden'}}>
      <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Новая приходная накладная</h3>
      <div style={formGridStyle}>
        <input placeholder="Номер накладной *" value={newInvoice.number} onChange={event => setNewInvoice({...newInvoice, number: event.target.value})} style={{...inp,marginBottom:0,width:'100%',minWidth:0,boxSizing:'border-box'}}/>
        <input type="date" value={newInvoice.date} onChange={event => setNewInvoice({...newInvoice, date: event.target.value})} style={{...inp,marginBottom:0,width:'100%',minWidth:0,boxSizing:'border-box'}}/>
        <div style={{gridColumn:spanAll,minWidth:0}}>
          <label style={{fontSize:'12px',color:C.textSec,display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px',cursor:'pointer'}}>
            <input type="checkbox" checked={newInvoice.isNewSupplier} onChange={event => setNewInvoice({...newInvoice, isNewSupplier: event.target.checked})} style={{accentColor:C.accent}}/>
            Новый поставщик
          </label>
          {newInvoice.isNewSupplier ? (
            <input placeholder="Название поставщика *" value={newInvoice.newSupplierName} onChange={event => setNewInvoice({...newInvoice, newSupplierName: event.target.value})} style={{...inp,width:'100%',minWidth:0,boxSizing:'border-box'}}/>
          ) : (
            <select value={newInvoice.supplierId} onChange={event => setNewInvoice({...newInvoice, supplierId: event.target.value})} style={{...inp,width:'100%',minWidth:0,boxSizing:'border-box'}}>
              <option value="">Выберите поставщика</option>
              {(suppliers || []).map(supplier => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
            </select>
          )}
        </div>
        <input placeholder="Принял" value={newInvoice.acceptedBy} onChange={event => setNewInvoice({...newInvoice, acceptedBy: event.target.value})} style={{...inp,marginBottom:0,width:'100%',minWidth:0,boxSizing:'border-box'}}/>
        <select value={newInvoice.vat} onChange={event => setNewInvoice({...newInvoice, vat: event.target.value})} style={{...inp,marginBottom:0,width:'100%',minWidth:0,boxSizing:'border-box'}}>
          {VAT_OPTIONS.map(value => <option key={value}>{value}</option>)}
        </select>
        <div style={{gridColumn:spanAll,minWidth:0}}>
          <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'5px'}}>Куда оприходовать:</label>
          <select value={newInvoice.location} onChange={event => updateLocation(event.target.value)} style={{...inp,width:'100%',minWidth:0,boxSizing:'border-box'}}>
            <option value="Основной склад">Основной склад</option>
            {(projects || []).map(project => <option key={project.id} value={project.name}>{project.name}</option>)}
          </select>
          {invoiceProject && (
            <p style={{color:C.textSec,fontSize:'12px',lineHeight:1.45,margin:'6px 0 0'}}>
              Ручной приход на объект разрешён для прямых закупок и распоряжений директора. Позиции попадут в материалы объекта, журнал движения и сметный контроль; поставки по заявке принимайте через цепочку снабжения, чтобы не задвоить приход.
            </p>
          )}
        </div>
      </div>

      <div style={{marginTop:'10px',marginBottom:'10px'}}>
        {newInvoice.location !== 'Основной склад' && materialEstimates.length > 0 && (
          <div style={{padding:'10px',backgroundColor:C.infoLight,borderRadius:'8px',border:'1.5px solid '+C.infoBorder}}>
            <p style={{color:C.info,fontSize:'12px',margin:'0 0 6px',fontWeight:'600'}}>📊 Сметы материалов по объекту:</p>
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
              {materialEstimates.map(estimate => (
                <button key={estimate.id} onClick={() => setSverkaModal({title:'Сверка накладной со сметой '+estimate.name,text:buildEstimateReconciliationReport(estimate)})} style={{...btnB,fontSize:'11px',padding:'5px 10px'}}>
                  🔍 Сверить с {estimate.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <b style={{color:C.text,fontSize:'13px',display:'block',marginTop:'15px',marginBottom:'10px'}}>Позиции накладной:</b>
      {invoiceItems.map((item, idx) => (
        <div key={idx} style={itemGridStyle}>
          <input placeholder="Наименование товара *" value={item.name} onChange={event => setItem(idx, {name: event.target.value})} style={compactInput}/>
          {isMobile ? (
            <>
              <div style={{display:'grid',gridTemplateColumns:'minmax(0,1fr) 96px',gap:'8px'}}>
                <input placeholder="Кол-во *" type="number" step="any" inputMode="decimal" value={item.quantity} onChange={event => setItem(idx, {quantity: event.target.value})} style={compactInput}/>
                <select value={item.unit} onChange={event => setItem(idx, {unit: event.target.value})} style={compactInput}>
                  {UNITS.map(unit => <option key={unit}>{unit}</option>)}
                </select>
              </div>
              <div style={{display:'grid',gridTemplateColumns:'minmax(0,1fr) minmax(0,1fr)',gap:'8px'}}>
                <input placeholder="Цена ₽" type="number" step="any" inputMode="decimal" value={item.price} onChange={event => setItem(idx, {price: event.target.value})} style={compactInput}/>
                <select value={item.category} onChange={event => setItem(idx, {category: event.target.value})} style={compactInput}>
                  <option value="">Категория</option>
                  {MATERIAL_CATEGORIES.map(category => <option key={category}>{category}</option>)}
                </select>
              </div>
              <select value={item.workPackage || ''} onChange={event => setItem(idx, {workPackage: event.target.value, estimateWorkValue:'', estimateId:'', estimateItemKey:'', parentWorkKey:'', parentWorkName:'', parentWorkSourceCode:'', sectionName:''})} disabled={!invoiceProject} style={{...compactInput,opacity:invoiceProject?1:0.65}}>
                <option value="">{invoiceProject ? 'Раздел сметы' : 'Только для объекта'}</option>
                {packageOptions.map(pkg => <option key={pkg} value={pkg}>{pkg}</option>)}
              </select>
              <select value={item.estimateWorkValue || ''} onChange={event => setItemWork(idx, event.target.value)} disabled={!invoiceProject} style={{...compactInput,opacity:invoiceProject?1:0.65}}>
                <option value="">{invoiceProject ? 'Работа сметы, если нет материала' : 'Работа сметы'}</option>
                {workOptionsForItem(item).map(work => (
                  <option key={work.value} value={work.value}>{work.label}</option>
                ))}
              </select>
              <button onClick={() => removeItem(idx)} style={{...btnR,padding:'8px 10px',width:'100%',justifyContent:'center'}}><X size={12}/>Удалить строку</button>
            </>
          ) : (
            <>
              <input placeholder="Кол-во *" type="number" step="any" inputMode="decimal" value={item.quantity} onChange={event => setItem(idx, {quantity: event.target.value})} style={compactInput}/>
              <select value={item.unit} onChange={event => setItem(idx, {unit: event.target.value})} style={compactInput}>
                {UNITS.map(unit => <option key={unit}>{unit}</option>)}
              </select>
              <input placeholder="Цена ₽" type="number" step="any" inputMode="decimal" value={item.price} onChange={event => setItem(idx, {price: event.target.value})} style={compactInput}/>
              <select value={item.category} onChange={event => setItem(idx, {category: event.target.value})} style={compactInput}>
                <option value="">Категория</option>
                {MATERIAL_CATEGORIES.map(category => <option key={category}>{category}</option>)}
              </select>
              <select value={item.workPackage || ''} onChange={event => setItem(idx, {workPackage: event.target.value, estimateWorkValue:'', estimateId:'', estimateItemKey:'', parentWorkKey:'', parentWorkName:'', parentWorkSourceCode:'', sectionName:''})} disabled={!invoiceProject} style={{...compactInput,opacity:invoiceProject?1:0.65}}>
                <option value="">{invoiceProject ? 'Раздел сметы' : 'Только для объекта'}</option>
                {packageOptions.map(pkg => <option key={pkg} value={pkg}>{pkg}</option>)}
              </select>
              <select value={item.estimateWorkValue || ''} onChange={event => setItemWork(idx, event.target.value)} disabled={!invoiceProject} style={{...compactInput,opacity:invoiceProject?1:0.65}}>
                <option value="">{invoiceProject ? 'Работа сметы, если нет материала' : 'Работа сметы'}</option>
                {workOptionsForItem(item).map(work => (
                  <option key={work.value} value={work.value}>{work.label}</option>
                ))}
              </select>
              <button onClick={() => removeItem(idx)} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
            </>
          )}
        </div>
      ))}

      <button onClick={addItem} style={{...btnG,fontSize:'12px',marginBottom:'15px'}}><Plus size={13}/>Добавить строку</button>

      {newInvoice.location !== 'Основной склад' && draftEstimateControl.some(row => row.name) && (
        <div style={{padding:'10px',backgroundColor:draftControlIssues.length?C.warningLight:C.successLight,borderRadius:'10px',border:'1.5px solid '+(draftControlIssues.length?C.warningBorder:C.successBorder),marginBottom:'15px'}}>
          <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'center',marginBottom:'8px'}}>
            <b style={{color:draftControlIssues.length?C.warning:C.success,fontSize:'12px'}}>Сверка накладной со сметой</b>
            <span style={{color:C.textSec,fontSize:'11px'}}>{draftControlIssues.length ? 'Замечаний: '+draftControlIssues.length : 'Без замечаний'}</span>
          </div>
          <div style={{display:'grid',gap:'6px'}}>
            {draftEstimateControl.filter(row => row.name).map(row => (
              <div key={row.index} style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'minmax(160px,1fr) auto minmax(180px,auto)',gap:'8px',alignItems:'center',fontSize:'11px',color:C.text,minWidth:0}}>
                <span style={{overflow:'hidden',textOverflow:isMobile?'clip':'ellipsis',whiteSpace:isMobile?'normal':'nowrap',overflowWrap:'anywhere'}} title={row.name}>
                  {row.name}
                  {row.canonicalName && row.canonicalName !== row.name ? ' → ' + row.canonicalName : ''}
                  {row.planSourceCount ? ' · ' + row.planSourceCount + ' строк сметы' : ''}
                </span>
                {renderControlBadge(row)}
                <span style={{color:C.textSec,textAlign:isMobile?'left':'right',overflowWrap:'anywhere'}}>
                  {'План '+row.planText+' · накл. '+(row.incomingText||'—')+' · после '+row.afterText+(row.shortageText && row.shortageText !== '—' ? ' · докупить '+row.shortageText : '')+(row.overText && row.overText !== '—' ? ' · сверх '+row.overText : '')+(row.priceOverText && row.priceOverText !== '—' ? ' · дороже '+row.priceOverText : '')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'15px',flexWrap:'wrap'}}>
        <input ref={invoiceGalleryInputRef} type="file" accept={invoiceImageAccept} multiple style={{display:'none'}} onChange={addPhotos}/>
        <input ref={invoiceCameraInputRef} type="file" accept="image/*" multiple capture="environment" style={{display:'none'}} onChange={addPhotos}/>
        <button type="button" onClick={() => invoiceGalleryInputRef.current?.click()} style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'8px 14px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'inline-flex',alignItems:'center',gap:'6px'}}>
          <Upload size={13}/>PDF/фото из галереи
        </button>
        <button type="button" onClick={() => invoiceCameraInputRef.current?.click()} style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'8px 14px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'inline-flex',alignItems:'center',gap:'6px'}}>
          📷 Камера
        </button>
        {(newInvoice.photos || []).map((url, index) => (
          isPdfUrl(url)
            ? <a key={index} href={fileSrc(url)} target="_blank" rel="noreferrer" style={{width:'48px',height:'48px',borderRadius:'8px',display:'inline-flex',alignItems:'center',justifyContent:'center',textDecoration:'none',fontSize:'11px',fontWeight:800,color:C.info,border:'1.5px solid '+C.border,backgroundColor:C.infoLight}}>PDF</a>
            : <img key={index} src={fileSrc(url)} alt="" onClick={() => setShowPhotoModal(fileSrc(url))} style={{width:'48px',height:'48px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>
        ))}
      </div>

      <div style={{backgroundColor:C.bg,borderRadius:'10px',padding:'12px',marginBottom:'15px',border:'1.5px solid '+C.border}}>
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
          <span style={{color:C.textSec,fontSize:'13px'}}>Итого без НДС:</span>
          <b style={{color:C.text,fontSize:'13px'}}>{invoiceBaseAmount.toLocaleString()+' ₽'}</b>
        </div>
        {vatRateValue > 0 && (
          <>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
              <span style={{color:C.textSec,fontSize:'13px'}}>НДС {vatRateValue}%:</span>
              <b style={{color:C.text,fontSize:'13px'}}>{invoiceVatAmount.toLocaleString()+' ₽'}</b>
            </div>
            <div style={{display:'flex',justifyContent:'space-between'}}>
              <b style={{color:C.text,fontSize:'13px'}}>Итого с НДС:</b>
              <b style={{color:C.accent,fontSize:'15px'}}>{invoiceTotal.toLocaleString()+' ₽'}</b>
            </div>
          </>
        )}
      </div>

      <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
        <button onClick={saveInvoiceNew} style={{...btnO, ...(isMobile ? {flex:'1 1 100%',justifyContent:'center'} : {})}}><Check size={14}/>Сохранить и оприходовать</button>
        <button onClick={() => setShowForm(false)} style={{...btnG, ...(isMobile ? {flex:'1 1 100%',justifyContent:'center'} : {})}}><X size={14}/>Отмена</button>
      </div>
    </div>
  );
}

export function WarehouseInvoiceCard({
  inv,
  invoiceRows,
  estimateControl,
  estimateIssues,
  isSupplyDeliveryInvoice,
  invoiceControlSummary,
  renderControlBadge,
  renderInvoiceControlActions,
  showPreview,
  buildInvoiceContent,
  setShowQRModal,
  fileSrc,
  setShowPhotoModal,
  projectName,
  materialSummary,
  materialTransfers = [],
  onPrepareTransfer,
  C,
  card,
  btnB,
  btnG,
  tbl,
  tblH,
  tblC,
  isMobile = false,
}) {
  const items = invoiceRows.items;
  const isPdfUrl = (url) => /\.pdf(?:$|[?#])/i.test(String(url || ''));
  const toNum = value => {
    const parsed = Number(String(value ?? '').replace(',', '.').replace(/\s+/g, ''));
    return Number.isFinite(parsed) ? parsed : 0;
  };
  const normalizeText = value => String(value || '')
    .toLowerCase()
    .replace(/[.,;:()«»"']/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  const packageOf = (row = {}) => String(row.workPackage || row.work_package || row.packageName || '').trim();
  const invoiceLineKeyFor = ({ materialName = '', workPackage = '', unit = '' } = {}) => [
    normalizeText(materialName),
    normalizeText(workPackage),
    normalizeText(unit),
  ].join('|');
  const formatMeasure = (value, unit) => {
    const num = toNum(value);
    if (!num) return '0 ' + (unit || '');
    return (Math.round(num * 1000) / 1000).toLocaleString('ru-RU') + ' ' + (unit || '');
  };
  const stockFactForItem = (item = {}, ctrl = {}) => {
    const rows = materialSummary?.rows || [];
    if (!rows.length) return null;
    const itemPackage = packageOf(ctrl) || packageOf(item);
    const names = [item.name, ctrl.canonicalName, ctrl.name].map(normalizeText).filter(Boolean);
    const nameMatches = row => {
      const rowName = normalizeText(row.name);
      return names.some(name => rowName === name || (name && (rowName.includes(name) || name.includes(rowName))));
    };
    const packageMatches = row => !itemPackage || packageOf(row) === itemPackage;
    return rows.find(row => packageMatches(row) && nameMatches(row)) || rows.find(nameMatches) || null;
  };
  const invoiceBalanceForItem = (item = {}, ctrl = {}, fact = null) => {
    const unit = fact?.unit || ctrl.rowUnit || item.unit || '';
    const workPackage = packageOf(fact || {}) || packageOf(ctrl) || packageOf(item);
    const materialName = item.name || fact?.name || ctrl.canonicalName || '';
    const invoiceLineKey = invoiceLineKeyFor({ materialName, workPackage, unit });
    const issued = (materialTransfers || [])
      .filter(transfer => String(transfer.invoiceId || '') === String(inv.id || ''))
      .filter(transfer => (transfer.status || 'Активна') !== 'Аннулирована')
      .filter(transfer => {
        const transferLineKey = transfer.invoiceLineKey || '';
        if (transferLineKey) return transferLineKey === invoiceLineKey;
        return normalizeText(transfer.materialName) === normalizeText(materialName) &&
          packageOf(transfer) === workPackage &&
          normalizeText(transfer.unit || '') === normalizeText(unit || '');
      })
      .reduce((sum, transfer) => sum + toNum(transfer.quantity), 0);
    const received = toNum(item.quantity);
    return {
      unit,
      received,
      issued,
      remaining: Math.max(0, received - issued),
      overIssued: Math.max(0, issued - received),
    };
  };

  return (
    <div style={{...card,padding:isMobile?'14px':'16px',marginBottom:'10px',overflow:'hidden'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexDirection:isMobile?'column':'row'}}>
        <div style={{minWidth:0}}>
          <b style={{color:C.text,fontSize:'14px'}}>{'Накладная № '+inv.number}</b>
          <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{inv.date+' · '+inv.supplierName+' · '+(inv.location==='Основной склад'?'Основной склад':inv.project||'')}</p>
          <p style={{color:C.textSec,margin:'0',fontSize:'12px'}}>{'Принял: '+inv.acceptedBy+' · '+inv.vat+' · позиций: '+items.length}</p>
          {inv.status && <p style={{color:inv.status==='Аннулирована'?C.danger:C.textSec,margin:'2px 0 0',fontSize:'11px',fontWeight:'700'}}>{'Статус: '+inv.status}</p>}
          {isSupplyDeliveryInvoice(inv) && <p style={{color:C.success,margin:'3px 0 0',fontSize:'11px',fontWeight:'700'}}>Из поставки снабжения #{inv.supplyDeliveryId||inv.sourceId}{inv.supplyRequestId?' · заявка #'+inv.supplyRequestId:''}</p>}
          {inv.sourceType === 'manual_project_invoice' && <p style={{color:C.info,margin:'3px 0 0',fontSize:'11px',fontWeight:'700'}}>Ручной приход на объект · прямой заказ / распоряжение директора</p>}
          {invoiceRows.reconstructed && <p style={{color:C.warning,margin:'2px 0 0',fontSize:'11px'}}>Строки восстановлены из {invoiceRows.source}</p>}
          {inv.location !== 'Основной склад' && estimateControl.length > 0 && (
            <p style={{color:estimateIssues.length?C.warning:C.success,margin:'3px 0 0',fontSize:'11px',fontWeight:'800'}}>
              {(() => {
                const sum = invoiceControlSummary(estimateControl);
                return 'Сметный контроль: ' + (estimateIssues.length ? 'замечаний ' + estimateIssues.length : 'без замечаний') +
                  ' · по смете ' + sum.ok +
                  (sum.composite ? ' · комплектация работ ' + sum.composite : '') +
                  (sum.outside ? ' · вне сметы ' + sum.outside : '') +
                  (sum.over ? ' · сверх плана ' + sum.over : '') +
                  (sum.price ? ' · цена выше ' + sum.price : '');
              })()}
            </p>
          )}
        </div>
        <div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap',width:isMobile?'100%':undefined,justifyContent:isMobile?'space-between':'flex-start'}}>
          <b style={{color:C.success,fontSize:'14px'}}>{(inv.totalWithVat||inv.totalBase||0).toLocaleString()+' ₽'}</b>
          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:isMobile?'flex-end':'flex-start'}}>
            {onPrepareTransfer && projectName && items.length > 0 && (
              <button onClick={onPrepareTransfer} style={{...btnG,padding:'6px 9px'}} title="Подготовить выдачу по материалам этой накладной">
                <Truck size={13}/>
                В выдачу
              </button>
            )}
            <button onClick={() => showPreview(buildInvoiceContent(inv),'Накладная № '+inv.number)} style={btnB} title="Печать"><Eye size={13}/></button>
            <button onClick={() => setShowQRModal({title:'QR накладной №'+inv.number,data:window.location.origin+'/?invoice='+inv.id})} style={btnG} title="QR-код накладной — отсканировав, можно быстро открыть на телефоне на стройке"><QrCode size={13}/></button>
          </div>
        </div>
      </div>

      {items.length > 0 ? (
        <details style={{marginTop:'10px'}}>
          <summary style={{cursor:'pointer',color:C.accent,fontSize:'12px',fontWeight:'600',padding:'4px 0'}}>📋 Материалы и остатки ({items.length})</summary>
          {isMobile ? (
            <div style={{display:'grid',gap:'10px',marginTop:'8px'}}>
              {items.map((item, index) => {
                const rowSum = Number(item.total || 0) || Number((item.quantity || 0) * (item.price || 0));
                const ctrl = estimateControl[index] || {};
                const fact = stockFactForItem(item, ctrl);
                const factUnit = fact?.unit || ctrl.rowUnit || item.unit || '';
                const invoiceBalance = invoiceBalanceForItem(item, ctrl, fact);
                return (
                  <div key={index} style={{border:'1.5px solid '+C.border,borderRadius:'12px',backgroundColor:C.bg,padding:'10px',minWidth:0}}>
                    <div style={{display:'flex',justifyContent:'space-between',gap:'8px',alignItems:'flex-start',marginBottom:'8px'}}>
                      <b style={{fontSize:'12px',color:C.text,overflowWrap:'anywhere'}}>{item.name || ''}</b>
                      {renderControlBadge(ctrl)}
                    </div>
                    {item.invoiceOriginalName && item.invoiceOriginalName !== item.name && <p style={{color:C.textMuted,fontSize:'11px',margin:'2px 0 0'}}>Из накладной: {item.invoiceOriginalName}</p>}
                    {ctrl.canonicalName && ctrl.canonicalName !== item.name && <p style={{color:C.info,fontSize:'11px',margin:'2px 0 0'}}>Смета: {ctrl.canonicalName}</p>}
                    {ctrl.planSourceCount > 0 && <p style={{color:C.textMuted,fontSize:'11px',margin:'2px 0 0'}}>Сгруппировано из {ctrl.planSourceCount} строк сметы</p>}
                    {ctrl.sectionsList?.length > 0 && <p style={{color:C.textMuted,fontSize:'11px',margin:'2px 0 0'}}>{ctrl.sectionsList.slice(0,2).join(' · ')}{ctrl.sectionsList.length > 2 ? '…' : ''}</p>}
                    {ctrl.workRefs?.length > 0 && <p style={{color:C.accent,fontSize:'11px',margin:'2px 0 0'}}>Работы: {ctrl.workRefs.slice(0,2).join('; ')}{ctrl.workRefs.length > 2 ? '…' : ''}</p>}
                    {ctrl.isCompositeWorkMaterial && <p style={{color:C.info,fontSize:'11px',margin:'2px 0 0',fontWeight:700}}>Комплектация укрупненной работы</p>}
                    {item.parentWorkName && !(ctrl.workRefs||[]).includes(item.parentWorkName) && <p style={{color:C.accent,fontSize:'11px',margin:'2px 0 0'}}>Комплектация: {item.parentWorkName}</p>}
                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'10px',fontSize:'12px'}}>
                      <span style={{color:C.textSec}}>Кол-во<br/><b style={{color:C.text}}>{item.quantity || 0} {item.unit || ''}</b></span>
                      <span style={{color:C.textSec}}>Сумма<br/><b style={{color:C.success}}>{rowSum.toLocaleString('ru-RU')+' ₽'}</b></span>
                      <span style={{color:C.textSec}}>План<br/><b style={{color:C.text}}>{ctrl.planText || '—'}</b></span>
                      <span style={{color:C.textSec}}>После<br/><b style={{color:ctrl.severity==='danger'?C.danger:C.text}}>{ctrl.afterText || '—'}</b></span>
                      <span style={{color:C.textSec}}>Накладная<br/><b style={{color:C.info}}>{ctrl.incomingText || item.quantity + ' ' + (item.unit || '')}</b></span>
                      <span style={{color:C.textSec}}>Цена<br/><b style={{color:ctrl.priceOverText && ctrl.priceOverText !== '—' ? C.warning : C.text}}>{ctrl.invoicePriceText||'—'}</b></span>
                    </div>
                    {projectName && (
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginTop:'10px',padding:'10px',borderRadius:'10px',border:'1px solid '+(fact?C.infoBorder:C.border),backgroundColor:fact?C.infoLight:C.bgWhite,fontSize:'12px'}}>
                        <span style={{color:C.textSec}}>Пришло по накладной<br/><b style={{color:C.text}}>{formatMeasure(invoiceBalance.received, invoiceBalance.unit)}</b></span>
                        <span style={{color:C.textSec}}>Выдано из накладной<br/><b style={{color:invoiceBalance.issued>0?C.info:C.textMuted}}>{formatMeasure(invoiceBalance.issued, invoiceBalance.unit)}</b></span>
                        <span style={{color:C.textSec}}>Осталось по накладной<br/><b style={{color:invoiceBalance.remaining>0?C.success:C.textMuted}}>{formatMeasure(invoiceBalance.remaining, invoiceBalance.unit)}</b></span>
                        <span style={{color:C.textSec}}>Перевыдача<br/><b style={{color:invoiceBalance.overIssued>0?C.danger:C.textMuted}}>{formatMeasure(invoiceBalance.overIssued, invoiceBalance.unit)}</b></span>
                        <span style={{color:C.textSec}}>Остаток объекта<br/><b style={{color:fact && toNum(fact.stock)>0?C.success:C.textMuted}}>{fact ? formatMeasure(fact.stock, factUnit) : 'не найден'}</b></span>
                        <span style={{color:C.textSec}}>Выдано по объекту<br/><b style={{color:fact && toNum(fact.issued)>0?C.info:C.textMuted}}>{fact ? formatMeasure(fact.issued, factUnit) : '—'}</b></span>
                        <span style={{color:C.textSec}}>У мастеров<br/><b style={{color:fact && toNum(fact.masterBalance)>0?C.warning:C.textMuted}}>{fact ? formatMeasure(fact.masterBalance, factUnit) : '—'}</b></span>
                        <span style={{color:C.textSec}}>Списано<br/><b style={{color:fact && toNum(fact.used)>0?C.text:C.textMuted}}>{fact ? formatMeasure(fact.used, factUnit) : '—'}</b></span>
                      </div>
                    )}
                    <div style={{marginTop:'8px',fontSize:'12px',color:ctrl.overText && ctrl.overText !== '—' ? C.danger : ctrl.shortageText && ctrl.shortageText !== '—' ? C.warning : C.success,fontWeight:'800'}}>
                      {ctrl.overText && ctrl.overText !== '—' ? 'Сверх сметы: '+ctrl.overText : ctrl.shortageText && ctrl.shortageText !== '—' ? 'Докупить: '+ctrl.shortageText : 'Закрыто по смете'}
                    </div>
                    <div style={{marginTop:'8px'}}>{renderInvoiceControlActions ? (renderInvoiceControlActions(inv, ctrl, item) || <span style={{color:C.textMuted,fontSize:'12px'}}>—</span>) : <span style={{color:C.textMuted,fontSize:'12px'}}>—</span>}</div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{marginTop:'8px',overflowX:'auto'}}>
              <table style={{...tbl,fontSize:'11px',minWidth:'1380px'}}>
                <thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>Кол-во</th><th style={tblH}>Сумма</th><th style={tblH}>Смета</th><th style={tblH}>План</th><th style={tblH}>До</th><th style={tblH}>Накладная</th><th style={tblH}>После</th><th style={tblH}>Докупить / сверх</th><th style={tblH}>Цена</th><th style={tblH}>Склад объекта</th><th style={tblH}>Действие</th></tr></thead>
                <tbody>
                  {items.map((item, index) => {
                    const rowSum = Number(item.total || 0) || Number((item.quantity || 0) * (item.price || 0));
                    const ctrl = estimateControl[index] || {};
                    const fact = stockFactForItem(item, ctrl);
                    const factUnit = fact?.unit || ctrl.rowUnit || item.unit || '';
                    const invoiceBalance = invoiceBalanceForItem(item, ctrl, fact);
                    return (
                      <tr key={index}>
                        <td style={tblC}>
                          <b style={{fontSize:'11px'}}>{item.name || ''}</b>
                          {item.invoiceOriginalName && item.invoiceOriginalName !== item.name && <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>Из накладной: {item.invoiceOriginalName}</p>}
                          {ctrl.canonicalName && ctrl.canonicalName !== item.name && <p style={{color:C.info,fontSize:'10px',margin:'2px 0 0'}}>Смета: {ctrl.canonicalName}</p>}
                          {ctrl.planSourceCount > 0 && <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>Сгруппировано из {ctrl.planSourceCount} строк сметы</p>}
                          {ctrl.sectionsList?.length > 0 && <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{ctrl.sectionsList.slice(0,2).join(' · ')}{ctrl.sectionsList.length > 2 ? '…' : ''}</p>}
                          {ctrl.workRefs?.length > 0 && <p style={{color:C.accent,fontSize:'10px',margin:'2px 0 0'}}>Работы: {ctrl.workRefs.slice(0,2).join('; ')}{ctrl.workRefs.length > 2 ? '…' : ''}</p>}
                          {ctrl.isCompositeWorkMaterial && <p style={{color:C.info,fontSize:'10px',margin:'2px 0 0',fontWeight:700}}>Комплектация укрупненной работы</p>}
                          {item.parentWorkName && !(ctrl.workRefs||[]).includes(item.parentWorkName) && <p style={{color:C.accent,fontSize:'10px',margin:'2px 0 0'}}>Комплектация: {item.parentWorkName}</p>}
                        </td>
                        <td style={tblC}>{item.unit || ''}</td>
                        <td style={tblC}>{item.quantity || 0}</td>
                        <td style={tblC}>{rowSum.toLocaleString('ru-RU')+' ₽'}</td>
                        <td style={tblC}>{renderControlBadge(ctrl)}</td>
                        <td style={tblC}>{ctrl.planText || '—'}</td>
                        <td style={tblC}>{ctrl.beforeText || '—'}</td>
                        <td style={{...tblC,color:C.info}}>{ctrl.incomingText || item.quantity + ' ' + (item.unit || '')}</td>
                        <td style={{...tblC,color:ctrl.severity==='danger'?C.danger:C.text}}>{ctrl.afterText || '—'}</td>
                        <td style={{...tblC,color:ctrl.overText && ctrl.overText !== '—' ? C.danger : ctrl.shortageText && ctrl.shortageText !== '—' ? C.warning : C.success}}>
                          {ctrl.overText && ctrl.overText !== '—' ? 'сверх '+ctrl.overText : ctrl.shortageText && ctrl.shortageText !== '—' ? 'докупить '+ctrl.shortageText : 'закрыто'}
                        </td>
                        <td style={{...tblC,color:ctrl.priceOverText && ctrl.priceOverText !== '—' ? C.warning : C.textSec}}>
                          {(ctrl.invoicePriceText||'—')+' / '+(ctrl.planPriceText||'—')+(ctrl.priceOverText && ctrl.priceOverText !== '—' ? ' · +'+ctrl.priceOverText : '')}
                        </td>
                        <td style={tblC}>
                          {projectName ? (
                            <div style={{display:'grid',gap:'2px',fontSize:'10px',color:C.textSec}}>
                              <span>Накл выд: <b style={{color:invoiceBalance.issued>0?C.info:C.textMuted}}>{formatMeasure(invoiceBalance.issued, invoiceBalance.unit)}</b></span>
                              <span>Накл ост: <b style={{color:invoiceBalance.remaining>0?C.success:C.textMuted}}>{formatMeasure(invoiceBalance.remaining, invoiceBalance.unit)}</b></span>
                              {fact && <span>Ост: <b style={{color:toNum(fact.stock)>0?C.success:C.textMuted}}>{formatMeasure(fact.stock, factUnit)}</b></span>}
                              {fact && <span>Выд: <b style={{color:toNum(fact.issued)>0?C.info:C.textMuted}}>{formatMeasure(fact.issued, factUnit)}</b></span>}
                              {fact && <span>У мастеров: <b style={{color:toNum(fact.masterBalance)>0?C.warning:C.textMuted}}>{formatMeasure(fact.masterBalance, factUnit)}</b></span>}
                            </div>
                          ) : '—'}
                        </td>
                        <td style={tblC}>{renderInvoiceControlActions ? (renderInvoiceControlActions(inv, ctrl, item) || <span style={{color:C.textMuted}}>—</span>) : <span style={{color:C.textMuted}}>—</span>}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </details>
      ) : (
        <div style={{marginTop:'10px',padding:'10px 12px',borderRadius:'10px',border:'1.5px solid '+C.warningBorder,backgroundColor:C.warningLight,color:C.warning,fontSize:'12px',fontWeight:'700'}}>
          В этой накладной нет сохранённых строк материалов. Для старых записей можно видеть только общую сумму, но списание и сметный контроль по строкам будут неполными.
        </div>
      )}

	      {(inv.photos || []).length > 0 && (
	        <div style={{display:'flex',gap:'6px',marginTop:'10px',flexWrap:'wrap'}}>
	          {(inv.photos || []).map((url, index) => (
	            isPdfUrl(url)
	              ? <a key={index} href={fileSrc(url)} target="_blank" rel="noreferrer" style={{width:'50px',height:'50px',borderRadius:'8px',display:'inline-flex',alignItems:'center',justifyContent:'center',textDecoration:'none',fontSize:'11px',fontWeight:800,color:C.info,border:'1.5px solid '+C.border,backgroundColor:C.infoLight}}>PDF</a>
	              : <img key={index} src={fileSrc(url)} alt="" onClick={() => setShowPhotoModal(fileSrc(url))} style={{width:'50px',height:'50px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>
	          ))}
	        </div>
	      )}
    </div>
  );
}
