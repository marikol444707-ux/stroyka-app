import React from 'react';
import { Check, X } from 'lucide-react';

export default function OwnExpenseFormModal({
  showOwnExpenseForm,
  setShowOwnExpenseForm,
  C,
  card,
  inp,
  btnO,
  btnG,
  projectOptions,
  expenseCategories,
  newOwnExpense,
  setNewOwnExpense,
  appendPhotos,
  fileSrc,
  API,
  user,
  loadAll,
  notify,
  showInfo = false,
  validationAlert = false,
}) {
  if (!showOwnExpenseForm) return null;

  const reset = () => {
    setShowOwnExpenseForm(false);
    setNewOwnExpense({projectName:'',category:'other',description:'',amount:'',photoUrl:'',date:''});
  };

  const submit = async () => {
    if(!newOwnExpense.description||!newOwnExpense.amount) {
      if (validationAlert) alert('Заполните: описание и сумму');
      return;
    }
    await fetch(API+'/own-expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({...newOwnExpense,amount:Number(newOwnExpense.amount),employeeName:user.name,employeeId:user.id})});
    setNewOwnExpense({projectName:'',category:'other',description:'',amount:'',photoUrl:'',date:''});
    setShowOwnExpenseForm(false);
    await loadAll();
    if (notify) notify('Трата отправлена на возмещение','myexpense');
    alert('Отправлено на возмещение!');
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>💸 Потратил свои деньги</b>
        <select value={newOwnExpense.projectName} onChange={e=>setNewOwnExpense({...newOwnExpense,projectName:e.target.value})} style={inp}><option value=''>Без объекта / личная трата</option>{projectOptions.map(proj=><option key={proj.id} value={proj.name}>{proj.name}</option>)}</select>
        <select value={newOwnExpense.category||'other'} onChange={e=>setNewOwnExpense({...newOwnExpense,category:e.target.value})} style={inp}><option value=''>Категория затрат *</option>{expenseCategories.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}</select>
        <input placeholder='За что потрачено *' value={newOwnExpense.description} onChange={e=>setNewOwnExpense({...newOwnExpense,description:e.target.value})} style={inp}/>
        <input placeholder='Сумма (₽) *' type='number' step='any' inputMode='decimal' value={newOwnExpense.amount} onChange={e=>setNewOwnExpense({...newOwnExpense,amount:e.target.value})} style={inp}/>
        <input type='date' value={newOwnExpense.date} onChange={e=>setNewOwnExpense({...newOwnExpense,date:e.target.value})} style={inp}/>
        <div style={{marginBottom:'12px'}}>
          <span style={{fontSize:'12px',color:C.textSec,display:'block',marginBottom:'6px'}}>📷 Фото чеков (можно несколько):</span>
          <label style={{cursor:'pointer'}}>
            <input type='file' accept='image/*' multiple capture='environment' style={{display:'none'}} onChange={async e=>{
              if(e.target.files&&e.target.files.length>0){
                const newCsv = await appendPhotos(newOwnExpense.photoUrl, e.target.files,{projectName:newOwnExpense.projectName,context:'own-expenses'});
                setNewOwnExpense(prev=>({...prev,photoUrl:newCsv}));
                e.target.value='';
              }
            }}/>
            {(()=>{const urls=(newOwnExpense.photoUrl||'').split(',').filter(Boolean);
              if (urls.length===0) return (<div style={{border:'2px dashed '+C.border,borderRadius:'8px',padding:'16px',textAlign:'center',color:C.textMuted,fontSize:'12px'}}>📷 Нажмите чтобы добавить фото<br/><span style={{fontSize:'10px'}}>можно несколько за раз</span></div>);
              return (<div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(80px,1fr))',gap:'6px',marginBottom:'8px'}}>
                  {urls.map((u,i)=>(<div key={i} style={{position:'relative'}}>
                    <img src={fileSrc(u)} alt='' style={{width:'100%',height:'80px',objectFit:'cover',borderRadius:'6px',border:'1px solid '+C.border}}/>
                    <button type='button' onClick={(ev)=>{ev.preventDefault();ev.stopPropagation();const rem=urls.filter((_,j)=>j!==i).join(',');setNewOwnExpense(prev=>({...prev,photoUrl:rem}));}} style={{position:'absolute',top:'2px',right:'2px',background:'rgba(220,38,38,0.9)',color:'white',border:'none',borderRadius:'50%',width:'20px',height:'20px',cursor:'pointer',fontSize:'12px',lineHeight:'1',padding:0}}>×</button>
                  </div>))}
                </div>
                <div style={{padding:'8px',backgroundColor:C.bg,borderRadius:'6px',textAlign:'center',fontSize:'11px',color:C.accent,fontWeight:'600'}}>+ Добавить ещё фото ({urls.length} загружено)</div>
              </div>);
            })()}
          </label>
        </div>
        {showInfo&&(<div style={{padding:'10px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,borderRadius:'8px',marginBottom:'10px',fontSize:'12px',color:C.text}}>
          ℹ️ После отправки трата попадёт бухгалтеру/директору на возмещение.
        </div>)}
        <div style={{display:'flex',gap:'8px'}}>
          <button onClick={submit} style={btnO}><Check size={14}/>Отправить</button>
          <button onClick={reset} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
