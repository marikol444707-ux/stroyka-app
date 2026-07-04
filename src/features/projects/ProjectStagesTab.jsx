import React from 'react';

export default function ProjectStagesTab({
  C,
  Check,
  Plus,
  STAGE_STATUSES,
  Trash2,
  X,
  badge,
  btnG,
  btnO,
  btnR,
  card,
  inp,
  isProrab,
  newStage,
  project,
  projectStages,
  saveProjectStage,
  setNewStage,
  setShowForm,
  showForm,
  updateStage,
  deleteStage,
}) {
  const stages = projectStages.filter(stage => stage.projectName === project.name);
  const statusColors = {
    'Не начат': [C.textSec, C.bgGray, C.border],
    'В работе': [C.info, C.infoLight, C.infoBorder],
    'Завершён': [C.success, C.successLight, C.successBorder],
    'Заморожен': [C.warning, C.warningLight, C.warningBorder],
    'Просрочен': [C.danger, C.dangerLight, C.dangerBorder],
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <b style={{ color: C.text }}>Этапы проекта</b>
        {isProrab() && (
          <button onClick={() => setShowForm(showForm === 'stages' ? false : 'stages')} style={btnO}>
            <Plus size={14} />Добавить этап
          </button>
        )}
      </div>

      {showForm === 'stages' && (
        <div style={{ ...card, padding: '16px', marginBottom: '16px', backgroundColor: C.bg }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <input placeholder="Название этапа *" value={newStage.name} onChange={e => setNewStage({ ...newStage, name: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <select value={newStage.status} onChange={e => setNewStage({ ...newStage, status: e.target.value })} style={{ ...inp, marginBottom: 0 }}>
              {STAGE_STATUSES.map(status => <option key={status}>{status}</option>)}
            </select>
            <input type="date" placeholder="Начало" value={newStage.startDate} onChange={e => setNewStage({ ...newStage, startDate: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input type="date" placeholder="Конец" value={newStage.endDate} onChange={e => setNewStage({ ...newStage, endDate: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <input placeholder="Ответственный" value={newStage.responsible} onChange={e => setNewStage({ ...newStage, responsible: e.target.value })} style={{ ...inp, marginBottom: 0 }} />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <label style={{ fontSize: '12px', color: C.textSec, whiteSpace: 'nowrap' }}>Прогресс: {newStage.progress}%</label>
              <input type="range" min="0" max="100" value={newStage.progress} onChange={e => setNewStage({ ...newStage, progress: Number(e.target.value) })} style={{ flex: 1, accentColor: C.accent }} />
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px', marginTop: '10px' }}>
            <button onClick={() => saveProjectStage(project.id, project.name)} style={btnO}><Check size={14} />Сохранить</button>
            <button onClick={() => setShowForm(false)} style={btnG}><X size={14} />Отмена</button>
          </div>
        </div>
      )}

      {stages.map(stage => {
        const colors = statusColors[stage.status] || statusColors['Не начат'];
        return (
          <div key={stage.id} style={{ ...card, padding: '14px', marginBottom: '10px', borderLeft: '3px solid ' + colors[0] }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                  <b style={{ color: C.text, fontSize: '13px' }}>{stage.name}</b>
                  <span style={badge(colors[0], colors[1], colors[2])}>{stage.status}</span>
                </div>
                {(stage.startDate || stage.endDate) && <p style={{ color: C.textSec, margin: '0 0 4px', fontSize: '12px' }}>{(stage.startDate || '') + (stage.endDate ? ' — ' + stage.endDate : '')}</p>}
                {stage.responsible && <p style={{ color: C.textSec, margin: '0 0 6px', fontSize: '12px' }}>{'👤 ' + stage.responsible}</p>}
                <div style={{ backgroundColor: C.bgGray, borderRadius: '4px', height: '6px', marginTop: '6px' }}>
                  <div style={{ backgroundColor: colors[0], width: (stage.progress || 0) + '%', height: '100%', borderRadius: '4px' }} />
                </div>
                <p style={{ color: C.textMuted, margin: '4px 0 0', fontSize: '11px' }}>{(stage.progress || 0) + '% выполнено'}</p>
              </div>
              {isProrab() && (
                <div style={{ display: 'flex', gap: '4px', marginLeft: '10px' }}>
                  <select value={stage.status} onChange={async e => { await updateStage({ ...stage, status: e.target.value }); }} style={{ fontSize: '11px', padding: '3px 6px', border: '1.5px solid ' + C.border, borderRadius: '6px', cursor: 'pointer' }}>
                    {STAGE_STATUSES.map(status => <option key={status}>{status}</option>)}
                  </select>
                  <button onClick={() => deleteStage(stage.id)} style={{ ...btnR, padding: '4px 8px' }}><Trash2 size={11} /></button>
                </div>
              )}
            </div>
          </div>
        );
      })}

      {stages.length === 0 && <p style={{ color: C.textMuted, textAlign: 'center', padding: '20px' }}>Этапов нет — добавьте первый!</p>}
    </div>
  );
}
