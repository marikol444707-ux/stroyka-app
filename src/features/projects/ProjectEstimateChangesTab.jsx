import React from 'react';

export default function ProjectEstimateChangesTab({ ctx, project }) {
  const p = project;
  const {
    API, Bot, C, Check, EMPTY_ESTIMATE_CHANGE, ESTIMATE_CHANGE_TYPES, ESTIMATE_CHANGE_VISIBLE_STATUSES,
    Eye, FileText, GitBranch, Plus, UNITS, Upload, X, activeProjectTab, activeEstimatesForProject,
    appendPhotos, approveUnexpectedWork, badge, btnB, btnG, btnGr, btnO, btnR,
    buildSupplementaryAgreementContent, card, denormalizeMeasure, estimateChangesForNewEstimate,
    estimateItemOptionsForProject, estimatePackage, estimateReconciliationsForProject, fileSrc,
    fmtMeasure, includeChangesInNewEstimate, includableEstimateChanges, inp,
    isApprovedEstimateChangeStatus, isLeadership, newUnexpected, normalizeMeasure, refreshData,
    saveUnexpectedWork, setActiveProjectTab, setActiveTabGroup, setNewUnexpected, setShowForm,
    setShowPhotoModal, showForm, showPreview, signedEstimateChangeTotal, toNum, unexpectedWorksList,
    user,
  } = ctx;

  return (
    <>
      {activeProjectTab==='Изменения к смете'&&(<div>
        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
          <b style={{color:C.text}}>Изменения к смете</b>
          <button onClick={()=>setShowForm(showForm==='unexpected'?false:'unexpected')} style={btnO}><Plus size={14}/>Создать изменение</button>
        </div>
        {(()=>{const budget=Number(p.budget||0);if(budget<=0) return null;const approved=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status)&&u.changeType!=='Исключение объёма'&&!u.includedInEstimateId).reduce((s,u)=>s+Number(u.total||0),0);const pending=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&u.status==='Ожидает согласования'&&u.changeType!=='Исключение объёма').reduce((s,u)=>s+Number(u.total||0),0);const pct=Math.round(approved/budget*100*10)/10;const LIMIT=10;const overLimit=pct>LIMIT;if(approved===0&&pending===0) return null;return(<div style={{...card,padding:'12px',marginBottom:'14px',backgroundColor:overLimit?C.dangerLight:pct>LIMIT*0.7?C.warningLight:C.bg,border:'1.5px solid '+(overLimit?C.dangerBorder:pct>LIMIT*0.7?C.warningBorder:C.border)}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
            <div>
              <b style={{color:C.text,fontSize:'13px'}}>📊 Изменения отдельной допработой: {pct}% от бюджета (контрольный порог {LIMIT}%)</b>
              <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждено: {Math.round(approved).toLocaleString('ru-RU')+' ₽'} {pending>0?'· Ждут: '+Math.round(pending).toLocaleString('ru-RU')+' ₽':''}</p>
            </div>
            {overLimit&&<span style={{padding:'4px 10px',backgroundColor:C.danger,color:'white',borderRadius:'10px',fontSize:'11px',fontWeight:'700'}}>⚠️ ПРЕВЫШЕН ЛИМИТ</span>}
          </div>
          {overLimit&&<p style={{color:C.danger,margin:'8px 0 0',fontSize:'11px',lineHeight:1.4}}>Сумма изменений превысила 10% бюджета. Это не блокировка, но стоит выпустить доп.соглашение или новую редакцию сметы, чтобы КС не задвоились.</p>}
        </div>);})()}
        {(()=>{const all=includableEstimateChanges(p.name);if(all.length===0) return null;const activeEsts=activeEstimatesForProject(p,'Заказчик');const unlinked=all.filter(u=>!u.estimateId);if(activeEsts.length===0) return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder}}><b style={{color:C.warning,fontSize:'13px'}}>📐 Есть утверждённые изменения, но нет активной сметы заказчика</b><p style={{color:C.textSec,margin:'3px 0 0',fontSize:'11px'}}>Создайте или активируйте смету заказчика, чтобы включить изменения в новую версию без задвоения КС.</p></div>);return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'8px'}}>
            <div>
              <b style={{color:C.info,fontSize:'13px'}}>📐 Включение изменений в новую смету</b>
              <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждённые изменения можно перенести в новую активную версию сметы. После этого они не пойдут в КС отдельными строками.</p>
            </div>
            <span style={badge(C.info,C.bgWhite,C.infoBorder)}>{all.length+' изм.'}</span>
          </div>
          {activeEsts.map(est=>{const rows=estimateChangesForNewEstimate(p,est);if(rows.length===0) return null;const signed=signedEstimateChangeTotal(rows);return(<div key={est.id} style={{padding:'10px',backgroundColor:C.bgWhite,borderRadius:'8px',border:'1px solid '+C.border,marginTop:'8px',display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
            <div style={{minWidth:'220px',flex:1}}>
              <b style={{color:C.text,fontSize:'12px'}}>{est.name+' · v'+(est.version||'1.0')}</b>
              <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>{estimatePackage(est)+' · '+rows.length+' изм. · влияние '+(signed>0?'+':'')+Math.round(signed).toLocaleString('ru-RU')+' ₽'}</p>
            </div>
            <button onClick={()=>includeChangesInNewEstimate(p,est,rows)} style={{...btnB,padding:'6px 12px',fontSize:'12px'}}><GitBranch size={13}/>В новую смету</button>
          </div>);})}
          {activeEsts.length>1&&unlinked.length>0&&<p style={{color:C.warning,margin:'8px 0 0',fontSize:'11px'}}>Есть изменения без привязки к строке сметы: {unlinked.length}. При нескольких активных пакетах их нужно привязать вручную, чтобы не включить не туда.</p>}
        </div>);})()}
        {(()=>{const recs=estimateReconciliationsForProject(p.name);if(recs.length===0)return null;const openChecks=recs.reduce((s,r)=>s+Number(r.reviewCount||0),0);return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.bg,border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
          <div>
            <b style={{color:C.text,fontSize:'13px'}}>Связанные сверки смет: {recs.length}</b>
            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Спорных строк к проверке: {openChecks}. Сверка фиксирует, что вошло в новую смету, а что остаётся отдельной допработой.</p>
          </div>
          <button onClick={()=>{setActiveProjectTab('Сверки смет');setActiveTabGroup('work');}} style={{...btnB,padding:'6px 12px',fontSize:'12px'}}><FileText size={13}/>Открыть сверки</button>
        </div>);})()}
        {showForm==='unexpected'&&(<div style={{...card,padding:'16px',marginBottom:'16px',backgroundColor:C.bg}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
            <select value={newUnexpected.changeType} onChange={e=>setNewUnexpected({...EMPTY_ESTIMATE_CHANGE,changeType:e.target.value,price:newUnexpected.price})} style={{...inp,marginBottom:0}}>
              {ESTIMATE_CHANGE_TYPES.map(t=><option key={t}>{t}</option>)}
            </select>
            {(()=>{const opts=estimateItemOptionsForProject(p);return(<select value={[newUnexpected.estimateId||'',newUnexpected.sectionName||'',newUnexpected.estimateItemName||''].join('|')} disabled={newUnexpected.changeType!=='Дополнительный объём к строке сметы'||opts.length===0} onChange={e=>{const o=opts.find(x=>[x.estimateId,x.sectionName,x.name].join('|')===e.target.value);if(!o)return;setNewUnexpected({...newUnexpected,estimateId:o.estimateId,sectionName:o.sectionName,estimateItemName:o.name,description:o.name,unit:o.unit,baseQuantity:o.quantity,quantity:'',newRequiredQuantity:'',deltaQuantity:'',price:Math.round(o.pricePerUnit||0)});}} style={{...inp,marginBottom:0}}>
              <option value=''>{opts.length?'Привязать строку сметы':'Активная смета не найдена'}</option>
              {opts.map(o=><option key={o.key} value={[o.estimateId,o.sectionName,o.name].join('|')}>{(o.sectionName?o.sectionName+' / ':'')+o.name+' · '+fmtMeasure(o.quantity,o.unit)}</option>)}
            </select>);})()}
          </div>
          {newUnexpected.changeType==='Дополнительный объём к строке сметы'&&(<div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px',marginBottom:'8px',padding:'10px',borderRadius:'8px',backgroundColor:C.bgWhite,border:'1.5px solid '+C.border}}>
            <div><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>По активной смете</p><b style={{fontSize:'12px',color:C.text}}>{fmtMeasure(toNum(newUnexpected.baseQuantity),newUnexpected.unit)}</b></div>
            <input placeholder="Фактически нужно всего" type="number" step="any" inputMode="decimal" value={newUnexpected.newRequiredQuantity?normalizeMeasure(toNum(newUnexpected.newRequiredQuantity),newUnexpected.unit).qty:''} onChange={e=>{const raw=denormalizeMeasure(e.target.value,newUnexpected.unit);const delta=Math.max(0,raw-toNum(newUnexpected.baseQuantity));setNewUnexpected({...newUnexpected,newRequiredQuantity:raw,deltaQuantity:delta,quantity:delta});}} style={{...inp,marginBottom:0}}/>
            <div><p style={{margin:'0 0 4px',fontSize:'11px',color:C.textSec}}>Доп.объём</p><b style={{fontSize:'12px',color:toNum(newUnexpected.deltaQuantity)>0?C.warning:C.textMuted}}>{fmtMeasure(toNum(newUnexpected.deltaQuantity),newUnexpected.unit)}</b></div>
          </div>)}
          <textarea placeholder="Описание изменения *" value={newUnexpected.description} onChange={e=>setNewUnexpected({...newUnexpected,description:e.target.value})} style={{...inp,height:'80px',resize:'vertical'}}/>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px'}}>
            <input placeholder="Кол-во" type="number" step="any" inputMode="decimal" disabled={newUnexpected.changeType==='Дополнительный объём к строке сметы'} value={newUnexpected.quantity} onChange={e=>setNewUnexpected({...newUnexpected,quantity:e.target.value,deltaQuantity:e.target.value})} style={{...inp,marginBottom:0}}/>
            <select value={newUnexpected.unit} onChange={e=>setNewUnexpected({...newUnexpected,unit:e.target.value})} style={{...inp,marginBottom:0}}>{UNITS.map(u=><option key={u}>{u}</option>)}</select>
            <input placeholder="Цена (₽)" type="number" step="any" inputMode="decimal" value={newUnexpected.price} onChange={e=>setNewUnexpected({...newUnexpected,price:e.target.value})} style={{...inp,marginBottom:0}}/>
          </div>
          <textarea placeholder="Причина изменения (ошибка объёма, решение заказчика, фактические условия)" value={newUnexpected.reason} onChange={e=>setNewUnexpected({...newUnexpected,reason:e.target.value})} style={{...inp,height:'56px',resize:'vertical',marginTop:'8px'}}/>
          <div style={{display:'flex',gap:'8px',marginTop:'6px',flexWrap:'wrap'}}>
            <button disabled={!newUnexpected.description||!!newUnexpected.__aiLoading} onClick={async()=>{
              setNewUnexpected(prev=>({...prev,__aiLoading:true}));
              try {
                // Создаём временную запись чтобы AI имел id
                const tmpRes = await fetch(API+'/unexpected-works',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectName:p.name,description:newUnexpected.description,unit:newUnexpected.unit||'шт',quantity:Number(newUnexpected.quantity||0),changeType:newUnexpected.changeType,price:0,total:0,addedBy:user.name,addedByRole:user.role,status:'_ai_temp_'})});
                const tmp = await tmpRes.json();
                const aiRes = await fetch(API+'/unexpected-works/'+tmp.id+'/ai-estimate',{method:'POST'});
                if(!aiRes.ok){const e=await aiRes.json().catch(()=>({}));throw new Error(e.detail||'Ошибка');}
                const d = await aiRes.json();
                // Удаляем временную
                await fetch(API+'/unexpected-works/'+tmp.id,{method:'DELETE'}).catch(()=>{});
                setNewUnexpected(prev=>({...prev,price:Math.round(d.pricePerUnit),__aiLoading:false,__aiNote:d.justification}));
              } catch(e){alert('AI: '+e.message);setNewUnexpected(prev=>({...prev,__aiLoading:false}));}
            }} style={{...btnB,backgroundColor:'#10b981',color:'white',borderColor:'#059669',fontSize:'12px',padding:'7px 12px',opacity:newUnexpected.__aiLoading?0.6:1}}><Bot size={13}/>{newUnexpected.__aiLoading?'…':'🤖 Оценить через ИИ'}</button>
            {newUnexpected.__aiNote&&<span style={{fontSize:'11px',color:C.textSec,flex:1,fontStyle:'italic'}}>{newUnexpected.__aiNote}</span>}
          </div>
          <div style={{marginTop:'8px'}}>
            <div style={{display:'flex',gap:'8px',alignItems:'center',marginBottom:'6px'}}>
              <label style={{...btnB,padding:'8px 12px',fontSize:'12px',cursor:'pointer'}}><Upload size={12}/>📷 Прикрепить фото (можно несколько)<input type='file' accept='image/*' multiple style={{display:'none'}} onChange={async e=>{if(e.target.files&&e.target.files.length>0){const csv=await appendPhotos(newUnexpected.photoUrl,e.target.files,{projectName:p.name,context:'estimate-changes'});setNewUnexpected({...newUnexpected,photoUrl:csv});e.target.value='';}}}/></label>
              {(newUnexpected.photoUrl||'').split(',').filter(Boolean).length>0&&<span style={{fontSize:'11px',color:C.success,fontWeight:'600'}}>📷 {(newUnexpected.photoUrl||'').split(',').filter(Boolean).length} фото</span>}
            </div>
            {(()=>{const urls=(newUnexpected.photoUrl||'').split(',').filter(Boolean);if(urls.length===0) return null;return (<div style={{display:'flex',gap:'4px',flexWrap:'wrap'}}>{urls.map((u,i)=>(<div key={i} style={{position:'relative'}}><img src={fileSrc(u)} alt='' onClick={()=>setShowPhotoModal(fileSrc(u))} style={{width:'60px',height:'60px',objectFit:'cover',borderRadius:'6px',cursor:'pointer',border:'1px solid '+C.border}}/><button type='button' onClick={(ev)=>{ev.preventDefault();ev.stopPropagation();setNewUnexpected({...newUnexpected,photoUrl:urls.filter((_,j)=>j!==i).join(',')});}} style={{position:'absolute',top:'-4px',right:'-4px',background:'rgba(220,38,38,0.9)',color:'white',border:'none',borderRadius:'50%',width:'18px',height:'18px',cursor:'pointer',fontSize:'10px',lineHeight:'1',padding:0}}>×</button></div>))}</div>);})()}
          </div>
          <div style={{display:'flex',gap:'8px',marginTop:'10px'}}><button onClick={()=>saveUnexpectedWork(p.name)} style={btnO}><Check size={14}/>Отправить</button><button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button></div>
    </div>)}
        {(()=>{const approvedAll=(unexpectedWorksList||[]).filter(u=>u.projectName===p.name&&isApprovedEstimateChangeStatus(u.status));const ver=approvedAll.length+1;const sumDS=approvedAll.reduce((s,u)=>s+Number(u.total||0),0);if(approvedAll.length===0) return null;return(<div style={{...card,padding:'12px 14px',marginBottom:'14px',backgroundColor:C.infoLight,border:'1.5px solid '+C.infoBorder,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
          <div>
            <b style={{color:C.info,fontSize:'13px'}}>📜 Договор подряда — версия v{ver}</b>
            <p style={{color:C.textSec,margin:'2px 0 0',fontSize:'11px'}}>Утверждённых изменений: {approvedAll.length} на сумму {Math.round(sumDS).toLocaleString('ru-RU')+' ₽'}. Если их не включили в новую смету, они идут в КС отдельными разделами.</p>
          </div>
        </div>);})()}
        {ESTIMATE_CHANGE_VISIBLE_STATUSES.map(status=>{ const items=unexpectedWorksList.filter(u=>u.projectName===p.name&&u.status===status); if(items.length===0) return null; return(<div key={status} style={{marginBottom:'16px'}}><b style={{color:isApprovedEstimateChangeStatus(status)?C.success:status==='Отклонено'?C.danger:status==='Включено в новую смету'?C.info:C.warning,fontSize:'12px',display:'block',marginBottom:'8px'}}>{status==='Ожидает согласования'?'⏳':isApprovedEstimateChangeStatus(status)?'✅':status==='Включено в новую смету'?'📐':'❌'} {status} ({items.length})</b>{items.map((u,idx)=>{const dsNum=isApprovedEstimateChangeStatus(status)?(()=>{const arr=(unexpectedWorksList||[]).filter(x=>x.projectName===p.name&&isApprovedEstimateChangeStatus(x.status));return arr.length-arr.findIndex(x=>x.id===u.id);})():null;return(<div key={u.id} style={{padding:'12px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border}}><div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}><div style={{flex:1,minWidth:'200px'}}>{dsNum&&<b style={{fontSize:'11px',color:C.info,display:'block'}}>ДС № {dsNum} к договору подряда</b>}<span style={{display:'inline-block',padding:'2px 7px',borderRadius:'9px',backgroundColor:C.bgWhite,border:'1px solid '+C.border,color:C.textSec,fontSize:'10px',marginBottom:'4px'}}>{u.changeType||'Работа вне сметы'}</span><b style={{fontSize:'13px',color:C.text,display:'block'}}>{u.description}</b>{u.estimateItemName&&<p style={{color:C.info,margin:'2px 0',fontSize:'11px'}}>{'Строка сметы: '+(u.sectionName?u.sectionName+' / ':'')+u.estimateItemName}</p>}<p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{fmtMeasure(u.deltaQuantity||u.quantity,u.unit)+(u.price>0?' · '+u.price.toLocaleString()+' ₽/'+u.unit:'')+(u.total>0?' · Итого: '+u.total.toLocaleString()+' ₽':'')}</p><p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{'Добавил: '+u.addedBy+(u.approvedAt?' · Утв.: '+u.approvedAt:'')+(u.reason?' · Причина: '+u.reason:'')}</p></div><div style={{display:'flex',gap:'6px',alignItems:'center',flexWrap:'wrap'}}>{isApprovedEstimateChangeStatus(u.status)&&<button onClick={()=>showPreview(buildSupplementaryAgreementContent(u,p),'Доп.соглашение № '+dsNum+' к договору подряда — '+p.name)} style={{...btnB,padding:'4px 8px',fontSize:'11px'}} title='Печать доп.соглашения'><Eye size={11}/>🖨️ ДС</button>}{isLeadership()&&u.status==='Ожидает согласования'&&(<><input placeholder="Цена ₽" type="number" step="any" inputMode="decimal" defaultValue={u.price||''} style={{width:'90px',padding:'4px 8px',border:'1.5px solid '+C.border,borderRadius:'6px',fontSize:'12px'}} onChange={e=>e.target.dataset.price=e.target.value}/><button onClick={e=>{approveUnexpectedWork(u,e.target.previousSibling.dataset.price||u.price||0);}} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}><Check size={11}/>Утвердить</button><button onClick={async()=>{await fetch(API+'/unexpected-works/'+u.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({status:'Отклонено',approvedBy:user.name,approvedAt:new Date().toISOString().split('T')[0]})});await refreshData();}} style={{...btnR,padding:'4px 8px',fontSize:'11px'}}><X size={11}/>Откл.</button></>)}</div></div></div>);})}</div>);})}
        {unexpectedWorksList.filter(u=>u.projectName===p.name).length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'20px'}}>Изменений к смете нет</p>}
    </div>)}
    </>
  );
}
