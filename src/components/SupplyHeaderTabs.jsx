import React from 'react';
import { Plus } from 'lucide-react';

function SupplyHeaderTabs({
  C,
  btnO,
  btnG,
  role,
  isLeadership,
  canCreate,
  curTab,
  tabs,
  showSupplyForm,
  setShowSupplyForm,
  setSupplyTab,
  setShowForm,
}) {
  const subtitle =
    role === 'мастер' || role === 'субподрядчик'
      ? 'Создавайте заявки когда нужен материал на стройку'
      : role === 'прораб'
        ? 'Подтверждайте заявки мастеров и создавайте свои'
        : isLeadership
          ? 'Утверждайте заявки. Проверяйте склад через AI'
          : 'Утверждённые заявки на закупку';

  const showCreateButton = canCreate && curTab !== 'catalog' && curTab !== 'invoices' && curTab !== 'suppliers';

  const selectTab = (tabId) => {
    setSupplyTab(tabId);
    setShowSupplyForm(false);
    if (tabId !== 'suppliers') setShowForm(false);
  };

  return (
    <>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
        <div>
          <b style={{color:C.text,fontSize:'18px',display:'block'}}>🛒 Снабжение — Заявки на материалы</b>
          <p style={{color:C.textSec,fontSize:'12px',margin:'2px 0 0'}}>{subtitle}</p>
        </div>
        {showCreateButton && (
          <button onClick={()=>setShowSupplyForm(!showSupplyForm)} style={btnO}>
            <Plus size={14}/>Новая заявка
          </button>
        )}
      </div>

      <div style={{display:'flex',gap:'8px',marginBottom:'16px',flexWrap:'wrap'}}>
        {tabs.map(t=>(
          <button
            key={t.id}
            onClick={()=>selectTab(t.id)}
            style={{...(curTab===t.id?btnO:btnG),fontSize:'12px',padding:'7px 14px'}}
          >
            {t.label}
          </button>
        ))}
      </div>
    </>
  );
}

export default SupplyHeaderTabs;
