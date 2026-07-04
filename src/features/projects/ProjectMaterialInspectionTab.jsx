import React from 'react';

export default function ProjectMaterialInspectionTab({
  C,
  Eye,
  badge,
  btnB,
  btnG,
  buildMaterialInspectionContent,
  card,
  journalDiagnosticMode,
  journalPackage,
  materialInspections,
  project,
  projectJournalDiagnostics,
  setEditingInspection,
  setJournalDiagnosticMode,
  showPreview,
  tbl,
  tblC,
  tblH,
  toNum,
}) {
  const diagnostics = projectJournalDiagnostics(project.name);
  const rows = materialInspections.filter(row => row.projectName === project.name);

  const modeControls = (
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '10px' }}>
      <button onClick={() => setJournalDiagnosticMode('all')} style={{ ...btnG, fontSize: '12px', padding: '6px 10px', backgroundColor: journalDiagnosticMode === 'all' ? C.accent : C.bg, color: journalDiagnosticMode === 'all' ? 'white' : C.text }}>
        Все записи: {rows.length}
      </button>
      <button onClick={() => setJournalDiagnosticMode('unlinked')} style={{ ...btnG, fontSize: '12px', padding: '6px 10px', backgroundColor: journalDiagnosticMode === 'unlinked' ? C.warning : C.bg, color: journalDiagnosticMode === 'unlinked' ? 'white' : C.text }}>
        Не связано: {diagnostics.stockWithoutInspection.length}
      </button>
    </div>
  );

  const unlinkedNotice = diagnostics.stockWithoutInspection.length > 0 && (
    <div style={{ ...card, padding: '12px', marginBottom: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}>
      <b style={{ color: C.warning, fontSize: '13px' }}>Не связан входной контроль: {diagnostics.stockWithoutInspection.length}</b>
      <p style={{ color: C.textSec, fontSize: '11px', margin: '4px 0 0' }}>
        Материал есть на складе объекта, но связанная запись контроля не найдена в загруженных данных.
      </p>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '8px' }}>
        {diagnostics.stockWithoutInspection.slice(0, 6).map((material, index) => (
          <span key={(material.id || material.name || 'm') + '-' + index} style={badge(C.warning, C.warningLight, C.warningBorder)}>
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
        {diagnostics.stockWithoutInspection.length === 0 ? (
          <div style={{ ...card, padding: '18px', color: C.success, backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder, fontWeight: '700' }}>
            Все складские материалы объекта связаны с входным контролем.
          </div>
        ) : (
          <div style={{ ...card, padding: 0, overflow: 'auto' }}>
            <table style={tbl}>
              <thead>
                <tr>
                  <th style={tblH}>Материал на складе</th>
                  <th style={tblH}>Кол-во</th>
                  <th style={tblH}>Ед.</th>
                  <th style={tblH}>Пакет работ</th>
                  <th style={tblH}>Что сделать</th>
                </tr>
              </thead>
              <tbody>
                {diagnostics.stockWithoutInspection.map((material, index) => (
                  <tr key={(material.id || material.name || 'stock') + '-' + index}>
                    <td style={{ ...tblC, maxWidth: '320px', whiteSpace: 'normal' }}>{material.name}</td>
                    <td style={tblC}>{toNum(material.quantity)}</td>
                    <td style={tblC}>{material.unit || '—'}</td>
                    <td style={tblC}>{journalPackage(material)}</td>
                    <td style={{ ...tblC, color: C.textSec, maxWidth: '260px', whiteSpace: 'normal' }}>
                      Проверить накладную, алиас или автоматическую связь журнала.
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
          <div style={{ fontSize: '40px', marginBottom: '10px' }}>📦</div>
          <p style={{ margin: '0 0 8px', fontWeight: '600' }}>Записей пока нет</p>
          <p style={{ fontSize: '12px', margin: 0, lineHeight: 1.6 }}>
            Записи создаются автоматически при приёмке поставки или оформлении приходной накладной на склад.<br />
            Затем здесь прораб/кладовщик дополняет паспорт, сертификат и отметку об осмотре.
          </p>
        </div>
      </div>
    );
  }

  const inspectedCount = rows.filter(row => row.inspected).length;
  const pendingCount = rows.length - inspectedCount;
  const conformingCount = rows.filter(row => row.visualInspectionResult === 'Соответствует').length;

  return (
    <div>
      {modeControls}
      {unlinkedNotice}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(120px,1fr))', gap: '10px', marginBottom: '14px' }}>
        <div style={{ ...card, padding: '12px', backgroundColor: C.bg }}><p style={{ color: C.textSec, fontSize: '11px', margin: '0 0 4px' }}>Записей</p><b style={{ color: C.text, fontSize: '16px' }}>{rows.length}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.warningLight, border: '1.5px solid ' + C.warningBorder }}><p style={{ color: C.warning, fontSize: '11px', margin: '0 0 4px' }}>Ждут проверки</p><b style={{ color: C.warning, fontSize: '16px' }}>{pendingCount}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.successLight, border: '1.5px solid ' + C.successBorder }}><p style={{ color: C.success, fontSize: '11px', margin: '0 0 4px' }}>Проверено</p><b style={{ color: C.success, fontSize: '16px' }}>{inspectedCount}</b></div>
        <div style={{ ...card, padding: '12px', backgroundColor: C.accentLight, border: '1.5px solid ' + C.accentBorder }}><p style={{ color: C.accent, fontSize: '11px', margin: '0 0 4px' }}>Соответствует</p><b style={{ color: C.accent, fontSize: '16px' }}>{conformingCount}</b></div>
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '10px' }}>
        <button onClick={() => showPreview(buildMaterialInspectionContent(rows, project.name, '', ''), 'Журнал входного контроля — ' + project.name)} style={{ ...btnB, fontSize: '12px', padding: '7px 12px' }}>
          <Eye size={13} />🖨 Печать журнала
        </button>
      </div>
      <div style={{ ...card, padding: 0, overflow: 'auto' }}>
        <table style={tbl}>
          <thead>
            <tr>
              <th style={tblH}>Дата приёмки</th>
              <th style={tblH}>Материал</th>
              <th style={tblH}>Кол-во</th>
              <th style={tblH}>Поставщик</th>
              <th style={tblH}>Партия</th>
              <th style={tblH}>Сертификат</th>
              <th style={tblH}>Результат осмотра</th>
              <th style={tblH}>Статус</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(row => (
              <tr key={row.id} style={{ cursor: 'pointer' }} onClick={() => setEditingInspection(row)}>
                <td style={tblC}>{row.receivedAt || '—'}</td>
                <td style={{ ...tblC, maxWidth: '260px', whiteSpace: 'normal' }}>{row.materialName}{row.aiFilled ? <span title="Заполнено AI" style={{ marginLeft: '4px' }}>🤖</span> : null}</td>
                <td style={tblC}>{(row.quantity || 0) + ' ' + (row.unit || '')}</td>
                <td style={tblC}>{row.supplier || '—'}</td>
                <td style={tblC}>{row.batchNumber || '—'}</td>
                <td style={tblC}>{row.certificateNumber || (row.passportNumber ? 'паспорт ' + row.passportNumber : '—')}</td>
                <td style={tblC}>{row.visualInspectionResult || '—'}</td>
                <td style={tblC}>
                  <span style={{ padding: '2px 8px', borderRadius: '10px', fontSize: '11px', fontWeight: '600', backgroundColor: row.inspected ? (row.visualInspectionResult === 'Не соответствует' ? C.dangerLight : C.successLight) : C.warningLight, color: row.inspected ? (row.visualInspectionResult === 'Не соответствует' ? C.danger : C.success) : C.warning }}>
                    {row.inspected ? 'Проверено' : 'Ждёт проверки'}
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
