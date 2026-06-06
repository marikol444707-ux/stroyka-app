import React from 'react';
import { Check, Edit2, Plus, Trash2, X } from 'lucide-react';

export default function WarehouseCompanyWarehousesPanel({
  warehouses,
  showForm,
  setShowForm,
  editingItem,
  setEditingItem,
  newWarehouse,
  setNewWarehouse,
  saveWarehouse,
  deleteWarehouse,
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
}) {
  const resetForm = () => {
    setEditingItem(null);
    setNewWarehouse({name:'',city:'',address:'',notes:''});
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
        <b style={{color:C.text}}>Склады компании</b>
        <button onClick={() => {setShowForm(!showForm); resetForm();}} style={btnO}><Plus size={14}/>Добавить склад</button>
      </div>

      {showForm && (
        <div style={{...card,padding:'20px',marginBottom:'16px'}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
            <input placeholder="Название склада *" value={newWarehouse.name} onChange={event => setNewWarehouse({...newWarehouse,name:event.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Город" value={newWarehouse.city} onChange={event => setNewWarehouse({...newWarehouse,city:event.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder="Адрес" value={newWarehouse.address} onChange={event => setNewWarehouse({...newWarehouse,address:event.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2'}}/>
            <textarea placeholder="Заметки" value={newWarehouse.notes} onChange={event => setNewWarehouse({...newWarehouse,notes:event.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
          </div>
          <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
            <button onClick={saveWarehouse} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Добавить'}</button>
            <button onClick={() => {setShowForm(false); setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button>
          </div>
        </div>
      )}

      {(warehouses || []).map(warehouse => (
        <div key={warehouse.id} style={{...card,padding:'16px',marginBottom:'10px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
          <div>
            <b style={{color:C.text,fontSize:'14px'}}>{'🏭 '+warehouse.name}</b>
            <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{(warehouse.city?warehouse.city+', ':'')+warehouse.address}</p>
            {warehouse.notes&&<p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{warehouse.notes}</p>}
          </div>
          <div style={{display:'flex',gap:'6px'}}>
            <button onClick={() => {setEditingItem(warehouse);setNewWarehouse({name:warehouse.name,city:warehouse.city,address:warehouse.address,notes:warehouse.notes});setShowForm(true);}} style={{...btnG,padding:'5px 10px'}}><Edit2 size={11}/></button>
            <button onClick={() => deleteWarehouse(warehouse.id)} style={{...btnR,padding:'5px 10px'}}><Trash2 size={11}/></button>
          </div>
        </div>
      ))}

      {(warehouses || []).length===0&&<div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Складов нет — добавьте первый!</div>}
    </div>
  );
}
