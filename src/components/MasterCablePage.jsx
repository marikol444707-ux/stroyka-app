import React from 'react';
import { Check, Eye } from 'lucide-react';

export default function MasterCablePage({
  API,
  C,
  btnB,
  btnO,
  buildCableJournalContent,
  cableJournal,
  cableTypeOf,
  card,
  projects,
  setCableJournal,
  showPreview,
  user,
}) {
  const projectNames = new Set((projects || []).map((project) => project.name));
  const rows = (cableJournal || []).filter((item) => projectNames.size === 0 || projectNames.has(item.projectName));
  const groupOrder = ['Силовой кабель', 'СКС / интернет', 'Пожарная сигнализация', 'Слаботочка / сигнализация', 'Кабель'];
  const rowsByType = rows.reduce((acc, item) => {
    const type = cableTypeOf(item);
    acc[type] = acc[type] || [];
    acc[type].push(item);
    return acc;
  }, {});
  const activeTypes = [...groupOrder.filter((type) => rowsByType[type]?.length), ...Object.keys(rowsByType).filter((type) => !groupOrder.includes(type))];

  const updateCable = (id, key, value) => {
    setCableJournal((prev) => prev.map((item) => (item.id === id ? { ...item, [key]: value } : item)));
  };

  const saveCable = async (item) => {
    const body = {
      cableType: cableTypeOf(item),
      lengthInstalled: Number(item.lengthInstalled) || 0,
      installationLocation: item.installationLocation || '',
      installationMethod: item.installationMethod || '',
      installedAt: item.installedAt || '',
      insulationBefore: Number(item.insulationBefore) || 0,
      insulationAfter: Number(item.insulationAfter) || 0,
      responsibleItr: item.responsibleItr || user.name,
    };
    await fetch(API + '/cable-journal/' + item.id, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setCableJournal((prev) => prev.map((row) => (row.id === item.id ? { ...row, ...body } : row)));
    alert('Запись кабельного журнала сохранена');
  };

  return (
    <div>
      <h3 style={{ color: C.text, marginBottom: '14px', fontSize: '18px', fontWeight: '700' }}>⚡ Кабель и слаботочка</h3>
      <div style={{ ...card, padding: '12px', marginBottom: '14px', backgroundColor: C.infoLight, border: '1.5px solid ' + C.infoBorder }}>
        <p style={{ color: C.text, fontSize: '12px', margin: 0 }}>
          Заполняй фактический монтаж силового кабеля, СКС/интернета, слаботочки и пожарной сигнализации: помещение/трасса, способ прокладки, длину, дату и замеры. Эти данные попадут в журнал кабельной продукции по объекту.
        </p>
      </div>

      {rows.length === 0 && (
        <div style={{ ...card, padding: '28px', textAlign: 'center', color: C.textMuted, fontSize: '13px' }}>
          Кабельных позиций пока нет.
          <br />
          Они появляются автоматически из поставок и накладных: ВВГ/NYM/СИП, UTP/FTP/SFTP, КПС/КСВВ/КСПВ и пожарные FRLS/FRHF.
        </div>
      )}

      {activeTypes.map((type) => (
        <div key={type} style={{ marginBottom: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', gap: '10px', flexWrap: 'wrap' }}>
            <b style={{ color: C.text, fontSize: '14px' }}>{type}</b>
            <span
              style={{
                color: C.accent,
                backgroundColor: C.accentLight,
                border: '1.5px solid ' + C.accentBorder,
                borderRadius: '999px',
                padding: '4px 10px',
                fontSize: '12px',
                fontWeight: '700',
              }}
            >
              {rowsByType[type].length + ' поз.'}
            </span>
          </div>

          {rowsByType[type].map((item) => (
            <div key={item.id} style={{ ...card, padding: '14px', marginBottom: '10px', borderLeft: '4px solid ' + (item.installedAt ? C.success : C.warning) }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', alignItems: 'flex-start', flexWrap: 'wrap', marginBottom: '10px' }}>
                <div style={{ flex: '1 1 220px' }}>
                  <b style={{ color: C.text, fontSize: '14px' }}>{item.cableBrand || 'Кабель'}</b>
                  <p style={{ color: C.textSec, margin: '3px 0', fontSize: '12px' }}>
                    {(item.projectName || '—') + ' · поступило ' + (item.lengthReceived || 0) + ' м' + (item.supplier ? ' · ' + item.supplier : '')}
                  </p>
                  <p style={{ color: C.textMuted, margin: 0, fontSize: '11px' }}>
                    {cableTypeOf(item) + ' · ' + (item.crossSection ? 'сечение ' + item.crossSection + ' мм²' : 'сечение не указано')}
                    {item.coresCount ? ' · ' + item.coresCount + ' жил' : ''}
                  </p>
                </div>
                <span
                  style={{
                    color: item.installedAt ? C.success : C.warning,
                    backgroundColor: item.installedAt ? C.successLight : C.warningLight,
                    border: '1.5px solid ' + (item.installedAt ? C.successBorder : C.warningBorder),
                    borderRadius: '999px',
                    padding: '4px 10px',
                    fontSize: '12px',
                    fontWeight: '700',
                  }}
                >
                  {item.installedAt ? 'Проложен' : 'К монтажу'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                <input placeholder="Место: комната, трасса, щит" value={item.installationLocation || ''} onChange={(e) => updateCable(item.id, 'installationLocation', e.target.value)} style={{ ...C.inp, marginBottom: 0 }} />
                <select value={item.installationMethod || ''} onChange={(e) => updateCable(item.id, 'installationMethod', e.target.value)} style={{ ...C.inp, marginBottom: 0 }}>
                  <option value="">Способ прокладки</option>
                  <option>Открыто</option>
                  <option>В кабель-канале</option>
                  <option>В трубе</option>
                  <option>По лотку</option>
                  <option>В слаботочном лотке</option>
                  <option>В гофре</option>
                  <option>В металлорукаве</option>
                  <option>На скобах</option>
                  <option>Под штукатуркой</option>
                  <option>В земле</option>
                </select>
                <input placeholder="Проложено, м" type="number" step="any" inputMode="decimal" value={item.lengthInstalled || ''} onChange={(e) => updateCable(item.id, 'lengthInstalled', e.target.value)} style={{ ...C.inp, marginBottom: 0 }} />
                <input type="date" value={item.installedAt || ''} onChange={(e) => updateCable(item.id, 'installedAt', e.target.value)} style={{ ...C.inp, marginBottom: 0 }} />
                <input placeholder="R до прокладки, МΩ" type="number" step="0.1" inputMode="decimal" value={item.insulationBefore || ''} onChange={(e) => updateCable(item.id, 'insulationBefore', e.target.value)} style={{ ...C.inp, marginBottom: 0 }} />
                <input placeholder="R после прокладки, МΩ" type="number" step="0.1" inputMode="decimal" value={item.insulationAfter || ''} onChange={(e) => updateCable(item.id, 'insulationAfter', e.target.value)} style={{ ...C.inp, marginBottom: 0 }} />
              </div>

              <div style={{ display: 'flex', gap: '8px', marginTop: '10px', flexWrap: 'wrap' }}>
                <button onClick={() => saveCable(item)} style={btnO}>
                  <Check size={14} />
                  Сохранить монтаж
                </button>
                <button onClick={() => showPreview(buildCableJournalContent([item], item.projectName, item.receivedAt, item.installedAt || item.receivedAt), 'Запись кабеля')} style={btnB}>
                  <Eye size={14} />
                  Печать
                </button>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
