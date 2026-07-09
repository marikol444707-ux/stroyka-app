import React from 'react';
import { Check, ChevronDown, ChevronUp, Edit2, Link2, Plus, Search, Trash2, X } from 'lucide-react';
import { API } from '../api';
import { createSupplierForm, createSupplierInviteForm } from '../features/supply/supplyInitialForms';
import DocumentRecognitionPanel from './DocumentRecognitionPanel';
import {
  SOURCE_FILTERS,
  SUPPLIER_SOURCE_META,
  groupSuppliers,
  normalizeSupplierNameKey,
  sourceMeta,
  supplierNameDuplicateReason,
  supplierMatchesRecord,
  supplierSourceInfo,
  warehouseInvoiceDocumentKey,
} from '../utils/supplierUtils';

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

const compactText = value => String(value || '')
  .toLowerCase()
  .replace(/ё/g, 'е')
  .replace(/\s+/g, ' ')
  .trim();

const dedupeByDocumentKey = (rows, keyFn) => {
  const seen = new Map();
  const duplicates = [];
  (rows || []).forEach(row => {
    const key = keyFn(row);
    if (!key || !seen.has(key)) {
      seen.set(key || 'id:' + (row?.id || seen.size), row);
      return;
    }
    duplicates.push(row);
  });
  return { rows: Array.from(seen.values()), duplicates };
};

const supplierInvoiceKey = invoice => {
  const warehouseId = invoice?.warehouseInvoiceId || invoice?.warehouse_invoice_id;
  if (warehouseId) return 'supplier-warehouse:' + warehouseId;
  const number = compactText(invoice?.invoiceNumber || invoice?.invoice_number || invoice?.number);
  const date = String(invoice?.invoiceDate || invoice?.invoice_date || invoice?.createdAt || '').slice(0, 10);
  const supplier = normalizeSupplierNameKey(invoice?.supplierName || invoice?.supplier_name || invoice?.supplier || '');
  const project = compactText(invoice?.projectName || invoice?.project_name || '');
  const amount = toNumber(invoice?.amount || invoice?.totalAmount || invoice?.total_amount).toFixed(2);
  if (number) return ['supplier-number', number, date, supplier, project, amount].join('|');
  if (date && supplier && amount !== '0.00') return ['supplier-content', date, supplier, project, amount, compactText(invoice?.materialName || invoice?.description)].join('|');
  return invoice?.id ? 'supplier-id:' + invoice.id : '';
};

const deliveryKey = delivery => {
  const supplier = normalizeSupplierNameKey(delivery?.supplierName || delivery?.supplier_name || delivery?.supplier || '');
  const project = compactText(delivery?.project || delivery?.projectName || delivery?.project_name || '');
  const material = compactText(delivery?.materialName || delivery?.material_name || '');
  const date = String(delivery?.receivedAt || delivery?.shippedAt || delivery?.createdAt || '').slice(0, 10);
  const qty = toNumber(delivery?.receivedQuantity || delivery?.shippedQuantity || delivery?.plannedQuantity).toFixed(4);
  if (supplier || project || material) return ['delivery', supplier, project, material, date, qty].join('|');
  return delivery?.id ? 'delivery-id:' + delivery.id : '';
};

function SupplySuppliersPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnB,
  btnGr,
  btnR,
  user,
  users = [],
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
  fileSrc,
  uploadPhoto,
  supplierLinkFocus = null,
}) {
  const [openedSupplierId, setOpenedSupplierId] = React.useState(null);
  const [linkingSupplierId, setLinkingSupplierId] = React.useState(null);
  const [linkUserId, setLinkUserId] = React.useState('');
  const [linkUserEmail, setLinkUserEmail] = React.useState('');
  const [duplicateLinkingSupplierId, setDuplicateLinkingSupplierId] = React.useState(null);
  const [duplicateSupplierId, setDuplicateSupplierId] = React.useState('');
  const [sourceFilter, setSourceFilter] = React.useState('all');
  const [collapsedCategories, setCollapsedCategories] = React.useState(() => new Set());
  const canEditSuppliers = ['директор','зам_директора','кладовщик','снабженец'].includes(user?.role || '');
  const canLinkSupplierUsers = ['директор','зам_директора'].includes(user?.role || '');
  const supplierUsers = React.useMemo(
    () => (users || []).filter(item => item?.role === 'поставщик'),
    [users],
  );
  const toggleCategory = category => {
    setCollapsedCategories(prev => {
      const next = new Set(prev);
      if (next.has(category)) next.delete(category);
      else next.add(category);
      return next;
    });
  };
  const emptySupplier = createSupplierForm({
    inn:'',kpp:'',ogrn:'',legalAddress:'',actualAddress:'',bank:'',bik:'',account:'',korAccount:'',
    directorName:'',directorPosition:'',contractUrl:'',contractNumber:'',contractDate:'',licenseUrl:'',priceUrl:'',website:'',notes:''
  });
  const supplierValue = (supplier, camel, snake=camel) => supplier?.[camel] || supplier?.[snake] || '';
  const normalizeSupplierForEdit = (supplier={}) => ({
    ...emptySupplier,
    ...supplier,
    legalAddress: supplierValue(supplier, 'legalAddress', 'legal_address'),
    actualAddress: supplierValue(supplier, 'actualAddress', 'actual_address'),
    korAccount: supplierValue(supplier, 'korAccount', 'kor_account'),
    directorName: supplierValue(supplier, 'directorName', 'director_name'),
    directorPosition: supplierValue(supplier, 'directorPosition', 'director_position'),
    contractUrl: supplierValue(supplier, 'contractUrl', 'contract_url'),
    contractNumber: supplierValue(supplier, 'contractNumber', 'contract_number'),
    contractDate: String(supplierValue(supplier, 'contractDate', 'contract_date') || '').slice(0, 10),
    licenseUrl: supplierValue(supplier, 'licenseUrl', 'license_url'),
    priceUrl: supplierValue(supplier, 'priceUrl', 'price_url'),
    sourceType: supplierValue(supplier, 'sourceType', 'source_type') || 'manual',
    sourceDetail: supplierValue(supplier, 'sourceDetail', 'source_detail'),
  });
  const appendSupplierNote = (current, line) => {
    const base = String(current || '').trim();
    const addition = String(line || '').trim();
    if (!addition || base.includes(addition)) return base;
    return base ? base + '\n' + addition : addition;
  };
  const supplierPatchFromRecognition = (result, current={}) => {
    const extracted = result?.extracted || {};
    const doc = result?.suggestedCrmDocument || {};
    const contractLike = String(extracted.docType || doc.docType || '').toLowerCase().includes('договор');
    const patch = {
      inn: extracted.inn || '',
      kpp: extracted.kpp || '',
      ogrn: extracted.ogrn || '',
      legalAddress: extracted.legalAddress || '',
      bank: extracted.bank || '',
      bik: extracted.bik || '',
      account: extracted.bankAccount || '',
      korAccount: extracted.corrAccount || '',
      directorName: extracted.signerName || '',
      directorPosition: extracted.signerBasis || '',
      contractNumber: contractLike ? (extracted.number || '') : '',
      contractDate: contractLike ? (extracted.docDate || '') : '',
      contractUrl: contractLike ? (result?.fileUrl || '') : '',
      specialization: extracted.workType || '',
    };
    if (extracted.counterpartyName && !current.name) patch.name = extracted.counterpartyName;
    if (extracted.contractSubject) patch.notes = appendSupplierNote(current.notes, 'Предмет договора: ' + extracted.contractSubject);
    return Object.fromEntries(Object.entries(patch).filter(([, value]) => value));
  };
  const applySupplierRecognition = (result) => {
    setNewSupplier(prev => ({...prev, ...supplierPatchFromRecognition(result, prev)}));
  };
  const createSupplierDocumentFromRecognition = async (docPatch, result) => {
    const supplierId = editingItem?.id || newSupplier?.id;
    if (!supplierId) return alert('Сначала сохраните поставщика, затем добавьте документ');
    const extracted = result?.extracted || {};
    const payload = {
      supplierId,
      docType: docPatch.docType || extracted.docType || 'Другое',
      title: docPatch.title || extracted.documentTitle || 'Распознанный документ',
      fileUrl: docPatch.fileUrl || result?.fileUrl || '',
      status: 'На проверке',
      signedAt: extracted.docDate || '',
      notes: docPatch.notes || (extracted.contractSubject ? 'Предмет договора: ' + extracted.contractSubject : ''),
      uploadedBy: user?.name || '',
    };
    const res = await fetch(API + '/supplier-documents', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      return alert(data.detail || 'Не удалось добавить документ поставщика');
    }
    await loadAll();
  };

  const supplierGroups = React.useMemo(() => groupSuppliers(suppliers), [suppliers]);

  React.useEffect(() => {
    const focusedSupplierId = Number(supplierLinkFocus?.supplierId || 0);
    if (!focusedSupplierId) return;
    const focusedGroup = supplierGroups.find(supplier => (
      Number(supplier.id || 0) === focusedSupplierId
      || (supplier._supplierIds || []).some(id => Number(id || 0) === focusedSupplierId)
    ));
    if (!focusedGroup) return;
    setSourceFilter('all');
    setOpenedSupplierId(focusedGroup.id);
    setLinkingSupplierId(focusedGroup.id);
    setLinkUserId('');
    setLinkUserEmail(supplierLinkFocus.email || '');
    setCollapsedCategories(prev => {
      const next = new Set(prev);
      next.delete(focusedGroup.category || 'Прочее');
      return next;
    });
  }, [supplierLinkFocus, supplierGroups]);

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

  const supplierStats = React.useCallback(supplier => {
    const rawLinkedInvoices = (invoices || []).filter(invoice => supplierMatchesRecord(supplier, invoice));
    const rawLinkedSupplierInvoices = (supplierInvoices || []).filter(invoice => supplierMatchesRecord(supplier, invoice));
    const rawLinkedDeliveries = (supplyDeliveries || []).filter(delivery => supplierMatchesRecord(supplier, delivery));
    const invoiceDedupe = dedupeByDocumentKey(rawLinkedInvoices, warehouseInvoiceDocumentKey);
    const supplierInvoiceDedupe = dedupeByDocumentKey(rawLinkedSupplierInvoices, supplierInvoiceKey);
    const deliveryDedupe = dedupeByDocumentKey(rawLinkedDeliveries, deliveryKey);
    const linkedInvoices = invoiceDedupe.rows;
    const linkedSupplierInvoices = supplierInvoiceDedupe.rows;
    const linkedDeliveries = deliveryDedupe.rows;
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

    const countedWarehouseIds = new Set(linkedInvoices.map(invoice => String(invoice.id || '')).filter(Boolean));
    const countedDeliveryIds = new Set(linkedInvoices.map(invoice => String(invoice.supplyDeliveryId || invoice.supply_delivery_id || '')).filter(Boolean));
    const warehouseTotal = linkedInvoices.reduce((sum, invoice) => sum + (toNumber(invoice.totalWithVat) || invoiceItemsTotal(invoice)), 0);
    const supplierInvoiceTotal = linkedSupplierInvoices
      .filter(invoice => !countedWarehouseIds.has(String(invoice.warehouseInvoiceId || invoice.warehouse_invoice_id || '')))
      .reduce((sum, invoice) => sum + toNumber(invoice.amount || invoice.totalAmount), 0);
    const deliveriesTotal = linkedDeliveries
      .filter(delivery => !countedDeliveryIds.has(String(delivery.id || '')))
      .reduce((sum, delivery) => sum + toNumber(delivery.totalPrice), 0);
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
      documentCount: linkedInvoices.length + linkedSupplierInvoices.length + linkedDeliveries.length,
      duplicateDocumentsCount: invoiceDedupe.duplicates.length + supplierInvoiceDedupe.duplicates.length + deliveryDedupe.duplicates.length,
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
  }, [invoices, supplierInvoices, supplyDeliveries, supplierOffers, supplierCatalog]);

  const sourceMatches = React.useCallback(sourceInfo => (
    sourceFilter === 'all'
    || sourceInfo.filterTypes.includes(sourceFilter)
    || (sourceFilter === 'site' && sourceInfo.filterTypes.includes('crm'))
    || (sourceFilter === 'warehouse_invoice' && sourceInfo.filterTypes.includes('max_invoice'))
  ), [sourceFilter]);

  const supplierStatsById = React.useMemo(() => {
    const statsById = new Map();
    supplierGroups.forEach(supplier => {
      statsById.set(supplier.id, supplierStats(supplier));
    });
    return statsById;
  }, [supplierGroups, supplierStats]);

  const supplierRows = React.useMemo(() => (
    supplierGroups.map(supplier => {
      const stats = supplierStatsById.get(supplier.id) || {};
      return {
        supplier,
        stats,
        sourceInfo: supplierSourceInfo(supplier, stats),
      };
    })
  ), [supplierGroups, supplierStatsById]);

  const possibleDuplicateRowsById = React.useMemo(() => {
    const map = new Map();
    supplierRows.forEach(row => {
      const ownIds = new Set((row.supplier._supplierIds || [row.supplier.id]).map(id => String(id)));
      const candidates = supplierRows
        .filter(candidate => {
          if ((candidate.supplier._supplierIds || [candidate.supplier.id]).some(id => ownIds.has(String(id)))) return false;
          return Boolean(supplierNameDuplicateReason(row.supplier, candidate.supplier));
        })
        .slice(0, 5)
        .map(candidate => ({
          ...candidate,
          reason: supplierNameDuplicateReason(row.supplier, candidate.supplier),
        }));
      if (candidates.length > 0) map.set(row.supplier.id, candidates);
    });
    return map;
  }, [supplierRows]);

  const supplierRowsByCategory = React.useMemo(() => {
    const byCategory = new Map(categories.map(category => [category, []]));
    supplierRows.forEach(row => {
      const { supplier, stats, sourceInfo } = row;
      const category = supplier.category || 'Прочее';
      if (!sourceMatches(sourceInfo)) return;
      if (!matchSearch(listSearch, supplier.name, supplier.specialization, supplier.phone, supplier.email, sourceInfo.label, sourceInfo.detail, stats.searchText)) return;
      if (!byCategory.has(category)) byCategory.set(category, []);
      byCategory.get(category).push(row);
    });
    return byCategory;
  }, [categories, supplierRows, sourceMatches, listSearch, matchSearch]);

  const openInvite = () => {
    setSupplierInviteForm(createSupplierInviteForm());
    setGeneratedInviteLink(null);
    setShowSupplierInviteModal(true);
  };

  const openManualForm = () => {
    setShowForm(!showForm);
    setEditingItem(null);
    setNewSupplier(createSupplierForm(emptySupplier));
  };

  const editSupplier = (supplier, event) => {
    event?.stopPropagation();
    setEditingItem(supplier);
    setNewSupplier(normalizeSupplierForEdit(supplier));
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

  const openLinkSupplier = (supplier, event) => {
    event?.stopPropagation();
    setLinkingSupplierId(prev => (prev === supplier.id ? null : supplier.id));
    setLinkUserId('');
    setLinkUserEmail('');
  };

  const openDuplicateLinkSupplier = (supplier, event) => {
    event?.stopPropagation();
    setDuplicateLinkingSupplierId(prev => (prev === supplier.id ? null : supplier.id));
    setDuplicateSupplierId('');
  };

  const linkSupplierUser = async (supplier, event) => {
    event?.stopPropagation();
    if (!canLinkSupplierUsers) return;
    const payload = {
      userId: linkUserId || undefined,
      email: linkUserEmail.trim() || undefined,
    };
    if (!payload.userId && !payload.email) {
      alert('Выберите пользователя-поставщика или укажите email');
      return;
    }
    const res = await fetch(API + '/suppliers/' + supplier.id + '/link-user', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || 'Не удалось связать пользователя с поставщиком');
      return;
    }
    setLinkingSupplierId(null);
    setLinkUserId('');
    setLinkUserEmail('');
    await loadAll();
  };

  const linkDuplicateSupplier = async (supplier, event) => {
    event?.stopPropagation();
    if (!canLinkSupplierUsers) return;
    if (!duplicateSupplierId) {
      alert('Выберите карточку-дубль поставщика');
      return;
    }
    const res = await fetch(API + '/suppliers/' + supplier.id + '/link-duplicate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({duplicateSupplierId}),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.detail || data.error) {
      alert(data.detail || data.error || 'Не удалось связать дубль поставщика');
      return;
    }
    setDuplicateLinkingSupplierId(null);
    setDuplicateSupplierId('');
    await loadAll();
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
            <select value={newSupplier.sourceType || 'manual'} onChange={e=>setNewSupplier({...newSupplier,sourceType:e.target.value})} style={{...inp,marginBottom:0}}>
              {Object.entries(SUPPLIER_SOURCE_META).map(([value, meta])=><option key={value} value={value}>{meta.label}</option>)}
            </select>
            <input placeholder="Детали источника" value={newSupplier.sourceDetail || ''} onChange={e=>setNewSupplier({...newSupplier,sourceDetail:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="ИНН" value={newSupplier.inn || ''} onChange={e=>setNewSupplier({...newSupplier,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="КПП" value={newSupplier.kpp || ''} onChange={e=>setNewSupplier({...newSupplier,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="ОГРН / ОГРНИП" value={newSupplier.ogrn || ''} onChange={e=>setNewSupplier({...newSupplier,ogrn:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Банк" value={newSupplier.bank || ''} onChange={e=>setNewSupplier({...newSupplier,bank:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="БИК" value={newSupplier.bik || ''} onChange={e=>setNewSupplier({...newSupplier,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Расчетный счет" value={newSupplier.account || ''} onChange={e=>setNewSupplier({...newSupplier,account:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Корр. счет" value={newSupplier.korAccount || ''} onChange={e=>setNewSupplier({...newSupplier,korAccount:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Подписант / директор" value={newSupplier.directorName || ''} onChange={e=>setNewSupplier({...newSupplier,directorName:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Основание / должность" value={newSupplier.directorPosition || ''} onChange={e=>setNewSupplier({...newSupplier,directorPosition:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Номер договора" value={newSupplier.contractNumber || ''} onChange={e=>setNewSupplier({...newSupplier,contractNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input type="date" value={newSupplier.contractDate || ''} onChange={e=>setNewSupplier({...newSupplier,contractDate:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Юридический адрес" value={newSupplier.legalAddress || ''} onChange={e=>setNewSupplier({...newSupplier,legalAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'1 / -1'}}/>
            <textarea placeholder="Примечания / предмет договора" value={newSupplier.notes || ''} onChange={e=>setNewSupplier({...newSupplier,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'1 / -1',minHeight:'64px',resize:'vertical'}}/>
          </div>
          <DocumentRecognitionPanel
            C={C}
            card={card}
            inp={inp}
            btnG={btnG}
            btnO={btnO}
            btnB={btnB}
            uploadPhoto={uploadPhoto}
            fileSrc={fileSrc}
            projectName={newSupplier.name || 'Поставщик'}
            context="supplier-documents"
            entityType="supplier"
            currentFields={newSupplier}
            onApplyExtracted={applySupplierRecognition}
            applyExtractedLabel="Заполнить поставщика"
            onCreateRecognizedDocument={editingItem?.id ? createSupplierDocumentFromRecognition : null}
            createRecognizedDocumentLabel="Добавить в документы поставщика"
          />
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

      <div style={{display:'flex',gap:'6px',flexWrap:'wrap',marginBottom:'12px'}}>
        {SOURCE_FILTERS.map(filter=>(
          <button
            key={filter.id}
            onClick={()=>setSourceFilter(filter.id)}
            style={{
              border:'1px solid '+(sourceFilter===filter.id?C.accent:C.border),
              backgroundColor:sourceFilter===filter.id?C.accentLight:C.bg,
              color:sourceFilter===filter.id?C.accent:C.textSec,
              borderRadius:'999px',
              padding:'6px 10px',
              fontSize:'11px',
              fontWeight:'700',
              cursor:'pointer'
            }}
          >
            {filter.label}
          </button>
        ))}
      </div>

      {categories.map(category=>{
        const catSuppliers = supplierRowsByCategory.get(category) || [];
        if (catSuppliers.length===0) return null;
        const categoryCollapsed = collapsedCategories.has(category);
        return (
          <div key={category} style={{marginBottom:'20px'}}>
            <button onClick={()=>toggleCategory(category)} style={{width:'100%',display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,cursor:'pointer',textAlign:'left'}}>
              {categoryCollapsed ? <ChevronDown size={14} color={C.textSec}/> : <ChevronUp size={14} color={C.textSec}/>}
              <b style={{color:C.accent,fontSize:'13px'}}>{'🏭 '+category}</b>
              <span style={{color:C.textSec,fontSize:'12px'}}>{'('+catSuppliers.length+')'}</span>
            </button>
            {!categoryCollapsed && catSuppliers.map(({supplier, stats, sourceInfo})=>{
              const isOpen = openedSupplierId === supplier.id;
              const materialPreview = stats.materials.slice(0, 5);
              const primarySourceMeta = sourceMeta(sourceInfo.primary);
              const possibleDuplicates = possibleDuplicateRowsById.get(supplier.id) || [];
              return (
                <div key={supplier.id} onClick={()=>setOpenedSupplierId(isOpen ? null : supplier.id)} style={{...card,padding:'14px',marginBottom:'8px',marginLeft:'12px',cursor:'pointer',borderColor:isOpen?C.accent:C.border}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                    <div style={{flex:'1 1 280px',minWidth:0}}>
                      <div style={{display:'flex',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                        <b style={{color:C.text,fontSize:'13px',overflowWrap:'anywhere'}}>{supplier.name}</b>
                        <span title={sourceInfo.detail || sourceInfo.types.map(type => sourceMeta(type).label).join(', ')} style={{fontSize:'11px',fontWeight:'700',color:primarySourceMeta.color,padding:'2px 7px',borderRadius:'999px',backgroundColor:C.bg,border:'1px solid '+primarySourceMeta.color}}>{primarySourceMeta.label}</span>
                        {supplier._duplicateCount > 1 && <span style={{fontSize:'11px',fontWeight:'700',color:C.warning,padding:'2px 7px',borderRadius:'999px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder}}>дублей: {supplier._duplicateCount}</span>}
                        {possibleDuplicates.length > 0 && <span title="Похожие названия не объединяются автоматически. Проверьте и свяжите вручную, если это один поставщик." style={{fontSize:'11px',fontWeight:'700',color:C.warning,padding:'2px 7px',borderRadius:'999px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder}}>возможных дублей: {possibleDuplicates.length}</span>}
                        {stats.duplicateDocumentsCount > 0 && <span title="Повторные строки документов скрыты из суммы и счетчиков" style={{fontSize:'11px',fontWeight:'700',color:C.warning,padding:'2px 7px',borderRadius:'999px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder}}>дублей документов: {stats.duplicateDocumentsCount}</span>}
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
                          {canLinkSupplierUsers&&(
                            <button title="Связать кабинет поставщика" onClick={event=>openLinkSupplier(supplier, event)} style={{...btnB,padding:'5px 10px'}}><Link2 size={11}/></button>
                          )}
                          {canLinkSupplierUsers&&(
                            <button title="Связать дубль поставщика" onClick={event=>openDuplicateLinkSupplier(supplier, event)} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Link2 size={11}/>Дубль</button>
                          )}
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
                      {canLinkSupplierUsers && possibleDuplicates.length > 0 && (
                        <div onClick={event=>event.stopPropagation()} style={{padding:'10px',borderRadius:'8px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder,marginBottom:'10px'}}>
                          <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>⚠️ Возможные дубли</b>
                          <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 8px'}}>
                            Эти карточки похожи по названию, но не объединены автоматически. Если это один поставщик, подставьте карточку и подтвердите ручную связку.
                          </p>
                          <div style={{display:'grid',gap:'6px'}}>
                            {possibleDuplicates.map(({supplier: candidate, reason}) => (
                              <button
                                key={candidate.id}
                                onClick={event=>{
                                  event.stopPropagation();
                                  setDuplicateLinkingSupplierId(supplier.id);
                                  setDuplicateSupplierId(String(candidate.id));
                                }}
                                style={{...btnG,justifyContent:'space-between',padding:'8px 10px',fontSize:'11px'}}
                              >
                                <span style={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                                  {candidate.name || 'Без названия'}{candidate.inn ? ' · ИНН ' + candidate.inn : ''}
                                </span>
                                <span style={{color:C.textMuted}}>{reason}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                      {canLinkSupplierUsers && linkingSupplierId === supplier.id && (
                        <div onClick={event=>event.stopPropagation()} style={{padding:'10px',borderRadius:'8px',backgroundColor:C.infoLight,border:'1px solid '+C.infoBorder,marginBottom:'10px'}}>
                          <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>🔗 Связать кабинет поставщика</b>
                          <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 8px'}}>Используйте это, если поставщик уже зарегистрировался, но в кабинете не видит свою компанию, КП или накладные.</p>
                          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',alignItems:'center'}}>
                            <select value={linkUserId} onChange={event=>setLinkUserId(event.target.value)} style={{...inp,marginBottom:0}}>
                              <option value="">Пользователь с ролью поставщик</option>
                              {supplierUsers.map(item=>(
                                <option key={item.id} value={item.id}>{(item.name || item.email || 'Поставщик') + (item.email ? ' · ' + item.email : '')}</option>
                              ))}
                            </select>
                            <input placeholder="или email поставщика" value={linkUserEmail} onChange={event=>setLinkUserEmail(event.target.value)} style={{...inp,marginBottom:0}}/>
                            <button onClick={event=>linkSupplierUser(supplier, event)} style={{...btnB,padding:'9px 12px'}}><Link2 size={13}/>Связать</button>
                          </div>
                          {supplierUsers.length===0 && <p style={{color:C.warning,fontSize:'11px',margin:'8px 0 0'}}>Пользователи с ролью поставщик не загружены. Укажите email, под которым поставщик входит в кабинет.</p>}
                        </div>
                      )}
                      {canLinkSupplierUsers && duplicateLinkingSupplierId === supplier.id && (
                        <div onClick={event=>event.stopPropagation()} style={{padding:'10px',borderRadius:'8px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder,marginBottom:'10px'}}>
                          <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'6px'}}>🔗 Связать дубль поставщика</b>
                          <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 8px'}}>
                            Используйте, когда поставщик создан из накладной или старой карточки и не схлопнулся автоматически. Документы не переносятся: система добавит двустороннюю связь и будет читать обе карточки одной группой.
                          </p>
                          <div style={{display:'grid',gridTemplateColumns:'minmax(220px,1fr) auto',gap:'8px',alignItems:'center'}}>
                            <select value={duplicateSupplierId} onChange={event=>setDuplicateSupplierId(event.target.value)} style={{...inp,marginBottom:0}}>
                              <option value="">Карточка-дубль</option>
                              {supplierRows
                                .filter(row => !(supplier._supplierIds || [supplier.id]).map(id => String(id)).includes(String(row.supplier.id)))
                                .map(row => (
                                  <option key={row.supplier.id} value={row.supplier.id}>
                                    {row.supplier.name + (row.supplier.inn ? ' · ИНН ' + row.supplier.inn : '') + (row.supplier.email ? ' · ' + row.supplier.email : '')}
                                  </option>
                                ))}
                            </select>
                            <button onClick={event=>linkDuplicateSupplier(supplier, event)} style={{...btnB,padding:'9px 12px'}}><Link2 size={13}/>Связать дубль</button>
                          </div>
                        </div>
                      )}
                      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'8px',marginBottom:'10px'}}>
                        <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>Последняя операция</p><b style={{color:C.text,fontSize:'13px'}}>{formatShortDate(stats.lastDate)}</b></div>
                        <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>КП</p><b style={{color:C.text,fontSize:'13px'}}>{stats.offers.length}</b></div>
                        <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.bg,border:'1px solid '+C.border}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>Связано документов</p><b style={{color:C.text,fontSize:'13px'}}>{stats.documentCount}</b></div>
                        {stats.duplicateDocumentsCount > 0 && <div style={{padding:'10px',borderRadius:'8px',backgroundColor:C.warningLight,border:'1px solid '+C.warningBorder}}><p style={{color:C.textSec,fontSize:'11px',margin:'0 0 3px'}}>Скрыто дублей</p><b style={{color:C.warning,fontSize:'13px'}}>{stats.duplicateDocumentsCount}</b></div>}
                      </div>
                      <p style={{color:C.textSec,fontSize:'11px',margin:'0 0 10px'}}>Источник: <b style={{color:primarySourceMeta.color}}>{primarySourceMeta.label}</b>{sourceInfo.detail ? ' · ' + sourceInfo.detail : ''}</p>
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
