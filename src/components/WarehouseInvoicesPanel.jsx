import React from 'react';
import { Check, Eye, Plus, QrCode, Upload, X } from 'lucide-react';

export default function WarehouseInvoicesPanel({
  showForm,
  setShowForm,
  newInvoice,
  setNewInvoice,
  suppliers,
  projects,
  estimatesList,
  invoices,
  saveInvoiceNew,
  uploadPhoto,
  fileSrc,
  setShowPhotoModal,
  setSverkaModal,
  warehouseInvoiceItems,
  isSupplyDeliveryInvoice,
  showPreview,
  buildInvoiceContent,
  setShowQRModal,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnR,
  tbl,
  tblH,
  tblC,
  VAT_OPTIONS,
  UNITS,
  MATERIAL_CATEGORIES,
}) {
  const invoiceItems = newInvoice.items || [];
  const invoiceTotal = invoiceItems.reduce((sum, item) => sum + Number(item.quantity || 0) * Number(item.price || 0), 0);
  const materialEstimates = (estimatesList || []).filter(est => est.projectName === newInvoice.location && est.smetaType === 'Материалы');

  const setItem = (idx, patch) => {
    const items = [...invoiceItems];
    items[idx] = {...items[idx], ...patch};
    setNewInvoice({...newInvoice, items});
  };

  const removeItem = (idx) => {
    const items = invoiceItems.filter((_, itemIdx) => itemIdx !== idx);
    setNewInvoice({
      ...newInvoice,
      items: items.length ? items : [{name:'', quantity:'', unit:'шт', price:'', category:''}],
    });
  };

  const addItem = () => {
    setNewInvoice({
      ...newInvoice,
      items: [...invoiceItems, {name:'', quantity:'', unit:'шт', price:'', category:''}],
    });
  };

  const addPhotos = async (event) => {
    const files = Array.from(event.target.files || []);
    const invoiceProject = newInvoice.location && newInvoice.location !== 'Основной склад' ? newInvoice.location : 'Основной склад';
    const urls = await Promise.all(files.map(file => uploadPhoto(file, {projectName: invoiceProject, context: 'warehouse-invoices'})));
    setNewInvoice(prev => ({...prev, photos: [...(prev.photos || []), ...urls.filter(Boolean)]}));
  };

  const buildEstimateReconciliationReport = (estimate) => {
    const smetaItems = (estimate.sections || []).flatMap(section => section.items || []);
    const filledItems = invoiceItems.filter(item => item.name && item.quantity);
    let report = '📊 СВЕРКА НАКЛАДНОЙ СО СМЕТОЙ\n';
    report += 'Смета: ' + estimate.name + '\n\n';

    const norm = (value) => String(value || '').toLowerCase().replace(/[хx×]/g, 'x').replace(/[,.]/g, '.').replace(/\s+/g, ' ').trim();

    filledItems.forEach(invItem => {
      const matched = smetaItems.find(si => (
        norm(si.name).includes(norm(invItem.name)) ||
        norm(invItem.name).includes(norm(si.name)) ||
        norm(si.name).split(' ').filter(word => word.length > 3).every(word => norm(invItem.name).includes(word))
      ));
      if (matched) {
        const need = Number(matched.quantity || 0);
        const got = Number(invItem.quantity || 0);
        const diff = need - got;
        report += `✅ ${invItem.name}\n`;
        report += `   По смете: ${need} ${matched.unit}\n`;
        report += `   Получено: ${got} ${invItem.unit}\n`;
        report += diff > 0 ? `   ⚠️ Дефицит: ${diff}\n\n` : '   ✅ Достаточно\n\n';
      } else {
        report += `❓ ${invItem.name} — не найдено в смете\n\n`;
      }
    });

    return report;
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Накладные</b>
        <button onClick={() => setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая накладная</button>
      </div>

      {showForm && (
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
              <select value={newInvoice.location} onChange={event => setNewInvoice({...newInvoice, location: event.target.value, project: event.target.value === 'Основной склад' ? '' : newInvoice.project})} style={inp}>
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
            <div key={idx} style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr 1fr 2fr auto',gap:'6px',marginBottom:'8px',alignItems:'center'}}>
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
              <button onClick={() => removeItem(idx)} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
            </div>
          ))}

          <button onClick={addItem} style={{...btnG,fontSize:'12px',marginBottom:'15px'}}><Plus size={13}/>Добавить строку</button>

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
      )}

      {(invoices || []).map(inv => {
        const invoiceRows = warehouseInvoiceItems(inv);
        const items = invoiceRows.items;
        return (
          <div key={inv.id} style={{...card,padding:'16px',marginBottom:'10px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
              <div>
                <b style={{color:C.text,fontSize:'14px'}}>{'Накладная № '+inv.number}</b>
                <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{inv.date+' · '+inv.supplierName+' · '+(inv.location==='Основной склад'?'Основной склад':inv.project||'')}</p>
                <p style={{color:C.textSec,margin:'0',fontSize:'12px'}}>{'Принял: '+inv.acceptedBy+' · '+inv.vat+' · позиций: '+items.length}</p>
                {isSupplyDeliveryInvoice(inv) && <p style={{color:C.success,margin:'3px 0 0',fontSize:'11px',fontWeight:'700'}}>Из поставки снабжения #{inv.supplyDeliveryId||inv.sourceId}{inv.supplyRequestId?' · заявка #'+inv.supplyRequestId:''}</p>}
                {invoiceRows.reconstructed && <p style={{color:C.warning,margin:'2px 0 0',fontSize:'11px'}}>Строки восстановлены из {invoiceRows.source}</p>}
              </div>
              <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                <b style={{color:C.success,fontSize:'14px'}}>{(inv.totalWithVat||inv.totalBase||0).toLocaleString()+' ₽'}</b>
                <button onClick={() => showPreview(buildInvoiceContent(inv),'Накладная № '+inv.number)} style={btnB} title="Печать"><Eye size={13}/></button>
                <button onClick={() => setShowQRModal({title:'QR накладной №'+inv.number,data:window.location.origin+'/?invoice='+inv.id})} style={btnG} title="QR-код накладной — отсканировав, можно быстро открыть на телефоне на стройке"><QrCode size={13}/></button>
              </div>
            </div>

            {items.length > 0 && (
              <details style={{marginTop:'10px'}}>
                <summary style={{cursor:'pointer',color:C.accent,fontSize:'12px',fontWeight:'600',padding:'4px 0'}}>📋 Показать материалы ({items.length})</summary>
                <div style={{marginTop:'8px',overflowX:'auto'}}>
                  <table style={{...tbl,fontSize:'11px'}}>
                    <thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>Кол-во</th><th style={tblH}>Цена</th><th style={tblH}>Сумма</th></tr></thead>
                    <tbody>
                      {items.map((item, index) => {
                        const rowSum = Number(item.total || 0) || Number((item.quantity || 0) * (item.price || 0));
                        return (
                          <tr key={index}>
                            <td style={tblC}>{item.name || ''}</td>
                            <td style={tblC}>{item.unit || ''}</td>
                            <td style={tblC}>{item.quantity || 0}</td>
                            <td style={tblC}>{Number(item.price || 0).toLocaleString('ru-RU')+' ₽'}</td>
                            <td style={tblC}>{rowSum.toLocaleString('ru-RU')+' ₽'}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
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
      })}

      {(invoices || []).length === 0 && <p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Накладных нет</p>}
    </div>
  );
}
