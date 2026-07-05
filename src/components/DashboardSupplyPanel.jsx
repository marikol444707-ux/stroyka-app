import React from 'react';

export default function DashboardSupplyPanel({
  showSupplyDashboard,
  user,
  openSupplyDashboard,
  supplyPendingRequests,
  supplyOffersToReview,
  supplyInvoicesToPay,
  supplyInvoiceDebt,
}) {
  if (!showSupplyDashboard) return null;
  const role = user?.role || '';
  const openSupply = typeof openSupplyDashboard === 'function' ? openSupplyDashboard : () => {};
  const pendingRequests = Array.isArray(supplyPendingRequests) ? supplyPendingRequests : [];
  const offersToReview = Array.isArray(supplyOffersToReview) ? supplyOffersToReview : [];
  const invoicesToPay = Array.isArray(supplyInvoicesToPay) ? supplyInvoicesToPay : [];
  const invoiceDebt = Number(supplyInvoiceDebt || 0);

  const cards = [
    {label:role==='прораб'?'Ждут подтверждения':'Заявки в работе',value:pendingRequests.length,sub:'материалы по объектам',color:'#fdba74',bg:'rgba(234,88,12,.14)',border:'rgba(234,88,12,.32)',tab:'inbox'},
    {label:'КП на согласование',value:offersToReview.length,sub:'ответы поставщиков',color:'#93c5fd',bg:'rgba(59,130,246,.12)',border:'rgba(59,130,246,.28)',tab:'all'},
    {label:'Счета к оплате',value:invoicesToPay.length,sub:invoiceDebt>0?Math.round(invoiceDebt).toLocaleString('ru-RU')+' ₽':'долга нет',color:'#86efac',bg:'rgba(34,197,94,.12)',border:'rgba(34,197,94,.28)',tab:'invoices'},
  ];

  return (
    <div style={{background:'rgba(17,24,39,.88)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'22px',padding:'18px 20px',marginBottom:'20px',backdropFilter:'blur(24px)',boxShadow:'0 24px 80px rgba(0,0,0,.28)'}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap',marginBottom:'14px'}}>
        <div>
          <h2 style={{margin:0,fontSize:'18px',color:'#f8fafc'}}>🛒 Снабжение</h2>
          <p style={{color:'#94a3b8',fontSize:'12px',margin:'3px 0 0'}}>Заявки, КП и счета поставщиков в одном месте</p>
        </div>
        <button onClick={()=>openSupply(role==='бухгалтер'?'invoices':'all')} style={{background:'rgba(30,41,59,.78)',border:'1px solid rgba(148,163,184,.18)',borderRadius:'12px',padding:'8px 12px',color:'#fdba74',fontWeight:'700',cursor:'pointer',fontSize:'12px'}}>Открыть →</button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(180px,1fr))',gap:'12px'}}>
        {cards.map((k,i)=>(<div key={i} onClick={()=>openSupply(k.tab)} style={{padding:'14px',borderRadius:'16px',background:k.bg,border:'1px solid '+k.border,cursor:'pointer',transition:'transform 0.15s, background 0.15s'}} onMouseEnter={e=>{e.currentTarget.style.transform='translateY(-2px)';e.currentTarget.style.background='rgba(30,41,59,.75)';}} onMouseLeave={e=>{e.currentTarget.style.transform='';e.currentTarget.style.background=k.bg;}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px'}}>
            <span style={{color:k.color,fontSize:'12px',fontWeight:'800'}}>{k.label}</span>
            <span style={{color:k.color,fontSize:'11px'}}>→</span>
          </div>
          <div style={{fontSize:'30px',fontWeight:'800',letterSpacing:'-.03em',margin:'8px 0 2px',color:'#f8fafc'}}>{k.value}</div>
          <div style={{color:'#94a3b8',fontSize:'12px'}}>{k.sub}</div>
        </div>))}
      </div>
    </div>
  );
}
