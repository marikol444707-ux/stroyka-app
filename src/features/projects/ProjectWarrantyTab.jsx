import React from 'react';

export default function ProjectWarrantyTab({
  API,
  C,
  Check,
  Plus,
  Trash2,
  badge,
  btnG,
  btnGr,
  btnO,
  btnR,
  card,
  createWarrantyDefectForm,
  inp,
  newWarrantyDefect,
  project,
  refreshData,
  setNewWarrantyDefect,
  setWarrantyEditForm,
  user,
  warrantyDefects,
  warrantyEditForm,
}) {
  const currentUser = user || {};
  const canEditWarranty = ['директор', 'зам_директора', 'бухгалтер', 'прораб'].includes(currentUser.role);
  const defects = warrantyDefects.filter(defect => defect.projectName === project.name);

  const openCount = defects.filter(defect => defect.status !== 'Закрыт').length;
  const fixedCount = defects.filter(defect => defect.status === 'Закрыт').length;

  const closeDefect = async (defect) => {
    const notes = prompt('Опишите как устранили:');
    if (!notes) return;
    await fetch(API + '/warranty-defects/' + defect.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'Закрыт', fixNotes: notes, fixedAt: new Date().toISOString().split('T')[0] }),
    });
    await refreshData();
  };

  const deleteDefect = async (defect) => {
    if (!window.confirm('Удалить дефект?')) return;
    await fetch(API + '/warranty-defects/' + defect.id, { method: 'DELETE' });
    await refreshData();
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px', flexWrap: 'wrap', gap: '8px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>🛠 Гарантийный период и дефекты</b>
        <button onClick={() => setNewWarrantyDefect(createWarrantyDefectForm())} style={btnO}>
          <Plus size={14} />Зафиксировать дефект
        </button>
      </div>

      <div style={{ ...card, padding: '14px', marginBottom: '12px', backgroundColor: C.bg, border: '1.5px solid ' + C.border }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', flexWrap: 'wrap', gap: '6px' }}>
          <b style={{ color: C.text, fontSize: '13px' }}>📋 Условия гарантии</b>
          {warrantyEditForm?.__projectId !== project.id && canEditWarranty && (
            <button
              onClick={() => setWarrantyEditForm({
                __projectId: project.id,
                warrantyStartDate: project.warrantyStartDate || project.warranty_start_date || '',
                warrantyEndDate: project.warrantyEndDate || project.warranty_end_date || '',
                warrantyContact: project.warrantyContact || project.warranty_contact || '',
              })}
              style={{ ...btnG, padding: '4px 10px', fontSize: '11px' }}
            >
              ✏️ Редактировать
            </button>
          )}
        </div>

        {warrantyEditForm?.__projectId === project.id ? (
          <div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '8px', marginBottom: '8px' }}>
              <div>
                <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Начало гарантии</p>
                <input type="date" value={warrantyEditForm.warrantyStartDate || ''} onChange={event => setWarrantyEditForm({ ...warrantyEditForm, warrantyStartDate: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
              </div>
              <div>
                <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Окончание</p>
                <input type="date" value={warrantyEditForm.warrantyEndDate || ''} onChange={event => setWarrantyEditForm({ ...warrantyEditForm, warrantyEndDate: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
              </div>
              <div>
                <p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Контакт</p>
                <input type="text" placeholder="ФИО + телефон" value={warrantyEditForm.warrantyContact || ''} onChange={event => setWarrantyEditForm({ ...warrantyEditForm, warrantyContact: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
              </div>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                onClick={async () => {
                  await fetch(API + '/projects/' + project.id, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      warrantyStartDate: warrantyEditForm.warrantyStartDate || null,
                      warrantyEndDate: warrantyEditForm.warrantyEndDate || null,
                      warrantyContact: warrantyEditForm.warrantyContact || '',
                    }),
                  });
                  await refreshData();
                  setWarrantyEditForm(null);
                }}
                style={btnO}
              >
                <Check size={14} />Сохранить
              </button>
              <button onClick={() => setWarrantyEditForm(null)} style={btnG}>Отмена</button>
            </div>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '8px', fontSize: '12px' }}>
            <div><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Начало гарантии</p><b style={{ color: C.text }}>{project.warrantyStartDate || project.warranty_start_date || 'не задано'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Окончание</p><b style={{ color: C.text }}>{project.warrantyEndDate || project.warranty_end_date || 'обычно +1 год'}</b></div>
            <div><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Контакт по гарантии</p><b style={{ color: C.text }}>{project.warrantyContact || project.warranty_contact || (project.foreman || '—')}</b></div>
          </div>
        )}

        <p style={{ color: C.textMuted, fontSize: '11px', margin: '8px 0 0', lineHeight: 1.4 }}>
          Срок гарантии устанавливается договором подряда (обычно 1-5 лет). В период гарантии устранение дефектов — за счёт подрядчика, если они вызваны его работой.
        </p>
      </div>

      {newWarrantyDefect && (
        <div style={{ ...card, padding: '16px', marginBottom: '14px', backgroundColor: C.bg, border: '1.5px solid ' + C.warningBorder }}>
          <b style={{ color: C.text, fontSize: '13px', display: 'block', marginBottom: '8px' }}>📝 Новый дефект</b>
          <textarea placeholder="Описание дефекта *" value={newWarrantyDefect.description} onChange={event => setNewWarrantyDefect({ ...newWarrantyDefect, description: event.target.value })} style={{ ...inp, minHeight: '60px', marginBottom: '8px' }} />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '8px' }}>
            <input type="date" value={newWarrantyDefect.foundAt} onChange={event => setNewWarrantyDefect({ ...newWarrantyDefect, foundAt: event.target.value })} title="Когда обнаружено" style={{ ...inp, marginBottom: 0 }} />
            <select value={newWarrantyDefect.severity} onChange={event => setNewWarrantyDefect({ ...newWarrantyDefect, severity: event.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {['Низкий', 'Средний', 'Высокий', 'Критический'].map(severity => <option key={severity}>{severity}</option>)}
            </select>
            <input placeholder="ФИО кто обнаружил" value={newWarrantyDefect.reportedBy} onChange={event => setNewWarrantyDefect({ ...newWarrantyDefect, reportedBy: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input placeholder="Телефон для связи" value={newWarrantyDefect.reporterPhone} onChange={event => setNewWarrantyDefect({ ...newWarrantyDefect, reporterPhone: event.target.value })} style={{ ...inp, marginBottom: 0 }} />
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={async () => {
                if (!newWarrantyDefect.description) {
                  alert('Опишите дефект');
                  return;
                }
                await fetch(API + '/warranty-defects', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ ...newWarrantyDefect, projectName: project.name, status: 'Открыт' }),
                });
                await refreshData();
                setNewWarrantyDefect(null);
              }}
              style={btnO}
            >
              <Check size={14} />Сохранить
            </button>
            <button onClick={() => setNewWarrantyDefect(null)} style={btnG}>Отмена</button>
          </div>
        </div>
      )}

      {defects.length === 0 ? (
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>Дефектов нет — гарантийных обращений по объекту не было.</div>
      ) : (
        <div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px', marginBottom: '12px' }}>
            <div style={{ ...card, padding: '10px', backgroundColor: C.dangerLight }}><p style={{ color: C.danger, fontSize: '11px', margin: '0 0 4px' }}>Открытых</p><b style={{ color: C.danger, fontSize: '16px' }}>{openCount}</b></div>
            <div style={{ ...card, padding: '10px', backgroundColor: C.successLight }}><p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>Устранено</p><b style={{ color: C.success, fontSize: '16px' }}>{fixedCount}</b></div>
            <div style={{ ...card, padding: '10px', backgroundColor: C.bg }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Всего</p><b style={{ color: C.text, fontSize: '16px' }}>{defects.length}</b></div>
          </div>
          {defects.map(defect => (
            <div key={defect.id} style={{ ...card, padding: '14px', marginBottom: '8px', borderLeft: '3px solid ' + (defect.status === 'Закрыт' ? C.success : defect.severity === 'Критический' ? C.danger : defect.severity === 'Высокий' ? C.warning : C.textSec) }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px', flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: '200px' }}>
                  <b style={{ color: C.text, fontSize: '13px' }}>{defect.description}</b>
                  <p style={{ color: C.textSec, margin: '4px 0', fontSize: '11px' }}>Обнаружено: {defect.foundAt}{defect.reportedBy ? ' · ' + defect.reportedBy : ''}{defect.reporterPhone ? ' · ' + defect.reporterPhone : ''}</p>
                  <p style={{ color: C.textMuted, margin: 0, fontSize: '11px' }}>Уровень: <b>{defect.severity || '—'}</b></p>
                  {defect.fixNotes && <div style={{ marginTop: '6px', padding: '8px 10px', backgroundColor: C.successLight, borderRadius: '6px', fontSize: '11px', color: C.success }}><b>Устранено ({defect.fixedAt || '—'}):</b> {defect.fixNotes}</div>}
                </div>
                <div style={{ display: 'flex', gap: '4px', alignItems: 'flex-start' }}>
                  <span style={badge(defect.status === 'Закрыт' ? C.success : defect.severity === 'Критический' ? C.danger : C.warning, defect.status === 'Закрыт' ? C.successLight : defect.severity === 'Критический' ? C.dangerLight : C.warningLight, defect.status === 'Закрыт' ? C.successBorder : defect.severity === 'Критический' ? C.dangerBorder : C.warningBorder)}>{defect.status || 'Открыт'}</span>
                  {defect.status !== 'Закрыт' && <button onClick={() => closeDefect(defect)} style={{ ...btnGr, padding: '4px 8px', fontSize: '11px' }}>Устранено</button>}
                  <button onClick={() => deleteDefect(defect)} style={{ ...btnR, padding: '4px 8px' }}><Trash2 size={11} /></button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
