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
  isMobile = false,
}) {
  const filteredClients = (clients || []).filter(c => matchSearch(listSearch, c.name, c.phone, c.email));
  const fieldStyle = {...inp,marginBottom:0,minWidth:0,width:'100%',boxSizing:'border-box'};

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'20px',gap:'10px',flexWrap:'wrap'}}>
        <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewClient({name:'',phone:'',email:'',status:'Активный',notes:''});}} style={{...btnO,width:isMobile?'100%':'auto',justifyContent:'center',minHeight:isMobile?'44px':undefined}}><Plus size={14}/>Новый клиент</button>
      </div>
      {showForm&&(<div style={{...card,padding:isMobile?'14px':'20px',marginBottom:'20px',maxWidth:isMobile?'720px':undefined,marginLeft:isMobile?'auto':undefined,marginRight:isMobile?'auto':undefined}}>
        <h3 style={{color:C.text,marginBottom:'15px',fontWeight:'700'}}>{editingItem?'Редактировать':'Новый клиент'}</h3>
        <div style={{display:'grid',gridTemplateColumns:isMobile?'1fr':'repeat(auto-fit,minmax(200px,1fr))',gap:'10px'}}>
          <input placeholder="Название *" value={newClient.name} onChange={e=>setNewClient({...newClient,name:e.target.value})} style={fieldStyle}/>
          <input placeholder="Телефон" value={newClient.phone} onChange={e=>setNewClient({...newClient,phone:e.target.value})} style={fieldStyle}/>
          <input placeholder="Email" value={newClient.email} onChange={e=>setNewClient({...newClient,email:e.target.value})} style={fieldStyle}/>
          <select value={newClient.status} onChange={e=>setNewClient({...newClient,status:e.target.value})} style={fieldStyle}>{['Активный','Потенциальный','Завершён'].map(s=><option key={s}>{s}</option>)}</select>
          <textarea placeholder="Заметки" value={newClient.notes} onChange={e=>setNewClient({...newClient,notes:e.target.value})} style={{...fieldStyle,gridColumn:isMobile?'auto':'span 2',height:isMobile?'88px':'60px',resize:'vertical'}}/>
        </div>
        <div style={{display:'flex',gap:'10px',marginTop:'15px',flexWrap:'wrap'}}><button onClick={saveClient} style={{...btnO,flex:isMobile?'1 1 160px':'0 0 auto',justifyContent:'center',minHeight:isMobile?'44px':undefined}}><Check size={14}/>{editingItem?'Сохранить':'Создать'}</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={{...btnG,flex:isMobile?'1 1 140px':'0 0 auto',justifyContent:'center',minHeight:isMobile?'44px':undefined}}><X size={14}/>Отмена</button></div>
      </div>)}
      <div style={{position:'relative',marginBottom:'12px'}}>
        <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
        <input placeholder='🔍 Поиск клиента' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px'}}/>
      </div>
      {filteredClients.map(c=>(<div key={c.id} style={{...card,marginBottom:'10px'}}>
        <div style={{padding:isMobile?'14px':'16px',display:'flex',justifyContent:'space-between',alignItems:isMobile?'flex-start':'center',gap:'10px',cursor:'pointer',flexWrap:isMobile?'wrap':'nowrap'}} onClick={()=>setExpandedClient(expandedClient===c.id?null:c.id)}>
          <div style={{minWidth:0,flex:'1 1 220px'}}><b style={{color:C.text,fontSize:'14px',display:'block',overflowWrap:'anywhere'}}>{c.name}</b><p style={{color:C.textSec,margin:'3px 0',fontSize:'12px',overflowWrap:'anywhere'}}>{c.phone+(c.email?' · '+c.email:'')}</p></div>
          <div style={{display:'flex',gap:'6px',alignItems:'center',flex:'0 0 auto'}}>
            <button onClick={e=>{e.stopPropagation();setEditingItem(c);setNewClient({...c});setShowForm(true);}} style={{...btnG,padding:isMobile?'8px 10px':'5px 10px',fontSize:'11px',minWidth:isMobile?'38px':undefined,justifyContent:'center'}}><Edit2 size={11}/></button>
            <button onClick={e=>{e.stopPropagation();deleteClient(c.id);}} style={{...btnR,padding:isMobile?'8px 10px':'5px 10px',fontSize:'11px',minWidth:isMobile?'38px':undefined,justifyContent:'center'}}><Trash2 size={11}/></button>
          </div>
        </div>
        {expandedClient===c.id&&(<div style={{borderTop:'1.5px solid '+C.border,padding:'16px'}}>
          <p style={{color:C.textSec,fontSize:'13px',overflowWrap:'anywhere'}}>{c.notes||'Заметок нет'}</p>
          <b style={{color:C.text,fontSize:'13px',display:'block',marginTop:'10px',marginBottom:'8px'}}>Проекты клиента:</b>
          {projects.filter(p=>p.client===c.name).map(p=>(<div key={p.id} style={{padding:'8px 10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:isMobile?'wrap':'nowrap'}}><span style={{fontSize:'13px',color:C.text,overflowWrap:'anywhere'}}>{p.name}</span><span style={{fontSize:'12px',color:C.textSec}}>{p.status}</span></div>))}
          {projects.filter(p=>p.client===c.name).length===0&&<p style={{color:C.textMuted,fontSize:'12px'}}>Проектов нет</p>}
        </div>)}
      </div>))}
      {clients.length===0&&<div style={{...card,padding:'40px',textAlign:'center',color:C.textMuted}}>Клиентов нет</div>}
    </div>
  );
}
