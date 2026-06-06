import React from 'react';
import { Check, ChevronDown, ChevronUp, Plus, Search, Trash2 } from 'lucide-react';
import { API } from '../api';

function SupplySupplierInvoicesPanel({
  C,
  card,
  inp,
  btnO,
  btnG,
  btnGr,
  btnR,
  badge,
  user,
  suppliers,
  projects,
  supplierInvoices,
  newSupplierInvoice,
  setNewSupplierInvoice,
  listSearch,
  setListSearch,
  expandedProject,
  setExpandedProject,
  canPay,
  matchSearch,
  loadAll,
  toNum,
}) {
  const today = () => new Date().toISOString().split('T')[0];

  const filtered = (supplierInvoices || []).filter(invoice =>
    matchSearch(listSearch, invoice.supplierName, invoice.invoiceNumber, invoice.projectName, invoice.description)
  );
  const pending = filtered.filter(invoice=>invoice.status==='На утверждении');
  const approved = filtered.filter(invoice=>invoice.status==='Утверждён'||invoice.status==='Частично оплачен');
  const paid = filtered.filter(invoice=>invoice.status==='Оплачен');
  const totalPending = pending.reduce((sum, invoice)=>sum+Number(invoice.amount||0),0);
  const totalDebt = approved.reduce((sum, invoice)=>sum+(Number(invoice.amount||0)-Number(invoice.paidAmount||0)),0);

  const byProject = {};
  filtered.forEach(invoice=>{
    const projectName = invoice.projectName || 'Без объекта';
    if (!byProject[projectName]) byProject[projectName] = [];
    byProject[projectName].push(invoice);
  });
  const projectNames = Object.keys(byProject).sort();

  const openNewInvoice = () => {
    setNewSupplierInvoice({supplierName:'',projectName:'',invoiceNumber:'',invoiceDate:'',amount:'',vatAmount:'',description:''});
  };

  const saveInvoice = async () => {
    if(!newSupplierInvoice.supplierName||!newSupplierInvoice.invoiceNumber||!newSupplierInvoice.amount){
      alert('Заполните: поставщик, № счёта, сумма');
      return;
    }
    await fetch(API+'/supplier-invoices',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        ...newSupplierInvoice,
        amount:Number(newSupplierInvoice.amount)||0,
        vatAmount:Number(newSupplierInvoice.vatAmount||0),
        status:'На утверждении',
      }),
    });
    await loadAll();
    setNewSupplierInvoice(null);
  };

  const approveInvoice = async (invoice) => {
    await fetch(API+'/supplier-invoices/'+invoice.id,{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({status:'Утверждён',approvedBy:user.name,approvedAt:today()}),
    });
    await loadAll();
  };

  const payInvoice = async (invoice, total, paidAmount, owe) => {
    const ans = prompt('Оплатить (₽). Полная: '+Math.round(owe).toLocaleString('ru-RU')+' ₽', String(owe));
    if(!ans) return;
    const sum = toNum(ans);
    if(sum<=0||sum>owe){
      alert('Сумма должна быть от 1 до '+Math.round(owe).toLocaleString('ru-RU'));
      return;
    }
    const newPaid = paidAmount + sum;
    const newStatus = newPaid >= total ? 'Оплачен' : 'Частично оплачен';
    await fetch(API+'/supplier-invoices/'+invoice.id,{
      method:'PUT',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        status:newStatus,
        paidAmount:newPaid,
        paidBy:user.name,
        paidAt:today(),
        paidNote:'Оплачено '+Math.round(sum).toLocaleString('ru-RU')+' ₽',
      }),
    });
    if(invoice.projectName){
      await fetch(API+'/project-payments',{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          projectName:invoice.projectName,
          amount:sum,
          note:'Оплата счёта '+invoice.supplierName+' №'+invoice.invoiceNumber,
          date:today(),
          paidBy:user.name,
        }),
      });
    }
    await loadAll();
  };

  const deleteInvoice = async (invoice) => {
    if(!window.confirm('Удалить?')) return;
    await fetch(API+'/supplier-invoices/'+invoice.id,{method:'DELETE'});
    await loadAll();
  };

  const invoiceBadge = (invoice) => badge(
    invoice.status==='Оплачен'?C.success:invoice.status==='Частично оплачен'?C.warning:invoice.status==='Утверждён'?C.accent:C.warning,
    invoice.status==='Оплачен'?C.successLight:invoice.status==='Частично оплачен'?C.warningLight:invoice.status==='Утверждён'?C.accentLight:C.warningLight,
    invoice.status==='Оплачен'?C.successBorder:invoice.status==='Частично оплачен'?C.warningBorder:invoice.status==='Утверждён'?C.accentBorder:C.warningBorder
  );

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:'15px',flexWrap:'wrap',gap:'8px'}}>
        <b style={{color:C.text,fontSize:'15px',fontWeight:'700'}}>📥 Входящие счета от поставщиков</b>
        <button onClick={openNewInvoice} style={btnO}><Plus size={14}/>Новый счёт</button>
      </div>

      {newSupplierInvoice&&(
        <div style={{...card,padding:'16px',marginBottom:'14px',backgroundColor:C.bg}}>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px',marginBottom:'8px'}}>
            <select value={newSupplierInvoice.supplierName} onChange={e=>{const supplier=suppliers.find(s=>s.name===e.target.value);setNewSupplierInvoice({...newSupplierInvoice,supplierName:e.target.value,supplierId:supplier?supplier.id:null});}} style={{...inp,marginBottom:0}}>
              <option value=''>Поставщик *</option>
              {(suppliers||[]).map(supplier=><option key={supplier.id} value={supplier.name}>{supplier.name}</option>)}
            </select>
            <select value={newSupplierInvoice.projectName} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,projectName:e.target.value})} style={{...inp,marginBottom:0}}>
              <option value=''>Объект (если по проекту)</option>
              {projects.map(project=><option key={project.id} value={project.name}>{project.name}</option>)}
            </select>
            <input placeholder='№ счёта *' value={newSupplierInvoice.invoiceNumber} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,invoiceNumber:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input type='date' value={newSupplierInvoice.invoiceDate} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,invoiceDate:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder='Сумма с НДС (₽) *' type='number' step='any' inputMode='decimal' value={newSupplierInvoice.amount} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,amount:e.target.value})} style={{...inp,marginBottom:0}}/>
            <input placeholder='В т.ч. НДС (₽)' type='number' step='any' inputMode='decimal' value={newSupplierInvoice.vatAmount} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,vatAmount:e.target.value})} style={{...inp,marginBottom:0}}/>
          </div>
          <textarea placeholder='Описание (за что счёт)' value={newSupplierInvoice.description} onChange={e=>setNewSupplierInvoice({...newSupplierInvoice,description:e.target.value})} style={{...inp,minHeight:'50px',marginBottom:'8px'}}/>
          <div style={{display:'flex',gap:'8px'}}>
            <button onClick={saveInvoice} style={btnO}><Check size={14}/>Сохранить</button>
            <button onClick={()=>setNewSupplierInvoice(null)} style={btnG}>Отмена</button>
          </div>
        </div>
      )}

      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))',gap:'10px',marginBottom:'14px'}}>
        <div style={{...card,padding:'12px',backgroundColor:C.warningLight}}><p style={{color:C.warning,fontSize:'11px',margin:'0 0 4px'}}>На утверждении</p><b style={{color:C.warning,fontSize:'15px'}}>{pending.length+' · '+Math.round(totalPending).toLocaleString('ru-RU')+' ₽'}</b></div>
        <div style={{...card,padding:'12px',backgroundColor:C.accentLight}}><p style={{color:C.accent,fontSize:'11px',margin:'0 0 4px'}}>К оплате</p><b style={{color:C.accent,fontSize:'15px'}}>{approved.length}</b></div>
        {totalDebt>0&&<div style={{...card,padding:'12px',backgroundColor:C.dangerLight}}><p style={{color:C.danger,fontSize:'11px',margin:'0 0 4px'}}>⚠️ Долг по счетам</p><b style={{color:C.danger,fontSize:'15px'}}>{Math.round(totalDebt).toLocaleString('ru-RU')+' ₽'}</b></div>}
        <div style={{...card,padding:'12px',backgroundColor:C.successLight}}><p style={{color:C.success,fontSize:'11px',margin:'0 0 4px'}}>Оплачены</p><b style={{color:C.success,fontSize:'15px'}}>{paid.length}</b></div>
      </div>

      <div style={{position:'relative',marginBottom:'12px'}}>
        <Search size={13} style={{position:'absolute',left:'10px',top:'50%',transform:'translateY(-50%)',color:C.textMuted}}/>
        <input placeholder='🔍 Поиск по поставщику, № счёта, объекту' value={listSearch} onChange={e=>setListSearch(e.target.value)} style={{...inp,marginBottom:0,paddingLeft:'30px',fontSize:'12px',padding:'6px 8px 6px 30px'}}/>
      </div>

      {filtered.length===0 ? (
        <div style={{...card,padding:'30px',textAlign:'center',color:C.textMuted}}>Счетов нет</div>
      ) : projectNames.map(projectName=>{
        const list = byProject[projectName];
        const sumTotal = list.reduce((sum, invoice)=>sum+Number(invoice.amount||0),0);
        const sumPaid = list.reduce((sum, invoice)=>sum+Number(invoice.paidAmount||0),0);
        const sumDebt = Math.max(0,sumTotal-sumPaid);
        const isOpen = expandedProject==='sup-'+projectName;
        return (
          <div key={projectName} style={{...card,marginBottom:'10px'}}>
            <div style={{padding:'12px 14px',cursor:'pointer',display:'flex',justifyContent:'space-between',alignItems:'center',flexWrap:'wrap',gap:'8px'}} onClick={()=>setExpandedProject(isOpen?null:'sup-'+projectName)}>
              <div>
                <b style={{color:C.text,fontSize:'13px'}}>🏗 {projectName}</b>
                <p style={{color:C.textSec,margin:'2px 0',fontSize:'11px'}}>{list.length+' счетов · итого '+Math.round(sumTotal).toLocaleString('ru-RU')+' ₽'+(sumPaid>0?' · оплачено '+Math.round(sumPaid).toLocaleString('ru-RU'):'')}</p>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:'8px'}}>
                {sumDebt>0&&<b style={{color:C.danger,fontSize:'13px'}}>{'⚠️ Долг '+Math.round(sumDebt).toLocaleString('ru-RU')+' ₽'}</b>}
                {isOpen?<ChevronUp size={14}/>:<ChevronDown size={14}/>}
              </div>
            </div>
            {isOpen&&(
              <div style={{borderTop:'1px solid '+C.border}}>
                {list.map(invoice=>{
                  const total = Number(invoice.amount||0);
                  const paidAmount = Number(invoice.paidAmount||0);
                  const owe = Math.max(0,total-paidAmount);
                  return (
                    <div key={invoice.id} style={{padding:'12px 14px',borderBottom:'1px solid '+C.border,borderLeft:'3px solid '+(invoice.status==='Оплачен'?C.success:owe>0&&paidAmount>0?C.warning:invoice.status==='Утверждён'?C.accent:C.warning),marginLeft:'10px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start',gap:'10px',flexWrap:'wrap'}}>
                        <div style={{flex:1,minWidth:'200px'}}>
                          <b style={{color:C.text,fontSize:'13px'}}>{invoice.supplierName+' · № '+invoice.invoiceNumber}</b>
                          <p style={{color:C.textSec,margin:'2px 0',fontSize:'12px'}}>{(invoice.invoiceDate||'')+(invoice.projectName?' · 🏗 '+invoice.projectName:'')+(invoice.description?' · '+invoice.description:'')}</p>
                          {(invoice.offerId||invoice.offer_id)&&<p style={{color:C.accent,margin:'2px 0',fontSize:'11px'}}>📨 Создан по выигранному КП #{invoice.offerId||invoice.offer_id}{invoice.materialName?' · '+invoice.materialName:''}{invoice.paymentTerms?' · условия: '+invoice.paymentTerms:''}</p>}
                          <div style={{display:'flex',gap:'10px',marginTop:'4px',flexWrap:'wrap'}}>
                            <span style={{fontSize:'12px',color:C.text}}>{'Сумма: '+Math.round(total).toLocaleString('ru-RU')+' ₽'}</span>
                            {paidAmount>0&&<span style={{fontSize:'12px',color:C.success}}>{'Оплачено: '+Math.round(paidAmount).toLocaleString('ru-RU')+' ₽'}</span>}
                            {owe>0&&paidAmount>0&&<span style={{fontSize:'12px',color:C.danger,fontWeight:'700',padding:'2px 8px',borderRadius:'6px',backgroundColor:C.dangerLight}}>{'⚠️ Недоплата: '+Math.round(owe).toLocaleString('ru-RU')+' ₽'}</span>}
                          </div>
                        </div>
                        <div style={{display:'flex',gap:'4px',alignItems:'center',flexWrap:'wrap'}}>
                          <span style={invoiceBadge(invoice)}>{invoice.status}</span>
                          {canPay&&invoice.status==='На утверждении'&&<button onClick={()=>approveInvoice(invoice)} style={{...btnGr,padding:'4px 8px',fontSize:'11px'}}>✅</button>}
                          {canPay&&(invoice.status==='Утверждён'||invoice.status==='Частично оплачен')&&owe>0&&<button onClick={()=>payInvoice(invoice, total, paidAmount, owe)} style={{...btnO,padding:'4px 8px',fontSize:'11px'}}>💰 {owe<total?'Доплатить':'Оплатить'}</button>}
                          {canPay&&<button onClick={()=>deleteInvoice(invoice)} style={{...btnR,padding:'4px 8px'}}><Trash2 size={11}/></button>}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

export default SupplySupplierInvoicesPanel;
