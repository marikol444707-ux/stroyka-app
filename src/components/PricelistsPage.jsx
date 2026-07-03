import React from 'react';
import { Bot, Check, Copy, Download, Edit2, Eye, FileText, Plus, Search, Tag, Trash2, X } from 'lucide-react';
import { createGeneratePricelistForm, createFromEstimateForm } from '../features/estimates/estimateInitialForms';
import { createPricelistForm, createPricelistItemForm } from '../features/pricelists/pricelistInitialForms';

export default function PricelistsPage({
  API,
  C,
  PRICELISTS_DATA,
  UNITS,
  buildPricelistContent,
  btnB,
  btnG,
  btnGr,
  btnO,
  btnR,
  card,
  copyPricelist,
  deletePlItem,
  deletePricelist,
  editingPlItem,
  exportToExcel,
  inlineEditPl,
  inlineEditPlData,
  inp,
  listSearch,
  loadAll,
  loadPricelistItems,
  matchSearch,
  newPlItem,
  newPricelist,
  pricelistItems,
  pricelists,
  saveInlinePlItem,
  savePlItem,
  savePricelist,
  selectedPricelist,
  setEditingItem,
  setEditingPlItem,
  setFromEstimateForm,
  setGeneratePricelistForm,
  setInlineEditPlData,
  setInlineEditPrice,
  setListSearch,
  setNewPlItem,
  setNewPricelist,
  setPricelistItems,
  setSelectedPricelist,
  setShowForm,
  setShowFromEstimate,
  setShowGeneratePricelist,
  showForm,
  showPreview,
  startInlinePlEdit,
  cancelInlinePlEdit,
  tbl,
  tblC,
  tblH,
}) {
  return (
    <div>
      <div style={{display:'flex',gap:'16px',height:'calc(100vh - 120px)'}}>
        <div style={{width:'280px',flexShrink:0,display:'flex',flexDirection:'column',gap:'10px',overflowY:'auto'}}>
          <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewPricelist(createPricelistForm());setSelectedPricelist(null);setPricelistItems([]);}} style={{...btnO,justifyContent:'center'}}><Plus size={14}/>Новый прайс-лист</button>
          <button onClick={()=>{setGeneratePricelistForm(createGeneratePricelistForm());setShowGeneratePricelist(true);}} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',justifyContent:'center'}}><Bot size={14}/>🤖 Сгенерировать ИИ</button>
          <button onClick={()=>{setFromEstimateForm(createFromEstimateForm());setShowFromEstimate(true);}} style={{...btnB,justifyContent:'center'}}><FileText size={14}/>📋 Из сметы</button>
          {showForm&&!selectedPricelist&&(<div style={{...card,padding:'20px'}}><div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}><input placeholder="Название *" value={newPricelist.name} onChange={e=>setNewPricelist({...newPricelist,name:e.target.value})} style={{...inp,marginBottom:0}}/><select value={newPricelist.forWho} onChange={e=>setNewPricelist({...newPricelist,forWho:e.target.value})} style={{...inp,marginBottom:0}}><option value="">Для кого</option>{['Электрики','Сантехники','Каменщики','Отделочники','Кровельщики','Монтажники','Общий'].map(r=><option key={r}>{r}</option>)}</select></div><label style={{color:C.textSec,fontSize:'13px',display:'block',marginTop:'10px',marginBottom:'4px'}}>{'Коэффициент: ×'+newPricelist.coefficient}</label><input type="range" min="0.5" max="3" step="0.1" value={newPricelist.coefficient} onChange={e=>setNewPricelist({...newPricelist,coefficient:Number(e.target.value)})} style={{width:'100%',marginBottom:'12px',accentColor:C.accent}}/><div style={{display:'flex',gap:'10px'}}><button onClick={savePricelist} style={btnO}>Сохранить</button><button onClick={()=>{setShowForm(false);setEditingItem(null);}} style={btnG}>Отмена</button></div></div>)}
          {pricelists.map(pl=>(<div key={pl.id} onClick={async()=>{setSelectedPricelist(pl);await loadPricelistItems(pl.id);setShowForm(false);setEditingPlItem(null);}} style={{...card,padding:'14px',cursor:'pointer',border:'1.5px solid '+(selectedPricelist?.id===pl.id?C.accent:C.border),backgroundColor:selectedPricelist?.id===pl.id?C.accentLight:C.bgWhite}}>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
              <div style={{flex:1}}><h3 style={{margin:0,color:C.text,fontSize:'14px',fontWeight:'600'}}>{pl.name}</h3>{pl.forWho&&<p style={{color:C.accent,margin:'3px 0',fontSize:'12px'}}>{'Для: '+pl.forWho}</p>}<p style={{color:C.info,margin:'3px 0',fontSize:'12px'}}>{'Коэф.: ×'+pl.coefficient}</p></div>
              <div style={{display:'flex',gap:'4px'}} onClick={e=>e.stopPropagation()}><button onClick={()=>copyPricelist(pl)} style={{...btnG,padding:'3px 7px',fontSize:'10px'}}><Copy size={10}/></button><button onClick={()=>deletePricelist(pl.id)} style={{...btnR,padding:'3px 7px'}}><Trash2 size={10}/></button></div>
            </div>
          </div>))}
        </div>
        <div style={{flex:1,overflowY:'auto'}}>
          {selectedPricelist?(<div>
            <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',marginBottom:'20px',flexWrap:'wrap',gap:'10px'}}>
              <div><h3 style={{margin:0,color:C.text,fontWeight:'700'}}>{selectedPricelist.name}</h3>{selectedPricelist.forWho&&<p style={{color:C.accent,margin:'4px 0',fontSize:'13px'}}>{'Для: '+selectedPricelist.forWho}</p>}<div style={{display:'flex',alignItems:'center',gap:'8px',marginTop:'4px'}}><span style={{color:C.textSec,fontSize:'13px'}}>Коэффициент: ×</span><input type='number' inputMode='decimal' step='0.1' min='0.1' max='10' value={selectedPricelist.coefficient} onChange={e=>setSelectedPricelist(prev=>({...prev,coefficient:Number(e.target.value)}))} onKeyDown={async e=>{if(e.key==='Enter'){await fetch(API+'/pricelists/'+selectedPricelist.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...selectedPricelist,coefficient:Number(e.target.value)})});await loadAll();alert('Сохранено!');}}} style={{width:'70px',padding:'4px 8px',border:'1.5px solid '+C.accent,borderRadius:'6px',fontSize:'13px',fontWeight:'600',color:C.accent}}/><span style={{color:C.textMuted,fontSize:'11px'}}>Enter для сохранения</span></div></div>
              <div style={{display:'flex',gap:'8px',flexWrap:'wrap'}}>
                <button onClick={()=>showPreview(buildPricelistContent(selectedPricelist,pricelistItems),'Прайс-лист')} style={btnB}><Eye size={14}/>Просмотр</button>
                <button onClick={()=>exportToExcel(pricelistItems.map(i=>({Категория:i.category||'',Наименование:i.name,Единица:i.unit,Цена:i.price,'С коэф.':i.price*selectedPricelist.coefficient})),'Прайс_'+selectedPricelist.name)} style={btnG}><Download size={14}/>Excel</button>
              </div>
            </div>
            <div style={{...card,padding:'16px',marginBottom:'16px'}}>
              <h4 style={{color:C.text,marginBottom:'12px',fontSize:'13px',fontWeight:'600'}}>{editingPlItem?'Редактировать позицию':'Добавить позицию'}</h4>
              <div style={{display:'grid',gridTemplateColumns:'3fr 1fr 1fr 2fr auto',gap:'8px',alignItems:'center'}}>
                <input placeholder="Наименование *" value={newPlItem.name} onChange={e=>setNewPlItem({...newPlItem,name:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}/>
                <select value={newPlItem.unit} onChange={e=>setNewPlItem({...newPlItem,unit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
                <input placeholder="Цена *" type="number" step="any" inputMode="decimal" value={newPlItem.price} onChange={e=>setNewPlItem({...newPlItem,price:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}/>
                <select value={newPlItem.category} onChange={e=>setNewPlItem({...newPlItem,category:e.target.value})} style={{...inp,marginBottom:0,fontSize:'13px'}}><option value="">Категория</option>{Object.keys(PRICELISTS_DATA).map(c=><option key={c}>{c}</option>)}</select>
                <button onClick={savePlItem} style={{...btnO,padding:'8px 14px'}}><Check size={14}/>{editingPlItem?'Сохр.':'Добавить'}</button>
              </div>
              {editingPlItem&&<button onClick={()=>{setEditingPlItem(null);setNewPlItem(createPricelistItemForm());}} style={{...btnG,marginTop:'8px',fontSize:'12px'}}><X size={12}/>Отменить</button>}
            </div>
            <div style={{position:'relative',marginBottom:'12px'}}>
              <Search size={14} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
              <input placeholder='🔍 Поиск позиции прайса' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'32px'}}/>
            </div>
            {[...new Set(pricelistItems.map(i=>(i.category||'').trim()))].sort((a,b)=>a==='' ? 1 : b==='' ? -1 : a.localeCompare(b,'ru')).map(cat=>{
              const catItems=pricelistItems.filter(i=>(i.category||'').trim()===cat&&matchSearch(listSearch,i.name,i.category));
              if(catItems.length===0) return null;
              return(<div key={cat||'nocat'} style={{marginBottom:'20px'}}>
                {cat&&<div style={{padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border,marginBottom:'8px',display:'flex',alignItems:'center',gap:'8px'}}><b style={{color:C.accent,fontSize:'12px',textTransform:'uppercase'}}>{'🔧 '+cat}</b><span style={{color:C.textSec,fontSize:'11px'}}>{'('+catItems.length+' позиций)'}</span></div>}
                <table style={tbl}><thead><tr><th style={tblH}>Наименование</th><th style={tblH}>Ед.</th><th style={tblH}>Цена</th><th style={tblH}>С коэф.</th><th style={tblH}></th></tr></thead><tbody>
                  {catItems.map(item=>{
                    const editing = inlineEditPl===item.id;
                    const editKey = async e => { if(e.key==='Enter') await saveInlinePlItem(item); if(e.key==='Escape') cancelInlinePlEdit(); };
                    return (<tr key={item.id}>
                      <td style={tblC}>{editing?<input value={inlineEditPlData.name} onChange={e=>setInlineEditPlData({...inlineEditPlData,name:e.target.value})} onKeyDown={editKey} autoFocus style={{...inp,marginBottom:0,fontSize:'12px',padding:'5px 8px',minWidth:'260px'}}/>:item.name}</td>
                      <td style={tblC}>{editing?<select value={inlineEditPlData.unit} onChange={e=>setInlineEditPlData({...inlineEditPlData,unit:e.target.value})} onKeyDown={editKey} style={{...inp,marginBottom:0,fontSize:'12px',padding:'5px 8px',width:'82px'}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>:item.unit}</td>
                      <td style={tblC}>{editing?<input type='number' step='any' inputMode='decimal' value={inlineEditPlData.price} onChange={e=>{setInlineEditPlData({...inlineEditPlData,price:e.target.value});setInlineEditPrice(e.target.value);}} onKeyDown={editKey} style={{...inp,marginBottom:0,fontSize:'12px',padding:'5px 8px',width:'105px'}}/>:<span style={{cursor:'pointer',fontWeight:'500'}} onClick={()=>startInlinePlEdit(item)}>{item.price.toLocaleString()+' ₽'}</span>}</td>
                      <td style={{...tblC,color:C.info,fontWeight:'600'}}>{((editing?Number(inlineEditPlData.price||0):item.price)*selectedPricelist.coefficient).toLocaleString()+' ₽'}</td>
                      <td style={tblC}><div style={{display:'flex',gap:'4px'}}>{editing?<><button onClick={()=>saveInlinePlItem(item)} style={{...btnGr,padding:'3px 8px',fontSize:'11px'}}><Check size={11}/></button><button onClick={cancelInlinePlEdit} style={{...btnG,padding:'3px 8px',fontSize:'11px'}}><X size={11}/></button></>:<><button onClick={()=>startInlinePlEdit(item)} style={{...btnG,padding:'3px 8px',fontSize:'11px'}}><Edit2 size={11}/></button><button onClick={()=>deletePlItem(item.id)} style={{...btnR,padding:'3px 6px'}}><Trash2 size={11}/></button></>}</div></td>
                    </tr>);
                  })}
                </tbody></table>
              </div>);
            })}
            {pricelistItems.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Позиций нет — добавьте первую!</p>}
          </div>):(<div style={{...card,padding:'60px',textAlign:'center',color:C.textMuted}}><Tag size={48} style={{marginBottom:'15px',opacity:0.3}}/><p>Выберите прайс-лист</p></div>)}
        </div>
      </div>
    </div>
  );
}
