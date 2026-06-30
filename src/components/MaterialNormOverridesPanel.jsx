import React from 'react';
import { C, badge, card } from '../constants/uiTheme';

export default function MaterialNormOverridesPanel({
  selectedProject,
  materialNormOverrides,
  isMobile,
}) {
  const overrides = (materialNormOverrides || []).filter(o => !selectedProject || o.projectName === selectedProject);
  if (!overrides.length) return null;

  return (
    <div style={{...card, padding: '14px', marginBottom: '16px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder}}>
      <div style={{display: 'flex', justifyContent: 'space-between', gap: '8px', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap'}}>
        <div>
          <b style={{color: C.text, fontSize: '13px'}}>🎯 Поправки норм объекта</b>
          <p style={{color: C.textSec, margin: '3px 0 0', fontSize: '11px'}}>Работают только внутри выбранного объекта или конкретной сметы. Глобальный справочник компании не меняют.</p>
        </div>
        <span style={badge(C.info, C.infoLight, C.infoBorder)}>{overrides.length}</span>
      </div>
      <div style={{display: 'grid', gap: '8px'}}>
        {overrides.slice(0, 10).map(o => (
          <div key={o.id} style={{display: 'grid', gridTemplateColumns: isMobile ? '1fr' : 'minmax(220px,1.2fr) minmax(240px,1.5fr) 160px', gap: '10px', alignItems: 'center', padding: '10px 12px', borderRadius: '8px', backgroundColor: C.bgWhite, border: '1px solid ' + C.border}}>
            <div style={{minWidth: 0}}>
              <b style={{color: C.text, fontSize: '12px', display: 'block'}}>{o.materialName || o.name || 'Материал'}</b>
              <p style={{color: C.textMuted, margin: '2px 0 0', fontSize: '10px'}}>{o.projectName || 'Объект'}{o.estimateId ? ' · смета #' + o.estimateId : ''}</p>
            </div>
            <div style={{minWidth: 0}}>
              <span style={{color: C.textMuted, fontSize: '10px', textTransform: 'uppercase'}}>Работа / причина</span>
              <p style={{color: C.textSec, margin: '2px 0 0', fontSize: '11px'}}>{o.workName || ((o.work || []).join(', ')) || '—'}</p>
              {o.reason && <p style={{color: C.textMuted, margin: '2px 0 0', fontSize: '10px'}}>{o.reason}</p>}
            </div>
            <div>
              <span style={{color: C.textMuted, fontSize: '10px', textTransform: 'uppercase'}}>Норма</span>
              <p style={{color: C.success, margin: '2px 0 0', fontSize: '12px', fontWeight: '800'}}>{Number(o.qtyPerUnit || 0).toLocaleString('ru-RU')} {o.materialUnit || ''} / {o.workUnit || ''}</p>
            </div>
          </div>
        ))}
        {overrides.length > 10 && <p style={{color: C.textMuted, fontSize: '11px', margin: '0'}}>Показано 10 из {overrides.length}. Выберите объект выше, чтобы сузить список.</p>}
      </div>
    </div>
  );
}
