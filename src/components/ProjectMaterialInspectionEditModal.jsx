import React from 'react';
import { Bot, Check, Eye } from 'lucide-react';
import { API } from '../api';
import useJournalMutation, { journalRowKey } from '../hooks/useJournalMutation';
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
  const mutation = useJournalMutation(inspection, { draft: true });
  if (!inspection) return null;
  const identity = journalRowKey(inspection);
  const close = () => { mutation.cancel(); setEditingInspection(null); };

  const updateInspection = (key, value) => setEditingInspection({...inspection, [key]: value});
  const labelStyle = formLabelStyle(C);
  const sectionStyle = formSectionStyle();
  const summaryValue = summaryValueStyle(C);

  const suggestByAI = async () => {
    await mutation.run({ url: API + '/material-inspection/' + inspection.id + '/ai-suggest', method: 'POST',
      onSuccess: (data, current) => {
        const applySuggestion = item => ({ ...item, normatives: data.normatives || item.normatives,
          remarks: item.remarks?.trim() || !data.requiredDocs ? item.remarks : 'Требуемые документы: ' + data.requiredDocs,
          aiFilled: true });
        setEditingInspection(prev => current() && journalRowKey(prev) === identity ? applySuggestion(prev) : prev);
        setMaterialInspections(prev => current() ? prev.map(item => journalRowKey(item) === identity ? applySuggestion(item) : item) : prev);
      },
    });
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
    await mutation.run({ url: API + '/material-inspection/' + inspection.id, body,
      onSuccess: (_data, current) => {
        setMaterialInspections(prev => current() ? prev.map(item => journalRowKey(item) === identity ? {...item, ...body, aiFilled: false} : item) : prev);
        setEditingInspection(prev => current() && journalRowKey(prev) === identity ? null : prev);
      },
    });
  };

  return (
    <div onClick={close} style={modalOverlayStyle()}>
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
            onClose={close}
            C={C}
            btnG={btnG}
          />
        </div>

        <fieldset disabled={mutation.busy} aria-busy={mutation.busy} style={{ ...modalBodyStyle(), border: 0, margin: 0, minWidth: 0 }}>
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
        </fieldset>

        {mutation.error && <div role="alert" style={{ color: C.danger, padding: '10px 24px' }}>{mutation.error}</div>}
        {mutation.busy && <div role="status" style={{ color: C.textSec, padding: '10px 24px' }}>Обработка запроса…</div>}
        <div style={modalFooterStyle(C)}>
          {mutation.printDirty && <span style={{ color: C.textSec }}>Сохраните изменения перед печатью и откройте запись заново.</span>}
          <button disabled={mutation.busy || mutation.printDirty} onClick={() => mutation.print(buildMaterialInspectionContent, showPreview, 'Запись входного контроля')} style={btnB}>
            <Eye size={14}/>🖨️ Печать
          </button>
          <div style={footerActionsStyle()}>
            <button disabled={mutation.busy} onClick={suggestByAI} style={aiActionButtonStyle(btnB, mutation.busy)}>
              <Bot size={14}/>🤖 AI-подсказка нормативов
            </button>
            <button onClick={close} style={btnG}>Отмена</button>
            <button disabled={mutation.busy} onClick={saveInspection} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
