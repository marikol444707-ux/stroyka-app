import SupplyFileLink from './SupplyFileLink';
import SupplierAttachmentInput from './SupplierAttachmentInput';
import { supplierOrders } from './supplierOrderProjection';
import { createShipmentForm } from './supplyInitialForms';
import { supplierPublicRequisites } from './supplierPublicRequisites';
import React, {useCallback, useState} from 'react';
import SupplierRequestRegistry from './SupplierRequestRegistry';
import SupplierOrders from './SupplierOrders';
import SupplierTeam from './SupplierTeam';
import SupplierCustomers from './SupplierCustomers';
import useSupplierRequestSelection from './useSupplierRequestSelection';
import SupplyClaims from './SupplyClaims';
import SupplierCatalogImport from './SupplierCatalogImport';
import useSupplierCatalogActions from './useSupplierCatalogActions';
import useSupplierQuoteResponse from './useSupplierQuoteResponse';
import { Check, Edit2, Plus, Trash2, X } from 'lucide-react';
import DocumentRecognitionPanel from '../../components/DocumentRecognitionPanel';
import { groupSuppliers, normalizeSupplierPayload, supplierIdentityKeys } from '../../utils/supplierUtils';
import { createSupplierPortalActions } from './supplierPortalActions';

const normalizeSupplierIdentity = value => String(value || '')
  .toLowerCase()
  .replace(/["'«»„“”]/g, '')
  .replace(/\b(ооо|оао|ао|ип|зао|пао|общество|с ограниченной|ответственностью)\b/g, ' ')
  .replace(/[^а-яa-z0-9]+/gi, ' ')
  .replace(/\s+/g, ' ')
  .trim();

function readOfferItems(offer) {
  try {
    const items = typeof offer.itemsKpJson === 'string' ? JSON.parse(offer.itemsKpJson) : offer.itemsKpJson;
    return Array.isArray(items) ? items : [];
  } catch { return []; }
}

export default function SupplierCabinetPage({
  API,
  C,
  UNITS,
  badge,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnR,
  card,
  createInvoiceFromOffer,
  createShipmentFromOffer,
  fileSrc,
  handleLogout,
  inp,
  invoices = [],
  inboxState,
  teamContext,
  invoicingOfferId,
  newCatalogItem,
  newKpResponse,
  newOfferInvoice,
  notify,
  parseSupplyItems,
  refreshData,
  respondingOfferId,
  setInvoicingOfferId,
  setNewCatalogItem,
  setNewKpResponse,
  setNewOfferInvoice,
  setRespondingOfferId,
  setShipmentForm,
  setShippingOfferId,
  setShowCatalogForm,
  setSupplierCatalog,
  setSupplierRequisites,
  setSupplierTab,
  shipmentForm,
  shippingOfferId,
  showCatalogForm,
  supplierCatalog,
  supplierInvoices,
  supplierOffers,
  supplierRequisites,
  supplierTab,
  suppliers,
  supplyClaims,
  supplyDeliveries,
  supplyRequests,
  tbl,
  tblC,
  tblH,
  uploadPhoto,
  user,
}) {
  const [activeUploads, setActiveUploads] = useState(() => new Set());
  const attachmentBusy = activeUploads.size > 0;
  const setAttachmentBusy = useCallback((busy, key) => setActiveUploads(current => {
    const next = new Set(current);
    if (busy) next.add(key); else next.delete(key);
    return next;
  }), []);
  const [selectedRequestId, selectRequest] = useSupplierRequestSelection();
    const requestDetailRef = React.useRef(null);
    const shipmentLock = React.useRef(false);
    const [shipmentBusy, setShipmentBusy] = React.useState(false);
    const sendShipment = async offer => {
      if (shipmentLock.current) return;
      shipmentLock.current = true;
      setShipmentBusy(true);
      try {
        if (await createShipmentFromOffer(offer)) await inboxState?.reload();
      } finally {
        shipmentLock.current = false;
        setShipmentBusy(false);
      }
    };
    React.useEffect(() => { if (selectedRequestId) requestDetailRef.current?.scrollIntoView?.({block:'start'}); }, [selectedRequestId, inboxState?.status]);
    const currentUserId = user?.id || user?.userId || user?.user_id || '';
    const quoteResponse = useSupplierQuoteResponse({
      API, actorId: `${currentUserId}:${user?.role || ''}`, offerId: respondingOfferId,
      onSaved: async () => {
        setRespondingOfferId(null);
        notify('КП отправлено директору', 'supply');
        await refreshData();
      },
    });
    const currentUserEmail = String(user?.email || '').toLowerCase();
    const currentUserName = normalizeSupplierIdentity(user?.name);
    const isSupplierRole = (user?.role || '') === 'поставщик';
    const supplierOffersList = Array.isArray(supplierOffers) ? supplierOffers : [];
    const supplierOfferFallback = supplierOffersList.find(offer => (
      offer?.supplierName || offer?.supplier_name || offer?.supplier || offer?.supplierId || offer?.supplier_id
    )) || null;
    const supplierOfferFallbackName = supplierOfferFallback
      ? (supplierOfferFallback.supplierName || supplierOfferFallback.supplier_name || supplierOfferFallback.supplier || '')
      : '';
    const supplierOfferFallbackId = supplierOfferFallback
      ? (supplierOfferFallback.supplierId || supplierOfferFallback.supplier_id || 0)
      : 0;
    const currentUserKeys = supplierIdentityKeys({
      name: user?.name || '',
      email: user?.email || '',
      phone: user?.phone || '',
    });
    const supplierGroups = groupSuppliers(suppliers || []);
    const matchesCurrentUser = supplier => {
      const supplierUserId = supplier.userId || supplier.user_id || '';
      const supplierEmail = String(supplier.email || supplier.supplierEmail || supplier.supplier_email || '').toLowerCase();
      const identityKeys = supplier._supplierIdentityKeys || supplierIdentityKeys(supplier);
      return (supplierUserId && currentUserId && String(supplierUserId) === String(currentUserId))
        || (supplierEmail && currentUserEmail && supplierEmail === currentUserEmail)
        || (normalizeSupplierIdentity(supplier.name) && normalizeSupplierIdentity(supplier.name) === currentUserName)
        || currentUserKeys.some(key => identityKeys.includes(key));
    };
    const mySupplier = supplierGroups.find(matchesCurrentUser) || (supplierGroups.length === 1 ? supplierGroups[0] : null);
    const verifiedTeam = teamContext?.suppliers || [];
    const teamLeader = verifiedTeam.some(s => s.role === 'leader');
    const managerOnly = Boolean(teamContext && teamContext.status !== 'legacy' && !teamLeader);
    const supplierAccountUnlinked = isSupplierRole && !mySupplier && !verifiedTeam.length;
    const mySupplierIds = new Set((mySupplier?._supplierIds || [mySupplier?.id]).filter(Boolean).map(id => String(id)));
    const mySupplierNames = new Set([
      ...(mySupplier?._supplierNames || []),
      mySupplier?.name || '',
      supplierOfferFallbackName || '',
      user?.name || '',
    ].map(normalizeSupplierIdentity).filter(Boolean));
    const isMySupplierId = value => value !== undefined && value !== null && value !== '' && mySupplierIds.has(String(value));
    const isMySupplierName = value => {
      const key = normalizeSupplierIdentity(value);
      if (!key) return false;
      if (mySupplierNames.has(key)) return true;
      return Array.from(mySupplierNames).some(nameKey => nameKey.length >= 4 && (nameKey.includes(key) || key.includes(nameKey)));
    };
    const belongsToMySupplier = row => (
      isMySupplierId(row?.supplierId || row?.supplier_id)
      || isMySupplierName(row?.supplierName || row?.supplier_name || row?.supplier || row?.name)
    );
    const myPrimarySupplierId = mySupplier?._supplierIds?.[0] || mySupplier?.id || supplierOfferFallbackId || 0;
    const catalogMutationLock = React.useRef(false);
    const catalogActions = useSupplierCatalogActions({ API, actorId: currentUserId,
      supplierId: myPrimarySupplierId, supplierName: user?.name, setCatalog: setSupplierCatalog, mutationLock: catalogMutationLock,
      onCreated: () => {
        setNewCatalogItem({materialName:'',unit:'шт',price:'',minQuantity:'1',deliveryDays:'3',notes:''});
        setShowCatalogForm(false);
      },
    });
    const myCatalog = isSupplierRole ? (supplierCatalog || []) : (supplierCatalog || []).filter(belongsToMySupplier);
    const myOffers = isSupplierRole ? supplierOffersList : supplierOffersList.filter(belongsToMySupplier);
    const mySupplierInvoices = isSupplierRole ? (supplierInvoices || []) : (supplierInvoices || []).filter(inv => belongsToMySupplier(inv) || isMySupplierName(inv.supplierName || user.name));
    const myDeliveries = isSupplierRole ? (supplyDeliveries || []) : (supplyDeliveries || []).filter(d => belongsToMySupplier(d) || isMySupplierName(d.supplierName || user.name));
    const myClaims = isSupplierRole ? (supplyClaims || []) : (supplyClaims || []).filter(belongsToMySupplier);
    const pendingOfferCount = myOffers.filter(o => o.status === 'Ожидает ответа').length;
    const approvedOfferCount = myOffers.filter(o => o.status === 'Утверждено').length;
    const supplierCardRequisites = React.useMemo(() => {
      if (!mySupplier) return null;
      const supplier = normalizeSupplierPayload(mySupplier);
      return {
        companyName: supplier.name || '',
        inn: supplier.inn || '',
        kpp: supplier.kpp || '',
        ogrn: supplier.ogrn || '',
        address: supplier.legalAddress || '',
        actualAddress: supplier.actualAddress || '',
        bank: supplier.bank || '',
        bik: supplier.bik || '',
        account: supplier.account || '',
        korAccount: supplier.korAccount || '',
        directorName: supplier.directorName || '',
        directorPosition: supplier.directorPosition || '',
        contractUrl: supplier.contractUrl || '',
        contractNumber: supplier.contractNumber || '',
        contractDate: supplier.contractDate || '',
        licenseUrl: supplier.licenseUrl || '',
        priceUrl: supplier.priceUrl || '',
        website: supplier.website || '',
        notes: supplier.notes || '',
        phone: supplier.phone || '',
        email: supplier.email || '',
        specialization: supplier.specialization || '',
      };
    }, [mySupplier]);
    React.useEffect(() => {
      if (!mySupplier?.id || !supplierCardRequisites) return;
      const supplierCardId = String(mySupplier.id);
      setSupplierRequisites(prev => {
        if (String(prev?._supplierCardId || '') === supplierCardId) return prev;
        const next = {...prev};
        Object.entries(supplierCardRequisites).forEach(([key, value]) => {
          if ((next[key] === undefined || next[key] === null || next[key] === '') && value) {
            next[key] = value;
          }
        });
        next._supplierCardId = supplierCardId;
        return next;
      });
    }, [mySupplier?.id, supplierCardRequisites, setSupplierRequisites]);
    const supplierDisplayName = verifiedTeam.map(s => s.name).join(', ') || mySupplier?.name || supplierRequisites.companyName || supplierOfferFallbackName || user?.name || 'Поставщик';
    const supplierHeaderMeta = [
      user?.name && user.name !== supplierDisplayName ? user.name : '',
      mySupplier?._duplicateCount > 1 ? 'связанных карточек: ' + mySupplier._duplicateCount : '',
      !mySupplier && supplierOffersList.length > 0 ? 'КП получены, карточку нужно связать' : '',
    ].filter(Boolean).join(' · ');
    const supplierInvoiceWarehouseId = inv => inv?.warehouseInvoiceId || inv?.warehouse_invoice_id || '';
    const warehouseInvoiceForSupplierInvoice = inv => (invoices || []).find(row => (
      String(row.id || '') === String(supplierInvoiceWarehouseId(inv))
      || String(row.supplierInvoiceId || row.supplier_invoice_id || '') === String(inv?.id || '')
    ));
    const warehouseInvoiceNumberForSupplierInvoice = (inv, linkedWarehouseInvoice = null) => (
      inv?.warehouseInvoiceNumber
      || inv?.warehouse_invoice_number
      || linkedWarehouseInvoice?.number
      || ''
    );
    const warehouseInvoiceDateForSupplierInvoice = (inv, linkedWarehouseInvoice = null) => (
      inv?.warehouseInvoiceDate
      || inv?.warehouse_invoice_date
      || linkedWarehouseInvoice?.date
      || ''
    );
    const warehouseInvoicePhotoForSupplierInvoice = (inv, linkedWarehouseInvoice = null) => (
      inv?.warehouseInvoicePhotoUrl
      || inv?.warehouse_invoice_photo_url
      || linkedWarehouseInvoice?.photoUrl
      || linkedWarehouseInvoice?.photo_url
      || ''
    );
    const deliveryForSupplierInvoice = (inv, warehouseInvoice = null) => {
      if (inv?.deliveryId || inv?.deliveryStatus || inv?.receivedQuantity) {
        return {
          id: inv.deliveryId,
          status: inv.deliveryStatus || '—',
          receivedQuantity: inv.receivedQuantity || 0,
          unit: inv.deliveryUnit || '',
          receivedAt: inv.receivedAt || '',
          receivedBy: inv.receivedBy || '',
          waybillNumber: inv.waybillNumber || '',
        };
      }
      const invoiceOfferId = inv?.offerId || inv?.offer_id || '';
      const invoiceRequestId = inv?.requestId || inv?.request_id || '';
      const warehouseDeliveryId = warehouseInvoice?.supplyDeliveryId || warehouseInvoice?.supply_delivery_id || '';
      return myDeliveries.find(delivery => (
        (warehouseDeliveryId && String(delivery.id || '') === String(warehouseDeliveryId))
        || (invoiceOfferId && String(delivery.offerId || delivery.offer_id || '') === String(invoiceOfferId))
        || (invoiceRequestId && String(delivery.requestId || delivery.request_id || '') === String(invoiceRequestId))
      ));
    };
    const SUPPLIER_TABS = [{id:'requests',label:'📋 Заявки'},{id:'orders',label:'📦 Заказы'},{id:'customers',label:'🏢 Заказчики'},{id:'catalog',label:'📦 Мой каталог'},{id:'offers',label:'💰 Предложения'},{id:'deliveries',label:'🚚 Отгрузки'},{id:'documents',label:'📄 Счета и накладные'},{id:'claims',label:'⚠️ Претензии'},{id:'profile',label:'⚙️ Профиль'}, ...(teamLeader ? [{id:'team',label:'👥 Команда'}] : [])].filter(t => !managerOnly || !['profile','catalog'].includes(t.id));
    const supplierOfferStatusStyle = (status) => {
      if (status === 'Утверждено') return {label:'Утверждено', color:C.success, bg:C.successLight};
      if (status === 'Получено') return {label:'Отправлено', color:C.info, bg:C.infoLight};
      if (status === 'Отозвано') return {label:'Отозвано', color:C.textMuted, bg:C.bgCard};
      if (status === 'Отклонено') return {label:'Отклонено', color:C.danger, bg:C.dangerLight};
      return {label:status || 'Ожидает', color:C.warning, bg:C.warningLight};
    };
    const {
      createOwnSupplierDocumentFromRecognition,
      supplierRequisitesPatchFromRecognition,
    } = createSupplierPortalActions({
      API,
      mySupplier,
      refreshData,
      user,
    });
    const withdrawOwnOffer = async (offer, label) => {
      if (!window.confirm(label)) return;
      const res = await fetch(API + '/supplier-offers/' + offer.id, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: 'withdraw' }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || data.detail || data.error) {
        alert('Не удалось отозвать КП: ' + (data.detail || data.error || res.status));
        return;
      }
      notify('КП отозвано', 'supply');
      await refreshData();
    };
    return (
      <div style={{minHeight:'100vh',backgroundColor:C.bg,padding:'20px'}}>
        <div className="supplier-workspace">
          <nav className="supplier-workspace-nav" aria-label="Кабинет поставщика">
            <strong>СТРОЙКА</strong>
            {SUPPLIER_TABS.map(t=><button key={t.id} type="button" aria-current={supplierTab===t.id?'page':undefined} onClick={()=>setSupplierTab(t.id)}>{t.label}</button>)}
          </nav>
          <main className="supplier-workspace-main">
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'16px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'12px'}}>
              <span style={{fontSize:'28px'}}>🏭</span>
              <div>
                <b style={{color:C.text,fontSize:'18px',display:'block'}}>Кабинет поставщика</b>
                <p style={{color:C.textSec,margin:0,fontSize:'13px'}}>{supplierDisplayName}</p>
                {supplierHeaderMeta && <p style={{color:C.textMuted,margin:'2px 0 0',fontSize:'11px'}}>{supplierHeaderMeta}</p>}
              </div>
            </div>
            <button onClick={()=>handleLogout()} style={{...btnG,fontSize:'12px'}}>Выйти</button>
          </div>
          {teamContext?.status==='error' && <div role="alert" style={{...card,padding:16,marginBottom:16}}>
            <p>{teamContext.error}</p><button type="button" onClick={teamContext.reload}>Повторить загрузку прав команды</button>
          </div>}
          {supplierAccountUnlinked && (
            <div style={{...card,padding:'12px 14px',marginBottom:'16px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}>
              <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'4px'}}>Кабинет не связан с карточкой поставщика</b>
              <p style={{color:C.textSec,fontSize:'12px',margin:0}}>
                {myOffers.length > 0
                  ? 'КП уже показаны по backend-доступу, но директору нужно связать карточку поставщика с вашим аккаунтом, чтобы корректно подтягивались название компании, реквизиты, счета и накладные.'
                  : 'Попросите директора открыть карточку поставщика и связать ваш пользовательский аккаунт с компанией. После этого здесь появятся название компании, КП, счета и накладные.'}
              </p>
            </div>
          )}
          <div className="supplier-workspace-summary" style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'12px',marginBottom:'16px'}}>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Новых заявок</p>
              <b style={{color:C.danger,fontSize:'24px'}}>{inboxState && inboxState.status!=='ready' ? '—' : pendingOfferCount}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Моих предложений</p>
              <b style={{color:C.accent,fontSize:'24px'}}>{inboxState && inboxState.status!=='ready' ? '—' : myOffers.length}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Утверждено</p>
              <b style={{color:C.success,fontSize:'24px'}}>{inboxState && inboxState.status!=='ready' ? '—' : approvedOfferCount}</b>
            </div>
          </div>

          {supplierTab==='team' && teamLeader && <SupplierTeam API={API} C={C} context={teamContext} onChanged={inboxState?.reload}/>}
          {supplierTab==='customers' && teamLeader && <SupplierTeam API={API} C={C} context={teamContext} mode="customers" onChanged={inboxState?.reload}/>}
          {supplierTab==='customers' && <SupplierCustomers API={API} user={user} teamContext={teamContext} C={C} fileSrc={fileSrc} onOpen={id=>{selectRequest(id);setSupplierTab('requests');inboxState?.reload();}}/>}
          {supplierTab==='orders' && <SupplierOrders API={API} user={user} C={C} fileSrc={fileSrc} onOpen={id=>{selectRequest(id);setSupplierTab('requests');inboxState?.reload();}}/>}
          {supplierTab==='requests'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📋 Запросы КП</b>
            {inboxState && <div style={{marginBottom:12}}>
              <button style={btnG} disabled={inboxState.status==='loading'} onClick={inboxState.reload}>Обновить заявки</button>
              {inboxState.status==='loading' && <p role="status">Загружаем входящие заявки…</p>}
              {inboxState.status==='error' && <p role="alert" style={{color:C.danger}}>Не удалось загрузить заявки: {inboxState.error}</p>}
            </div>}
            {(!inboxState || inboxState.status==='ready') && <>
              <SupplierRequestRegistry C={C} requests={supplyRequests || []} offers={myOffers} selectedId={selectedRequestId} onOpen={selectRequest} busy={quoteResponse.busy} invoices={supplierInvoices || []} deliveries={supplyDeliveries || []} />
              {selectedRequestId && <div ref={requestDetailRef}>
                <button type="button" style={btnG} disabled={quoteResponse.busy || attachmentBusy} onClick={()=>selectRequest('')}>← К списку заявок</button>
                <h2 style={{color:C.text,fontSize:18}}>Заявка №{selectedRequestId}</h2>
                {!myOffers.some(o=>String(o.requestId)===selectedRequestId) && <p role="status">Заявка недоступна или больше не входит в ваш список.</p>}
              </div>}
            </>}
            {(()=>{
              if (inboxState && inboxState.status!=='ready') return null;
              // Берём supplier_offers где я — поставщик, и группируем по статусу
              const detailId = selectedRequestId;
              const myOffersForMe = myOffers.filter(o=>String(o.requestId)===detailId);
              if (!detailId) return null;
              if (myOffersForMe.length===0) return null;
              const waiting = myOffersForMe.filter(o=>o.status==='Ожидает ответа');
              const responded = myOffersForMe.filter(o=>o.status==='Получено');
              const won = myOffersForMe.filter(o=>o.status==='Утверждено');
              const lost = myOffersForMe.filter(o=>o.status==='Отклонено');
              const withdrawn = myOffersForMe.filter(o=>o.status==='Отозвано');
              const groups = [
                {key:'wait', title:'⏳ Ждут ответа', items:waiting, color:C.warning, bg:C.warningLight, bd:C.warningBorder},
                {key:'resp', title:'📤 КП отправлено, ждёт решения', items:responded, color:C.info, bg:C.infoLight, bd:C.infoBorder},
                {key:'won',  title:'✅ Выиграно', items:won, color:C.success, bg:C.successLight, bd:C.successBorder},
                {key:'lost', title:'❌ Отклонено', items:lost, color:C.danger, bg:C.dangerLight, bd:C.dangerBorder},
                {key:'withdrawn', title:'Отозвано', items:withdrawn, color:C.textMuted, bg:C.bg, bd:C.border},
              ];
              return groups.filter(g=>g.items.length>0).map(g=>(<div key={g.key} style={{marginBottom:'16px'}}>
                <b style={{color:g.color,fontSize:'12px',display:'block',marginBottom:'8px'}}>{g.title} ({g.items.length})</b>
                {g.items.map(o=>{
                  const req = supplyRequests.find(r=>r.id===o.requestId);
                  if (!req) return null;
                  const isResponding = respondingOfferId===o.id;
                  return (<div key={o.id} style={{padding:'12px',backgroundColor:g.bg,borderRadius:'8px',marginBottom:'8px',border:'1.5px solid '+g.bd}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
                      <div style={{flex:1,minWidth:'200px'}}>
                        {(()=>{const items=parseSupplyItems(req); if (items.length<=1) {
                          const it = items[0] || {materialName:req.materialName,quantity:req.quantity,unit:req.unit};
                          return (<><b style={{fontSize:'13px',color:C.text}}>{it.materialName}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{it.quantity+' '+it.unit+' · 🏗 '+(req.project||'')}</p></>);
                        } return (<>
                          <b style={{fontSize:'13px',color:C.text}}>📋 Запрос на {items.length} позиций <span style={{color:C.textSec,fontWeight:'400'}}>· 🏗 {req.project||''}</span></b>
                          <ol style={{margin:'4px 0 6px',paddingLeft:'18px',color:C.text,fontSize:'12px'}}>
                            {items.map((it,i)=>(<li key={i} style={{marginBottom:'2px'}}>{it.materialName} <span style={{color:C.textSec}}>— {it.quantity} {it.unit}</span></li>))}
                          </ol>
                        </>);})()}
                        {req.notes && <p style={{color:C.textMuted,margin:'0',fontSize:'11px',fontStyle:'italic'}}>«{req.notes}»</p>}
                        {o.aiRecommended && <span style={badge(C.accent,C.accentLight,C.accentBorder||C.border)}>🤖 AI рекомендовал вас</span>}
                        {o.pricePerUnit>0 && (<p style={{color:C.textSec,margin:'4px 0 0',fontSize:'11px'}}>
                          Ваш ответ: <b>{Number(o.pricePerUnit).toLocaleString('ru-RU')+' ₽/'+req.unit}</b>{o.deliveryDays?' · '+o.deliveryDays+' дн.':''}{o.paymentTerms?' · '+o.paymentTerms:''}
                        </p>)}
                      </div>
                      <div>
                        {g.key==='wait' && !isResponding && (
                          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                            <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays??'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||'',expectedRespondedAt:o.respondedAt||null,itemsKp:readOfferItems(o)});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>💰 Отправить КП</button>
                            <button onClick={()=>withdrawOwnOffer(o,'Отказаться от запроса КП?')} style={{...btnG,padding:'5px 10px',fontSize:'12px'}}><X size={12}/>Отказаться</button>
                          </div>
                        )}
                        {g.key==='resp' && (
                          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                            <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays??'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||'',expectedRespondedAt:o.respondedAt||null,itemsKp:readOfferItems(o)});}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><Edit2 size={11}/>Изменить</button>
                            <button onClick={()=>withdrawOwnOffer(o,'Отозвать отправленное КП?')} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отозвать</button>
                          </div>
                        )}
                        {g.key==='withdrawn' && (
                          <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays??'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||'',expectedRespondedAt:o.respondedAt||null,itemsKp:readOfferItems(o)});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>Подать заново</button>
                        )}
                        {g.key==='won' && (
                          (()=>{
                            const order = supplierOrders([req], [o], supplyDeliveries || [], supplierInvoices || [])[0];
                            const hasInvoice = order?.documents.find(inv=>inv.status!=='Аннулирован');
                            const remaining = order?.lines.filter(line=>line.toShip>0) || [];
                            const canShip = order && !order.review && remaining.length>0;
                            const paid = Number(hasInvoice?.paidAmount||0);
                            const amount = Number(hasInvoice?.amount||hasInvoice?.totalAmount||o.totalPrice||0);
                            const terms = String(o.paymentTerms||'').toLowerCase();
                            const needPay = terms.includes('предоплат') || terms.includes('50/50');
                            const required = terms.includes('50/50') ? amount*0.5 : amount;
                            const blockedByPay = needPay && (!hasInvoice || paid + 0.01 < required);
                            return (<div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                              {hasInvoice
                                ? <span style={badge(hasInvoice.status==='Оплачен'||hasInvoice.status==='Частично оплачен'?C.success:C.info,hasInvoice.status==='Оплачен'||hasInvoice.status==='Частично оплачен'?C.successLight:C.infoLight,hasInvoice.status==='Оплачен'||hasInvoice.status==='Частично оплачен'?C.successBorder:C.infoBorder)}>💳 {hasInvoice.status}</span>
                                : <button onClick={()=>{setInvoicingOfferId(o.id);setNewOfferInvoice({invoiceNumber:'',invoiceDate:new Date().toISOString().split('T')[0],amount:o.totalPrice||'',vatAmount:'',description:'Материал: '+req.materialName,fileUrl:''});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>💳 Выставить счёт</button>}
                              {order && <span style={{fontSize:12}}>{order.status}</span>}
                              {canShip && <button disabled={blockedByPay || shipmentBusy} title={blockedByPay?'По условиям оплаты сначала нужна оплата бухгалтерии':''}
                                onClick={()=>{setShippingOfferId(o.id);setShipmentForm(createShipmentForm({
                                  requestId: crypto.randomUUID(),
                                  shippedItems: remaining.map(line=>({...line,shippedQuantity:String(line.toShip)})),
                                }));}}
                                style={{...btnGr,padding:'5px 12px',fontSize:12}}>
                                🚚 {order.shipments.length ? 'Отгрузить остаток' : 'Отгрузить'}
                              </button>}

                            </div>);
                          })()
                        )}
                      </div>
                    </div>
                    <SupplyFileLink url={o.pdfUrl} fileSrc={fileSrc}>Скачать файл КП</SupplyFileLink>
                    {/* Форма ответа КП — постатейная для multi-item */}
                    {isResponding && (()=>{
                      const reqItems = parseSupplyItems(req);
                      const isMulti = reqItems.length > 1;
                      // Сохранённые цены по позициям — берём из state, если уже инициализированы
                      const itemsKp = (newKpResponse.itemsKp && newKpResponse.itemsKp.length === reqItems.length)
                        ? newKpResponse.itemsKp
                        : reqItems.map(it => ({
                            materialName: it.materialName, quantity: Number(it.quantity)||0, unit: it.unit,
                            workPackage: it.workPackage || it.work_package || req.workPackage || req.work_package || '',
                            pricePerUnit: '', deliveryDays: '', notes: ''
                          }));
                      const grandTotal = itemsKp.reduce((s,it)=>s+(Number(it.pricePerUnit||0)*Number(it.quantity||0)), 0);
                      const setItem = (idx, field, value) => {
                        const arr = [...itemsKp];
                        arr[idx] = {...arr[idx], [field]: value};
                        setNewKpResponse({...newKpResponse, itemsKp: arr});
                      };
                      return (<fieldset disabled={quoteResponse.busy || attachmentBusy} style={{border:0,minWidth:0,padding:0,borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>
                        💰 Ваше КП {isMulti?'(заполните цену по каждой позиции)':'на '+(reqItems[0]?.quantity||req.quantity)+' '+(reqItems[0]?.unit||req.unit)}:
                      </b>
                      {/* Постатейная таблица для multi-item */}
                      {isMulti && (<div style={{marginBottom:'10px',overflowX:'auto'}}>
                        <table style={{width:'100%',borderCollapse:'collapse',fontSize:'12px'}}>
                          <thead>
                            <tr style={{backgroundColor:C.bg}}>
                              <th style={{padding:'6px 8px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>#</th>
                              <th style={{padding:'6px 8px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Материал</th>
                              <th style={{padding:'6px 8px',textAlign:'center',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Кол-во</th>
                              <th style={{padding:'6px 8px',textAlign:'right',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border,minWidth:'110px'}}>Цена за ед. (₽)</th>
                              <th style={{padding:'6px 8px',textAlign:'right',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border,minWidth:'100px'}}>Сумма</th>
                            </tr>
                          </thead>
                          <tbody>
                            {itemsKp.map((it,i)=>{
                              const subtotal = Number(it.pricePerUnit||0) * Number(it.quantity||0);
                              return (<tr key={i} style={{borderBottom:'1px solid '+C.border}}>
                                <td style={{padding:'6px 8px',color:C.textMuted}}>{i+1}</td>
                                <td style={{padding:'6px 8px',color:C.text}}>{it.materialName}</td>
                                <td style={{padding:'6px 8px',color:C.text,textAlign:'center',whiteSpace:'nowrap'}}>{it.quantity} {it.unit}</td>
                                <td style={{padding:'4px 8px',textAlign:'right'}}>
                                  <input type='number' step='any' inputMode='decimal' value={it.pricePerUnit} onChange={e=>setItem(i,'pricePerUnit',e.target.value)} placeholder='—' style={{...inp,marginBottom:0,textAlign:'right',padding:'4px 6px',fontSize:'12px'}}/>
                                </td>
                                <td style={{padding:'6px 8px',color:C.text,textAlign:'right',fontWeight:'600',whiteSpace:'nowrap'}}>
                                  {subtotal>0 ? Math.round(subtotal).toLocaleString('ru-RU')+' ₽' : '—'}
                                </td>
                              </tr>);
                            })}
                            <tr style={{backgroundColor:C.successLight}}>
                              <td colSpan={4} style={{padding:'8px',textAlign:'right',color:C.text,fontWeight:'700'}}>ИТОГО:</td>
                              <td style={{padding:'8px',textAlign:'right',color:C.success,fontWeight:'800',fontSize:'14px'}}>{grandTotal>0 ? Math.round(grandTotal).toLocaleString('ru-RU')+' ₽' : '—'}</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>)}
                      {/* Single-item: одно поле цены */}
                      {!isMulti && (<div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Цена за {reqItems[0]?.unit||req.unit} (₽) *</label>
                          <input type='number' step='any' inputMode='decimal' value={newKpResponse.pricePerUnit} onChange={e=>setNewKpResponse({...newKpResponse,pricePerUnit:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Срок поставки (дни) *</label>
                          <input type='number' step='1' inputMode='numeric' value={newKpResponse.deliveryDays} onChange={e=>setNewKpResponse({...newKpResponse,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                      </div>)}
                      {/* Общие поля */}
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        {isMulti && (<div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Срок поставки (дни) *</label>
                          <input type='number' step='1' inputMode='numeric' value={newKpResponse.deliveryDays} onChange={e=>setNewKpResponse({...newKpResponse,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>)}
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Условия оплаты</label>
                          <select value={newKpResponse.paymentTerms} onChange={e=>setNewKpResponse({...newKpResponse,paymentTerms:e.target.value})} style={{...inp,marginBottom:0}}>
                            <option>Предоплата 100%</option>
                            <option>50/50</option>
                            <option>Постоплата</option>
                            <option>Отсрочка 7 дней</option>
                            <option>Отсрочка 14 дней</option>
                            <option>Отсрочка 30 дней</option>
                          </select>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>НДС</label>
                          <select value={newKpResponse.vatIncluded?'incl':'excl'} onChange={e=>setNewKpResponse({...newKpResponse,vatIncluded:e.target.value==='incl'})} style={{...inp,marginBottom:0}}>
                            <option value='incl'>С НДС (включён)</option>
                            <option value='excl'>Без НДС</option>
                          </select>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>КП действительно до</label>
                          <input type='date' value={newKpResponse.validUntil} onChange={e=>setNewKpResponse({...newKpResponse,validUntil:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div style={{gridColumn:isMulti?'span 2':'span 2'}}>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>PDF КП (опц.)</label>
                          <SupplierAttachmentInput onBusy={setAttachmentBusy} offerId={o.id} uploadPhoto={uploadPhoto} label="Прикрепить PDF" attached={newKpResponse.pdfUrl} onUploaded={url=>setNewKpResponse(current=>({...current,pdfUrl:url}))}/>
                        </div>
                      </div>
                      <textarea placeholder='Комментарий (опц.) — особенности, условия доставки' value={newKpResponse.supplierMessage} onChange={e=>setNewKpResponse({...newKpResponse,supplierMessage:e.target.value})} style={{...inp,height:'50px',resize:'vertical'}}/>
                      {/* Итог для single-item */}
                      {!isMulti && newKpResponse.pricePerUnit && (<div style={{padding:'8px 10px',backgroundColor:C.successLight,borderRadius:'6px',marginBottom:'8px',fontSize:'12px',color:C.text}}>
                        Итого: <b>{Math.round(Number(newKpResponse.pricePerUnit||0)*Number(reqItems[0]?.quantity||req.quantity||0)).toLocaleString('ru-RU')} ₽</b>
                      </div>)}
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={async()=>{
                          if (isMulti) {
                            // Валидация: все позиции должны иметь цену > 0
                            const missing = itemsKp.filter(it=>!(Number(it.pricePerUnit)>0));
                            if (missing.length>0) { alert('Заполните цену по всем '+itemsKp.length+' позициям'); return; }
                            if (!newKpResponse.deliveryDays) { alert('Заполните срок'); return; }
                          } else {
                            if (!newKpResponse.pricePerUnit||!newKpResponse.deliveryDays) { alert('Заполните цену и срок'); return; }
                          }
                          const body = isMulti
                            ? {
                                action:'respond',
                                itemsKp: itemsKp.map(it=>({materialName:it.materialName, quantity:Number(it.quantity)||0, unit:it.unit, workPackage:it.workPackage||it.work_package||req.workPackage||req.work_package||'', pricePerUnit:Number(it.pricePerUnit)||0})),
                                deliveryDays: Number(newKpResponse.deliveryDays),
                                paymentTerms: newKpResponse.paymentTerms,
                                vatIncluded: newKpResponse.vatIncluded,
                                validUntil: newKpResponse.validUntil||null,
                                supplierMessage: newKpResponse.supplierMessage,
                                pdfUrl: newKpResponse.pdfUrl,
                              }
                            : {
                                action:'respond',
                                pricePerUnit: Number(newKpResponse.pricePerUnit),
                                quantity: Number(reqItems[0]?.quantity||req.quantity||0),
                                totalPrice: Number(newKpResponse.pricePerUnit) * Number(reqItems[0]?.quantity||req.quantity||0),
                                deliveryDays: Number(newKpResponse.deliveryDays),
                                paymentTerms: newKpResponse.paymentTerms,
                                vatIncluded: newKpResponse.vatIncluded,
                                validUntil: newKpResponse.validUntil||null,
                                supplierMessage: newKpResponse.supplierMessage,
                                pdfUrl: newKpResponse.pdfUrl,
                              };
                          await quoteResponse.submit({ ...body, expectedRespondedAt: newKpResponse.expectedRespondedAt || null });
                        }} style={btnO}><Check size={14}/>{quoteResponse.busy ? 'Отправляем…' : 'Отправить КП'}</button>
                        <button onClick={()=>setRespondingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                      {quoteResponse.error && <p role='alert' style={{color:C.danger,fontSize:'12px'}}>{quoteResponse.error}</p>}
                    </fieldset>);
                    })()}
                    {/* Форма выставления счёта (Сн.3) — для выигранного КП */}
                    {invoicingOfferId===o.id && (<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>💳 Выставить счёт по выигранному КП</b>
                      <div style={{padding:'10px',backgroundColor:C.successLight,borderRadius:'6px',marginBottom:'10px',fontSize:'11px',color:C.text}}>
                        Условия оплаты по КП: <b>{o.paymentTerms||'Не указано'}</b>. После выставления счёт уйдёт бухгалтеру компании на оплату.
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Номер счёта *</label>
                          <input value={newOfferInvoice.invoiceNumber} onChange={e=>setNewOfferInvoice({...newOfferInvoice,invoiceNumber:e.target.value})} placeholder='№ 123/05' style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Дата счёта</label>
                          <input type='date' value={newOfferInvoice.invoiceDate} onChange={e=>setNewOfferInvoice({...newOfferInvoice,invoiceDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Сумма (₽) *</label>
                          <input type='number' step='any' inputMode='decimal' value={newOfferInvoice.amount} onChange={e=>setNewOfferInvoice({...newOfferInvoice,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>в т.ч. НДС (₽)</label>
                          <input type='number' step='any' inputMode='decimal' value={newOfferInvoice.vatAmount} onChange={e=>setNewOfferInvoice({...newOfferInvoice,vatAmount:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                      </div>
                      <input value={newOfferInvoice.description} onChange={e=>setNewOfferInvoice({...newOfferInvoice,description:e.target.value})} placeholder='Описание (по умолчанию название материала)' style={inp}/>
                      <SupplierAttachmentInput onBusy={setAttachmentBusy} offerId={o.id} uploadPhoto={uploadPhoto} label="Прикрепить счёт (PDF/фото)" attached={newOfferInvoice.fileUrl} onUploaded={url=>setNewOfferInvoice(current=>({...current,fileUrl:url}))}/>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button disabled={attachmentBusy} onClick={async()=>{await createInvoiceFromOffer(o.id);await inboxState?.reload();}} style={btnO}><Check size={14}/>Отправить счёт</button>
                        <button disabled={attachmentBusy} onClick={()=>setInvoicingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>)}
                    {/* Сн.4: форма отгрузки поставщика */}
                    {shippingOfferId===o.id && (<fieldset disabled={shipmentBusy || attachmentBusy} style={{border:0,minWidth:0,borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>🚚 Отгрузка по выигранному КП</b>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        {(shipmentForm.shippedItems || []).map((line,index)=><label key={index} style={{fontSize:12}}>
                          {line.materialName} · {line.workPackage || 'Основная'} — остаток {line.toShip} {line.unit}
                          <input aria-label={'Отгрузить: '+line.materialName} type="number" min="0" max={line.toShip} step="0.0001" inputMode="decimal"
                            value={line.shippedQuantity} onChange={e=>setShipmentForm({...shipmentForm,shippedItems:shipmentForm.shippedItems.map((item,i)=>i===index?{...item,shippedQuantity:e.target.value}:item)})} style={inp}/>
                        </label>)}
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Дата накладной</label>
                          <input type='date' value={shipmentForm.waybillDate} onChange={e=>setShipmentForm({...shipmentForm,waybillDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <input placeholder='Номер накладной / УПД' value={shipmentForm.waybillNumber} onChange={e=>setShipmentForm({...shipmentForm,waybillNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Машина / госномер' value={shipmentForm.vehicleNumber} onChange={e=>setShipmentForm({...shipmentForm,vehicleNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Водитель / контакт' value={shipmentForm.driverName} onChange={e=>setShipmentForm({...shipmentForm,driverName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                      </div>
                      <SupplierAttachmentInput onBusy={setAttachmentBusy} offerId={o.id} uploadPhoto={uploadPhoto} label="Прикрепить накладную / УПД" attached={shipmentForm.documentUrl} onUploaded={url=>setShipmentForm(current=>({...current,documentUrl:url}))}/>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={()=>sendShipment(o)} style={btnO}><Check size={14}/>{shipmentBusy ? 'Отправляем…' : 'Отгрузить'}</button>
                        <button onClick={()=>setShippingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </fieldset>)}
                  </div>);
                })}
              </div>));
            })()}
          </div>)}

          {supplierTab==='catalog'&&!managerOnly&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
              <b style={{color:C.text,fontSize:'14px'}}>📦 Мой каталог</b>
              <div style={{display:'flex',gap:'8px'}}>
                <button disabled={catalogActions.busy} onClick={()=>setShowCatalogForm(!showCatalogForm)} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
            </div>
            <SupplierCatalogImport key={`${currentUserId}:${myPrimarySupplierId}`} API={API}
              supplierId={myPrimarySupplierId} supplierName={user.name}
              priceUrl={supplierRequisites.priceUrl} catalog={supplierCatalog || []}
              onSaved={setSupplierCatalog} buttonStyle={btnG} mutationLock={catalogMutationLock} />
            {catalogActions.error && <p role="alert" style={{color:C.danger}}>{catalogActions.error}</p>}
            {showCatalogForm&&(<fieldset disabled={catalogActions.busy} style={{...card,minWidth:0,padding:'16px',marginBottom:'12px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Наименование *' value={newCatalogItem.materialName} onChange={e=>setNewCatalogItem({...newCatalogItem,materialName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <select value={newCatalogItem.unit} onChange={e=>setNewCatalogItem({...newCatalogItem,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                <input placeholder='Цена за ед.' type='number' step='any' inputMode='decimal' value={newCatalogItem.price} onChange={e=>setNewCatalogItem({...newCatalogItem,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Мин. партия' type='number' step='any' inputMode='decimal' value={newCatalogItem.minQuantity} onChange={e=>setNewCatalogItem({...newCatalogItem,minQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Срок поставки (дней)' type='number' step='any' inputMode='decimal' value={newCatalogItem.deliveryDays} onChange={e=>setNewCatalogItem({...newCatalogItem,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Примечание' value={newCatalogItem.notes} onChange={e=>setNewCatalogItem({...newCatalogItem,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                <button onClick={()=>catalogActions.create(newCatalogItem)} style={btnO}><Check size={14}/>Сохранить</button>
                <button onClick={()=>setShowCatalogForm(false)} style={btnG}><X size={14}/>Отмена</button>
              </div>
            </fieldset>)}
            <table style={tbl}><thead><tr>
              <th style={tblH}>Наименование</th>
              <th style={tblH}>Ед.</th>
              <th style={tblH}>Цена</th>
              <th style={tblH}>Мин. партия</th>
              <th style={tblH}>Поставка</th>
              <th style={tblH}>Наличие</th>
              <th style={tblH}></th>
            </tr></thead><tbody>
              {myCatalog.map(item=>(<tr key={item.id}>
                <td style={tblC}>{item.materialName}</td>
                <td style={tblC}>{item.unit}</td>
                <td style={tblC}>{Number(item.price).toLocaleString()+' ₽'}</td>
                <td style={tblC}>{item.minQuantity}</td>
                <td style={tblC}>{item.deliveryDays+' дн.'}</td>
                <td style={tblC}><span style={{color:item.inStock?C.success:C.danger,fontSize:'12px'}}>{item.inStock?'✅ Есть':'❌ Нет'}</span></td>
                <td style={tblC}><button aria-label={'Удалить '+item.materialName} disabled={catalogActions.busy} onClick={()=>catalogActions.remove(item.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
              </tr>))}
            </tbody></table>
            {myCatalog.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Каталог пуст — добавьте материалы</p>}
          </div>)}

          {supplierTab==='offers'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>Мои предложения</b>
            {myOffers.map(o=>(<div key={o.id} style={{...card,padding:'12px',marginBottom:'8px'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'8px'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{(()=>{const r=supplyRequests.find(r=>r.id===o.requestId);if(!r) return 'Материал';const items=parseSupplyItems(r);return items.length>1?('📋 Пакет из '+items.length+' позиций'):(items[0]?.materialName||r.materialName||'Материал');})()}</b>
                  {Number(o.pricePerUnit||0)>0
                    ? <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{Number(o.pricePerUnit||0).toLocaleString('ru-RU')+' руб/ед · '+Number(o.totalPrice||0).toLocaleString('ru-RU')+' руб'+(o.deliveryDays?' · '+o.deliveryDays+' дн.':'')}</p>
                    : <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px',fontStyle:'italic'}}>⏳ Не отправлено ещё</p>}
                </div>
                {(()=>{const st=supplierOfferStatusStyle(o.status);return <span style={{padding:'3px 8px',borderRadius:'6px',fontSize:'11px',backgroundColor:st.bg,color:st.color}}>{st.label}</span>;})()}
              </div>
              {o.status==='Утверждено'&&(<p style={{fontSize:'11px',color:C.textSec,margin:'6px 0 0'}}>Отгрузка теперь оформляется из вкладки «📋 Заявки» по выигранному КП, чтобы не обходить счёт и приёмку.</p>)}
            </div>))}
            {myOffers.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Предложений нет</p>}
          </div>)}

          {['deliveries','documents'].includes(supplierTab) && inboxState && <div style={{marginBottom:16}}>
            <button type="button" disabled={inboxState.status==='loading'} onClick={inboxState.reload}>Обновить документы и отгрузки</button>
            {inboxState.status==='loading' && <p role="status">Загружаем документы и отгрузки…</p>}
            {inboxState.status==='error' && <p role="alert">Не удалось загрузить документы и отгрузки: {inboxState.error}</p>}
          </div>}
          {supplierTab==='deliveries'&&(!inboxState||inboxState.status==='ready')&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🚚 Мои отгрузки</b>
            {myDeliveries.map(d=>{const claim=myClaims.find(c=>c.deliveryId===d.id);return(<div key={d.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning)}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{d.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{d.shippedQuantity||d.plannedQuantity} {d.unit} · 🏗 {d.project||'—'} · накл. {d.waybillNumber||'—'}</p>
                  <SupplyFileLink url={d.documentUrl} fileSrc={fileSrc}>Скачать накладную / УПД</SupplyFileLink>
                  <SupplyFileLink url={d.photoUrl} fileSrc={fileSrc}>Скачать фото отгрузки</SupplyFileLink>
                  {d.receivedBy&&<p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Принял: {d.receivedBy} · принято {d.receivedQuantity||0} {d.unit}</p>}
                  {claim&&<p style={{color:C.danger,margin:'4px 0 0',fontSize:'11px'}}>⚠️ Претензия: {claim.claimType} · {claim.status}</p>}
                </div>
                <span style={badge(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning,d.status==='Принято'?C.successLight:d.status==='Проблема'?C.dangerLight:C.warningLight,d.status==='Принято'?C.successBorder:d.status==='Проблема'?C.dangerBorder:C.warningBorder)}>{d.status}</span>
              </div>
            </div>);})}
            {myDeliveries.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Отгрузок пока нет</p>}
          </div>)}

          {supplierTab==='documents'&&(!inboxState||inboxState.status==='ready')&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📄 Мои счета и накладные</b>
            {mySupplierInvoices.map(inv=>{
              const linkedWarehouseId = supplierInvoiceWarehouseId(inv);
              const linkedWarehouseInvoice = warehouseInvoiceForSupplierInvoice(inv);
              const delivery = deliveryForSupplierInvoice(inv, linkedWarehouseInvoice);
              const deliveryAccepted = delivery?.status === 'Принято';
              const deliveryProblem = delivery?.status === 'Проблема';
              const warehouseInvoiceNumber = warehouseInvoiceNumberForSupplierInvoice(inv, linkedWarehouseInvoice);
              const warehouseInvoiceDate = warehouseInvoiceDateForSupplierInvoice(inv, linkedWarehouseInvoice);
              const warehouseInvoicePhoto = warehouseInvoicePhotoForSupplierInvoice(inv, linkedWarehouseInvoice);
              const warehouseItems = Array.isArray(inv.warehouseInvoiceItems) ? inv.warehouseInvoiceItems : (linkedWarehouseInvoice?.items || []);
              return (
                <div key={inv.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                    <div>
                      <b style={{fontSize:'12px',color:C.text}}>Счёт № {inv.invoiceNumber||'—'}</b>
                      <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{(inv.invoiceDate||'')+' · '+Number(inv.amount||0).toLocaleString('ru-RU')+' ₽ · '+(inv.projectName||'—')}</p>
                      {inv.materialName&&<p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px'}}>Материал: {inv.materialName}</p>}
                      {inv.paidAmount>0&&<p style={{color:C.success,margin:0,fontSize:'11px'}}>Оплачено: {Number(inv.paidAmount||0).toLocaleString('ru-RU')} ₽</p>}
                    </div>
                    <span style={badge(inv.status==='Оплачен'?C.success:inv.status==='Частично оплачен'?C.warning:C.info,inv.status==='Оплачен'?C.successLight:inv.status==='Частично оплачен'?C.warningLight:C.infoLight,inv.status==='Оплачен'?C.successBorder:inv.status==='Частично оплачен'?C.warningBorder:C.infoBorder)}>{inv.status}</span>
                  </div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'8px',marginTop:'8px'}}>
                    <div style={{padding:'8px',borderRadius:'8px',border:'1px solid '+C.border,backgroundColor:linkedWarehouseId?C.successLight:C.bgCard}}>
                      <p style={{color:linkedWarehouseId?C.success:C.textSec,margin:'0 0 3px',fontSize:'10px',fontWeight:800}}>Складская накладная</p>
                      <b style={{color:C.text,fontSize:'12px'}}>{warehouseInvoiceNumber || (linkedWarehouseId ? 'запись #' + linkedWarehouseId : 'не связана')}</b>
                      {warehouseInvoiceDate&&<p style={{color:C.textSec,margin:'3px 0 0',fontSize:'10px'}}>Дата: {warehouseInvoiceDate}</p>}
                    </div>
                    <div style={{padding:'8px',borderRadius:'8px',border:'1px solid '+(deliveryProblem?C.dangerBorder:deliveryAccepted?C.successBorder:C.border),backgroundColor:deliveryProblem?C.dangerLight:deliveryAccepted?C.successLight:C.bgCard}}>
                      <p style={{color:deliveryProblem?C.danger:deliveryAccepted?C.success:C.textSec,margin:'0 0 3px',fontSize:'10px',fontWeight:800}}>Приёмка</p>
                      <b style={{color:C.text,fontSize:'12px'}}>{delivery ? delivery.status : 'отгрузка не найдена'}</b>
                      {delivery?.receivedQuantity>0&&<p style={{color:C.textSec,margin:'3px 0 0',fontSize:'10px'}}>Принято: {delivery.receivedQuantity} {delivery.unit}</p>}
                      {delivery?.receivedBy&&<p style={{color:C.textSec,margin:'3px 0 0',fontSize:'10px'}}>Принял: {delivery.receivedBy}</p>}
                    </div>
                  </div>
                  {warehouseItems.length>0&&(
                    <div style={{marginTop:'8px',padding:'8px',borderRadius:'8px',backgroundColor:C.bgCard,border:'1px solid '+C.border}}>
                      <p style={{color:C.textSec,margin:'0 0 4px',fontSize:'10px',fontWeight:800}}>Материалы по накладной</p>
                      {warehouseItems.slice(0,5).map((item,index)=>(
                        <p key={index} style={{color:C.text,margin:'2px 0',fontSize:'11px'}}>
                          {item.name || item.materialName || 'Материал'} · {item.quantity || item.qty || '—'} {item.unit || ''}
                        </p>
                      ))}
                      {warehouseItems.length>5&&<p style={{color:C.textMuted,margin:'4px 0 0',fontSize:'10px'}}>Еще позиций: {warehouseItems.length-5}</p>}
                    </div>
                  )}
                  {(inv.fileUrl||inv.photoUrl||warehouseInvoicePhoto||inv.deliveryDocumentUrl||inv.deliveryPhotoUrl)&&(
                    <div style={{display:'flex',gap:'8px',flexWrap:'wrap',marginTop:'8px'}}>
                      {inv.fileUrl&&<SupplyFileLink url={inv.fileUrl} fileSrc={fileSrc}>Файл счёта</SupplyFileLink>}
                      {inv.photoUrl&&<SupplyFileLink url={inv.photoUrl} fileSrc={fileSrc}>Фото</SupplyFileLink>}
                      {warehouseInvoicePhoto&&<SupplyFileLink url={warehouseInvoicePhoto} fileSrc={fileSrc}>Фото складской накладной</SupplyFileLink>}
                      {inv.deliveryDocumentUrl&&<SupplyFileLink url={inv.deliveryDocumentUrl} fileSrc={fileSrc}>Документ отгрузки</SupplyFileLink>}
                      {inv.deliveryPhotoUrl&&<SupplyFileLink url={inv.deliveryPhotoUrl} fileSrc={fileSrc}>Фото отгрузки</SupplyFileLink>}
                    </div>
                  )}
                </div>
              );
            })}
            {mySupplierInvoices.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Счетов пока нет</p>}
          </div>)}

          {supplierTab==='claims'&&<SupplyClaims API={API} C={C} user={user} onChanged={refreshData} />}

          {supplierTab==='profile'&&!managerOnly&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚙️ Реквизиты компании</b>
            <div style={{...card,padding:'16px',marginBottom:'14px'}}>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'10px'}}>📋 Основное</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Название компании' value={supplierRequisites.companyName} onChange={e=>setSupplierRequisites({...supplierRequisites,companyName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='ИНН' value={supplierRequisites.inn} onChange={e=>setSupplierRequisites({...supplierRequisites,inn:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='КПП' value={supplierRequisites.kpp} onChange={e=>setSupplierRequisites({...supplierRequisites,kpp:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='ОГРН/ОГРНИП' value={supplierRequisites.ogrn||''} onChange={e=>setSupplierRequisites({...supplierRequisites,ogrn:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Юридический адрес' value={supplierRequisites.address} onChange={e=>setSupplierRequisites({...supplierRequisites,address:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Фактический адрес' value={supplierRequisites.actualAddress||''} onChange={e=>setSupplierRequisites({...supplierRequisites,actualAddress:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Директор (ФИО)' value={supplierRequisites.directorName||''} onChange={e=>setSupplierRequisites({...supplierRequisites,directorName:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Должность директора' value={supplierRequisites.directorPosition||''} onChange={e=>setSupplierRequisites({...supplierRequisites,directorPosition:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Телефон' value={supplierRequisites.phone} onChange={e=>setSupplierRequisites({...supplierRequisites,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Email' value={supplierRequisites.email} onChange={e=>setSupplierRequisites({...supplierRequisites,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Сайт (опц.)' value={supplierRequisites.website||''} onChange={e=>setSupplierRequisites({...supplierRequisites,website:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='Специализация (что поставляете)' value={supplierRequisites.specialization||''} onChange={e=>setSupplierRequisites({...supplierRequisites,specialization:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>🏦 Банковские реквизиты</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Банк' value={supplierRequisites.bank} onChange={e=>setSupplierRequisites({...supplierRequisites,bank:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='БИК' value={supplierRequisites.bik} onChange={e=>setSupplierRequisites({...supplierRequisites,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Корр. счёт' value={supplierRequisites.korAccount||''} onChange={e=>setSupplierRequisites({...supplierRequisites,korAccount:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Расчётный счёт' value={supplierRequisites.account} onChange={e=>setSupplierRequisites({...supplierRequisites,account:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <p style={{color:C.textSec,fontSize:'12px'}}>Договоры и условия относятся к конкретному заказчику и хранятся в документах сделки.</p>
              <DocumentRecognitionPanel
                C={C}
                card={card}
                inp={inp}
                btnG={btnG}
                btnO={btnO}
                btnB={btnB}
                uploadPhoto={uploadPhoto}
                fileSrc={fileSrc}
                projectName={supplierRequisites.companyName || user.name || 'Поставщик'}
                context="supplier-documents"
                entityType="supplier"
                currentFields={supplierRequisites}
                onApplyExtracted={result => setSupplierRequisites(prev => ({...prev, ...supplierRequisitesPatchFromRecognition(result, prev)}))}
                applyExtractedLabel="Заполнить реквизиты"
                onCreateRecognizedDocument={myPrimarySupplierId ? createOwnSupplierDocumentFromRecognition : null}
                createRecognizedDocumentLabel="Добавить в документы"
              />
              <button onClick={async()=>{
                if (!myPrimarySupplierId) {
                  alert('Кабинет не связан с карточкой поставщика. Обратитесь к администратору платформы для проверки привязки.');
                  return;
                }
                const res = await fetch(API+'/suppliers/'+(myPrimarySupplierId||0)+'/requisites',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(supplierPublicRequisites(supplierRequisites))});
                if (res.ok) {
                  localStorage.setItem('supplierReq_'+user.id,JSON.stringify(supplierRequisites));
                  alert('Реквизиты сохранены!');
                  await refreshData();
                } else {
                  alert('Ошибка сохранения');
                }
              }} style={{...btnO,marginTop:'14px',width:'100%',justifyContent:'center',padding:'12px'}}><Check size={14}/>Сохранить реквизиты</button>
            </div>
          </div>)}
          </main>
        </div>
      </div>
    );
}
