import React from 'react';
import { Check, X } from 'lucide-react';

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
  API,
  user,
  loadAll,
}) {
  if (!addExpenseProject) return null;

  const isProjectPicker = addExpenseProject === '__choose__';
  const projectOptions = typeof visibleActiveProjects === 'function'
    ? visibleActiveProjects(projects || [])
    : (projects || []).filter(project => !project.archived && project.status !== 'Завершён');
  const selectedProject = isProjectPicker ? (newManualExpense.projectName || '') : addExpenseProject;
  const allowedCategories = isFinanceRole()
    ? expenseCategories
    : expenseCategories.filter(c => ['materials', 'delivery', 'other'].includes(c.id));
  const close = () => {
    setAddExpenseProject('');
    setNewManualExpense({category: 'materials', customCategory: '', projectName: '', amount: '', note: '', date: ''});
  };

  const submit = async () => {
    const category = newManualExpense.category === '__custom__'
      ? (newManualExpense.customCategory || '').trim()
      : (newManualExpense.category || 'other');
    if(!selectedProject) { alert('Выберите объект'); return; }
    if(!category) { alert('Введите статью расхода'); return; }
    if(!newManualExpense.amount) return;
    await fetch(API+'/expenses',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({project:selectedProject,category,amount:Number(newManualExpense.amount),note:newManualExpense.note||'',date:newManualExpense.date||new Date().toISOString().split('T')[0],addedBy:user.name})});
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
        <div className='mobile-actions' style={{display:'flex',gap:'8px'}}>
          <button onClick={submit} style={btnO}><Check size={14}/>Добавить</button>
          <button onClick={close} style={btnG}><X size={14}/>Отмена</button>
        </div>
      </div>
    </div>
  );
}
