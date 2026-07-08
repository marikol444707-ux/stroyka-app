import React from 'react';
import { Check, Download, Edit2, Plus, Trash2, Upload, X } from 'lucide-react';
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
    const currentUserId = user?.id || user?.userId || user?.user_id || '';
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
    const supplierAccountUnlinked = isSupplierRole && !mySupplier;
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
    const supplierDisplayName = mySupplier?.name || supplierRequisites.companyName || supplierOfferFallbackName || user?.name || 'Поставщик';
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
    const SUPPLIER_TABS = [{id:'requests',label:'📋 Заявки'},{id:'catalog',label:'📦 Мой каталог'},{id:'offers',label:'💰 Предложения'},{id:'deliveries',label:'🚚 Отгрузки'},{id:'documents',label:'📄 Счета и накладные'},{id:'claims',label:'⚠️ Претензии'},{id:'profile',label:'⚙️ Профиль'}];
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
        <div style={{maxWidth:'900px',margin:'0 auto'}}>
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
          {/* Селектор клиентов (заготовка под multi-tenancy) */}
          <div style={{...card,padding:'10px 14px',marginBottom:'16px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,display:'flex',alignItems:'center',justifyContent:'space-between',gap:'10px',flexWrap:'wrap'}}>
            <div style={{display:'flex',alignItems:'center',gap:'10px'}}>
              <span style={{fontSize:'18px'}}>🏢</span>
              <div>
                <b style={{color:C.text,fontSize:'13px'}}>Компания-клиент: СтройКа</b>
                <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Сейчас показываем заявки только от одной компании. В будущем сюда подключатся другие клиенты — увидите всех в одном кабинете.</p>
              </div>
            </div>
            <select disabled value='1' style={{...inp,marginBottom:0,width:'auto',cursor:'not-allowed',opacity:0.7}}>
              <option value='1'>СтройКа</option>
              <option value='all' disabled>🚧 Скоро: все клиенты</option>
            </select>
          </div>
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
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:'12px',marginBottom:'16px'}}>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Новых заявок</p>
              <b style={{color:C.danger,fontSize:'24px'}}>{pendingOfferCount}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Моих предложений</p>
              <b style={{color:C.accent,fontSize:'24px'}}>{myOffers.length}</b>
            </div>
            <div style={{...card,padding:'16px',textAlign:'center'}}>
              <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 4px'}}>Утверждено</p>
              <b style={{color:C.success,fontSize:'24px'}}>{approvedOfferCount}</b>
            </div>
          </div>

          <div style={{display:'flex',gap:0,overflowX:'auto',borderBottom:'1.5px solid '+C.border,marginBottom:'16px'}}>
            {SUPPLIER_TABS.map(t=>(<button key={t.id} onClick={()=>setSupplierTab(t.id)} style={{padding:'10px 16px',border:'none',backgroundColor:'transparent',cursor:'pointer',fontSize:'12px',fontWeight:supplierTab===t.id?'700':'400',color:supplierTab===t.id?C.accent:C.textSec,borderBottom:supplierTab===t.id?'2px solid '+C.accent:'2px solid transparent',whiteSpace:'nowrap'}}>{t.label}</button>))}
          </div>

          {supplierTab==='requests'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>📋 Запросы КП</b>
            {(()=>{
              // Берём supplier_offers где я — поставщик, и группируем по статусу
              const myOffersForMe = myOffers;
              if (myOffersForMe.length===0) return (<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>
                Запросов нет. Когда директор запросит у вас КП по своей заявке — он появится здесь.
              </p>);
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
                            <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays||'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||''});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>💰 Отправить КП</button>
                            <button onClick={()=>withdrawOwnOffer(o,'Отказаться от запроса КП?')} style={{...btnG,padding:'5px 10px',fontSize:'12px'}}><X size={12}/>Отказаться</button>
                          </div>
                        )}
                        {g.key==='resp' && (
                          <div style={{display:'flex',gap:'6px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                            <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays||'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||''});}} style={{...btnG,padding:'4px 10px',fontSize:'11px'}}><Edit2 size={11}/>Изменить</button>
                            <button onClick={()=>withdrawOwnOffer(o,'Отозвать отправленное КП?')} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}><X size={11}/>Отозвать</button>
                          </div>
                        )}
                        {g.key==='withdrawn' && (
                          <button onClick={()=>{setRespondingOfferId(o.id);setNewKpResponse({pricePerUnit:o.pricePerUnit||'',deliveryDays:o.deliveryDays||'',paymentTerms:o.paymentTerms||'Постоплата',vatIncluded:o.vatIncluded!==false,validUntil:o.validUntil||'',supplierMessage:o.supplierMessage||'',pdfUrl:o.pdfUrl||''});}} style={{...btnO,padding:'5px 12px',fontSize:'12px'}}>Подать заново</button>
                        )}
                        {g.key==='won' && (
                          (()=>{
                            const hasInvoice = (supplierInvoices||[]).find(inv=>inv.offerId===o.id||inv.offer_id===o.id);
                            const delivery = (supplyDeliveries||[]).find(d=>d.offerId===o.id);
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
                              {delivery
                                ? <span style={badge(delivery.status==='Принято'?C.success:delivery.status==='Проблема'?C.danger:C.warning,delivery.status==='Принято'?C.successLight:delivery.status==='Проблема'?C.dangerLight:C.warningLight,delivery.status==='Принято'?C.successBorder:delivery.status==='Проблема'?C.dangerBorder:C.warningBorder)}>🚚 {delivery.status}</span>
                                : <button disabled={blockedByPay} title={blockedByPay?'По условиям оплаты сначала нужна оплата бухгалтерии':''} onClick={()=>{if(blockedByPay){alert('По условиям «'+(o.paymentTerms||'')+'» сначала нужна оплата.');return;}setShippingOfferId(o.id);setShipmentForm({shippedQuantity:String(req.quantity||''),waybillNumber:'',waybillDate:new Date().toISOString().split('T')[0],vehicleNumber:'',driverName:'',documentUrl:'',photoUrl:''});}} style={{...btnGr,padding:'5px 12px',fontSize:'12px',opacity:blockedByPay?0.5:1,cursor:blockedByPay?'not-allowed':'pointer'}}>🚚 Отгрузить</button>}
                            </div>);
                          })()
                        )}
                      </div>
                    </div>
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
                      return (<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
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
                          <label style={{...btnG,padding:'8px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'4px',width:'100%',justifyContent:'center'}}>
                            <Upload size={12}/>{newKpResponse.pdfUrl?'PDF загружен':'Прикрепить PDF'}
                            <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:req.project||req.projectName,context:'supplier-offers'});setNewKpResponse({...newKpResponse,pdfUrl:url});}}}/>
                          </label>
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
                          await fetch(API+'/supplier-offers/'+o.id,{
                            method:'PUT', headers:{'Content-Type':'application/json'},
                            body: JSON.stringify(body)
                          });
                          setRespondingOfferId(null);
                          await refreshData();
                          notify('КП отправлено директору','supply');
                        }} style={btnO}><Check size={14}/>Отправить КП</button>
                        <button onClick={()=>setRespondingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>);
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
                      <label style={{...btnG,padding:'8px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'4px',marginBottom:'10px'}}>
                        <Upload size={12}/>{newOfferInvoice.fileUrl?'PDF/Фото загружен':'Прикрепить счёт (PDF/фото)'}
                        <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:req.project||req.projectName,context:'supplier-invoices'});setNewOfferInvoice({...newOfferInvoice,fileUrl:url});}}}/>
                      </label>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={()=>createInvoiceFromOffer(o.id)} style={btnO}><Check size={14}/>Отправить счёт</button>
                        <button onClick={()=>setInvoicingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>)}
                    {/* Сн.4: форма отгрузки поставщика */}
                    {shippingOfferId===o.id && (<div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                      <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'8px'}}>🚚 Отгрузка по выигранному КП</b>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Отгружено, {req.unit}</label>
                          <input type='number' step='any' inputMode='decimal' value={shipmentForm.shippedQuantity} onChange={e=>setShipmentForm({...shipmentForm,shippedQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <div>
                          <label style={{fontSize:'11px',color:C.textSec,display:'block',marginBottom:'3px'}}>Дата накладной</label>
                          <input type='date' value={shipmentForm.waybillDate} onChange={e=>setShipmentForm({...shipmentForm,waybillDate:e.target.value})} style={{...inp,marginBottom:0}}/>
                        </div>
                        <input placeholder='Номер накладной / УПД' value={shipmentForm.waybillNumber} onChange={e=>setShipmentForm({...shipmentForm,waybillNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Машина / госномер' value={shipmentForm.vehicleNumber} onChange={e=>setShipmentForm({...shipmentForm,vehicleNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                        <input placeholder='Водитель / контакт' value={shipmentForm.driverName} onChange={e=>setShipmentForm({...shipmentForm,driverName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                      </div>
                      <label style={{...btnG,padding:'8px 12px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'4px',marginBottom:'10px'}}>
                        <Upload size={12}/>{shipmentForm.documentUrl?'Документ загружен':'Прикрепить накладную / УПД'}
                        <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{projectName:req.project||req.projectName,context:'supply-shipments'});setShipmentForm({...shipmentForm,documentUrl:url});}}}/>
                      </label>
                      <div style={{display:'flex',gap:'8px'}}>
                        <button onClick={()=>createShipmentFromOffer(o)} style={btnO}><Check size={14}/>Отгрузить</button>
                        <button onClick={()=>setShippingOfferId(null)} style={btnG}><X size={14}/>Отмена</button>
                      </div>
                    </div>)}
                  </div>);
                })}
              </div>));
            })()}
          </div>)}

          {supplierTab==='catalog'&&(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'12px'}}>
              <b style={{color:C.text,fontSize:'14px'}}>📦 Мой каталог</b>
              <div style={{display:'flex',gap:'8px'}}>
                <label style={{...btnG,padding:'6px 12px',fontSize:'12px',cursor:'pointer',display:'flex',alignItems:'center',gap:'4px'}}>
                  📥 Excel
                  <input type='file' accept='.xlsx,.xls,.csv' style={{display:'none'}} onChange={e=>{const file=e.target.files[0];if(!file)return;const reader=new FileReader();reader.onload=async ev=>{try{const XLSX=await import('xlsx');const wb=XLSX.read(ev.target.result,{type:'array'});const ws=wb.Sheets[wb.SheetNames[0]];const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});let count=0;for(let i=1;i<rows.length;i++){const r=rows[i];if(!r[0])continue;const item={materialName:String(r[0]),unit:String(r[1]||'шт'),price:Number(r[2]||0),minQuantity:Number(r[3]||1),deliveryDays:Number(r[4]||3),notes:String(r[5]||''),supplierId:myPrimarySupplierId||0,supplierName:user.name};const res=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});const saved=await res.json();setSupplierCatalog(prev=>[...prev,{...item,id:saved.id}]);count++;}alert('Импортировано '+count+' позиций!');}catch(err){alert('Ошибка: '+err.message);}};reader.readAsArrayBuffer(file);e.target.value='';}} />
                </label>
                {supplierRequisites.priceUrl&&(<button onClick={async()=>{
                  try{
                    alert('Загрузка прайса... Это может занять несколько секунд.');
                    const res=await fetch('https://corsproxy.io/?'+encodeURIComponent(supplierRequisites.priceUrl));
                    const blob=await res.arrayBuffer();
                    const XLSX=await import('xlsx');
                    const wb=XLSX.read(blob,{type:'array'});
                    const ws=wb.Sheets[wb.SheetNames[0]];
                    const rows=XLSX.utils.sheet_to_json(ws,{header:1,defval:''});
                    let count=0;
                    for(let i=1;i<rows.length;i++){
                      const r=rows[i];
                      if(!r[0]) continue;
                      const item={materialName:String(r[0]),unit:String(r[1]||'шт'),price:Number(r[2]||0),minQuantity:Number(r[3]||1),deliveryDays:Number(r[4]||3),notes:String(r[5]||''),supplierId:myPrimarySupplierId||0,supplierName:user.name};
                      const res2=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(item)});
                      const saved=await res2.json();
                      setSupplierCatalog(prev=>[...prev,{...item,id:saved.id}]);
                      count++;
                    }
                    alert('Загружено '+count+' позиций!');
                  }catch(err){alert('Ошибка загрузки: '+err.message);}
                }} style={btnG}><Download size={14}/>По ссылке</button>)}
                <button onClick={()=>setShowCatalogForm(!showCatalogForm)} style={btnO}><Plus size={14}/>Добавить</button>
              </div>
            </div>
            {showCatalogForm&&(<div style={{...card,padding:'16px',marginBottom:'12px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Наименование *' value={newCatalogItem.materialName} onChange={e=>setNewCatalogItem({...newCatalogItem,materialName:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <select value={newCatalogItem.unit} onChange={e=>setNewCatalogItem({...newCatalogItem,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                <input placeholder='Цена за ед.' type='number' step='any' inputMode='decimal' value={newCatalogItem.price} onChange={e=>setNewCatalogItem({...newCatalogItem,price:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Мин. партия' type='number' step='any' inputMode='decimal' value={newCatalogItem.minQuantity} onChange={e=>setNewCatalogItem({...newCatalogItem,minQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Срок поставки (дней)' type='number' step='any' inputMode='decimal' value={newCatalogItem.deliveryDays} onChange={e=>setNewCatalogItem({...newCatalogItem,deliveryDays:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Примечание' value={newCatalogItem.notes} onChange={e=>setNewCatalogItem({...newCatalogItem,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <div style={{display:'flex',gap:'8px',marginTop:'10px'}}>
                <button onClick={async()=>{
                  if(!newCatalogItem.materialName) return;
                  const res=await fetch(API+'/supplier-catalog',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newCatalogItem,supplierId:myPrimarySupplierId||0,supplierName:user.name})});
                  const saved=await res.json();
                  setSupplierCatalog(prev=>[...prev,{...newCatalogItem,id:saved.id,supplierId:myPrimarySupplierId||0}]);
                  setNewCatalogItem({materialName:'',unit:'шт',price:'',minQuantity:'1',deliveryDays:'3',notes:''});
                  setShowCatalogForm(false);
                }} style={btnO}><Check size={14}/>Сохранить</button>
                <button onClick={()=>setShowCatalogForm(false)} style={btnG}><X size={14}/>Отмена</button>
              </div>
            </div>)}
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
                <td style={tblC}><button onClick={async()=>{await fetch(API+'/supplier-catalog/'+item.id,{method:'DELETE'});setSupplierCatalog(prev=>prev.filter(c=>c.id!==item.id));}} style={{...btnR,padding:'3px 7px'}}><Trash2 size={11}/></button></td>
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

          {supplierTab==='deliveries'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>🚚 Мои отгрузки</b>
            {myDeliveries.map(d=>{const claim=myClaims.find(c=>c.deliveryId===d.id);return(<div key={d.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning)}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{d.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{d.shippedQuantity||d.plannedQuantity} {d.unit} · 🏗 {d.project||'—'} · накл. {d.waybillNumber||'—'}</p>
                  {d.receivedBy&&<p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>Принял: {d.receivedBy} · принято {d.receivedQuantity||0} {d.unit}</p>}
                  {claim&&<p style={{color:C.danger,margin:'4px 0 0',fontSize:'11px'}}>⚠️ Претензия: {claim.claimType} · {claim.status}</p>}
                </div>
                <span style={badge(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning,d.status==='Принято'?C.successLight:d.status==='Проблема'?C.dangerLight:C.warningLight,d.status==='Принято'?C.successBorder:d.status==='Проблема'?C.dangerBorder:C.warningBorder)}>{d.status}</span>
              </div>
            </div>);})}
            {myDeliveries.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Отгрузок пока нет</p>}
          </div>)}

          {supplierTab==='documents'&&(<div>
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
                      {inv.fileUrl&&<a href={fileSrc(inv.fileUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'11px',color:C.accent}}>Файл счёта</a>}
                      {inv.photoUrl&&<a href={fileSrc(inv.photoUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'11px',color:C.accent}}>Фото</a>}
                      {warehouseInvoicePhoto&&<a href={fileSrc(warehouseInvoicePhoto)} target='_blank' rel='noopener noreferrer' style={{fontSize:'11px',color:C.accent}}>Фото складской накладной</a>}
                      {inv.deliveryDocumentUrl&&<a href={fileSrc(inv.deliveryDocumentUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'11px',color:C.accent}}>Документ отгрузки</a>}
                      {inv.deliveryPhotoUrl&&<a href={fileSrc(inv.deliveryPhotoUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'11px',color:C.accent}}>Фото отгрузки</a>}
                    </div>
                  )}
                </div>
              );
            })}
            {mySupplierInvoices.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Счетов пока нет</p>}
          </div>)}

          {supplierTab==='claims'&&(<div>
            <b style={{color:C.text,fontSize:'14px',display:'block',marginBottom:'12px'}}>⚠️ Претензии по поставкам</b>
            {myClaims.map(c=>(<div key={c.id} style={{...card,padding:'12px',marginBottom:'8px',borderLeft:'3px solid '+(c.status==='Открыта'?C.danger:C.success)}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{c.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{c.claimType} · 🏗 {c.project||'—'}</p>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{c.description}</p>
                </div>
                <span style={badge(c.status==='Открыта'?C.danger:C.success,c.status==='Открыта'?C.dangerLight:C.successLight,c.status==='Открыта'?C.dangerBorder:C.successBorder)}>{c.status}</span>
              </div>
            </div>))}
            {myClaims.length===0&&<p style={{color:C.textMuted,fontSize:'12px',textAlign:'center',padding:'20px'}}>Претензий нет</p>}
          </div>)}

          {supplierTab==='profile'&&(<div>
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
                <textarea placeholder='Примечания / предмет договора' value={supplierRequisites.notes||''} onChange={e=>setSupplierRequisites({...supplierRequisites,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',minHeight:'64px',resize:'vertical',fontFamily:'inherit'}}/>
              </div>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>🏦 Банковские реквизиты</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
                <input placeholder='Банк' value={supplierRequisites.bank} onChange={e=>setSupplierRequisites({...supplierRequisites,bank:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
                <input placeholder='БИК' value={supplierRequisites.bik} onChange={e=>setSupplierRequisites({...supplierRequisites,bik:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Корр. счёт' value={supplierRequisites.korAccount||''} onChange={e=>setSupplierRequisites({...supplierRequisites,korAccount:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder='Расчётный счёт' value={supplierRequisites.account} onChange={e=>setSupplierRequisites({...supplierRequisites,account:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
              </div>
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>📄 Договор поставки</b>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
                <input placeholder='Номер договора' value={supplierRequisites.contractNumber||''} onChange={e=>setSupplierRequisites({...supplierRequisites,contractNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input type='date' placeholder='Дата договора' value={supplierRequisites.contractDate||''} onChange={e=>setSupplierRequisites({...supplierRequisites,contractDate:e.target.value})} style={{...inp,marginBottom:0}}/>
              </div>
              <label style={{...btnG,padding:'10px 14px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'6px',marginRight:'8px'}}>
                <Upload size={14}/>{supplierRequisites.contractUrl?'✅ Договор загружен':'Загрузить договор (PDF)'}
                <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{context:'supplier-documents'});setSupplierRequisites({...supplierRequisites,contractUrl:url});}}}/>
              </label>
              {supplierRequisites.contractUrl && (<a href={fileSrc(supplierRequisites.contractUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'12px',color:C.accent,marginRight:'8px'}}>📥 Посмотреть</a>)}
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
              <b style={{color:C.textSec,fontSize:'12px',display:'block',marginBottom:'8px',marginTop:'12px'}}>📦 Прайс-лист (опц.)</b>
              <input placeholder='Ссылка на прайс (Google Sheet / Excel URL)' value={supplierRequisites.priceUrl||''} onChange={e=>setSupplierRequisites({...supplierRequisites,priceUrl:e.target.value})} style={inp}/>
              <label style={{...btnG,padding:'10px 14px',fontSize:'12px',cursor:'pointer',display:'inline-flex',alignItems:'center',gap:'6px',marginRight:'8px'}}>
                <Upload size={14}/>{supplierRequisites.licenseUrl?'✅ Лицензия загружена':'Загрузить лицензию/сертификат'}
                <input type='file' accept='.pdf,image/*' style={{display:'none'}} onChange={async e=>{if(e.target.files[0]){const url=await uploadPhoto(e.target.files[0],{context:'supplier-documents'});setSupplierRequisites({...supplierRequisites,licenseUrl:url});}}}/>
              </label>
              {supplierRequisites.licenseUrl && (<a href={fileSrc(supplierRequisites.licenseUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'12px',color:C.accent}}>📥 Посмотреть</a>)}
              <button onClick={async()=>{
                if (!myPrimarySupplierId) {
                  alert('Кабинет не связан с карточкой поставщика. Попросите директора связать аккаунт с компанией.');
                  return;
                }
                const res = await fetch(API+'/suppliers/'+(myPrimarySupplierId||0)+'/requisites',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({
                  ...supplierRequisites,
                  legalAddress: supplierRequisites.address // alias
                })});
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
        </div>
      </div>
    );
}
