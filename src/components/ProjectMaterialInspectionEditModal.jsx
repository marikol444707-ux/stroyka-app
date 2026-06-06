import React from 'react';
import { Bot, Check, Eye, X } from 'lucide-react';
import { API } from '../api';

export default function ProjectMaterialInspectionEditModal({
  inspection,
  setEditingInspection,
  setMaterialInspections,
  showPreview,
  buildMaterialInspectionContent,
  C,
  card,
  inp,
  btnB,
  btnG,
  btnO,
  aiNotice,
  aiNoticeIcon,
  aiNoticeText,
}) {
  if (!inspection) return null;

  const updateInspection = (key, value) => setEditingInspection({...inspection, [key]: value});
  const labelStyle = {fontSize: '11px', color: C.textSec, fontWeight: '600', marginBottom: '4px', display: 'block'};
  const sectionStyle = {marginBottom: '14px'};

  const suggestByAI = async () => {
    setEditingInspection(prev => ({...prev, __aiLoading: true}));
    try {
      const res = await fetch(API + '/material-inspection/' + inspection.id + '/ai-suggest', {method: 'POST'});
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || ('HTTP ' + res.status));
      }
      const data = await res.json();
      setEditingInspection(prev => ({
        ...prev,
        normatives: data.normatives || prev.normatives,
        remarks: (prev.remarks && prev.remarks.trim()) ? prev.remarks : ('Требуемые документы: ' + (data.requiredDocs || '')),
        aiFilled: true,
        __aiLoading: false,
      }));
      setMaterialInspections(prev => prev.map(item => (
        item.id === inspection.id
          ? {...item, normatives: data.normatives || item.normatives, aiFilled: true}
          : item
      )));
    } catch (error) {
      alert('Не получилось получить ответ от AI: ' + error.message);
      setEditingInspection(prev => ({...prev, __aiLoading: false}));
    }
  };

  const saveInspection = async () => {
    const body = {
      batchNumber: inspection.batchNumber || '',
      passportNumber: inspection.passportNumber || '',
      certificateNumber: inspection.certificateNumber || '',
      testProtocolNumber: inspection.testProtocolNumber || '',
      visualInspectionResult: inspection.visualInspectionResult || '',
      remarks: inspection.remarks || '',
      inspectorName: inspection.inspectorName || '',
      inspectedAt: inspection.inspectedAt || '',
      inspected: !!inspection.inspected,
      normatives: inspection.normatives || '',
    };
    await fetch(API + '/material-inspection/' + inspection.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    setMaterialInspections(prev => prev.map(item => item.id === inspection.id ? {...item, ...body, aiFilled: false} : item));
    setEditingInspection(null);
  };

  return (
    <div onClick={() => setEditingInspection(null)} style={{position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.55)', zIndex: 1600, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '20px'}}>
      <div onClick={event => event.stopPropagation()} style={{...card, padding: 0, width: 'min(820px,100%)', maxHeight: '92vh', display: 'flex', flexDirection: 'column', overflow: 'hidden'}}>
        <div style={{padding: '16px 20px', borderBottom: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px'}}>
          <div>
            <b style={{color: C.text, fontSize: '16px', display: 'block'}}>📦 Входной контроль материала</b>
            <span style={{fontSize: '12px', color: C.textSec}}>{(inspection.materialName || '—') + ' · ' + (inspection.quantity || 0) + ' ' + (inspection.unit || '') + ' · ' + (inspection.supplier || '—')}</span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
            <span style={{
              padding: '4px 10px',
              borderRadius: '12px',
              fontSize: '12px',
              fontWeight: '600',
              backgroundColor: inspection.inspected ? C.successLight : C.warningLight,
              color: inspection.inspected ? C.success : C.warning,
            }}>
              {inspection.inspected ? 'Проверено' : 'Ждёт проверки'}
            </span>
            <button onClick={() => setEditingInspection(null)} style={{...btnG, padding: '5px 10px'}}>
              <X size={14}/>
            </button>
          </div>
        </div>

        <div style={{flex: 1, overflowY: 'auto', padding: '18px 20px'}}>
          {inspection.aiFilled && (
            <div style={aiNotice}>
              <span style={aiNoticeIcon}>🤖</span>
              <span style={aiNoticeText}><b>Поле «Нормативы» подсказано AI.</b> Проверь и сохрани — при правке метка снимется.</span>
            </div>
          )}

          <div style={{display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(180px,1fr))', gap: '10px', marginBottom: '18px', padding: '12px', backgroundColor: C.bg, borderRadius: '10px', border: '1.5px solid ' + C.border}}>
            <div><p style={labelStyle}>Материал</p><b style={{fontSize: '13px', color: C.text}}>{inspection.materialName || '—'}</b></div>
            <div><p style={labelStyle}>Количество</p><b style={{fontSize: '13px', color: C.text}}>{(inspection.quantity || 0) + ' ' + (inspection.unit || '')}</b></div>
            <div><p style={labelStyle}>Поставщик</p><b style={{fontSize: '13px', color: C.text}}>{inspection.supplier || '—'}</b></div>
            <div><p style={labelStyle}>Дата приёмки</p><b style={{fontSize: '13px', color: C.text}}>{inspection.receivedAt || '—'}</b></div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px'}}>
            <div>
              <label style={labelStyle}>№ партии (на упаковке/паспорте)</label>
              <input value={inspection.batchNumber || ''} onChange={event => updateInspection('batchNumber', event.target.value)} placeholder="напр. №147" style={inp}/>
            </div>
            <div>
              <label style={labelStyle}>Паспорт качества №</label>
              <input value={inspection.passportNumber || ''} onChange={event => updateInspection('passportNumber', event.target.value)} placeholder="напр. ПК-2026/05/12" style={inp}/>
            </div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px'}}>
            <div>
              <label style={labelStyle}>Сертификат соответствия №</label>
              <input value={inspection.certificateNumber || ''} onChange={event => updateInspection('certificateNumber', event.target.value)} placeholder="напр. РОСС RU.AB12.H00000" style={inp}/>
            </div>
            <div>
              <label style={labelStyle}>Протокол испытаний №</label>
              <input value={inspection.testProtocolNumber || ''} onChange={event => updateInspection('testProtocolNumber', event.target.value)} placeholder="напр. ПИ-15 от 14.05.2026" style={inp}/>
            </div>
          </div>

          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '14px'}}>
            <div>
              <label style={labelStyle}>Результат визуального осмотра</label>
              <select value={inspection.visualInspectionResult || ''} onChange={event => updateInspection('visualInspectionResult', event.target.value)} style={inp}>
                <option value="">— не указано —</option>
                <option>Соответствует</option>
                <option>С замечаниями</option>
                <option>Не соответствует</option>
              </select>
            </div>
            <div>
              <label style={labelStyle}>Дата осмотра</label>
              <input type="date" value={inspection.inspectedAt || ''} onChange={event => updateInspection('inspectedAt', event.target.value)} style={inp}/>
            </div>
          </div>

          <div style={sectionStyle}>
            <label style={labelStyle}>ФИО лица, проводившего входной контроль</label>
            <input value={inspection.inspectorName || ''} onChange={event => updateInspection('inspectorName', event.target.value)} placeholder="ФИО прораба или кладовщика" style={inp}/>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>Применимые нормативы (ГОСТ/СП/СНиП){inspection.aiFilled ? ' 🤖' : ''}</label>
            <textarea value={inspection.normatives || ''} onChange={event => updateInspection('normatives', event.target.value)} placeholder="Напр.: ГОСТ 7473-2010 (бетон), ГОСТ 5781-82 (арматура)" style={{...inp, minHeight: '60px', resize: 'vertical'}}/>
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>Замечания / комментарий</label>
            <textarea value={inspection.remarks || ''} onChange={event => updateInspection('remarks', event.target.value)} placeholder="Замечания по качеству, упаковке, документам" style={{...inp, minHeight: '70px', resize: 'vertical'}}/>
          </div>
          <div style={{padding: '10px 12px', backgroundColor: C.bg, borderRadius: '8px', border: '1.5px solid ' + C.border, display: 'flex', alignItems: 'center', gap: '10px'}}>
            <input type="checkbox" id="mi-checked" checked={!!inspection.inspected} onChange={event => updateInspection('inspected', event.target.checked)} style={{width: '18px', height: '18px', cursor: 'pointer'}}/>
            <label htmlFor="mi-checked" style={{fontSize: '13px', color: C.text, cursor: 'pointer', fontWeight: '600'}}>Входной контроль завершён — материал можно выдавать на работы</label>
          </div>
        </div>

        <div style={{padding: '14px 20px', borderTop: '1.5px solid ' + C.border, backgroundColor: C.bg, display: 'flex', gap: '8px', justifyContent: 'space-between', flexWrap: 'wrap'}}>
          <button onClick={() => showPreview(buildMaterialInspectionContent([inspection], inspection.projectName, inspection.receivedAt, inspection.receivedAt), 'Запись входного контроля')} style={btnB}>
            <Eye size={14}/>🖨️ Печать
          </button>
          <div style={{display: 'flex', gap: '8px', flexWrap: 'wrap'}}>
            <button disabled={!!inspection.__aiLoading} onClick={suggestByAI} style={{...btnB, backgroundColor: '#10b981', color: 'white', borderColor: '#059669', opacity: inspection.__aiLoading ? 0.6 : 1, cursor: inspection.__aiLoading ? 'not-allowed' : 'pointer'}}>
              <Bot size={14}/>{inspection.__aiLoading ? 'AI работает…' : '🤖 AI-подсказка нормативов'}
            </button>
            <button onClick={() => setEditingInspection(null)} style={btnG}>Отмена</button>
            <button onClick={saveInspection} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
