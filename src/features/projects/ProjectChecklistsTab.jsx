import React from 'react';

export default function ProjectChecklistsTab({
  API,
  C,
  CHECKLIST_TEMPLATES,
  Check,
  ChevronDown,
  ChevronUp,
  Plus,
  X,
  btnG,
  btnO,
  card,
  checklistItems,
  checklists,
  inp,
  isProrab,
  loadChecklistItems,
  newChecklist,
  newChecklistItem,
  project,
  saveChecklist,
  selectedChecklist,
  setNewChecklist,
  setNewChecklistItem,
  setSelectedChecklist,
  setShowForm,
  showForm,
  toggleChecklistItem,
}) {
  const projectChecklists = checklists.filter(checklist => checklist.projectName === project.name);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <b style={{ color: C.text }}>Чек-листы</b>
        {isProrab() && (
          <button onClick={() => setShowForm(showForm === 'checklist' ? false : 'checklist')} style={btnO}>
            <Plus size={14} />Создать
          </button>
        )}
      </div>

      {showForm === 'checklist' && (
        <div style={{ ...card, padding: '16px', marginBottom: '16px', backgroundColor: C.bg }}>
          <input placeholder="Название чек-листа *" value={newChecklist.name} onChange={event => setNewChecklist({ ...newChecklist, name: event.target.value })} style={inp} />
          <select value={newChecklist.template} onChange={event => setNewChecklist({ ...newChecklist, template: event.target.value, name: event.target.value || newChecklist.name })} style={inp}>
            <option value="">Свой чек-лист</option>
            {Object.keys(CHECKLIST_TEMPLATES).map(template => <option key={template} value={template}>{template}</option>)}
          </select>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button onClick={() => saveChecklist(project.id, project.name)} style={btnO}><Check size={14} />Создать</button>
            <button onClick={() => setShowForm(false)} style={btnG}><X size={14} />Отмена</button>
          </div>
        </div>
      )}

      {projectChecklists.map(checklist => {
        const items = checklistItems[checklist.id] || [];
        const checkedCount = items.filter(item => item.checked).length;
        const isOpen = selectedChecklist === checklist.id;

        return (
          <div key={checklist.id} style={{ ...card, marginBottom: '10px' }}>
            <div
              style={{ padding: '14px', cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
              onClick={async () => {
                if (isOpen) {
                  setSelectedChecklist(null);
                } else {
                  setSelectedChecklist(checklist.id);
                  await loadChecklistItems(checklist.id);
                }
              }}
            >
              <div>
                <b style={{ color: C.text, fontSize: '13px' }}>{checklist.name}</b>
                <p style={{ color: C.textSec, margin: '2px 0', fontSize: '12px' }}>{checkedCount + '/' + items.length + ' выполнено'}</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ backgroundColor: C.bgGray, borderRadius: '10px', height: '8px', width: '80px' }}>
                  <div style={{ backgroundColor: items.length > 0 && checkedCount === items.length ? C.success : C.accent, width: (items.length > 0 ? checkedCount / items.length * 100 : 0) + '%', height: '100%', borderRadius: '10px' }} />
                </div>
                {isOpen ? <ChevronUp size={16} color={C.textMuted} /> : <ChevronDown size={16} color={C.textMuted} />}
              </div>
            </div>

            {isOpen && (
              <div style={{ borderTop: '1.5px solid ' + C.border, padding: '12px 14px' }}>
                {items.map(item => (
                  <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: '10px', padding: '8px 0', borderBottom: '1px solid ' + C.border }}>
                    <input type="checkbox" checked={item.checked} onChange={() => toggleChecklistItem(item)} style={{ width: '18px', height: '18px', accentColor: C.accent, cursor: 'pointer' }} />
                    <span style={{ fontSize: '13px', color: item.checked ? C.textMuted : C.text, textDecoration: item.checked ? 'line-through' : 'none', flex: 1 }}>{item.name}</span>
                    {item.checked && item.checkedBy && <span style={{ fontSize: '11px', color: C.textMuted }}>{item.checkedBy}</span>}
                  </div>
                ))}
                <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
                  <input placeholder="Добавить пункт..." value={newChecklistItem} onChange={event => setNewChecklistItem(event.target.value)} style={{ ...inp, marginBottom: 0, flex: 1, fontSize: '12px' }} />
                  <button
                    onClick={async () => {
                      if (!newChecklistItem) return;
                      await fetch(API + '/checklist-items', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ checklistId: checklist.id, name: newChecklistItem, checked: false, orderNum: items.length }),
                      });
                      await loadChecklistItems(checklist.id);
                      setNewChecklistItem('');
                    }}
                    style={{ ...btnO, padding: '6px 12px' }}
                  >
                    <Plus size={13} />
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}

      {projectChecklists.length === 0 && <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px' }}>Чек-листов нет</p>}
    </div>
  );
}
