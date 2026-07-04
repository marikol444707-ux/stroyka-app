import React from 'react';

export default function ProjectCableJournalTab({
  C,
  Eye,
  badge,
  btnB,
  btnG,
  buildCableJournalContent,
  cableJournal,
  cableTypeOf,
  card,
  journalDiagnosticMode,
  journalPackage,
  project,
  projectJournalDiagnostics,
  setEditingCable,
  setJournalDiagnosticMode,
  showPreview,
  tbl,
  tblC,
  tblH,
  toNum,
}) {
  const diagnostics = projectJournalDiagnostics(project.name);
  const rows = cableJournal.filter(row => row.projectName === project.name);

  const modeControls = (
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
      <button onClick={() => setJournalDiagnosticMode('all')} style={{ ...btnG, fontSize: '12px', padding: '6px 10px', backgroundColor: journalDiagnosticMode === 'all' ? C.accent : C.bg, color: journalDiagnosticMode === 'all' ? 'white' : C.text }}>
        Все записи: {rows.length}
      </button>
      <button onClick={() => setJournalDiagnosticMode('unlinked')} style={{ ...btnG, fontSize: '12px', padding: '6px 10px', backgroundColor: journalDiagnosticMode === 'unlinked' ? C.warning : C.bg, color: journalDiagnosticMode === 'unlinked' ? 'white' : C.text }}>
        Не связано: {diagnostics.cableWithoutJournal.length}
      </button>
    </div>
  );

  const unlinkedNotice = diagnostics.cableWithoutJournal.length > 0 && (
    <div style={{ ...card, padding: '12px', marginBottom: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
      <b style={{ color: C.warning, fontSize: '13px' }}>Кабель на складе без журнальной записи: {diagnostics.cableWithoutJournal.length}</b>
      <p style={{ color: C.textSec, fontSize: '11px', margin: '4px 0 0' }}>
        Система распознала кабель в остатках объекта, но не видит соответствующую строку в журнале кабельной продукции.
      </p>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
        {diagnostics.cableWithoutJournal.slice(0, 6).map((material, index) => (
          <span key={(material.id || material.name || 'c') + '-' + index} style={badge(C.warning, C.warningLight, C.warningBorder)}>
            {material.name} · {toNum(material.quantity)} {material.unit || ''}
          </span>
        ))}
      </div>
    </div>
  );

  if (journalDiagnosticMode === 'unlinked') {
    return (
      <div>
        {modeControls}
        {diagnostics.cableWithoutJournal.length === 0 ? (
          <div style={{ ...card, padding: '18px', color: C.success, backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, fontWeight: '700' }}>
            Весь кабель на складе связан с журналом кабельной продукции.
          </div>
        ) : (
          <div style={{ ...card, padding: 0, overflow: 'auto' }}>
            <table style={tbl}>
              <thead>
                <tr>
                  <th style={tblH}>Кабель на складе</th>
                  <th style={tblH}>Тип</th>
                  <th style={tblH}>Кол-во</th>
                  <th style={tblH}>Ед.</th>
                  <th style={tblH}>Пакет работ</th>
                  <th style={tblH}>Что сделать</th>
                </tr>
              </thead>
              <tbody>
                {diagnostics.cableWithoutJournal.map((material, index) => (
                  <tr key={(material.id || material.name || 'cable') + '-' + index}>
                    <td style={{ ...tblC, maxWidth: '320px', whiteSpace: 'normal' }}>{material.name}</td>
                    <td style={tblC}>{cableTypeOf({ cableBrand: material.name })}</td>
                    <td style={tblC}>{toNum(material.quantity)}</td>
                    <td style={tblC}>{material.unit || '—'}</td>
                    <td style={tblC}>{journalPackage(material)}</td>
                    <td style={{ ...tblC, color: C.textSec, maxWidth: '260px', whiteSpace: 'normal' }}>
                      Проверить распознавание марки, пакет работ или backfill кабельного журнала.
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div>
        {modeControls}
        {unlinkedNotice}
        <div style={{ ...card, padding: '30px', textAlign: 'center', color: C.textMuted }}>
          <div style={{ fontSize: '40px', marginBottom: '10px' }}>⚡</div>
          <p style={{ margin: '0 0 8px', fontWeight: '600' }}>Записей пока нет</p>
          <p style={{ fontSize: '12px', margin: 0, lineHeight: 1.6 }}>
            Записи создаются автоматически при приходе кабеля (по поставке или накладной).<br />
            Система распознаёт силовые ВВГ/NYM/СИП, СКС UTP/FTP/SFTP, слаботочку КСВВ/КСПВ и пожарные КПС/КПСЭ/FRLS.
          </p>
        </div>
      </div>
    );
  }

  const installedCount = rows.filter(row => row.installedAt).length;
  const pendingCount = rows.length - installedCount;
  const totalLength = rows.reduce((sum, row) => sum + Number(row.lengthReceived || 0), 0);
  const typeCounts = rows.reduce((acc, row) => {
    const type = cableTypeOf(row);
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {});

  return (
    <div>
      {modeControls}
      {unlinkedNotice}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '10px', marginBottom: '14px' }}>
        <div style={{ ...card, padding: '12px', backgroundColor: C.bg }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Записей</p><b style={{ color: C.text, fontSize: '16px' }}>{rows.length}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}><p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px' }}>Ждут монтажа</p><b style={{ color: C.warning, fontSize: '16px' }}>{pendingCount}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder }}><p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>Проложено</p><b style={{ color: C.success, fontSize: '16px' }}>{installedCount}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder }}><p style={{ color: C.accent, fontSize: '11px', margin: '0 0 4px' }}>Общая длина</p><b style={{ color: C.accent, fontSize: '16px' }}>{totalLength.toLocaleString('ru-RU') + ' м'}</b></div>
      </div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
        {Object.entries(typeCounts).map(([type, count]) => <span key={type} style={badge(C.accent, C.accentLight, C.accentBorder)}>{type + ': ' + count}</span>)}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
        <button onClick={() => showPreview(buildCableJournalContent(rows, project.name, '', ''), 'Журнал кабельной продукции — ' + project.name)} style={{ ...btnB, fontSize: '12px', padding: '7px 12px' }}>
          <Eye size={13} />🖨 Печать журнала
        </button>
      </div>
      <div style={{ ...card, padding: 0, overflow: 'auto' }}>
        <table style={tbl}>
          <thead>
            <tr>
              <th style={tblH}>Дата</th>
              <th style={tblH}>Тип системы</th>
              <th style={tblH}>Марка</th>
              <th style={tblH}>Сечение</th>
              <th style={tblH}>Жил</th>
              <th style={tblH}>Длина</th>
              <th style={tblH}>Барабан №</th>
              <th style={tblH}>R изол. ДО</th>
              <th style={tblH}>R изол. ПОСЛЕ</th>
              <th style={tblH}>Место прокладки</th>
              <th style={tblH}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id} style={{ cursor: 'pointer' }} onClick={() => setEditingCable(row)}>
                <td style={tblC}>{row.receivedAt || '—'}</td>
                <td style={tblC}>{cableTypeOf(row)}</td>
                <td style={{ ...tblC, maxWidth: '220px', whiteSpace: 'normal' }}>{row.cableBrand}{row.aiFilled ? <span title="Заполнено AI" style={{ marginLeft: '4px' }}>🤖</span> : null}</td>
                <td style={tblC}>{row.crossSection ? row.crossSection + ' мм²' : '—'}</td>
                <td style={tblC}>{row.coresCount || '—'}</td>
                <td style={tblC}>{(row.lengthReceived || 0) + ' м'}</td>
                <td style={tblC}>{row.drumNumber || '—'}</td>
                <td style={tblC}>{row.insulationBefore ? row.insulationBefore + ' МΩ' : '—'}</td>
                <td style={tblC}>{row.insulationAfter ? row.insulationAfter + ' МΩ' : '—'}</td>
                <td style={{ ...tblC, maxWidth: '220px', whiteSpace: 'normal' }}>{row.installationLocation || '—'}</td>
                <td style={tblC}>
                  <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: '600', backgroundColor: row.installedAt ? C.successLight : C.warningLight, color: row.installedAt ? C.success : C.warning }}>
                    {row.installedAt ? 'Проложен' : 'На складе'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
