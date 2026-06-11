import React from 'react';
import { Bot, Check, Eye, X } from 'lucide-react';
import { API } from '../api';
import { aiActionButtonStyle, checkboxInputStyle, checkboxLabelStyle, checkboxRowStyle, closeButtonStyle, footerActionsStyle, formLabelStyle, formSectionStyle, modalBodyStyle, modalFooterStyle, modalHeaderStyle, modalOverlayStyle, modalShellStyle, modalSummaryGridStyle, statusPillStyle, summaryValueStyle, textareaStyle, twoColumnGridStyle } from '../utils/modalStyles';

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
  const labelStyle = formLabelStyle(C);
  const sectionStyle = formSectionStyle();
  const summaryValue = summaryValueStyle(C);

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
    <div onClick={() => setEditingInspection(null)} style={modalOverlayStyle()}>
      <div onClick={event => event.stopPropagation()} style={modalShellStyle(card, 'min(820px,100%)')}>
        <div style={modalHeaderStyle(C)}>
          <div>
            <b style={{color: C.text, fontSize: '16px', display: 'block'}}>📦 Входной контроль материала</b>
            <span style={{fontSize: '12px', color: C.textSec}}>{(inspection.materialName || '—') + ' · ' + (inspection.quantity || 0) + ' ' + (inspection.unit || '') + ' · ' + (inspection.supplier || '—')}</span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
            <span style={statusPillStyle(C, inspection.inspected ? 'success' : 'warning')}>
              {inspection.inspected ? 'Проверено' : 'Ждёт проверки'}
            </span>
            <button onClick={() => setEditingInspection(null)} style={closeButtonStyle(btnG)}>
              <X size={14}/>
            </button>
          </div>
        </div>

        <div style={modalBodyStyle()}>
          {inspection.aiFilled && (
            <div style={aiNotice}>
              <span style={aiNoticeIcon}>🤖</span>
              <span style={aiNoticeText}><b>Поле «Нормативы» подсказано AI.</b> Проверь и сохрани — при правке метка снимется.</span>
            </div>
          )}

          <div style={modalSummaryGridStyle(C)}>
            <div><p style={labelStyle}>Материал</p><b style={summaryValue}>{inspection.materialName || '—'}</b></div>
            <div><p style={labelStyle}>Количество</p><b style={summaryValue}>{(inspection.quantity || 0) + ' ' + (inspection.unit || '')}</b></div>
            <div><p style={labelStyle}>Поставщик</p><b style={summaryValue}>{inspection.supplier || '—'}</b></div>
            <div><p style={labelStyle}>Дата приёмки</p><b style={summaryValue}>{inspection.receivedAt || '—'}</b></div>
          </div>

          <div style={twoColumnGridStyle()}>
            <div>
              <label style={labelStyle}>№ партии (на упаковке/паспорте)</label>
              <input value={inspection.batchNumber || ''} onChange={event => updateInspection('batchNumber', event.target.value)} placeholder="напр. №147" style={inp}/>
            </div>
            <div>
              <label style={labelStyle}>Паспорт качества №</label>
              <input value={inspection.passportNumber || ''} onChange={event => updateInspection('passportNumber', event.target.value)} placeholder="напр. ПК-2026/05/12" style={inp}/>
            </div>
          </div>

          <div style={twoColumnGridStyle()}>
            <div>
              <label style={labelStyle}>Сертификат соответствия №</label>
              <input value={inspection.certificateNumber || ''} onChange={event => updateInspection('certificateNumber', event.target.value)} placeholder="напр. РОСС RU.AB12.H00000" style={inp}/>
            </div>
            <div>
              <label style={labelStyle}>Протокол испытаний №</label>
              <input value={inspection.testProtocolNumber || ''} onChange={event => updateInspection('testProtocolNumber', event.target.value)} placeholder="напр. ПИ-15 от 14.05.2026" style={inp}/>
            </div>
          </div>

          <div style={twoColumnGridStyle()}>
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
            <textarea value={inspection.remarks || ''} onChange={event => updateInspection('remarks', event.target.value)} placeholder="Замечания по качеству, упаковке, документам" style={textareaStyle(inp)}/>
          </div>
          <div style={checkboxRowStyle(C)}>
            <input type="checkbox" id="mi-checked" checked={!!inspection.inspected} onChange={event => updateInspection('inspected', event.target.checked)} style={checkboxInputStyle()}/>
            <label htmlFor="mi-checked" style={checkboxLabelStyle(C)}>Входной контроль завершён — материал можно выдавать на работы</label>
          </div>
        </div>

        <div style={modalFooterStyle(C)}>
          <button onClick={() => showPreview(buildMaterialInspectionContent([inspection], inspection.projectName, inspection.receivedAt, inspection.receivedAt), 'Запись входного контроля')} style={btnB}>
            <Eye size={14}/>🖨️ Печать
          </button>
          <div style={footerActionsStyle()}>
            <button disabled={!!inspection.__aiLoading} onClick={suggestByAI} style={aiActionButtonStyle(btnB, !!inspection.__aiLoading)}>
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
