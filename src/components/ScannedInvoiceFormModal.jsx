import React from 'react';
import { Check, Plus, X } from 'lucide-react';

export default function ScannedInvoiceFormModal({
  showScannedInvoiceForm,
  setShowScannedInvoiceForm,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  newInvoice,
  setNewInvoice,
  projects,
  units,
  saveInvoiceNew,
}) {
  if (!showScannedInvoiceForm) return null;

  const updateItem = (idx, patch) => {
    const items=[...newInvoice.items];
    items[idx]={...items[idx],...patch};
    setNewInvoice({...newInvoice,items});
  };

  const save = async () => {
    if(!newInvoice.number) return alert('Укажите номер накладной');
    if(!newInvoice.location) return alert('Выберите склад');
    const validItems=(newInvoice.items||[]).filter(i=>i.name&&Number(i.quantity)>0);
    if(!validItems.length) return alert('Добавьте хотя бы одну позицию');
    try{
      await saveInvoiceNew();
      setShowScannedInvoiceForm(false);
      alert('Накладная принята, материалы оприходованы!');
    }catch(e){alert('Ошибка: '+(e.message||e));}
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'380px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'4px'}}>📋 Накладная</b>
        <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>Проверьте данные и сохраните</p>
        <input placeholder='Номер накладной *' value={newInvoice.number||''} onChange={e=>setNewInvoice({...newInvoice,number:e.target.value})} style={inp}/>
        <input placeholder='Поставщик' value={newInvoice.supplier||newInvoice.newSupplierName||''} onChange={e=>setNewInvoice({...newInvoice,supplier:e.target.value,newSupplierName:e.target.value,isNewSupplier:true})} style={inp}/>
        <select value={newInvoice.location||''} onChange={e=>setNewInvoice({...newInvoice,location:e.target.value,project:e.target.value!=='Основной склад'?e.target.value:''})} style={inp}>
          <option value=''>Выберите склад *</option>
          <option value='Основной склад'>📦 Основной склад</option>
          {projects.map(p=><option key={p.id} value={p.name}>🏗️ {p.name}</option>)}
        </select>
        <input type='date' value={newInvoice.date||new Date().toISOString().split('T')[0]} onChange={e=>setNewInvoice({...newInvoice,date:e.target.value})} style={inp}/>
        <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Позиции:</b>
        {(newInvoice.items||[]).map((item,idx)=>(
          <div key={idx} style={{display:'grid',gridTemplateColumns:'2fr 0.7fr 0.7fr 1fr 24px',gap:'4px',marginBottom:'6px'}}>
            <input placeholder='Название' value={item.name} onChange={e=>updateItem(idx,{name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
            <input placeholder='Кол.' type='number' step='any' inputMode='decimal' value={item.quantity} onChange={e=>updateItem(idx,{quantity:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
            <select value={item.unit||'шт'} onChange={e=>updateItem(idx,{unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'11px',padding:'6px 4px'}}>{units.map(u=><option key={u}>{u}</option>)}</select>
            <input placeholder='Цена' type='number' step='any' inputMode='decimal' value={item.price} onChange={e=>updateItem(idx,{price:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
            <button onClick={()=>{const items=newInvoice.items.filter((_,i)=>i!==idx);if(!items.length)items.push({name:'',quantity:'',unit:'шт',price:'',category:''});setNewInvoice({...newInvoice,items});}} style={{...btnR,padding:'4px 6px',fontSize:'11px'}}><X size={12}/></button>
          </div>
        ))}
        <button onClick={()=>setNewInvoice({...newInvoice,items:[...(newInvoice.items||[]),{name:'',quantity:'',unit:'шт',price:'',category:''}]})} style={{...btnG,fontSize:'12px',padding:'6px 12px',marginBottom:'10px'}}><Plus size={12}/>Ещё позиция</button>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',margin:'8px 0'}}>
          <b style={{color:C.text,fontSize:'13px'}}>Итого: {(newInvoice.items||[]).reduce((s,i)=>s+Number(i.quantity||0)*Number(i.price||0),0).toLocaleString()} ₽</b>
        </div>
        <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
          <button onClick={save} style={btnO}><Check size={14}/>Сохранить</button>
          <button onClick={()=>setShowScannedInvoiceForm(false)} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
