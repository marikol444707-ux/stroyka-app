import React from 'react';
import { Check, Edit2, Plus, Search, Trash2, X } from 'lucide-react';
import { API } from '../api';

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
}) {
  const canEditSuppliers = ['директор','зам_директора','кладовщик','снабженец'].includes(user.role);
  const emptySupplier = {name:'',phone:'',email:'',specialization:'',category:'Сыпучие и бетон',rating:5.0,status:'Активный'};

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

  const editSupplier = (supplier) => {
    setEditingItem(supplier);
    setNewSupplier({...supplier});
    setShowForm(true);
  };

  const updateRating = async (supplier, rating) => {
    if (!canEditSuppliers) return;
    await fetch(API+'/suppliers/'+supplier.id,{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({...supplier,rating}),
    });
    await loadAll();
  };

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',gap:'8px',flexWrap:'wrap'}}>
        <div>
          <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>🚚 Поставщики</b>
          <p style={{color:C.textSec,fontSize:'11px',margin:'2px 0 0'}}>Справочник поставщиков теперь находится внутри снабжения.</p>
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
        <input placeholder='🔍 Поиск поставщика' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px'}}/>
      </div>

      {supplierCategories.map(category=>{
        const catSuppliers = suppliers.filter(s=>s.category===category&&matchSearch(listSearch,s.name,s.specialization,s.phone,s.email));
        if (catSuppliers.length===0) return null;
        return (
          <div key={category} style={{marginBottom:'20px'}}>
            <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
              <b style={{color:C.accent,fontSize:'13px'}}>{'🏭 '+category}</b>
              <span style={{color:C.textSec,fontSize:'12px'}}>{'('+catSuppliers.length+')'}</span>
            </div>
            {catSuppliers.map(supplier=>(
              <div key={supplier.id} style={{...card,padding:'14px',marginBottom:'8px',marginLeft:'12px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                  <div>
                    <b style={{color:C.text,fontSize:'13px'}}>{supplier.name}</b>
                    <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{supplier.phone+(supplier.email?' · '+supplier.email:'')+(supplier.specialization?' · '+supplier.specialization:'')}</p>
                    <div style={{display:'flex',gap:'4px',marginTop:'4px'}}>
                      {[1,2,3,4,5].map(star=>(
                        <span key={star} style={{color:star<=supplier.rating?'#f59e0b':'#d1d5db',fontSize:'14px',cursor:canEditSuppliers?'pointer':'default'}} onClick={()=>updateRating(supplier, star)}>★</span>
                      ))}
                    </div>
                  </div>
                  {canEditSuppliers&&(
                    <div style={{display:'flex',gap:'6px'}}>
                      <button onClick={()=>editSupplier(supplier)} style={{...btnG,padding:'5px 10px'}}><Edit2 size={11}/></button>
                      <button onClick={()=>deleteSupplier(supplier.id)} style={{...btnR,padding:'5px 10px'}}><Trash2 size={11}/></button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        );
      })}

      {suppliers.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Поставщиков нет</p>}
    </div>
  );
}

export default SupplySuppliersPanel;
