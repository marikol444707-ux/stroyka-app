import React from 'react';

export default function ProjectSupervisorActsTab({
  C,
  card,
  fileSrc,
  project,
  setShowPhotoModal,
  supervisorActs,
}) {
  const acts = (supervisorActs || []).filter(act => act.projectName === project.name);

  if (acts.length === 0) {
    return (
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
          <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>📝 Акты осмотра / обследования от технадзора</b>
          <span style={{ fontSize: '11px', color: C.textMuted }}>Создаются технадзором в его кабинете</span>
        </div>
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          Технадзор пока не загружал актов осмотра по этому объекту.
        </div>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '15px' }}>
        <b style={{ color: C.text, fontSize: '15px', fontWeight: '700' }}>📝 Акты осмотра / обследования от технадзора</b>
        <span style={{ fontSize: '11px', color: C.textMuted }}>Создаются технадзором в его кабинете</span>
      </div>
      {acts.map(act => (
        <div key={act.id} style={{ ...card, padding: '14px', marginBottom: '8px', borderLeft: '3px solid ' + C.accent }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '10px' }}>
            <div style={{ flex: 1 }}>
              <b style={{ color: C.text, fontSize: '13px' }}>{act.actNumber + ' · ' + act.actType}</b>
              <p style={{ color: C.textSec, margin: '4px 0', fontSize: '12px' }}>{act.description || '—'}</p>
              {act.findings && <p style={{ color: C.text, margin: '4px 0', fontSize: '11px' }}><b>Обнаружено:</b> {act.findings}</p>}
              {act.recommendations && <p style={{ color: C.text, margin: '4px 0', fontSize: '11px' }}><b>Рекомендации:</b> {act.recommendations}</p>}
              <p style={{ color: C.textMuted, margin: '4px 0 0', fontSize: '11px' }}>{act.date + ' · ' + (act.issuedBy || '—')}</p>
            </div>
            {act.photoUrl && (
              <img
                src={fileSrc(act.photoUrl)}
                alt=""
                onClick={() => setShowPhotoModal(fileSrc(act.photoUrl))}
                style={{ width: '56px', height: '56px', borderRadius: '6px', objectFit: 'cover', cursor: 'pointer', flexShrink: 0 }}
              />
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
