import React from 'react';
import { API } from '../api';

const SIGNATURES = [
  {role: 'Заказчик', field: 'signedCustomer'},
  {role: 'Технадзор', field: 'signedSupervisor'},
  {role: 'Генподрядчик', field: 'signedContractor'},
  {role: 'Субподрядчик', field: 'signedSubcontractor'},
];

const SIGNATURE_CONFIG = {
  customer: {
    title: 'Заказчик',
    field: 'signedCustomer',
    dateField: 'signedCustomerAt',
    materialLabel: 'Материалы',
    helper: '',
    tone: 'accent',
    showProjectDocs: false,
  },
  supervisor: {
    title: 'Технадзор',
    field: 'signedSupervisor',
    dateField: 'signedSupervisorAt',
    materialLabel: 'Материалы и применённые конструкции',
    helper: 'Впиши свои ФИО и дату → нажми «Подписать». Подпись подрядчика, заказчика и субподрядчика поставит каждый со своей стороны.',
    tone: 'warning',
    showProjectDocs: true,
  },
};

export default function ProjectHiddenWorksActSignatureModal({
  act,
  mode,
  setEditingAct,
  setHiddenActs,
  C,
  card,
  inp,
  btnG,
  btnO,
}) {
  if (!act) return null;

  const config = SIGNATURE_CONFIG[mode] || SIGNATURE_CONFIG.customer;
  const updateAct = (key, value) => setEditingAct({...act, [key]: value});
  const allSigned = !!(act.signedCustomer && act.signedSupervisor && act.signedContractor && act.signedSubcontractor);
  const toneColor = config.tone === 'warning' ? C.warning : C.accent;
  const toneLight = config.tone === 'warning' ? C.warningLight : C.accentLight;
  const toneBorder = config.tone === 'warning' ? C.warningBorder : C.accentBorder;

  const saveSignature = async () => {
    const body = {
      status: allSigned ? 'Подписан' : (act.status || 'Черновик'),
      signedCustomer: act.signedCustomer || '',
      signedSupervisor: act.signedSupervisor || '',
      signedContractor: act.signedContractor || '',
      signedSubcontractor: act.signedSubcontractor || '',
      signedCustomerAt: act.signedCustomerAt || '',
      signedSupervisorAt: act.signedSupervisorAt || '',
      signedContractorAt: act.signedContractorAt || '',
      signedSubcontractorAt: act.signedSubcontractorAt || '',
      conclusion: act.conclusion || '',
      comments: act.comments || '',
      materialsUsed: act.materialsUsed || '',
      projectDocs: act.projectDocs || '',
      photos: act.photos || '',
      certificates: act.certificates || '',
      city: act.city || '',
    };
    const res = await fetch(API + '/hidden-works-acts/' + act.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    setHiddenActs(prev => prev.map(item => (
      item.id === act.id ? {...item, ...body, status: data.status || body.status} : item
    )));
    setEditingAct(null);
  };

  return (
    <div onClick={() => setEditingAct(null)} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.55)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'}}>
      <div onClick={event => event.stopPropagation()} style={{...card, padding: 0, width: 'min(640px,100%)', maxHeight: '92vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
        <div style={{padding: '16px 20px', borderBottom: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
          <div>
            <b style={{color: C.text, fontSize: '15px', display: 'block'}}>🔒 {act.actNumber}</b>
            <span style={{fontSize: '11px', color: C.textSec}}>Акт освидетельствования скрытых работ</span>
          </div>
          <button onClick={() => setEditingAct(null)} style={{...btnG, padding: '5px 10px'}}>✕</button>
        </div>

        <div style={{flex: 1, overflowY: 'auto', padding: '18px 20px'}}>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px', padding: '12px', backgroundColor: C.bg, borderRadius: '10px', border: '1.5px solid ' + C.border}}>
            <div><p style={labelStyle(C)}>Работа</p><b style={valueStyle(C)}>{act.workName}</b></div>
            <div><p style={labelStyle(C)}>Объём</p><b style={valueStyle(C)}>{Number(act.quantity || 0).toLocaleString('ru-RU') + ' ' + (act.unit || '')}</b></div>
            <div><p style={labelStyle(C)}>Бригада</p><b style={valueStyle(C)}>{act.brigade || '—'}</b></div>
            <div><p style={labelStyle(C)}>Дата</p><b style={valueStyle(C)}>{act.workDate || '—'}</b></div>
          </div>

          <p style={plainLabel(C)}>{config.materialLabel}</p>
          <div style={readOnlyBox(C)}>{act.materialsUsed || '(не указаны подрядчиком)'}</div>

          {config.showProjectDocs && (
            <>
              <p style={plainLabel(C)}>Проектная документация</p>
              <div style={readOnlyBox(C)}>{act.projectDocs || '(не указаны)'}</div>
            </>
          )}

          <p style={plainLabel(C)}>Заключение комиссии</p>
          <div style={readOnlyBox(C)}>{act.conclusion || '(подрядчик ещё не заполнил)'}</div>

          <div style={{padding: '14px', backgroundColor: toneLight, border: '1.5px solid ' + toneBorder, borderRadius: '10px'}}>
            <b style={{display: 'block', marginBottom: '10px', color: toneColor, fontSize: '13px'}}>✍️ Моя подпись ({config.title})</b>
            <input value={act[config.field] || ''} onChange={event => updateAct(config.field, event.target.value)} placeholder="ФИО, должность, организация" style={{...inp, marginBottom: '8px'}}/>
            <input type="date" value={act[config.dateField] || ''} onChange={event => updateAct(config.dateField, event.target.value)} style={inp}/>
            {config.helper && <p style={{fontSize: '11px', color: C.textSec, margin: '8px 0 0', lineHeight: 1.4}}>{config.helper}</p>}
          </div>

          <div style={{marginTop: '14px', padding: '10px', backgroundColor: C.bg, borderRadius: '8px', border: '1.5px solid ' + C.border, fontSize: '11px'}}>
            <b style={{color: C.text, fontSize: '12px'}}>Подписи 4 сторон:</b>
            <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px'}}>
              {SIGNATURES.map(signature => (
                <div key={signature.field}>
                  <span style={{color: act[signature.field] ? C.success : C.textMuted}}>
                    {act[signature.field] ? '✅' : '⏳'} {signature.role}:
                  </span>{' '}
                  {act[signature.field] || '—'}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{padding: '14px 20px', borderTop: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', gap: '8px', justifyContent: 'flex-end'}}>
          <button onClick={() => setEditingAct(null)} style={btnG}>Отмена</button>
          <button onClick={saveSignature} style={btnO}>✍️ Подписать</button>
        </div>
      </div>
    </div>
  );
}

function labelStyle(C) {
  return {fontSize: '11px', color: C.textSec, margin: '0 0 4px', fontWeight: '600'};
}

function valueStyle(C) {
  return {fontSize: '13px', color: C.text};
}

function plainLabel(C) {
  return {fontSize: '11px', color: C.textSec, fontWeight: '600', marginBottom: '4px'};
}

function readOnlyBox(C) {
  return {
    padding: '10px',
    backgroundColor: C.bg,
    borderRadius: '8px',
    border: '1.5px solid ' + C.border,
    fontSize: '12px',
    color: C.textSec,
    whiteSpace: 'pre-wrap',
    marginBottom: '14px',
    minHeight: '40px',
  };
}
