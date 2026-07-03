import React from 'react';
import { Bot, Check, Edit2, Plus, Search, Trash2, X } from 'lucide-react';
import { API } from '../api';
import { createRequestForm, createSupplierForm, createSupplierInviteForm } from '../features/supply/supplyInitialForms';

function SuppliersPage({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  btnR,
  btnB,
  badge,
  suppliersTab,
  setSuppliersTab,
  showForm,
  setShowForm,
  editingItem,
  setEditingItem,
  newSupplier,
  setNewSupplier,
  supplierCategories,
  suppliers,
  saveSupplier,
  deleteSupplier,
  loadAll,
  listSearch,
  setListSearch,
  matchSearch,
  setSupplierInviteForm,
  setGeneratedInviteLink,
  setShowSupplierInviteModal,
  newRequest,
  setNewRequest,
  projects,
  getProjectWorkPackageOptions,
  units,
  saveRequest,
  supplyRequests,
  parseSupplyItems,
  renderSupplyRequestOrigin,
  supplyRequestOrigin,
  showOffers,
  setShowOffers,
  cancelRequest,
  newOffer,
  setNewOffer,
  saveOffer,
  supplierOffers,
  isLeadership,
  approveOffer,
  compareResultByReq,
  compareLoadingReqId,
  runCompareKp,
  fileSrc,
  parseOfferItems,
  selectSupplierOffer,
  rejectSupplierOffer,
  supplyDeliveries,
  supplyHistory,
}) {
  const supplierRequestPackages = typeof getProjectWorkPackageOptions === 'function'
    ? getProjectWorkPackageOptions(newRequest.project)
    : [];
  const supplierRequestDefaultPackage = supplierRequestPackages.length === 1 ? supplierRequestPackages[0] : '';
  const updateRequestProject = (projectName) => {
    const packages = typeof getProjectWorkPackageOptions === 'function' ? getProjectWorkPackageOptions(projectName) : [];
    const defaultPackage = packages.length === 1 ? packages[0] : '';
    setNewRequest(createRequestForm({
      ...newRequest,
      project: projectName,
      workPackage: defaultPackage,
      items: (newRequest.items || []).map(item => ({...item, workPackage: item.workPackage || defaultPackage})),
    }));
  };

  return (
    <div>
      <div style={{display:'flex',gap:'8px',marginBottom:'20px',flexWrap:'wrap'}}>
        {['active','requests','offers','history'].map(tab=>(
          <button key={tab} onClick={()=>{setSuppliersTab(tab);setShowForm(false);}} style={{...(suppliersTab===tab?btnO:btnG),fontSize:'12px',padding:'7px 14px'}}>
            {{active:'Поставщики',requests:'Заявки',offers:'КП',history:'История'}[tab]}
          </button>
        ))}
      </div>

      {suppliersTab==='active'&&(
        <div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',gap:'8px',flexWrap:'wrap'}}>
            <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Поставщики</b>
            <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
              <button onClick={()=>{setSupplierInviteForm(createSupplierInviteForm());setGeneratedInviteLink(null);setShowSupplierInviteModal(true);}} style={btnGr}><Plus size={14}/>🔗 Пригласить по ссылке</button>
              <button onClick={()=>{setShowForm(!showForm);setEditingItem(null);setNewSupplier(createSupplierForm());}} style={btnO}><Plus size={14}/>Добавить вручную</button>
            </div>
          </div>

          {showForm&&(
            <div style={{...card,padding:'20px',marginBottom:'16px'}}>
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'10px'}}>
                <input placeholder="Название *" value={newSupplier.name} onChange={e=>setNewSupplier({...newSupplier,name:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Телефон" value={newSupplier.phone} onChange={e=>setNewSupplier({...newSupplier,phone:e.target.value})} style={{...inp,marginBottom:0}}/>
                <input placeholder="Email" value={newSupplier.email} onChange={e=>setNewSupplier({...newSupplier,email:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newSupplier.category} onChange={e=>setNewSupplier({...newSupplier,category:e.target.value})} style={{...inp,marginBottom:0}}>{supplierCategories.map(c=><option key={c}>{c}</option>)}</select>
                <input placeholder="Специализация" value={newSupplier.specialization} onChange={e=>setNewSupplier({...newSupplier,specialization:e.target.value})} style={{...inp,marginBottom:0}}/>
                <select value={newSupplier.status} onChange={e=>setNewSupplier({...newSupplier,status:e.target.value})} style={{...inp,marginBottom:0}}>{['Активный','Неактивный','Заблокирован'].map(s=><option key={s}>{s}</option>)}</select>
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

          {supplierCategories.map(cat=>{
            const catSuppliers=suppliers.filter(s=>s.category===cat&&matchSearch(listSearch,s.name,s.specialization,s.phone,s.email));
            if(catSuppliers.length===0) return null;
            return (
              <div key={cat} style={{marginBottom:'20px'}}>
                <div style={{display:'flex',alignItems:'center',gap:'8px',marginBottom:'10px',padding:'8px 12px',backgroundColor:C.bg,borderRadius:'8px',border:'1.5px solid '+C.border}}>
                  <b style={{color:C.accent,fontSize:'13px'}}>{'🏭 '+cat}</b>
                  <span style={{color:C.textSec,fontSize:'12px'}}>{'('+catSuppliers.length+')'}</span>
                </div>
                {catSuppliers.map(s=>(
                  <div key={s.id} style={{...card,padding:'14px',marginBottom:'8px',marginLeft:'12px'}}>
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                      <div>
                        <b style={{color:C.text,fontSize:'13px'}}>{s.name}</b>
                        <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{s.phone+(s.email?' · '+s.email:'')+(s.specialization?' · '+s.specialization:'')}</p>
                        <div style={{display:'flex',gap:'4px',marginTop:'4px'}}>
                          {[1,2,3,4,5].map(star=>(
                            <span key={star} style={{color:star<=s.rating?'#f59e0b':'#d1d5db',fontSize:'14px',cursor:'pointer'}} onClick={async()=>{await fetch(API+'/suppliers/'+s.id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...s,rating:star})});await loadAll();}}>★</span>
                          ))}
                        </div>
                      </div>
                      <div style={{display:'flex',gap:'6px'}}>
                        <button onClick={()=>{setEditingItem(s);setNewSupplier(createSupplierForm(s));setShowForm(true);}} style={{...btnG,padding:'5px 10px'}}><Edit2 size={11}/></button>
                        <button onClick={()=>deleteSupplier(s.id)} style={{...btnR,padding:'5px 10px'}}><Trash2 size={11}/></button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            );
          })}

          {suppliers.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Поставщиков нет</p>}
        </div>
      )}

      {suppliersTab==='requests'&&(
        <div>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px'}}>
            <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>Заявки на материалы</b>
            <button onClick={()=>setShowForm(!showForm)} style={btnO}><Plus size={14}/>Новая заявка</button>
          </div>

          {showForm&&(
            <div style={{...card,padding:'20px',marginBottom:'16px'}}>
              <select value={newRequest.project} onChange={e=>updateRequestProject(e.target.value)} style={inp}><option value="">Выберите объект *</option>{projects.map(p=><option key={p.id} value={p.name}>{p.name}</option>)}</select>
              <select value={newRequest.category} onChange={e=>setNewRequest({...newRequest,category:e.target.value})} style={inp}><option value="">Категория материала</option>{supplierCategories.map(c=><option key={c}>{c}</option>)}</select>
              {newRequest.items.map((item,idx)=>(
                <div key={idx} style={{display:'grid',gridTemplateColumns:'minmax(180px,3fr) minmax(130px,1.5fr) 1fr 1fr auto',gap:'8px',marginBottom:'8px',alignItems:'center'}}>
                  <input placeholder="Материал *" value={item.materialName} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],materialName:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <select value={item.workPackage || ''} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],workPackage:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}>
                    <option value="">Раздел сметы</option>
                    {supplierRequestPackages.map(pkg=><option key={pkg} value={pkg}>{pkg}</option>)}
                  </select>
                  <input placeholder="Кол-во *" type="number" step="any" inputMode="decimal" value={item.quantity} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],quantity:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                  <select value={item.unit} onChange={e=>{const items=[...newRequest.items];items[idx]={...items[idx],unit:e.target.value};setNewRequest({...newRequest,items});}} style={{...inp,marginBottom:0,fontSize:'12px'}}>{units.map(u=><option key={u}>{u}</option>)}</select>
                  <button onClick={()=>setNewRequest({...newRequest,items:newRequest.items.filter((_,i)=>i!==idx)})} style={{...btnR,padding:'5px 8px'}}><X size={12}/></button>
                </div>
              ))}
              <button onClick={()=>setNewRequest({...newRequest,items:[...newRequest.items,{materialName:'',quantity:'',unit:'шт',workPackage:supplierRequestDefaultPackage}]})} style={{...btnG,fontSize:'12px',marginBottom:'12px'}}><Plus size={13}/>Строка</button>
              <textarea placeholder="Примечания" value={newRequest.notes} onChange={e=>setNewRequest({...newRequest,notes:e.target.value})} style={{...inp,height:'60px',resize:'vertical'}}/>
              <b style={{color:C.text,fontSize:'13px',display:'block',marginBottom:'8px'}}>Отправить поставщикам:</b>
              {suppliers.filter(s=>!newRequest.category||s.category===newRequest.category).map(s=>(
                <label key={s.id} style={{display:'flex',alignItems:'center',gap:'8px',padding:'8px',cursor:'pointer',borderRadius:'6px',marginBottom:'4px',backgroundColor:newRequest.selectedSuppliers.includes(s.id)?C.accentLight:'transparent'}}>
                  <input type="checkbox" checked={newRequest.selectedSuppliers.includes(s.id)} onChange={e=>setNewRequest({...newRequest,selectedSuppliers:e.target.checked?[...newRequest.selectedSuppliers,s.id]:newRequest.selectedSuppliers.filter(id=>id!==s.id)})} style={{accentColor:C.accent}}/>
                  <span style={{fontSize:'13px',color:C.text}}>{s.name}</span>
                  <span style={{fontSize:'11px',color:C.textSec}}>{s.category}</span>
                </label>
              ))}
              <div style={{display:'flex',gap:'8px',marginTop:'12px'}}>
                <button onClick={saveRequest} style={btnO}><Check size={14}/>Отправить заявку</button>
                <button onClick={()=>setShowForm(false)} style={btnG}><X size={14}/>Отмена</button>
              </div>
            </div>
          )}

          {supplyRequests.map(req=>{
            const items=parseSupplyItems(req);
            const approvedStatus=['Утверждено','Утверждена','Поставлено'].includes(req.status);
            const canceledStatus=req.status==='Отменена';
            return (
              <div key={req.id} style={{...card,padding:'14px',marginBottom:'8px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                  <div style={{flex:'1 1 260px'}}>
                    {items.length<=1?(()=>{const it=items[0]||{materialName:req.materialName,quantity:req.quantity,unit:req.unit};return(<><b style={{color:C.text,fontSize:'13px'}}>{it.materialName}</b><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{it.quantity+' '+it.unit+' · '+req.project+(req.category?' · '+req.category:'')}</p></>);})():(<><b style={{color:C.text,fontSize:'13px'}}>📋 Заявка из {items.length} позиций</b><ol style={{margin:'4px 0 6px',paddingLeft:'18px',color:C.text,fontSize:'12px'}}>{items.map((it,i)=><li key={i}>{it.materialName} <span style={{color:C.textSec}}>— {it.quantity} {it.unit}</span></li>)}</ol><p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{req.project+(req.category?' · '+req.category:'')}</p></>)}
                    <p style={{color:C.textMuted,margin:'0',fontSize:'11px'}}>{req.date+' · '+req.createdBy}</p>
                    {renderSupplyRequestOrigin(req,{compact:true})}
                    {req.notes&&!supplyRequestOrigin(req)&&<p style={{color:C.textSec,margin:'4px 0 0',fontSize:'11px',fontStyle:'italic'}}>«{req.notes}»</p>}
                  </div>
                  <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                    <span style={badge(approvedStatus?C.success:canceledStatus?C.danger:C.warning,approvedStatus?C.successLight:canceledStatus?C.dangerLight:C.warningLight,approvedStatus?C.successBorder:canceledStatus?C.dangerBorder:C.warningBorder)}>{req.status}</span>
                    {req.status==='Новая'&&(<><button onClick={()=>setShowOffers(showOffers===req.id?null:req.id)} style={{...btnB,padding:'4px 10px',fontSize:'11px'}}>КП</button><button onClick={()=>cancelRequest(req.id)} style={{...btnR,padding:'4px 10px',fontSize:'11px'}}>Отменить</button></>)}
                  </div>
                </div>
                {showOffers===req.id&&(
                  <div style={{borderTop:'1.5px solid '+C.border,paddingTop:'12px',marginTop:'10px'}}>
                    <b style={{color:C.text,fontSize:'12px',display:'block',marginBottom:'10px'}}>Добавить КП:</b>
                    <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:'8px',marginBottom:'10px'}}>
                      <select value={newOffer.supplierId} onChange={e=>setNewOffer({...newOffer,supplierId:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}><option value="">Поставщик</option>{suppliers.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</select>
                      <input placeholder="Цена за ед. *" type="number" step="any" inputMode="decimal" value={newOffer.pricePerUnit} onChange={e=>setNewOffer({...newOffer,pricePerUnit:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                      <input placeholder="Срок поставки (дней) *" type="number" step="any" inputMode="decimal" value={newOffer.deliveryDays} onChange={e=>setNewOffer({...newOffer,deliveryDays:e.target.value})} style={{...inp,marginBottom:0,fontSize:'12px'}}/>
                    </div>
                    <button onClick={()=>saveOffer(req.id)} style={{...btnO,fontSize:'12px',padding:'6px 14px',marginBottom:'12px'}}><Plus size={12}/>Добавить КП</button>
                    {supplierOffers.filter(o=>o.requestId===req.id).map(o=>{
                      const sup=suppliers.find(s=>s.id===o.supplierId);
                      const hasPrice = Number(o.pricePerUnit||0) > 0;
                      return (
                        <div key={o.id} style={{padding:'10px',backgroundColor:C.bg,borderRadius:'8px',marginBottom:'6px',border:'1.5px solid '+C.border,display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',flexWrap:'wrap'}}>
                          <div style={{flex:1,minWidth:'180px'}}>
                            <b style={{fontSize:'12px',color:C.text}}>{sup?sup.name:'Поставщик'}</b>
                            {hasPrice
                              ? <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{'Цена: '+Number(o.pricePerUnit||0).toLocaleString('ru-RU')+' ₽/ед · Итого: '+Number(o.totalPrice||0).toLocaleString('ru-RU')+' ₽'+(o.deliveryDays?' · '+o.deliveryDays+' дней':'')+(o.notes?' · '+o.notes:'')}</p>
                              : <p style={{color:C.textMuted,margin:'2px 0',fontSize:'11px',fontStyle:'italic'}}>⏳ Ждём ответ поставщика</p>}
                          </div>
                          {o.status==='Ожидает'&&isLeadership()&&hasPrice&&<button onClick={()=>approveOffer(o)} style={{...btnGr,padding:'4px 10px',fontSize:'11px'}}><Check size={11}/>Утвердить</button>}
                          {o.status==='Утверждено'&&<span style={badge(C.success,C.successLight,C.successBorder)}>✅ Утверждено</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
          {supplyRequests.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Заявок нет</p>}
        </div>
      )}

      {suppliersTab==='offers'&&(
        <div>
          <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>📊 Коммерческие предложения по заявкам</h3>
          {(supplierOffers||[]).length===0 && <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>КП пока нет.<br/><span style={{fontSize:'12px'}}>Они появятся когда вы запросите их у поставщиков из раздела «🛒 Снабжение».</span></div>}
          {(()=>{
            const byReq = new Map();
            (supplierOffers||[]).forEach(o => {
              if (!byReq.has(o.requestId)) byReq.set(o.requestId, []);
              byReq.get(o.requestId).push(o);
            });
            if (byReq.size === 0) return null;
            return Array.from(byReq.entries()).map(([reqId, offers]) => {
              const req = supplyRequests.find(r => r.id === reqId);
              if (!req) return null;
              const items = parseSupplyItems(req);
              const isMulti = items.length > 1;
              const titleText = isMulti ? ('📋 Заявка из '+items.length+' позиций') : (items[0]?.materialName || req.materialName || '—');
              const winner = offers.find(o => o.status === 'Утверждено');
              const receivedOffers = offers.filter(o => o.status === 'Получено' || o.status === 'Утверждено');
              const compareResult = compareResultByReq[req.id];
              const compareLoading = compareLoadingReqId === req.id;
              return (
                <div key={reqId} style={{...card,padding:'16px',marginBottom:'14px'}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap',marginBottom:'12px'}}>
                    <div>
                      <b style={{color:C.text,fontSize:'15px'}}>{titleText}</b>
                      <p style={{color:C.textSec,margin:'3px 0',fontSize:'12px'}}>🏗 {req.project||'—'} · {offers.length} КП {winner?' · ✅ выбрано':''}</p>
                      {isMulti && (<ol style={{margin:'4px 0 0',paddingLeft:'18px',color:C.textSec,fontSize:'11px'}}>{items.map((it,i)=>(<li key={i} style={{marginBottom:'1px'}}>{it.materialName} <span>— {it.quantity} {it.unit}</span></li>))}</ol>)}
                      {renderSupplyRequestOrigin(req,{compact:true})}
                    </div>
                    {receivedOffers.length>=2 && isLeadership() && !winner && (
                      <button onClick={()=>runCompareKp(req.id)} disabled={compareLoading} style={{...btnGr,padding:'5px 12px',fontSize:'12px',opacity:compareLoading?0.6:1}}>
                        <Bot size={12}/>{compareLoading?'AI сравнивает...':'🤖 Сравнить через AI'}
                      </button>
                    )}
                  </div>

                  {compareResult && !compareResult.error && (
                    <div style={{padding:'12px',backgroundColor:C.successLight,border:'1.5px solid '+C.successBorder,borderRadius:'8px',marginBottom:'10px'}}>
                      <b style={{color:C.success,fontSize:'11px',display:'block',marginBottom:'6px'}}>🤖 AI рекомендует: {compareResult.bestSupplier}</b>
                      {compareResult.aiText && <p style={{color:C.text,fontSize:'12px',margin:'0 0 8px',lineHeight:'1.5'}}>{compareResult.aiText}</p>}
                      <table style={{width:'100%',borderCollapse:'collapse',fontSize:'11px'}}>
                        <thead>
                          <tr style={{backgroundColor:C.bg}}>
                            <th style={{padding:'4px 6px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>#</th>
                            <th style={{padding:'4px 6px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Поставщик</th>
                            <th style={{padding:'4px 6px',textAlign:'right',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Цена</th>
                            <th style={{padding:'4px 6px',textAlign:'center',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Срок</th>
                            <th style={{padding:'4px 6px',textAlign:'left',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Оплата</th>
                            <th style={{padding:'4px 6px',textAlign:'center',color:C.textSec,fontWeight:'600',borderBottom:'1px solid '+C.border}}>Балл</th>
                          </tr>
                        </thead>
                        <tbody>
                          {compareResult.ranking.map((r,i)=>(
                            <tr key={r.offerId} style={{backgroundColor:i===0?'rgba(34,197,94,0.08)':'transparent'}}>
                              <td style={{padding:'4px 6px',color:i===0?C.success:C.textSec,fontWeight:'600'}}>{i===0?'🥇':i===1?'🥈':i===2?'🥉':(i+1)+'.'}</td>
                              <td style={{padding:'4px 6px',color:C.text}}>{r.supplier}{r.rating>0?' ⭐'+r.rating:''}</td>
                              <td style={{padding:'4px 6px',textAlign:'right',color:C.text}}>{Number(r.pricePerUnit||r.totalPrice||0).toLocaleString('ru-RU')} ₽</td>
                              <td style={{padding:'4px 6px',textAlign:'center',color:C.text}}>{r.deliveryDays} дн.</td>
                              <td style={{padding:'4px 6px',color:C.text,fontSize:'10px'}}>{r.paymentTerms}{r.vatIncluded===false?' · б/НДС':''}</td>
                              <td style={{padding:'4px 6px',textAlign:'center',color:i===0?C.success:C.text,fontWeight:i===0?'700':'400'}}>{r.score}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p style={{color:C.textMuted,fontSize:'10px',margin:'6px 0 0',fontStyle:'italic'}}>Балл: цена 40% · срок 20% · условия 20% · рейтинг 20%. Финальное решение за вами.</p>
                    </div>
                  )}

                  {compareResult && compareResult.error && (<div style={{padding:'10px 12px',backgroundColor:C.warningLight,border:'1.5px solid '+C.warningBorder,borderRadius:'8px',marginBottom:'10px',fontSize:'12px',color:C.text}}>ℹ️ {compareResult.error}</div>)}

                  {offers.map(o => {
                    const sup = suppliers.find(s => s.id === o.supplierId);
                    const hasPrice = Number(o.pricePerUnit||0) > 0;
                    const stC = o.status==='Утверждено'?C.success:o.status==='Отклонено'?C.danger:o.status==='Получено'?C.info:C.warning;
                    const stBg = o.status==='Утверждено'?C.successLight:o.status==='Отклонено'?C.dangerLight:o.status==='Получено'?C.infoLight:C.warningLight;
                    const stBd = o.status==='Утверждено'?C.successBorder:o.status==='Отклонено'?C.dangerBorder:o.status==='Получено'?C.infoBorder:C.warningBorder;
                    return (
                      <div key={o.id} style={{padding:'10px 12px',backgroundColor:stBg,borderRadius:'6px',marginBottom:'6px',border:'1.5px solid '+stBd}}>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'8px',flexWrap:'wrap'}}>
                          <div style={{flex:'1 1 220px'}}>
                            <b style={{color:C.text,fontSize:'13px'}}>{sup?sup.name:'Поставщик #'+o.supplierId}{o.aiRecommended&&<span style={{marginLeft:'6px',fontSize:'10px',color:C.accent}}>🤖 AI рек.</span>}</b>
                            {hasPrice
                              ? (<p style={{color:C.text,margin:'2px 0',fontSize:'12px'}}>{isMulti ? ('Итого за пакет: '+Number(o.totalPrice||o.pricePerUnit||0).toLocaleString('ru-RU')+' ₽') : (Number(o.pricePerUnit||0).toLocaleString('ru-RU')+' ₽/ед · итого '+Number(o.totalPrice||0).toLocaleString('ru-RU')+' ₽')}{o.deliveryDays?' · '+o.deliveryDays+' дн.':''}</p>)
                              : <p style={{color:C.textMuted,margin:'2px 0',fontSize:'12px',fontStyle:'italic'}}>⏳ Поставщик ещё не ответил</p>}
                            {o.paymentTerms && <p style={{color:C.textMuted,margin:0,fontSize:'11px'}}>💳 {o.paymentTerms}{o.vatIncluded===false?' · без НДС':' · с НДС'}{o.validUntil?' · до '+o.validUntil:''}</p>}
                            {o.supplierMessage && <p style={{color:C.textSec,margin:'4px 0 0',fontSize:'11px',fontStyle:'italic'}}>💬 «{o.supplierMessage}»</p>}
                            {o.pdfUrl && <a href={fileSrc(o.pdfUrl)} target='_blank' rel='noopener noreferrer' style={{fontSize:'11px',color:C.accent,display:'inline-block',marginTop:'4px'}}>📄 PDF</a>}
                            {(()=>{const ki=parseOfferItems(o); if (ki.length<2) return null; return (
                              <details style={{marginTop:'6px'}}>
                                <summary style={{cursor:'pointer',fontSize:'11px',color:C.accent,fontWeight:'600'}}>📋 Разбивка по позициям ({ki.length})</summary>
                                <table style={{width:'100%',borderCollapse:'collapse',fontSize:'11px',marginTop:'6px'}}>
                                  <thead><tr style={{backgroundColor:C.bg}}>
                                    <th style={{padding:'4px 6px',textAlign:'left',color:C.textSec,fontWeight:'600'}}>Материал</th>
                                    <th style={{padding:'4px 6px',textAlign:'center',color:C.textSec,fontWeight:'600'}}>Кол-во</th>
                                    <th style={{padding:'4px 6px',textAlign:'right',color:C.textSec,fontWeight:'600'}}>Цена/ед</th>
                                    <th style={{padding:'4px 6px',textAlign:'right',color:C.textSec,fontWeight:'600'}}>Сумма</th>
                                  </tr></thead>
                                  <tbody>
                                    {ki.map((it,i)=>(
                                      <tr key={i}>
                                        <td style={{padding:'3px 6px',color:C.text}}>{it.materialName}</td>
                                        <td style={{padding:'3px 6px',color:C.text,textAlign:'center'}}>{it.quantity} {it.unit}</td>
                                        <td style={{padding:'3px 6px',color:C.text,textAlign:'right'}}>{Number(it.pricePerUnit||0).toLocaleString('ru-RU')} ₽</td>
                                        <td style={{padding:'3px 6px',color:C.text,textAlign:'right',fontWeight:'600'}}>{Math.round(Number(it.totalPrice||it.pricePerUnit*it.quantity||0)).toLocaleString('ru-RU')} ₽</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </details>
                            );})()}
                          </div>
                          <div style={{display:'flex',gap:'4px',alignItems:'center',flexWrap:'wrap'}}>
                            <span style={badge(stC,stBg,stBd)}>{o.status||'—'}</span>
                            {o.status==='Получено' && isLeadership() && (<>
                              <button onClick={()=>selectSupplierOffer(o.id)} style={{...btnGr,padding:'3px 8px',fontSize:'11px'}}><Check size={11}/>Выбрать</button>
                              <button onClick={()=>rejectSupplierOffer(o.id)} style={{...btnR,padding:'3px 8px',fontSize:'11px'}}><X size={11}/></button>
                            </>)}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              );
            });
          })()}
        </div>
      )}

      {suppliersTab==='history'&&(
        <div>
          <h3 style={{color:C.text,marginBottom:'15px',fontSize:'15px',fontWeight:'700'}}>История поставок</h3>
          {(supplyDeliveries||[]).map(d=>(
            <div key={d.id} style={{...card,padding:'14px',marginBottom:'8px'}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'10px',flexWrap:'wrap'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{d.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(d.receivedQuantity||d.shippedQuantity||d.plannedQuantity)+' '+d.unit+' · '+d.project+' · накл. '+(d.waybillNumber||'—')}</p>
                  <p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>{'Поставщик: '+(d.supplierName||suppliers.find(s=>s.id===d.supplierId)?.name||'—')+(d.receivedBy?' · принял '+d.receivedBy:'')}</p>
                </div>
                <div style={{display:'flex',gap:'6px',alignItems:'center'}}>
                  <b style={{color:C.success,fontSize:'13px'}}>{Number(d.totalPrice||0).toLocaleString('ru-RU')+' ₽'}</b>
                  <span style={badge(d.status==='Принято'?C.success:d.status==='Проблема'?C.danger:C.warning,d.status==='Принято'?C.successLight:d.status==='Проблема'?C.dangerLight:C.warningLight,d.status==='Принято'?C.successBorder:d.status==='Проблема'?C.dangerBorder:C.warningBorder)}>{d.status}</span>
                </div>
              </div>
            </div>
          ))}
          {(supplyDeliveries||[]).length===0 && supplyHistory.map(d=>(
            <div key={d.id} style={{...card,padding:'14px',marginBottom:'8px',opacity:0.75}}>
              <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                <div>
                  <b style={{fontSize:'13px',color:C.text}}>{d.materialName}</b>
                  <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{d.quantity+' '+d.unit+' · '+d.project+' · '+d.date}</p>
                  <p style={{color:C.textSec,margin:'0',fontSize:'11px'}}>Старая запись истории. Новые поставки принимаются через «Снабжение → Поставки и приёмка».</p>
                </div>
                <span style={badge(C.textMuted,C.bg,C.border)}>{d.status}</span>
              </div>
            </div>
          ))}
          {supplyHistory.length===0&&<p style={{color:C.textMuted,textAlign:'center',padding:'30px'}}>Истории нет</p>}
        </div>
      )}
    </div>
  );
}

export default SuppliersPage;
