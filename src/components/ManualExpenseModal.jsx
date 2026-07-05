import React from 'react';
import { Camera, Check, FileText, Paperclip, Upload, X } from 'lucide-react';
import { createManualExpenseForm } from '../features/payments/paymentInitialForms';

export default function ManualExpenseModal({
  addExpenseProject,
  setAddExpenseProject,
  C,
  card,
  inp,
  btnO,
  btnG,
  newManualExpense,
  setNewManualExpense,
  isFinanceRole,
  expenseCategories,
  projects = [],
  visibleActiveProjects,
  appendPhotos,
  fileSrc,
  setShowPhotoModal,
  API,
  user,
  loadAll,
}) {
  const fileInputRef = React.useRef(null);
  const cameraInputRef = React.useRef(null);
  if (!addExpenseProject) return null;

  const isProjectPicker = addExpenseProject === '__choose__';
  const projectOptions = typeof visibleActiveProjects === 'function'
    ? visibleActiveProjects(projects || [])
    : (projects || []).filter(project => !project.archived && project.status !== 'Завершён');
  const selectedProject = isProjectPicker ? (newManualExpense.projectName || '') : addExpenseProject;
  const isFinanceUser = typeof isFinanceRole === 'function' ? isFinanceRole() : Boolean(isFinanceRole);
  const allowedCategories = isFinanceUser
    ? expenseCategories
    : expenseCategories.filter(c => ['materials', 'delivery', 'other'].includes(c.id));
  const attachmentUrls = (newManualExpense.photoUrl || '').split(',').map(url => url.trim()).filter(Boolean);
  const isImageUrl = url => /\.(png|jpe?g|webp|gif|heic|heif|bmp|svg)(\?|$)/i.test(String(url || ''));
  const attachmentLabel = url => {
    const raw = String(url || '').split('?')[0].split('/').filter(Boolean).pop() || 'Файл';
    try {
      return decodeURIComponent(raw);
    } catch (_e) {
      return raw;
    }
  };
  const close = () => {
    setAddExpenseProject('');
    setNewManualExpense(createManualExpenseForm());
  };

  const appendExpenseFiles = async (event) => {
    if (!event.target.files || event.target.files.length === 0) return;
    if (!selectedProject) {
      alert('Сначала выберите объект');
      event.target.value = '';
      return;
    }
    if (typeof appendPhotos !== 'function') {
      alert('Загрузка файлов временно недоступна');
      event.target.value = '';
      return;
    }
    const newCsv = await appendPhotos(newManualExpense.photoUrl, event.target.files, {projectName: selectedProject, context: 'manual-expenses'});
    setNewManualExpense(prev => ({...prev, photoUrl: newCsv}));
    event.target.value = '';
  };

  const removeAttachment = index => {
    const next = attachmentUrls.filter((_, i) => i !== index).join(',');
    setNewManualExpense(prev => ({...prev, photoUrl: next}));
  };

  const openAttachment = url => {
    const src = typeof fileSrc === 'function' ? fileSrc(url) : url;
    if (isImageUrl(url) && typeof setShowPhotoModal === 'function') {
      setShowPhotoModal(src);
      return;
    }
    if (typeof window !== 'undefined') window.open(src, '_blank', 'noopener,noreferrer');
  };

  const submit = async () => {
    const category = newManualExpense.category === '__custom__'
      ? (newManualExpense.customCategory || '').trim()
      : (newManualExpense.category || 'other');
    if(!selectedProject) { alert('Выберите объект'); return; }
    if(!category) { alert('Введите статью расхода'); return; }
    if(!newManualExpense.amount) return;
    await fetch(API+'/expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedProject,category,amount:Number(newManualExpense.amount),note:newManualExpense.note||'',date:newManualExpense.date||new Date().toISOString().split('T')[0],addedBy:user?.name||'',photoUrl:newManualExpense.photoUrl||''})});
    close();
    await loadAll();
    alert('Расход добавлен!');
  };

  return (
    <div style={{position:'fixed',top:0,left:0,right:0,bottom:0,backgroundColor:'rgba(0,0,0,0.5)',zIndex:500,display:'flex',alignItems:'center',justifyContent:'center'}}>
      <div className='mobile-modal' style={{...card,padding:'20px',width:'340px',margin:'20px',maxHeight:'90vh',overflowY:'auto'}}>
        <b style={{color:C.text,fontSize:'15px',display:'block',marginBottom:'12px'}}>➕ Добавить расход</b>
        {isProjectPicker ? (
          <select value={selectedProject} onChange={e=>setNewManualExpense({...newManualExpense,projectName:e.target.value})} style={inp}>
            <option value=''>Выберите объект *</option>
            {projectOptions.map(project => <option key={project.id || project.name} value={project.name}>{project.name}</option>)}
          </select>
        ) : (
          <p style={{color:C.textSec,fontSize:'12px',margin:'0 0 12px'}}>{'Проект: '+addExpenseProject}</p>
        )}
        <select value={newManualExpense.category} onChange={e=>setNewManualExpense({...newManualExpense,category:e.target.value})} style={inp}>
          {allowedCategories.map(c=><option key={c.id} value={c.id}>{c.label}</option>)}
          <option value='__custom__'>Своя статья / вручную</option>
        </select>
        {newManualExpense.category === '__custom__' && (
          <input placeholder='Статья расхода *' value={newManualExpense.customCategory || ''} onChange={e=>setNewManualExpense({...newManualExpense,customCategory:e.target.value})} style={inp}/>
        )}
        <input placeholder='Сумма (₽) *' type='number' step='any' inputMode='decimal' value={newManualExpense.amount} onChange={e=>setNewManualExpense({...newManualExpense,amount:e.target.value})} style={inp}/>
        <input placeholder='За что / примечание' value={newManualExpense.note} onChange={e=>setNewManualExpense({...newManualExpense,note:e.target.value})} style={inp}/>
        <input type='date' value={newManualExpense.date} onChange={e=>setNewManualExpense({...newManualExpense,date:e.target.value})} style={inp}/>
        <div style={{marginBottom:'12px'}}>
          <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',gap:'8px',marginBottom:'6px'}}>
            <span style={{fontSize:'12px',color:C.textSec,display:'flex',alignItems:'center',gap:'5px'}}><Paperclip size={13}/>Вложения</span>
            <span style={{fontSize:'11px',color:C.textMuted}}>{attachmentUrls.length ? attachmentUrls.length + ' файл.' : 'Фото, PDF, документы'}</span>
          </div>
          <input ref={fileInputRef} type='file' multiple style={{display:'none'}} onChange={appendExpenseFiles}/>
          <input ref={cameraInputRef} type='file' accept='image/*' multiple capture='environment' style={{display:'none'}} onChange={appendExpenseFiles}/>
          {attachmentUrls.length === 0 ? (
            <div onClick={()=>fileInputRef.current?.click()} role='button' tabIndex={0} onKeyDown={event=>{ if(event.key==='Enter' || event.key===' ') fileInputRef.current?.click(); }} style={{border:'2px dashed '+C.border,borderRadius:'8px',padding:'16px',textAlign:'center',color:C.textMuted,fontSize:'12px',cursor:'pointer',marginBottom:'8px'}}>
              <Paperclip size={20} style={{display:'block',margin:'0 auto 6px'}}/>
              Прикрепить чек, накладную или документ
              <br/>
              <span style={{fontSize:'10px'}}>можно несколько файлов за раз</span>
            </div>
          ) : (
            <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(92px,1fr))',gap:'6px',marginBottom:'8px'}}>
              {attachmentUrls.map((url, index) => {
                const src = typeof fileSrc === 'function' ? fileSrc(url) : url;
                const isImage = isImageUrl(url);
                return (
                  <div key={url + index} onClick={()=>openAttachment(url)} role='button' tabIndex={0} onKeyDown={event=>{ if(event.key==='Enter' || event.key===' ') openAttachment(url); }} style={{position:'relative',minHeight:'84px',border:'1px solid '+C.border,borderRadius:'8px',backgroundColor:C.bg,cursor:'pointer',overflow:'hidden'}}>
                    {isImage ? (
                      <img src={src} alt='' style={{width:'100%',height:'84px',objectFit:'cover',display:'block'}}/>
                    ) : (
                      <div style={{height:'84px',padding:'9px 6px',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:'5px',boxSizing:'border-box'}}>
                        <FileText size={22} color={C.accent}/>
                        <span style={{fontSize:'10px',color:C.text,textAlign:'center',lineHeight:1.2,wordBreak:'break-word',maxHeight:'30px',overflow:'hidden'}}>{attachmentLabel(url)}</span>
                      </div>
                    )}
                    <button type='button' onClick={event=>{event.preventDefault();event.stopPropagation();removeAttachment(index);}} style={{position:'absolute',top:'2px',right:'2px',background:'rgba(220,38,38,0.9)',color:'white',border:'none',borderRadius:'50%',width:'20px',height:'20px',cursor:'pointer',fontSize:'12px',lineHeight:'1',padding:0}}>×</button>
                  </div>
                );
              })}
            </div>
          )}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:'8px'}}>
            <button type='button' onClick={()=>fileInputRef.current?.click()} style={{...btnG,justifyContent:'center'}}><Upload size={14}/>Файлы/PDF</button>
            <button type='button' onClick={()=>cameraInputRef.current?.click()} style={{...btnG,justifyContent:'center'}}><Camera size={14}/>Камера</button>
          </div>
        </div>
        <div className='mobile-actions' style={{display:'flex',gap:'8px'}}>
          <button onClick={submit} style={btnO}><Check size={14}/>Добавить</button>
          <button onClick={close} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
