import React from 'react';
import { Bot, Check, Eye, X } from 'lucide-react';
import { API } from '../api';
import { aiActionButtonStyle, borderedBlockStyle, closeButtonStyle, footerActionsStyle, formLabelStyle, formSectionStyle, installGridStyle, modalBodyStyle, modalFooterStyle, modalHeaderStyle, modalOverlayStyle, modalShellStyle, modalSummaryGridStyle, sectionHintStyle, sectionTitleStyle, statusPillStyle, summaryValueStyle, textareaStyle, twoColumnGridStyle, twoColumnGridTightStyle } from '../utils/modalStyles';

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
  if (!cable) return null;

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
    setEditingCable(prev => ({...prev, __aiLoading: true}));
    try {
      const res = await fetch(API + '/cable-journal/' + cable.id + '/ai-suggest', {method: 'POST'});
      if (!res.ok) {
        const error = await res.json().catch(() => ({}));
        throw new Error(error.detail || ('HTTP ' + res.status));
      }
      const data = await res.json();
      setEditingCable(prev => ({
        ...prev,
        normatives: data.normatives || prev.normatives,
        aiFilled: true,
        __aiLoading: false,
      }));
      setCableJournal(prev => prev.map(item => (
        item.id === cable.id
          ? {...item, normatives: data.normatives || item.normatives, aiFilled: true}
          : item
      )));
    } catch (error) {
      alert('Не получилось получить ответ от AI: ' + error.message);
      setEditingCable(prev => ({...prev, __aiLoading: false}));
    }
  };

  const saveCable = async () => {
    const body = {
      cableType,
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
    await fetch(API + '/cable-journal/' + cable.id, {
      method: 'PUT',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    setCableJournal(prev => prev.map(item => item.id === cable.id ? {...item, ...body, aiFilled: false} : item));
    setEditingCable(null);
  };

  return (
    <div onClick={() => setEditingCable(null)} style={modalOverlayStyle()}>
      <div onClick={event => event.stopPropagation()} style={modalShellStyle(card)}>
        <div style={modalHeaderStyle(C)}>
          <div>
            <b style={{color: C.text, fontSize: '16px', display: 'block'}}>⚡ Запись журнала кабельной продукции</b>
            <span style={{fontSize: '12px', color: C.textSec}}>{cableType + ' · ' + (cable.cableBrand || '—') + ' · ' + (cable.crossSection ? cable.crossSection + ' мм² × ' + (cable.coresCount || '?') + ' жил' : '—') + ' · ' + (cable.lengthReceived || 0) + ' м'}</span>
          </div>
          <div style={{display: 'flex', alignItems: 'center', gap: '10px'}}>
            <span style={statusPillStyle(C, cable.installedAt ? 'success' : 'warning')}>
              {cable.installedAt ? 'Проложен' : 'На складе'}
            </span>
            <button onClick={() => setEditingCable(null)} style={closeButtonStyle(btnG)}>
              <X size={14}/>
            </button>
          </div>
        </div>

        <div style={modalBodyStyle()}>
          {cable.aiFilled && (
            <div style={aiNotice}>
              <span style={aiNoticeIcon}>🤖</span>
              <span style={aiNoticeText}><b>Нормативы и мин. R подсказаны AI.</b> Проверь и сохрани — при правке поля метка снимется.</span>
            </div>
          )}

          <div style={modalSummaryGridStyle(C)}>
            <div><p style={labelStyle}>Марка кабеля</p><b style={summaryValue}>{cable.cableBrand || '—'}</b></div>
            <div><p style={labelStyle}>Тип системы</p><b style={summaryValue}>{cableType}</b></div>
            <div><p style={labelStyle}>Сечение жилы</p><b style={summaryValue}>{cable.crossSection ? cable.crossSection + ' мм²' : '—'}</b></div>
            <div><p style={labelStyle}>Кол-во жил</p><b style={summaryValue}>{cable.coresCount || '—'}</b></div>
            <div><p style={labelStyle}>Длина с барабана</p><b style={summaryValue}>{(cable.lengthReceived || 0) + ' м'}</b></div>
            <div><p style={labelStyle}>Поставщик</p><b style={summaryValue}>{cable.supplier || '—'}</b></div>
            <div><p style={labelStyle}>Дата приёмки</p><b style={summaryValue}>{cable.receivedAt || '—'}</b></div>
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
              <label style={labelStyle}>Место прокладки (объект, этаж, помещение)</label>
              <textarea value={cable.installationLocation || ''} onChange={event => updateCable('installationLocation', event.target.value)} placeholder="напр. этаж 2, эл.щитовая → коридор → квартиры 21-25" style={textareaStyle(inp, '50px')}/>
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
            <label style={labelStyle}>Применимые нормативы (ГОСТ/СП/ПУЭ){cable.aiFilled ? ' 🤖' : ''}</label>
            <textarea value={cable.normatives || ''} onChange={event => updateCable('normatives', event.target.value)} placeholder="Напр.: ПУЭ 7-е изд., ГОСТ Р 53769 (кабели силовые), СП 76.13330" style={textareaStyle(inp, '80px')}/>
          </div>
        </div>

        <div style={modalFooterStyle(C)}>
          <button onClick={() => showPreview(buildCableJournalContent([cable], cable.projectName, cable.receivedAt, cable.installedAt || cable.receivedAt), 'Запись кабеля')} style={btnB}>
            <Eye size={14}/>🖨️ Печать
          </button>
          <div style={footerActionsStyle()}>
            <button disabled={!!cable.__aiLoading} onClick={suggestByAI} style={aiActionButtonStyle(btnB, !!cable.__aiLoading)}>
              <Bot size={14}/>{cable.__aiLoading ? 'AI работает…' : '🤖 AI-подсказка нормативов и R изоляции'}
            </button>
            <button onClick={() => setEditingCable(null)} style={btnG}>Отмена</button>
            <button onClick={saveCable} style={btnO}>
              <Check size={14}/>Сохранить
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
