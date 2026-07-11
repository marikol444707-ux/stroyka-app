import React from 'react';
import { Bot, Check, Eye } from 'lucide-react';
import { API } from '../api';
import { aiActionButtonStyle, footerActionsStyle, formLabelStyle, formSectionStyle, infoPanelStyle, modalBodyStyle, modalFooterStyle, modalHeaderStyle, modalOverlayStyle, modalShellStyle, modalSummaryGridStyle, smallIconButtonStyle, summaryValueStyle, threeColumnGridStyle, twoColumnGridStyle } from '../utils/modalStyles';
import { AiNotice, ModalHeaderActions, ModalTitleBlock, SummaryCell, TextareaField } from './common/ModalParts';
import PhotoAttachmentField from './PhotoAttachmentField';

export default function ProjectWorkJournalEditModal({
  journal,
  setEditingJournal,
  setWorkJournal,
  weatherLog = [],
  users = [],
  hiddenActs = [],
  setEditingAct,
  showPreview,
  buildWorkJournalContent,
  fmtMeasure,
  C,
  card,
  inp,
  btnB,
  btnG,
  btnO,
  appendPhotos,
  fileSrc,
  setShowPhotoModal,
  aiNotice,
  aiNoticeIcon,
  aiNoticeText,
}) {
  if (!journal) return null;

  const updateJournal = (key, value) => setEditingJournal({...journal, [key]: value});
  const todayWeather = weatherLog.find(item => item.projectName === journal.project && item.date === journal.date);
  const prorabNames = users
    .filter(user => ['прораб', 'главный_инженер', 'зам_директора'].includes(user.role))
    .map(user => user.name)
    .filter(Boolean);
  const labelStyle = formLabelStyle(C);
  const sectionStyle = formSectionStyle();
  const summaryValue = summaryValueStyle(C);

  const fillByAI = async () => {
    setEditingJournal(prev => ({...prev, __aiLoading: true}));
    try {
      const res = await fetch(API + '/work-journal/' + journal.id + '/ai-prefill', {method: 'POST'});
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || ('HTTP ' + res.status));
      }
      const data = await res.json();
      setEditingJournal(prev => ({
        ...prev,
        normatives: data.normatives || prev.normatives,
        projectDocs: data.projectDocs || prev.projectDocs,
        comment: (prev.comment && prev.comment.trim()) ? prev.comment : (data.qualityNote || ''),
        aiFilled: true,
        __aiLoading: false,
      }));
      setWorkJournal(prev => prev.map(item => (
        item.id === journal.id
          ? {...item, normatives: data.normatives || item.normatives, projectDocs: data.projectDocs || item.projectDocs, aiFilled: true}
          : item
      )));
    } catch (error) {
      alert('Не получилось получить ответ от AI: ' + error.message);
      setEditingJournal(prev => ({...prev, __aiLoading: false}));
    }
  };

  const saveJournal = async () => {
    const body = {
      status: journal.status || 'На проверке',
      comment: journal.comment || '',
      responsibleItr: journal.responsibleItr || '',
      weather: journal.weather || '',
      timeStart: journal.timeStart || '',
      timeEnd: journal.timeEnd || '',
      qualityStatus: journal.qualityStatus || '',
      normatives: journal.normatives || '',
      projectDocs: journal.projectDocs || '',
      sectionName: journal.sectionName || '',
      hiddenWork: !!journal.hiddenWork,
      photoUrl: journal.photoUrl || '',
    };
    const res = await fetch(API + '/work-journal/' + journal.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      alert(data.detail || data.error || 'Не удалось сохранить запись журнала');
      return;
    }
    setWorkJournal(prev => prev.map(item => item.id === journal.id ? {...item, ...body, aiFilled: false} : item));
    setEditingJournal(null);
  };

  const openHiddenAct = () => {
    const matchingAct = hiddenActs.find(act => (
      act.projectName === journal.project && (act.workName || '').trim() === (journal.description || '').trim()
    ));
    if (matchingAct) {
      setEditingJournal(null);
      setEditingAct(matchingAct);
      return;
    }
    alert('Печатная форма АОСР для этой записи пока не создана. Она появляется из сметы: отметьте позицию 🔒 и заполните «Сделано».');
  };

  return (
    <div onClick={() => setEditingJournal(null)} style={modalOverlayStyle()}>
      <div onClick={event => event.stopPropagation()} style={modalShellStyle(card)}>
        <div style={modalHeaderStyle(C)}>
          <ModalTitleBlock
            title="📖 Запись журнала производства работ"
            subtitle={(journal.project || '—') + ' · ' + (journal.date || '—') + ' · ' + (journal.masterName || '—')}
            C={C}
          />
          <ModalHeaderActions
            status={journal.status || '—'}
            statusVariant={journal.status === 'Подтверждено' ? 'success' : journal.status === 'Отклонено' ? 'danger' : 'warning'}
            onClose={() => setEditingJournal(null)}
            C={C}
            btnG={btnG}
          />
        </div>

        <div style={modalBodyStyle()}>
          <AiNotice show={journal.aiFilled} noticeStyle={aiNotice} iconStyle={aiNoticeIcon} textStyle={aiNoticeText}>
            <b>Поля заполнены AI.</b> Проверь нормативы и проектные документы — при сохранении после правки метка снимется.
          </AiNotice>

          <div style={modalSummaryGridStyle(C)}>
            <SummaryCell label="Раздел сметы" labelStyle={labelStyle} valueStyle={summaryValue}>{journal.sectionName || '—'}</SummaryCell>
            <SummaryCell label="Работа" labelStyle={labelStyle} valueStyle={summaryValue}>{journal.description}</SummaryCell>
            <SummaryCell label="Исполнитель" labelStyle={labelStyle} valueStyle={summaryValue}>{journal.masterName || '—'}</SummaryCell>
            <SummaryCell label="Объём" labelStyle={labelStyle} valueStyle={summaryValue}>{fmtMeasure(journal.quantity, journal.unit)}</SummaryCell>
            <div><p style={labelStyle}>Сумма</p><b style={{fontSize: '14px', color: C.accent}}>{Number(journal.total || 0).toLocaleString('ru-RU') + ' ₽'}</b></div>
            <SummaryCell label="Дата" labelStyle={labelStyle} valueStyle={summaryValue}>{journal.date || '—'}</SummaryCell>
          </div>

          <div style={twoColumnGridStyle()}>
            <div>
              <label style={labelStyle}>Ответственный ИТР (прораб)</label>
              <input list="jrnl-itr-list" value={journal.responsibleItr || ''} onChange={event => updateJournal('responsibleItr', event.target.value)} placeholder="ФИО прораба или инженера" style={inp}/>
              <datalist id="jrnl-itr-list">{prorabNames.map(name => <option key={name} value={name}/>)}</datalist>
            </div>
            <div>
              <label style={labelStyle}>Статус</label>
              <select value={journal.status || 'На проверке'} onChange={event => updateJournal('status', event.target.value)} style={inp}>
                <option>На проверке</option>
                <option>Подтверждено</option>
                <option>Отклонено</option>
              </select>
            </div>
          </div>

          <div style={threeColumnGridStyle()}>
            <div><label style={labelStyle}>Начало работы</label><input type="time" value={journal.timeStart || ''} onChange={event => updateJournal('timeStart', event.target.value)} style={inp}/></div>
            <div><label style={labelStyle}>Окончание</label><input type="time" value={journal.timeEnd || ''} onChange={event => updateJournal('timeEnd', event.target.value)} style={inp}/></div>
            <div>
              <label style={labelStyle}>Метеоусловия (температура, осадки, ветер)</label>
              <div style={{display: 'flex', gap: '4px'}}>
                <input value={journal.weather || ''} onChange={event => updateJournal('weather', event.target.value)} placeholder="напр. +12°C, без осадков, ветер 3 м/с" style={{...inp, marginBottom: 0, flex: 1}}/>
                {todayWeather && (
                  <button onClick={() => updateJournal('weather', (todayWeather.condition || '') + ', ' + (todayWeather.temperature || '') + '°C, ветер ' + (todayWeather.windSpeed || '') + ' м/с')} title="Подтянуть из журнала погоды" style={smallIconButtonStyle(btnG)}>📡</button>
                )}
              </div>
            </div>
          </div>

          <div style={sectionStyle}>
            <label style={labelStyle}>Качество / соответствие проекту</label>
            <select value={journal.qualityStatus || ''} onChange={event => updateJournal('qualityStatus', event.target.value)} style={inp}>
              <option value="">— не указано —</option>
              <option>Соответствует проекту</option>
              <option>Соответствует с замечаниями</option>
              <option>Не соответствует</option>
            </select>
          </div>

          <div style={sectionStyle}>
            <TextareaField
              label={'Применимые нормативы (СНиП/СП/ГОСТ)' + (journal.aiFilled ? ' 🤖' : '')}
              value={journal.normatives}
              onChange={value => updateJournal('normatives', value)}
              placeholder="Напр.: СП 71.13330.2017, ГОСТ 30693-2000"
              inputStyle={inp}
              labelStyle={labelStyle}
              minHeight="60px"
            />
          </div>
          <div style={sectionStyle}>
            <TextareaField
              label={'Проектная документация (разделы, листы)' + (journal.aiFilled ? ' 🤖' : '')}
              value={journal.projectDocs}
              onChange={value => updateJournal('projectDocs', value)}
              placeholder="Напр.: раздел КЖ, лист 12; раздел АР, узел 4"
              inputStyle={inp}
              labelStyle={labelStyle}
              minHeight="60px"
            />
          </div>
          <div style={sectionStyle}>
            <label style={labelStyle}>Использованные материалы</label>
            <div style={infoPanelStyle(C, {padding: '10px', whiteSpace: 'pre-wrap'})}>
              {journal.materialsUsed ? (typeof journal.materialsUsed === 'string' ? journal.materialsUsed : JSON.stringify(journal.materialsUsed)) : '(не указаны)'}
            </div>
          </div>
          <div style={sectionStyle}>
            <TextareaField
              label="Комментарий / заключение"
              value={journal.comment}
              onChange={value => updateJournal('comment', value)}
              placeholder="Замечания, особенности производства работ, ссылки на акты"
              inputStyle={inp}
              labelStyle={labelStyle}
            />
          </div>
          <div style={sectionStyle}>
            <PhotoAttachmentField
              C={C}
              btnG={btnG}
              value={journal.photoUrl || ''}
              onChange={photoUrl => updateJournal('photoUrl', photoUrl)}
              appendPhotos={appendPhotos}
              fileSrc={fileSrc}
              setShowPhotoModal={setShowPhotoModal}
              projectName={journal.project || ''}
              context="work-journal"
              title="Фото работы / помещения"
              protectedPreview
            />
          </div>

          {journal.hiddenWork && (
            <div style={infoPanelStyle(C, {marginBottom: '10px'})}>
              🔒 По этой записи доступна печатная форма АОСР. Проверьте реквизиты и распечатайте акт для исполнительной документации.
            </div>
          )}
        </div>

        <div style={modalFooterStyle(C)}>
          <div style={footerActionsStyle()}>
            <button onClick={() => showPreview(buildWorkJournalContent([journal], journal.project, journal.date, journal.date), 'Запись журнала')} style={btnB}>
              <Eye size={14}/>🖨️ Печать
            </button>
            {journal.hiddenWork && (
              <button onClick={openHiddenAct} style={{...btnB, backgroundColor: '#10b981', color: 'white', borderColor: '#059669'}}>🔒 АОСР / печать</button>
            )}
          </div>
          <div style={footerActionsStyle()}>
            <button disabled={!!journal.__aiLoading} onClick={fillByAI} style={aiActionButtonStyle(btnB, !!journal.__aiLoading)}>
              <Bot size={14}/>{journal.__aiLoading ? 'AI работает…' : (journal.aiFilled ? '🤖 Перезаполнить AI' : '🤖 Заполнить через AI')}
            </button>
            <button onClick={() => setEditingJournal(null)} style={btnG}>Отмена</button>
            <button onClick={saveJournal} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
