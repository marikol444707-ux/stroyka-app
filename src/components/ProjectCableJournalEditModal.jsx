import React from 'react';
import { Bot, Check, Eye } from 'lucide-react';
import { API } from '../api';
import useJournalMutation, { journalRowKey } from '../hooks/useJournalMutation';
import { aiActionButtonStyle, borderedBlockStyle, footerActionsStyle, formLabelStyle, formSectionStyle, installGridStyle, modalBodyStyle, modalFooterStyle, modalHeaderStyle, modalOverlayStyle, modalShellStyle, modalSummaryGridStyle, sectionHintStyle, sectionTitleStyle, summaryValueStyle, twoColumnGridStyle, twoColumnGridTightStyle } from '../utils/modalStyles';
import { AiNotice, ModalHeaderActions, ModalTitleBlock, SummaryCell, TextareaField } from './common/ModalParts';

export default function ProjectCableJournalEditModal({
  cable,
  setEditingCable,
  setCableJournal,
  users = [],
  cableTypeOf,
  showPreview,
  buildCableJournalContent,
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
  const mutation = useJournalMutation(cable, { draft: true });
  if (!cable) return null;
  const identity = journalRowKey(cable);
  const close = () => { mutation.cancel(); setEditingCable(null); };

  const updateCable = (key, value) => setEditingCable({...cable, [key]: value});
  const responsibleNames = users
    .filter(user => ['прораб', 'главный_инженер', 'зам_директора'].includes(user.role))
    .map(user => user.name)
    .filter(Boolean);
  const labelStyle = formLabelStyle(C);
  const sectionStyle = formSectionStyle();
  const summaryValue = summaryValueStyle(C);
  const cableType = cableTypeOf(cable);

  const suggestByAI = async () => {
    await mutation.run({ url: API + '/cable-journal/' + cable.id + '/ai-suggest', method: 'POST',
      onSuccess: (data, current) => {
        const applySuggestion = item => ({ ...item, normatives: data.normatives || item.normatives, aiFilled: true });
        setEditingCable(prev => current() && journalRowKey(prev) === identity ? applySuggestion(prev) : prev);
        setCableJournal(prev => current() ? prev.map(item => journalRowKey(item) === identity ? applySuggestion(item) : item) : prev);
      },
    });
  };

  const saveCable = async () => {
    const body = {
      drumNumber: cable.drumNumber || '',
      manufacturer: cable.manufacturer || '',
      certificateNumber: cable.certificateNumber || '',
      passportNumber: cable.passportNumber || '',
      insulationBefore: Number(cable.insulationBefore) || 0,
      insulationAfter: Number(cable.insulationAfter) || 0,
      lengthInstalled: Number(cable.lengthInstalled) || 0,
      installationLocation: cable.installationLocation || '',
      installationMethod: cable.installationMethod || '',
      installedAt: cable.installedAt || '',
      responsibleItr: cable.responsibleItr || '',
      normatives: cable.normatives || '',
    };
    await mutation.run({ url: API + '/cable-journal/' + cable.id, body,
      onSuccess: (_data, current) => {
        setCableJournal(prev => current() ? prev.map(item => journalRowKey(item) === identity ? {...item, ...body, aiFilled: false} : item) : prev);
        setEditingCable(prev => current() && journalRowKey(prev) === identity ? null : prev);
      },
    });
  };

  return (
    <div onClick={close} style={modalOverlayStyle()}>
      <div onClick={event => event.stopPropagation()} style={modalShellStyle(card)}>
        <div style={modalHeaderStyle(C)}>
          <ModalTitleBlock
            title="⚡ Запись журнала кабельной продукции"
            subtitle={cableType + ' · ' + (cable.cableBrand || '—') + ' · ' + (cable.crossSection ? cable.crossSection + ' мм² × ' + (cable.coresCount || '?') + ' жил' : '—') + ' · ' + (cable.lengthReceived || 0) + ' м'}
            C={C}
          />
          <ModalHeaderActions
            status={cable.installedAt ? 'Проложен' : 'На складе'}
            statusVariant={cable.installedAt ? 'success' : 'warning'}
            onClose={close}
            C={C}
            btnG={btnG}
          />
        </div>

        <fieldset disabled={mutation.busy} aria-busy={mutation.busy} style={{ ...modalBodyStyle(), border: 0, margin: 0, minWidth: 0 }}>
          <AiNotice show={cable.aiFilled} noticeStyle={aiNotice} iconStyle={aiNoticeIcon} textStyle={aiNoticeText}>
            <b>Нормативы и мин. R подсказаны AI.</b> Проверь и сохрани — при правке поля метка снимется.
          </AiNotice>

          <div style={modalSummaryGridStyle(C)}>
            <SummaryCell label="Марка кабеля" labelStyle={labelStyle} valueStyle={summaryValue}>{cable.cableBrand || '—'}</SummaryCell>
            <SummaryCell label="Тип системы" labelStyle={labelStyle} valueStyle={summaryValue}>{cableType}</SummaryCell>
            <SummaryCell label="Сечение жилы" labelStyle={labelStyle} valueStyle={summaryValue}>{cable.crossSection ? cable.crossSection + ' мм²' : '—'}</SummaryCell>
            <SummaryCell label="Кол-во жил" labelStyle={labelStyle} valueStyle={summaryValue}>{cable.coresCount || '—'}</SummaryCell>
            <SummaryCell label="Длина с барабана" labelStyle={labelStyle} valueStyle={summaryValue}>{(cable.lengthReceived || 0) + ' м'}</SummaryCell>
            <SummaryCell label="Поставщик" labelStyle={labelStyle} valueStyle={summaryValue}>{cable.supplier || '—'}</SummaryCell>
            <SummaryCell label="Дата приёмки" labelStyle={labelStyle} valueStyle={summaryValue}>{cable.receivedAt || '—'}</SummaryCell>
          </div>

          <div style={twoColumnGridStyle()}>
            <div>
              <label style={labelStyle}>№ барабана / бухты</label>
              <input value={cable.drumNumber || ''} onChange={event => updateCable('drumNumber', event.target.value)} placeholder="напр. барабан №47" style={inp}/>
            </div>
            <div>
              <label style={labelStyle}>Изготовитель</label>
              <input value={cable.manufacturer || ''} onChange={event => updateCable('manufacturer', event.target.value)} placeholder="напр. Камкабель, Севкабель" style={inp}/>
            </div>
          </div>

          <div style={twoColumnGridStyle()}>
            <div>
              <label style={labelStyle}>Сертификат соответствия №</label>
              <input value={cable.certificateNumber || ''} onChange={event => updateCable('certificateNumber', event.target.value)} style={inp}/>
            </div>
            <div>
              <label style={labelStyle}>Паспорт качества №</label>
              <input value={cable.passportNumber || ''} onChange={event => updateCable('passportNumber', event.target.value)} style={inp}/>
            </div>
          </div>

          <div style={borderedBlockStyle(C)}>
            <b style={sectionTitleStyle(C)}>🔌 Замеры сопротивления изоляции (мегаомметр)</b>
            <div style={twoColumnGridTightStyle()}>
              <div>
                <label style={labelStyle}>R изоляции ДО прокладки, МΩ</label>
                <input type="number" inputMode="decimal" step="0.1" value={cable.insulationBefore || ''} onChange={event => updateCable('insulationBefore', event.target.value)} placeholder="напр. 500" style={inp}/>
              </div>
              <div>
                <label style={labelStyle}>R изоляции ПОСЛЕ прокладки, МΩ</label>
                <input type="number" inputMode="decimal" step="0.1" value={cable.insulationAfter || ''} onChange={event => updateCable('insulationAfter', event.target.value)} placeholder="напр. 480" style={inp}/>
              </div>
            </div>
            <p style={sectionHintStyle(C)}>По ПУЭ для большинства силовых кабелей мин. R изоляции = 0.5 МΩ. AI-подсказка ниже даст точное значение для этой марки.</p>
          </div>

          <div style={borderedBlockStyle(C)}>
            <b style={sectionTitleStyle(C)}>🔧 Монтаж</b>
            <div style={sectionStyle}>
              <TextareaField
                label="Место прокладки (объект, этаж, помещение)"
                value={cable.installationLocation}
                onChange={value => updateCable('installationLocation', value)}
                placeholder="напр. этаж 2, эл.щитовая → коридор → квартиры 21-25"
                inputStyle={inp}
                labelStyle={labelStyle}
                minHeight="50px"
              />
            </div>
            <div style={installGridStyle()}>
              <div>
                <label style={labelStyle}>Способ прокладки</label>
                <select value={cable.installationMethod || ''} onChange={event => updateCable('installationMethod', event.target.value)} style={inp}>
                  <option value="">— не указано —</option>
                  <option>Открыто</option>
                  <option>В кабель-канале</option>
                  <option>В трубе</option>
                  <option>По лотку</option>
                  <option>В слаботочном лотке</option>
                  <option>В гофре</option>
                  <option>В металлорукаве</option>
                  <option>На скобах</option>
                  <option>В земле</option>
                  <option>Под штукатуркой</option>
                </select>
              </div>
              <div>
                <label style={labelStyle}>Длина проложенная, м</label>
                <input type="number" inputMode="decimal" step="0.1" value={cable.lengthInstalled || ''} onChange={event => updateCable('lengthInstalled', event.target.value)} style={inp}/>
              </div>
              <div>
                <label style={labelStyle}>Дата монтажа</label>
                <input type="date" value={cable.installedAt || ''} onChange={event => updateCable('installedAt', event.target.value)} style={inp}/>
              </div>
            </div>
          </div>

          <div style={sectionStyle}>
            <label style={labelStyle}>Ответственный ИТР / мастер</label>
            <input list="cable-itr-list" value={cable.responsibleItr || ''} onChange={event => updateCable('responsibleItr', event.target.value)} placeholder="ФИО электрика или слаботочника" style={inp}/>
            <datalist id="cable-itr-list">{responsibleNames.map(name => <option key={name} value={name}/>)}</datalist>
          </div>
          <div style={sectionStyle}>
            <TextareaField
              label={'Применимые нормативы (ГОСТ/СП/ПУЭ)' + (cable.aiFilled ? ' 🤖' : '')}
              value={cable.normatives}
              onChange={value => updateCable('normatives', value)}
              placeholder="Напр.: ПУЭ 7-е изд., ГОСТ Р 53769 (кабели силовые), СП 76.13330"
              inputStyle={inp}
              labelStyle={labelStyle}
              minHeight="80px"
            />
          </div>
        </fieldset>

        {mutation.error && <div role="alert" style={{ color: C.danger, padding: '10px 24px' }}>{mutation.error}</div>}
        {mutation.busy && <div role="status" style={{ color: C.textSec, padding: '10px 24px' }}>Обработка запроса…</div>}
        <div style={modalFooterStyle(C)}>
          {mutation.printDirty && <span style={{ color: C.textSec }}>Сохраните изменения перед печатью и откройте запись заново.</span>}
          <button disabled={mutation.busy || mutation.printDirty} onClick={() => mutation.print(buildCableJournalContent, showPreview, 'Запись кабеля', cable.installedAt)} style={btnB}>
            <Eye size={14}/>🖨️ Печать
          </button>
          <div style={footerActionsStyle()}>
            <button disabled={mutation.busy} onClick={suggestByAI} style={aiActionButtonStyle(btnB, mutation.busy)}>
              <Bot size={14}/>🤖 AI-подсказка нормативов и R изоляции
            </button>
            <button onClick={close} style={btnG}>Отмена</button>
            <button disabled={mutation.busy} onClick={saveCable} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
