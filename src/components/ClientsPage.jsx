import React from 'react';
import { Check, Edit2, Plus, Search, Trash2, X } from 'lucide-react';

export default function ClientsPage({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnR,
  clients,
  projects,
  showForm,
  setShowForm,
  editingItem,
  setEditingItem,
  newClient,
  setNewClient,
  saveClient,
  listSearch,
  setListSearch,
  expandedClient,
  setExpandedClient,
  deleteClient,
  matchSearch,
}) {
  const filteredClients = (clients || []).filter(c => matchSearch(listSearch, c.name, c.phone, c.email));

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px'}}>
        <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewClient({name:'',phone:'',email:'',status:'Активный',notes:''});}} style={btnO}><Plus size={14}/>Новый клиент</button>
      </div>
      {showForm&&(<div style={{...card,padding:'20px',marginBottom:'20px'}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать':'Новый клиент'}</h3>
        <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(200px,1fr))',gap:'10px'}}>
          <input placeholder="Название *" value={newClient.name} onChange={e=>setNewClient({...newClient,name:e.target.value})} style={{...inp,marginBottom:0}}/>
          <input placeholder="Телефон" value={newClient.phone} onChange={e=>setNewClient({...newClient,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
          <input placeholder="Email" value={newClient.email} onChange={e=>setNewClient({...newClient,email:e.target.value})} style={{...inp,marginBottom:0}}/>
          <select value={newClient.status} onChange={e=>setNewClient({...newClient,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Активный','Потенциальный','Завершён'].map(s=><option key={s}>{s}</option>)}</select>
          <textarea placeholder="Заметки" value={newClient.notes} onChange={e=>setNewClient({...newClient,notes:e.target.value})} style={{...inp,marginBottom:0,gridColumn:'span 2',height:'60px',resize:'vertical'}}/>
        </div>
        <div style={{display:'flex',gap:'10px',marginTop:'15px'}}><button onClick={saveClient} style={btnO}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}><X size={14}/>Отмена</button></div>
      </div>)}
      <div style={{position:'relative',marginBottom:'12px'}}>
        <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
        <input placeholder='🔍 Поиск клиента' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px'}}/>
      </div>
      {filteredClients.map(c=>(<div key={c.id} style={{...card,marginBottom:'10px'}}>
        <div style={{padding:'16px',display:'flex',justifyContent:'space-between',alignItems:'center',cursor:'pointer'}} onClick={()=>setExpandedClient(expandedClient===c.id?null:c.id)}>
          <div><b style={{color:C.text,fontSize:'14px'}}>{c.name}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>{c.phone+(c.email?' · '+c.email:'')}</p></div>
          <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
            <button onClick={e=>{e.stopPropagation();setEditingItem(c);setNewClient({...c});setShowForm(true);}} style={{...btnG,padding:'5px 10px',fontSize:'11px'}}><Edit2 size={11}/></button>
            <button onClick={e=>{e.stopPropagation();deleteClient(c.id);}} style={{...btnR,padding:'5px 10px',fontSize:'11px'}}><Trash2 size={11}/></button>
          </div>
        </div>
        {expandedClient===c.id&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'16px'}}>
          <p style={{color:C.textSec,fontSize:'13px'}}>{c.notes||'Заметок нет'}</p>
          <b style={{color:C.text,fontSize:'13px',display:'block',marginTop:'10px',marginBottom:'8px'}}>Проекты клиента:</b>
          {projects.filter(p=>p.client===c.name).map(p=>(<div key={p.id} style={{padding:'8px 10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center'}}><span style={{fontSize:'13px',color:C.text}}>{p.name}</span><span style={{fontSize:'12px',color:C.textSec}}>{p.status}</span></div>))}
          {projects.filter(p=>p.client===c.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Проектов нет</p>}
        </div>)}
      </div>))}
      {clients.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Клиентов нет</div>}
    </div>
  );
}

