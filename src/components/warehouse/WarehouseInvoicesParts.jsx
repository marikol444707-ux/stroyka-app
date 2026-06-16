import React from 'react';
import { Check, Eye, Plus, QrCode, Upload, X } from 'lucide-react';

export function WarehouseInvoiceForm({
  newInvoice,
  setNewInvoice,
  suppliers,
  projects,
  materialEstimates,
  getProjectWorkPackageOptions,
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
}) {
  const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : '';
  const packageOptions = invoiceProject && typeof getProjectWorkPackageOptions === 'function'
    ? getProjectWorkPackageOptions(invoiceProject)
    : [];
  const defaultWorkPackage = packageOptions.length === 1 ? packageOptions[0] : '';

  const setItem = (idx, patch) => {
    const items = [...invoiceItems];
    items[idx] = {...items[idx], ...patch};
    setNewInvoice({...newInvoice, items});
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
    const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : 'Основной склад';
    const urls = await Promise.all(files.map(file => uploadPhoto(file, {projectName: invoiceProject, context: 'warehouse-invoices'})));
    setNewInvoice(prev => ({...prev, photos: [...(prev.photos || []), ...urls.filter(Boolean)]}));
  };

  return (
    <div style={{...card,padding:'20px',marginBottom:'20px'}}>
      <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>Новая приходная накладная</h3>
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
        <input placeholder="Номер накладной *" value={newInvoice.number} onChange={event => setNewInvoice({...newInvoice, number: event.target.value})} style={{...inp,marginBottom:0}}/>
        <input type="date" value={newInvoice.date} onChange={event => setNewInvoice({...newInvoice, date: event.target.value})} style={{...inp,marginBottom:0}}/>
        <div style={{gridColumn:'span 2'}}>
          <label style={{fontSize:'12px',color:C.textSec,display:'flex',alignItems:'center',gap:'8px',marginBottom:'8px',cursor:'pointer'}}>
            <input type="checkbox" checked={newInvoice.isNewSupplier} onChange={event => setNewInvoice({...newInvoice, isNewSupplier: event.target.checked})} style={{accentColor:C.accent}}/>
            Новый поставщик
          </label>
          {newInvoice.isNewSupplier ? (
            <input placeholder="Название поставщика *" value={newInvoice.newSupplierName} onChange={event => setNewInvoice({...newInvoice, newSupplierName: event.target.value})} style={inp}/>
          ) : (
            <select value={newInvoice.supplierId} onChange={event => setNewInvoice({...newInvoice, supplierId: event.target.value})} style={inp}>
              <option value="">Выберите поставщика</option>
              {(suppliers || []).map(supplier => <option key={supplier.id} value={supplier.id}>{supplier.name}</option>)}
            </select>
          )}
        </div>
        <input placeholder="Принял" value={newInvoice.acceptedBy} onChange={event => setNewInvoice({...newInvoice, acceptedBy: event.target.value})} style={{...inp,marginBottom:0}}/>
        <select value={newInvoice.vat} onChange={event => setNewInvoice({...newInvoice, vat: event.target.value})} style={{...inp,marginBottom:0}}>
          {VAT_OPTIONS.map(value => <option key={value}>{value}</option>)}
        </select>
        <div style={{gridColumn:'span 2'}}>
          <label style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'5px'}}>Куда оприходовать:</label>
          <select value={newInvoice.location} onChange={event => updateLocation(event.target.value)} style={inp}>
            <option value="Основной склад">Основной склад</option>
            {(projects || []).map(project => <option key={project.id} value={project.name}>{project.name}</option>)}
          </select>
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
        <div key={idx} style={{display:'grid',gridTemplateColumns:'minmax(180px,3fr) 1fr 1fr 1fr minmax(130px,1.5fr) minmax(140px,1.7fr) auto',gap:'6px',marginBottom:'8px',alignItems:'center'}}>
          <input placeholder="Наименование товара *" value={item.name} onChange={event => setItem(idx, {name: event.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
          <input placeholder="Кол-во *" type="number" step="any" inputMode="decimal" value={item.quantity} onChange={event => setItem(idx, {quantity: event.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
          <select value={item.unit} onChange={event => setItem(idx, {unit: event.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>
            {UNITS.map(unit => <option key={unit}>{unit}</option>)}
          </select>
          <input placeholder="Цена ₽" type="number" step="any" inputMode="decimal" value={item.price} onChange={event => setItem(idx, {price: event.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
          <select value={item.category} onChange={event => setItem(idx, {category: event.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}>
            <option value="">Категория</option>
            {MATERIAL_CATEGORIES.map(category => <option key={category}>{category}</option>)}
          </select>
          <select value={item.workPackage || ''} onChange={event => setItem(idx, {workPackage: event.target.value})} disabled={!invoiceProject} style={{...inp,marginBottom:0,fontSize:'12px',opacity:invoiceProject?1:0.65}}>
            <option value="">{invoiceProject ? 'Раздел сметы' : 'Только для объекта'}</option>
            {packageOptions.map(pkg => <option key={pkg} value={pkg}>{pkg}</option>)}
          </select>
          <button onClick={() => removeItem(idx)} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
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
              <div key={row.index} style={{display:'grid',gridTemplateColumns:'minmax(160px,1fr) auto minmax(180px,auto)',gap:'8px',alignItems:'center',fontSize:'11px',color:C.text}}>
                <span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={row.name}>
                  {row.name}
                  {row.canonicalName && row.canonicalName !== row.name ? ' → ' + row.canonicalName : ''}
                  {row.planSourceCount ? ' · ' + row.planSourceCount + ' строк сметы' : ''}
                </span>
                {renderControlBadge(row)}
                <span style={{color:C.textSec,textAlign:'right'}}>
                  {'План '+row.planText+' · накл. '+(row.incomingText||'—')+' · после '+row.afterText+(row.shortageText && row.shortageText !== '—' ? ' · докупить '+row.shortageText : '')+(row.overText && row.overText !== '—' ? ' · сверх '+row.overText : '')+(row.priceOverText && row.priceOverText !== '—' ? ' · дороже '+row.priceOverText : '')}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'15px',flexWrap:'wrap'}}>
        <label style={{cursor:'pointer',backgroundColor:C.infoLight,padding:'8px 14px',borderRadius:'8px',fontSize:'13px',color:C.info,border:'1.5px solid '+C.infoBorder,display:'inline-flex',alignItems:'center',gap:'6px'}}>
          <Upload size={13}/>Добавить фото
          <input type="file" accept="image/*" multiple style={{display:'none'}} onChange={addPhotos}/>
        </label>
        {(newInvoice.photos || []).map((url, index) => (
          <img key={index} src={fileSrc(url)} alt="" onClick={() => setShowPhotoModal(fileSrc(url))} style={{width:'48px',height:'48px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>
        ))}
      </div>

      <div style={{backgroundColor:C.bg,borderRadius:'10px',padding:'12px',marginBottom:'15px',border:'1.5px solid '+C.border}}>
        <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
          <span style={{color:C.textSec,fontSize:'13px'}}>Итого без НДС:</span>
          <b style={{color:C.text,fontSize:'13px'}}>{invoiceTotal.toLocaleString()+' ₽'}</b>
        </div>
        {newInvoice.vat === 'С НДС 22%' && (
          <>
            <div style={{display:'flex',justifyContent:'space-between',marginBottom:'4px'}}>
              <span style={{color:C.textSec,fontSize:'13px'}}>НДС 22%:</span>
              <b style={{color:C.text,fontSize:'13px'}}>{Math.round(invoiceTotal / 1.22 * 0.22).toLocaleString()+' ₽'}</b>
            </div>
            <div style={{display:'flex',justifyContent:'space-between'}}>
              <b style={{color:C.text,fontSize:'13px'}}>Итого с НДС:</b>
              <b style={{color:C.accent,fontSize:'15px'}}>{invoiceTotal.toLocaleString()+' ₽'}</b>
            </div>
          </>
        )}
      </div>

      <div style={{display:'flex',gap:'8px'}}>
        <button onClick={saveInvoiceNew} style={btnO}><Check size={14}/>Сохранить и оприходовать</button>
        <button onClick={() => setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
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
  C,
  card,
  btnB,
  btnG,
  tbl,
  tblH,
  tblC,
}) {
  const items = invoiceRows.items;

  return (
    <div style={{...card,padding:'16px',marginBottom:'10px'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px'}}>{'Накладная № '+inv.number}</b>
          <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{inv.date+' · '+inv.supplierName+' · '+(inv.location==='Основной склад'?'Основной склад':inv.project||'')}</p>
          <p style={{color:C.textSec,margin:'0',fontSize:'12px'}}>{'Принял: '+inv.acceptedBy+' · '+inv.vat+' · позиций: '+items.length}</p>
          {inv.status && <p style={{color:inv.status==='Аннулирована'?C.danger:C.textSec,margin:'2px 0 0',fontSize:'11px',fontWeight:'700'}}>{'Статус: '+inv.status}</p>}
          {isSupplyDeliveryInvoice(inv) && <p style={{color:C.success,margin:'3px 0 0',fontSize:'11px',fontWeight:'700'}}>Из поставки снабжения #{inv.supplyDeliveryId||inv.sourceId}{inv.supplyRequestId?' · заявка #'+inv.supplyRequestId:''}</p>}
          {invoiceRows.reconstructed && <p style={{color:C.warning,margin:'2px 0 0',fontSize:'11px'}}>Строки восстановлены из {invoiceRows.source}</p>}
          {inv.location !== 'Основной склад' && estimateControl.length > 0 && (
            <p style={{color:estimateIssues.length?C.warning:C.success,margin:'3px 0 0',fontSize:'11px',fontWeight:'800'}}>
              {(() => {
                const sum = invoiceControlSummary(estimateControl);
                return 'Сметный контроль: ' + (estimateIssues.length ? 'замечаний ' + estimateIssues.length : 'без замечаний') +
                  ' · по смете ' + sum.ok +
                  (sum.outside ? ' · вне сметы ' + sum.outside : '') +
                  (sum.over ? ' · сверх плана ' + sum.over : '') +
                  (sum.price ? ' · цена выше ' + sum.price : '');
              })()}
            </p>
          )}
        </div>
        <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
          <b style={{color:C.success,fontSize:'14px'}}>{(inv.totalWithVat||inv.totalBase||0).toLocaleString()+' ₽'}</b>
          <button onClick={() => showPreview(buildInvoiceContent(inv),'Накладная № '+inv.number)} style={btnB} title="Печать"><Eye size={13}/></button>
          <button onClick={() => setShowQRModal({title:'QR накладной №'+inv.number,data:window.location.origin+'/?invoice='+inv.id})} style={btnG} title="QR-код накладной — отсканировав, можно быстро открыть на телефоне на стройке"><QrCode size={13}/></button>
        </div>
      </div>

      {items.length > 0 ? (
        <details style={{marginTop:'10px'}}>
          <summary style={{cursor:'pointer',color:C.accent,fontSize:'12px',fontWeight:'600',padding:'4px 0'}}>📋 Показать материалы ({items.length})</summary>
          <div style={{marginTop:'8px',overflowX:'auto'}}>
            <table style={{...tbl,fontSize:'11px',minWidth:'1260px'}}>
              <thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>Кол-во</th><th style={tblH}>Сумма</th><th style={tblH}>Смета</th><th style={tblH}>План</th><th style={tblH}>До</th><th style={tblH}>Накладная</th><th style={tblH}>После</th><th style={tblH}>Докупить / сверх</th><th style={tblH}>Цена</th><th style={tblH}>Действие</th></tr></thead>
              <tbody>
                {items.map((item, index) => {
                  const rowSum = Number(item.total || 0) || Number((item.quantity || 0) * (item.price || 0));
                  const ctrl = estimateControl[index] || {};
                  return (
                    <tr key={index}>
                      <td style={tblC}>
                        <b style={{fontSize:'11px'}}>{item.name || ''}</b>
                        {ctrl.canonicalName && ctrl.canonicalName !== item.name && <p style={{color:C.info,fontSize:'10px',margin:'2px 0 0'}}>Смета: {ctrl.canonicalName}</p>}
                        {ctrl.planSourceCount > 0 && <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>Сгруппировано из {ctrl.planSourceCount} строк сметы</p>}
                        {ctrl.sectionsList?.length > 0 && <p style={{color:C.textMuted,fontSize:'10px',margin:'2px 0 0'}}>{ctrl.sectionsList.slice(0,2).join(' · ')}{ctrl.sectionsList.length > 2 ? '…' : ''}</p>}
                        {ctrl.workRefs?.length > 0 && <p style={{color:C.accent,fontSize:'10px',margin:'2px 0 0'}}>Работы: {ctrl.workRefs.slice(0,2).join('; ')}{ctrl.workRefs.length > 2 ? '…' : ''}</p>}
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
                      <td style={tblC}>{renderInvoiceControlActions ? (renderInvoiceControlActions(inv, ctrl, item) || <span style={{color:C.textMuted}}>—</span>) : <span style={{color:C.textMuted}}>—</span>}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </details>
      ) : (
        <div style={{marginTop:'10px',padding:'10px 12px',borderRadius:'10px',border:'1.5px solid '+C.warningBorder,backgroundColor:C.warningLight,color:C.warning,fontSize:'12px',fontWeight:'700'}}>
          В этой накладной нет сохранённых строк материалов. Для старых записей можно видеть только общую сумму, но списание и сметный контроль по строкам будут неполными.
        </div>
      )}

      {(inv.photos || []).length > 0 && (
        <div style={{display:'flex',gap:'6px',marginTop:'10px',flexWrap:'wrap'}}>
          {(inv.photos || []).map((url, index) => (
            <img key={index} src={fileSrc(url)} alt="" onClick={() => setShowPhotoModal(fileSrc(url))} style={{width:'50px',height:'50px',borderRadius:'8px',objectFit:'cover',cursor:'pointer',border:'1.5px solid '+C.border}}/>
          ))}
        </div>
      )}
    </div>
  );
}
