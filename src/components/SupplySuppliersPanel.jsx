import React from 'react';
import { Check, ChevronDown, ChevronUp, Edit2, Plus, Search, Trash2, X } from 'lucide-react';
import { API } from '../api';

const normalizeSupplierKey = value => String(value || '')
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/(?:,|\s)\s*(инн|кпп|огрн|огрнип|тел\.?|телефон|р\/с|расч[её]тн|адрес)\b.*$/g, ' ')
  .replace(/\b(инн|кпп|огрн|огрнип)\s*[:№#-]?\s*\d+\b/g, ' ')
  .replace(/\b(ооо|оао|ао|пао|зао|ип|индивидуальный предприниматель)\b/g, ' ')
  .replace(/[.,;:()«»"'`/\\]+/g, ' ')
  .replace(/\s+/g, ' ')
  .trim();

const supplierKeysMatch = (left, right) => {
  if (!left || !right) return false;
  if (left === right) return true;
  const short = left.length < right.length ? left : right;
  const long = left.length < right.length ? right : left;
  return short.length >= 6 && long.includes(short);
};

const toNumber = value => {
  const num = Number(value || 0);
  return Number.isFinite(num) ? num : 0;
};

const formatMoney = value => Math.round(toNumber(value)).toLocaleString('ru-RU') + ' ₽';

const formatShortDate = value => {
  if (!value) return 'без даты';
  const raw = String(value).slice(0, 10);
  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString('ru-RU');
};

const itemName = item => item?.materialName || item?.material_name || item?.name || '';

const invoiceItemsTotal = invoice => (invoice?.items || []).reduce((sum, item) => {
  const line = toNumber(item.lineTotal || item.line_total);
  return sum + (line > 0 ? line : toNumber(item.quantity) * toNumber(item.price));
}, 0);

function SupplySuppliersPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  btnR,
  user,
  suppliers,
  supplierCategories,
  showForm,
  setShowForm,
  editingItem,
  setEditingItem,
  newSupplier,
  setNewSupplier,
  saveSupplier,
  deleteSupplier,
  listSearch,
  setListSearch,
  matchSearch,
  setSupplierInviteForm,
  setGeneratedInviteLink,
  setShowSupplierInviteModal,
  loadAll,
  supplierInvoices = [],
  supplierOffers = [],
  supplyDeliveries = [],
  invoices = [],
  supplierCatalog = [],
}) {
  const [openedSupplierId, setOpenedSupplierId] = React.useState(null);
  const canEditSuppliers = ['директор','зам_директора','кладовщик','снабженец'].includes(user.role);
  const emptySupplier = {name:'',phone:'',email:'',specialization:'',category:'Сыпучие и бетон',rating:5.0,status:'Активный'};

  const supplierGroups = React.useMemo(() => {
    const groups = new Map();
    (suppliers || []).forEach(supplier => {
      const key = normalizeSupplierKey(supplier.name) || ('id:' + supplier.id);
      if (!groups.has(key)) {
        groups.set(key, {
          ...supplier,
          category: supplier.category || 'Прочее',
          _supplierIds: [supplier.id],
          _supplierKeys: [key],
          _supplierNames: [supplier.name || ''],
          _duplicateCount: 1,
        });
        return;
      }
      const group = groups.get(key);
      group._supplierIds.push(supplier.id);
      group._supplierNames.push(supplier.name || '');
      group._duplicateCount += 1;
      if (!group.phone && supplier.phone) group.phone = supplier.phone;
      if (!group.email && supplier.email) group.email = supplier.email;
      if (!group.specialization && supplier.specialization) group.specialization = supplier.specialization;
      if ((!group.category || group.category === 'Прочее') && supplier.category) group.category = supplier.category;
      if (!group.status && supplier.status) group.status = supplier.status;
      group.rating = Math.max(toNumber(group.rating), toNumber(supplier.rating));
    });
    return Array.from(groups.values()).sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'ru'));
  }, [suppliers]);

  const categories = React.useMemo(() => {
    const seen = new Set();
    return [...(supplierCategories || []), ...supplierGroups.map(supplier => supplier.category || 'Прочее')]
      .filter(category => {
        const key = category || 'Прочее';
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      });
  }, [supplierCategories, supplierGroups]);

  const supplierMatchesRecord = (supplier, record) => {
    const ids = new Set((supplier._supplierIds || []).map(id => Number(id)).filter(Boolean));
    const recordId = Number(record?.supplierId || record?.supplier_id || 0);
    if (recordId && ids.has(recordId)) return true;
    const key = normalizeSupplierKey(record?.supplierName || record?.supplier_name || record?.supplier || '');
    return key && (supplier._supplierKeys || []).some(supplierKey => supplierKeysMatch(supplierKey, key));
  };

  const supplierStats = supplier => {
    const linkedInvoices = (invoices || []).filter(invoice => supplierMatchesRecord(supplier, invoice));
    const linkedSupplierInvoices = (supplierInvoices || []).filter(invoice => supplierMatchesRecord(supplier, invoice));
    const linkedDeliveries = (supplyDeliveries || []).filter(delivery => supplierMatchesRecord(supplier, delivery));
    const linkedOffers = (supplierOffers || []).filter(offer => (supplier._supplierIds || []).map(String).includes(String(offer.supplierId || offer.supplier_id || '')));
    const linkedCatalog = (supplierCatalog || []).filter(item => supplierMatchesRecord(supplier, item));
    const materialNames = new Set();

    linkedInvoices.forEach(invoice => (invoice.items || []).forEach(item => {
      const name = itemName(item);
      if (name) materialNames.add(name);
    }));
    linkedSupplierInvoices.forEach(invoice => {
      if (invoice.materialName) materialNames.add(invoice.materialName);
      if (invoice.description) materialNames.add(invoice.description);
    });
    linkedDeliveries.forEach(delivery => {
      if (delivery.materialName) materialNames.add(delivery.materialName);
    });
    linkedCatalog.forEach(item => {
      if (item.materialName) materialNames.add(item.materialName);
    });

    const warehouseTotal = linkedInvoices.reduce((sum, invoice) => sum + (toNumber(invoice.totalWithVat) || invoiceItemsTotal(invoice)), 0);
    const supplierInvoiceTotal = linkedSupplierInvoices.reduce((sum, invoice) => sum + toNumber(invoice.amount || invoice.totalAmount), 0);
    const deliveriesTotal = linkedDeliveries.reduce((sum, delivery) => sum + toNumber(delivery.totalPrice), 0);
    const allDates = [
      ...linkedInvoices.map(invoice => invoice.date || invoice.createdAt),
      ...linkedSupplierInvoices.map(invoice => invoice.invoiceDate || invoice.createdAt),
      ...linkedDeliveries.map(delivery => delivery.receivedAt || delivery.shippedAt || delivery.createdAt),
    ].filter(Boolean).sort();
    const materials = Array.from(materialNames).filter(Boolean);
    const recent = [
      ...linkedInvoices.map(invoice => ({
        type: 'Складская накладная',
        title: '№ ' + (invoice.number || invoice.id || 'без номера'),
        date: invoice.date || invoice.createdAt,
        details: (invoice.project || invoice.location || 'без объекта') + ' · ' + formatMoney(invoice.totalWithVat || invoiceItemsTotal(invoice)),
      })),
      ...linkedSupplierInvoices.map(invoice => ({
        type: 'Счёт поставщика',
        title: '№ ' + (invoice.invoiceNumber || invoice.id || 'без номера'),
        date: invoice.invoiceDate || invoice.createdAt,
        details: (invoice.projectName || 'без объекта') + ' · ' + formatMoney(invoice.amount || invoice.totalAmount) + ' · ' + (invoice.status || 'статус не указан'),
      })),
      ...linkedDeliveries.map(delivery => ({
        type: 'Поставка',
        title: delivery.materialName || 'материал не указан',
        date: delivery.receivedAt || delivery.shippedAt || delivery.createdAt,
        details: (delivery.project || 'без объекта') + ' · ' + (delivery.receivedQuantity || delivery.shippedQuantity || delivery.plannedQuantity || 0) + ' ' + (delivery.unit || '') + ' · ' + (delivery.status || 'статус не указан'),
      })),
    ].sort((a, b) => String(b.date || '').localeCompare(String(a.date || ''))).slice(0, 8);

    return {
      warehouseInvoices: linkedInvoices,
      supplierInvoices: linkedSupplierInvoices,
      deliveries: linkedDeliveries,
      offers: linkedOffers,
      catalog: linkedCatalog,
      materials,
      recent,
      total: warehouseTotal + supplierInvoiceTotal + deliveriesTotal,
      lastDate: allDates.length ? allDates[allDates.length - 1] : '',
      searchText: [
        ...materials,
        ...linkedInvoices.map(invoice => invoice.number),
        ...linkedSupplierInvoices.map(invoice => invoice.invoiceNumber),
        ...linkedDeliveries.map(delivery => delivery.project),
        ...linkedCatalog.map(item => item.materialName),
      ].join(' '),
    };
  };

  const openInvite = () => {
    setSupplierInviteForm({presetName:'',presetCategory:'Сыпучие и бетон',supplierId:null,expiresInDays:14});
    setGeneratedInviteLink(null);
    setShowSupplierInviteModal(true);
  };

  const openManualForm = () => {
    setShowForm(!showForm);
    setEditingItem(null);
    setNewSupplier({...emptySupplier});
  };

  const editSupplier = (supplier, event) => {
    event?.stopPropagation();
    setEditingItem(supplier);
    setNewSupplier({...supplier});
    setShowForm(true);
  };

  const updateRating = async (supplier, rating, event) => {
    event?.stopPropagation();
    if (!canEditSuppliers) return;
    await fetch(API+'/suppliers/'+supplier.id,{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...supplier,rating}),
    });
    await loadAll();
  };

  const handleDeleteSupplier = (supplier, event) => {
    event?.stopPropagation();
    deleteSupplier(supplier.id);
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',gap:'8px',flexWrap:'wrap'}}>
        <div>
          <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🚚 Поставщики</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>Единая карточка поставщика: счета, поставки, складские накладные и каталог в одном месте.</p>
        </div>
        {canEditSuppliers&&(
          <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
            <button onClick={openInvite} style={btnGr}><Plus size={14}/>🔗 Пригласить по ссылке</button>
            <button onClick={openManualForm} style={btnO}><Plus size={14}/>Добавить вручную</button>
          </div>
        )}
      </div>

      {showForm&&canEditSuppliers&&(
        <div style={{...card,padding:'20px',marginBottom:'16px'}}>
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(190px,1fr))',gap:'10px'}}>
            <input placeholder="Название *" value={newSupplier.name} onChange={e=>setNewSupplier({...newSupplier,name:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Телефон" value={newSupplier.phone} onChange={e=>setNewSupplier({...newSupplier,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Email" value={newSupplier.email} onChange={e=>setNewSupplier({...newSupplier,email:e.target.value})} style={{...inp,marginBottom:0}}/>
            <select value={newSupplier.category} onChange={e=>setNewSupplier({...newSupplier,category:e.target.value})} style={{...inp,marginBottom:0}}>
              {supplierCategories.map(category=><option key={category}>{category}</option>)}
            </select>
            <input placeholder="Специализация" value={newSupplier.specialization} onChange={e=>setNewSupplier({...newSupplier,specialization:e.target.value})} style={{...inp,marginBottom:0}}/>
            <select value={newSupplier.status} onChange={e=>setNewSupplier({...newSupplier,status:e.target.value})} style={{...inp,marginBottom:0}}>
              {['Активный','Неактивный','Заблокирован'].map(status=><option key={status}>{status}</option>)}
            </select>
          </div>
          <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
            <button onClick={saveSupplier} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
            <button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button>
          </div>
        </div>
      )}

      <div style={{position:'relative',marginBottom:'12px'}}>
        <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
        <input placeholder='🔍 Поиск поставщика, материала, счёта или объекта' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px'}}/>
      </div>

      {categories.map(category=>{
        const catSuppliers = supplierGroups.filter(supplier => {
          const stats = supplierStats(supplier);
          return (supplier.category || 'Прочее') === category && matchSearch(listSearch, supplier.name, supplier.specialization, supplier.phone, supplier.email, stats.searchText);
        });
        if (catSuppliers.length===0) return null;
        return (
          <div key={category} style={{marginBottom:'20px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
              <b style={{color:C.accent,fontSize:'13px'}}>{'🏭 '+category}</b>
              <span style={{color:C.textSec,fontSize:'12px'}}>{'('+catSuppliers.length+')'}</span>
            </div>
            {catSuppliers.map(supplier=>{
              const stats = supplierStats(supplier);
              const isOpen = openedSupplierId === supplier.id;
              const materialPreview = stats.materials.slice(0, 5);
              return (
                <div key={supplier.id} onClick={()=>setOpenedSupplierId(isOpen ? null : supplier.id)} style={{...card,padding:'14px',marginBottom:'8px',marginLeft:'12px',cursor:'pointer',borderColor:isOpen?C.accent:C.border}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                    <div style={{flex:'1 1 280px',minWidth:0}}>
                      <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                        <b style={{color:C.text,fontSize:'13px',overflowWrap:'anywhere'}}>{supplier.name}</b>
                        {supplier._duplicateCount > 1 && <span style={{fontSize:'11px',fontWeight:'700',color:C.warning,padding:'2px 7px',borderRadius:'999px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder}}>дублей: {supplier._duplicateCount}</span>}
                        {isOpen ? <ChevronUp size={14} color={C.textSec}/> : <ChevronDown size={14} color={C.textSec}/>}
                      </div>
                      <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{supplier.phone+(supplier.email?' · '+supplier.email:'')+(supplier.specialization?' · '+supplier.specialization:'')}</p>
                      <div style={{display:'flex',gap:'4px',marginTop:'4px'}}>
                        {[1,2,3,4,5].map(star=>(
                          <span key={star} style={{color:star<=toNumber(supplier.rating)?'#f59e0b':'#d1d5db',fontSize:'14px',cursor:canEditSuppliers?'pointer':'default'}} onClick={event=>updateRating(supplier, star, event)}>★</span>
                        ))}
                      </div>
                    </div>

                    <div style={{display:'flex',gap:'8px',alignItems:'center',flexWrap:'wrap',justifyContent:'flex-end'}}>
                      <span style={{color:C.textSec,fontSize:'11px'}}>Счета: <b style={{color:C.text}}>{stats.supplierInvoices.length}</b></span>
                      <span style={{color:C.textSec,fontSize:'11px'}}>Поставки: <b style={{color:C.text}}>{stats.deliveries.length}</b></span>
                      <span style={{color:C.textSec,fontSize:'11px'}}>Накладные: <b style={{color:C.text}}>{stats.warehouseInvoices.length}</b></span>
                      <span style={{color:C.textSec,fontSize:'11px'}}>Каталог: <b style={{color:C.text}}>{stats.catalog.length}</b></span>
                      {stats.total > 0 && <span style={{fontSize:'11px',fontWeight:'700',color:C.success,padding:'3px 8px',borderRadius:'999px',backgroundColor:C.successLight,border:'1px solid '+C.successBorder}}>{formatMoney(stats.total)}</span>}
                      {canEditSuppliers&&(
                        <div style={{display:'flex',gap:'6px'}}>
                          <button onClick={event=>editSupplier(supplier, event)} style={{...btnG,padding:'5px 10px'}}><Edit2 size={11}/></button>
                          <button onClick={event=>handleDeleteSupplier(supplier, event)} style={{...btnR,padding:'5px 10px'}}><Trash2 size={11}/></button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginTop:'8px'}}>
                    {materialPreview.length > 0 ? materialPreview.map(name=>(
                      <span key={name} style={{fontSize:'11px',color:C.textSec,padding:'3px 8px',borderRadius:'999px',backgroundColor:C.bg,border:'1px solid '+C.border,maxWidth:'260px',overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}} title={name}>{name}</span>
                    )) : <span style={{fontSize:'11px',color:C.textMuted}}>Поставки и материалы пока не привязаны</span>}
                    {stats.materials.length > materialPreview.length && <span style={{fontSize:'11px',color:C.textMuted}}>+{stats.materials.length - materialPreview.length}</span>}
                  </div>

                  {isOpen && (
                    <div style={{marginTop:'12px',paddingTop:'12px',borderTop:'1px solid '+C.border}}>
                      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'8px',marginBottom:'10px'}}>
                        <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>Последняя операция</p><b style={{color:C.text,fontSize:'13px'}}>{formatShortDate(stats.lastDate)}</b></div>
                        <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>КП</p><b style={{color:C.text,fontSize:'13px'}}>{stats.offers.length}</b></div>
                        <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>Связано документов</p><b style={{color:C.text,fontSize:'13px'}}>{stats.recent.length}</b></div>
                      </div>
                      {stats.recent.length > 0 ? stats.recent.map((doc, index)=>(
                        <div key={doc.type + doc.title + index} style={{padding:'9px 0',borderTop:index===0?'none':'1px solid '+C.border}}>
                          <div style={{display:'flex',justifyContent:'space-between',gap:'8px',flexWrap:'wrap'}}>
                            <b style={{color:C.text,fontSize:'12px'}}>{doc.type} · {doc.title}</b>
                            <span style={{color:C.textMuted,fontSize:'11px'}}>{formatShortDate(doc.date)}</span>
                          </div>
                          <p style={{color:C.textSec,fontSize:'11px',margin:'3px 0 0'}}>{doc.details}</p>
                        </div>
                      )) : (
                        <p style={{color:C.textMuted,fontSize:'12px',margin:'0'}}>История пока пустая. После счёта, поставки или складской накладной она появится здесь.</p>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        );
      })}

      {supplierGroups.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Поставщиков нет</p>}
    </div>
  );
}

export default SupplySuppliersPanel;
