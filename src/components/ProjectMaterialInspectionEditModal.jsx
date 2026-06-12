import React from 'react';
import { Bot, Check, Eye } from 'lucide-react';
import { API } from '../api';
import { aiActionButtonStyle, checkboxInputStyle, checkboxLabelStyle, checkboxRowStyle, footerActionsStyle, formLabelStyle, formSectionStyle, modalBodyStyle, modalFooterStyle, modalHeaderStyle, modalOverlayStyle, modalShellStyle, modalSummaryGridStyle, summaryValueStyle, twoColumnGridStyle } from '../utils/modalStyles';
import { AiNotice, ModalHeaderActions, ModalTitleBlock, SummaryCell, TextareaField } from './common/ModalParts';

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
          <ModalTitleBlock
            title="📦 Входной контроль материала"
            subtitle={(inspection.materialName || '—') + ' · ' + (inspection.quantity || 0) + ' ' + (inspection.unit || '') + ' · ' + (inspection.supplier || '—')}
            C={C}
          />
          <ModalHeaderActions
            status={inspection.inspected ? 'Проверено' : 'Ждёт проверки'}
            statusVariant={inspection.inspected ? 'success' : 'warning'}
            onClose={() => setEditingInspection(null)}
            C={C}
            btnG={btnG}
          />
        </div>

        <div style={modalBodyStyle()}>
          <AiNotice show={inspection.aiFilled} noticeStyle={aiNotice} iconStyle={aiNoticeIcon} textStyle={aiNoticeText}>
            <b>Поле «Нормативы» подсказано AI.</b> Проверь и сохрани — при правке метка снимется.
          </AiNotice>

          <div style={modalSummaryGridStyle(C)}>
            <SummaryCell label="Материал" labelStyle={labelStyle} valueStyle={summaryValue}>{inspection.materialName || '—'}</SummaryCell>
            <SummaryCell label="Количество" labelStyle={labelStyle} valueStyle={summaryValue}>{(inspection.quantity || 0) + ' ' + (inspection.unit || '')}</SummaryCell>
            <SummaryCell label="Поставщик" labelStyle={labelStyle} valueStyle={summaryValue}>{inspection.supplier || '—'}</SummaryCell>
            <SummaryCell label="Дата приёмки" labelStyle={labelStyle} valueStyle={summaryValue}>{inspection.receivedAt || '—'}</SummaryCell>
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
            <TextareaField
              label="Замечания / комментарий"
              value={inspection.remarks}
              onChange={value => updateInspection('remarks', value)}
              placeholder="Замечания по качеству, упаковке, документам"
              inputStyle={inp}
              labelStyle={labelStyle}
            />
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
