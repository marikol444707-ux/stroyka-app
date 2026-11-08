import React from 'react';
import { Check } from 'lucide-react';
import { API } from '../api';
import ScanInvoiceModal from './ScanInvoiceModal';

const hasReceipt = delivery => Boolean(delivery.receivedAt) || ['Принято', 'Проблема'].includes(delivery.status);
const hasProblem = delivery => delivery.status === 'Проблема'
  || (hasReceipt(delivery) && ['Брак', 'Несоответствие', 'Недостача', 'Частично'].includes(delivery.qualityStatus));
const unresolved = claim => ['Открыта', 'В работе'].includes(claim?.status);

function SupplyDeliveriesPanel({
  C,
  card,
  inp,
  btnG,
  btnB,
  btnGr,
  badge,
  role,
  supplyClaims,
  supplyDeliveries,
  deliveryAiLoadingId,
  deliveryAiResultById,
  invoices,
  showPreview,
  buildInvoiceContent,
  user,
  companyId,
  projects = [],
  onReceiptConfirmed,
  onStandaloneReceipt,
  onOpenReceipt,
}) {
  const [visibleCount, setVisibleCount] = React.useState(8);
  const [filter, setFilter] = React.useState('all');
  const [scanDelivery, setScanDelivery] = React.useState(null);
  const [scanDraft, setScanDraft] = React.useState({});
  const [scanning, setScanning] = React.useState(false);
  const [scanContext, setScanContext] = React.useState(null);
  const deliveriesId = React.useId();
  const deliveries = supplyDeliveries || [];
  const claimsById = new Map((supplyClaims || []).map(claim => [claim.id, claim]));
  const claimsByDelivery = new Map((supplyClaims || []).map(claim => [claim.deliveryId, claim]));
  const claimFor = delivery => claimsById.get(delivery.claimId) || claimsByDelivery.get(delivery.id);
  const filters = [
    ['all', 'Все', () => true],
    ['pending', 'Ожидают приёмки', delivery => !hasReceipt(delivery)],
    ['accepted', 'Приняты без замечаний', delivery => hasReceipt(delivery) && !hasProblem(delivery)],
    ['problem', 'С проблемой', hasProblem],
    ['claims', 'С незакрытой претензией', delivery => unresolved(claimFor(delivery))],
  ];
  const filteredDeliveries = deliveries.filter(filters.find(([value]) => value === filter)[2]);
  const visibleDeliveries = filteredDeliveries.slice(0, visibleCount);
  const remainingCount = filteredDeliveries.length - visibleDeliveries.length;
  const openClaimsCount = (supplyClaims || []).filter(unresolved).length;

  const startReceiving = delivery => {
    if (scanContext !== delivery.id) setScanDraft({location: delivery.project || delivery.projectName || 'Основной склад', items: []});
    setScanContext(delivery.id);
    setScanDelivery(delivery);
  };

  return (
    <div style={{...card,padding:'16px',marginBottom:'16px'}}>
      <ScanInvoiceModal key={`${companyId ?? user?.companyId ?? user?.company_id ?? ''}:${scanContext}`} showScanInvoice={Boolean(scanDelivery) && ['прораб','кладовщик','снабженец','директор','зам_директора','главный_инженер'].includes(role)} setShowScanInvoice={show => {if (!show) setScanDelivery(null);}}
        C={C} card={card} btnG={btnG} scanningInvoice={scanning} setScanningInvoice={setScanning}
        API={API} user={user} companyId={companyId} newInvoice={scanDraft} setNewInvoice={setScanDraft}
        projects={projects.length ? projects : Array.from(new Set(deliveries.map(d => d.project || d.projectName).filter(Boolean))).map(name => ({name}))}
        unifiedReceipt onReceiptConfirmed={onReceiptConfirmed} onStandaloneReceipt={onStandaloneReceipt} onOpenReceipt={onOpenReceipt || (id => { const invoice = (invoices || []).find(row => Number(row.id) === Number(id)); if (invoice) showPreview(buildInvoiceContent(invoice), 'Накладная № ' + invoice.number); else { onReceiptConfirmed?.(); alert('Обновляем список накладных. Повторите открытие прихода.'); } })}/>

      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap',marginBottom:'10px'}}>
        <div>
          <b style={{color:C.text,fontSize:'14px'}}>🚚 Поставки и приёмка</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>Отгрузка поставщика → AI-сверка накладной → приёмка на склад объекта → претензия при проблеме.</p>
        </div>
        {openClaimsCount>0 && <span style={badge(C.danger,C.dangerLight,C.dangerBorder)}>⚠️ Претензий: {openClaimsCount}</span>}
      </div>

      {(supplyDeliveries||[]).length===0 && <p style={{color:C.textMuted,fontSize:'12px',margin:'8px 0'}}>Поставок пока нет. Они появятся после отгрузки выигранного КП поставщиком.</p>}

      {deliveries.length > 0 && <label style={{display:'grid',gap:'6px',marginBottom:'12px',fontSize:'12px',color:C.textSec}}>
        Показать поставки
        <select value={filter} onChange={event => { setFilter(event.target.value); setVisibleCount(8); }}
          style={{...inp,width:'100%',maxWidth:'360px',minWidth:0,boxSizing:'border-box',marginBottom:0}}>
          {filters.map(([value, label, matches]) => <option key={value} value={value}>{label} ({deliveries.filter(matches).length})</option>)}
        </select>
      </label>}
      {deliveries.length > 0 && filteredDeliveries.length === 0 && <p style={{color:C.textMuted,fontSize:'12px'}}>По этому фильтру поставок нет.</p>}

      <div id={deliveriesId}>
      {visibleDeliveries.map(delivery=>{
        const problem = hasProblem(delivery);
        const done = hasReceipt(delivery);
        const stC = problem?C.danger:done?C.success:C.info;
        const stBg = problem?C.dangerLight:done?C.successLight:C.infoLight;
        const stBd = problem?C.dangerBorder:done?C.successBorder:C.infoBorder;
        const canReceive = ['прораб','кладовщик','снабженец','директор','зам_директора','главный_инженер'].includes(role) && !done;
        const claim = claimFor(delivery);
        const linkedInvoice = (invoices||[]).find(inv=>String(inv.supplyDeliveryId||'')===String(delivery.id));

        return (
          <div key={delivery.id} style={{padding:'12px',border:'1.5px solid '+stBd,backgroundColor:stBg,borderRadius:'8px',marginBottom:'8px'}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
              <div style={{flex:'1 1 260px'}}>
                <b style={{color:C.text,fontSize:'13px'}}>{delivery.materialName}</b>
                <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{delivery.shippedQuantity || delivery.plannedQuantity} {delivery.unit} · 🏗 {delivery.project || '—'} · {delivery.supplierName || 'Поставщик'}</p>
                {done && <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>
                  {delivery.receivedQuantity == null ? 'Принятое количество не указано' : `Принято: ${delivery.receivedQuantity} ${delivery.unit}`}
                  {Number(delivery.shortageQuantity) > 0 ? ` · Недостача: ${delivery.shortageQuantity} ${delivery.unit}` : ''}
                </p>}
                {done && delivery.qualityStatus === 'Брак' && <p style={{color:C.danger,fontSize:'12px'}}>Брак — в доступный остаток не включён.</p>}
                <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>ТТН/накладная: {delivery.waybillNumber || '—'}{delivery.vehicleNumber?' · авто '+delivery.vehicleNumber:''}{delivery.driverName?' · '+delivery.driverName:''}</p>
                {delivery.documentParties?.reviewRequired ? (
                  <p style={{color:C.warning,margin:'6px 0 0',fontSize:'11px',fontWeight:700}}>⚠️ {delivery.documentParties.reviewReason}</p>
                ) : delivery.documentParties && (
                  <div style={{padding:'8px 10px',marginTop:'7px',border:'1px solid '+C.border,borderRadius:'7px',backgroundColor:C.bgCard||C.bg,fontSize:'11px',color:C.textSec}}>
                    <b style={{color:C.text}}>Документы поставки</b>
                    <p style={{margin:'3px 0'}}>{delivery.documentParties.supplier?.fullName || 'Поставщик'} → {delivery.documentParties.buyer?.fullName || delivery.documentParties.consignee?.companyName || 'Заказчик'}</p>
                    <p style={{margin:'3px 0'}}>Доставка: {delivery.documentParties.consignee?.deliveryAddress || 'адрес не указан'}{delivery.documentParties.consignee?.contactName ? ' · '+delivery.documentParties.consignee.contactName : ''}{delivery.documentParties.consignee?.contactPhone ? ' · '+delivery.documentParties.consignee.contactPhone : ''}</p>
                    {delivery.documentParties.contract && <p style={{margin:'3px 0'}}>Договор № {delivery.documentParties.contract.number || '—'}{delivery.documentParties.contract.date ? ' от '+delivery.documentParties.contract.date : ''}</p>}
                  </div>
                )}
                {delivery.aiCheckResult && <p style={{color:C.accent,margin:'5px 0 0',fontSize:'11px'}}>🤖 {delivery.aiCheckResult}</p>}
                {claim && <p style={{color:C.danger,margin:'5px 0 0',fontSize:'11px'}}>⚠️ Претензия: {claim.claimType} · {claim.status}</p>}
                {linkedInvoice && <p style={{color:C.success,margin:'5px 0 0',fontSize:'11px'}}>📄 Накладная № {linkedInvoice.number} · запись #{linkedInvoice.id}</p>}
              </div>
              <div style={{display:'flex',gap:'5px',flexWrap:'wrap',justifyContent:'flex-end'}}>
                <span style={badge(stC,stBg,stBd)}>{delivery.status}</span>
                {canReceive && <button onClick={()=>startReceiving(delivery)} style={{...btnGr,padding:'5px 10px',fontSize:'11px'}}><Check size={11}/>Принять</button>}
                {linkedInvoice && <button onClick={()=>showPreview(buildInvoiceContent(linkedInvoice),'Накладная № '+linkedInvoice.number)} style={{...btnB,padding:'5px 10px',fontSize:'11px'}}>Печать накл.</button>}
              </div>
            </div>

            {deliveryAiLoadingId===delivery.id && <p style={{color:C.textMuted,fontSize:'11px',margin:'8px 0 0'}}>AI сверяет накладную...</p>}
            {deliveryAiResultById?.[delivery.id] && <div style={{padding:'8px 10px',backgroundColor:C.bg,border:'1px solid '+C.border,borderRadius:'6px',fontSize:'11px',color:C.text,marginTop:'8px'}}>{deliveryAiResultById?.[delivery.id]}</div>}


          </div>
        );
      })}
      </div>
      {deliveries.length > 0 && (
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:'8px',flexWrap:'wrap',marginTop:'8px'}}>
          <span role="status" style={{color:C.textSec,fontSize:'12px'}}>
            Показано поставок: {visibleDeliveries.length} из {filteredDeliveries.length}
          </span>
          {remainingCount > 0 && (
            <button type="button" aria-controls={deliveriesId} onClick={()=>setVisibleCount(count=>count+8)} style={btnG}>
              Показать ещё {Math.min(8, remainingCount)}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default SupplyDeliveriesPanel;
